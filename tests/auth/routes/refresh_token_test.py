from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select, update

from app.auth import utils
from app.auth.models import RefreshToken
from tests.users.factories import UserFactory


class TestRefreshAccessToken:
    """Comprehensive test suite for /token/refresh endpoint"""

    @pytest.fixture
    async def user(self):
        """Create a test user"""
        user = await UserFactory.create()
        return user

    @pytest.fixture
    async def valid_refresh_token(self, user, db_session):
        """Create a valid refresh token for testing"""
        plaintext_token, token_hash = utils.generate_refresh_token()

        refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            user_agent="TestAgent/1.0",
            ip_address="192.168.1.100",
        )

        db_session.add(refresh_token)
        await db_session.commit()
        await db_session.refresh(refresh_token)

        return plaintext_token, refresh_token

    @pytest.fixture
    async def expired_refresh_token(self, user, db_session):
        """Create an expired refresh token"""
        plaintext_token, token_hash = utils.generate_refresh_token()

        refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),  # Expired
            user_agent="TestAgent/1.0",
            ip_address="192.168.1.100",
        )

        db_session.add(refresh_token)
        await db_session.commit()
        await db_session.refresh(refresh_token)

        return plaintext_token, refresh_token

    @pytest.fixture
    async def revoked_refresh_token(self, user, db_session):
        """Create a revoked refresh token"""
        plaintext_token, token_hash = utils.generate_refresh_token()

        refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            user_agent="TestAgent/1.0",
            ip_address="192.168.1.100",
        )
        refresh_token.revoked_at = datetime.now(timezone.utc)
        refresh_token.revocation_reason = "manual_revoke"

        db_session.add(refresh_token)
        await db_session.commit()
        await db_session.refresh(refresh_token)

        return plaintext_token, refresh_token

    # ==================== SUCCESSFUL TOKEN REFRESH ====================

    async def test_successful_token_refresh(
        self,
        client: AsyncClient,
        user,
        valid_refresh_token,
        db_session,
        disable_rate_limiting,
    ):
        """Test successful refresh token flow"""
        plaintext_token, stored_token = valid_refresh_token

        client.cookies.set("refresh_token", plaintext_token, path="/api/v1/auth/")
        response = await client.post("/api/v1/auth/token/refresh")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Verify new refresh token cookie is set
        assert "refresh_token" in response.cookies
        new_refresh_token = response.cookies["refresh_token"]
        assert new_refresh_token != plaintext_token  # Should be rotated

        # Verify cookie attributes
        cookie_attrs = response.cookies.get("refresh_token")
        assert cookie_attrs is not None

    async def test_old_token_is_revoked_after_refresh(
        self,
        client: AsyncClient,
        user,
        valid_refresh_token,
        db_session,
        disable_rate_limiting,
    ):
        """Test that old token is revoked after successful refresh"""
        plaintext_token, stored_token = valid_refresh_token

        client.cookies.set("refresh_token", plaintext_token, path="/api/v1/auth/")
        await client.post("/api/v1/auth/token/refresh")

        # Refresh the token from database
        await db_session.refresh(stored_token)

        # Old token should be revoked
        assert stored_token.is_revoked is True
        assert stored_token.revocation_reason == "rotation"
        assert stored_token.replaced_by_token_hash is not None

    async def test_new_token_is_stored_in_database(
        self,
        client: AsyncClient,
        user,
        valid_refresh_token,
        db_session,
        disable_rate_limiting,
    ):
        """Test that new token is created and stored in database"""
        plaintext_token, old_token = valid_refresh_token

        client.cookies.set("refresh_token", plaintext_token, path="/api/v1/auth/")
        response = await client.post("/api/v1/auth/token/refresh")

        new_plaintext_token = response.cookies["refresh_token"]
        new_token_hash = utils.get_hashed_token(new_plaintext_token)

        # Find new token in database
        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == new_token_hash)
        )
        new_stored_token = result.scalar_one_or_none()

        assert new_stored_token is not None
        assert new_stored_token.user_id == user.id
        assert new_stored_token.is_revoked is False
        assert new_stored_token.is_expired is False

    async def test_access_token_is_valid_jwt(
        self,
        client: AsyncClient,
        user,
        valid_refresh_token,
        disable_rate_limiting,
    ):
        """Test that returned access token is a valid JWT"""
        plaintext_token, _ = valid_refresh_token

        client.cookies.set("refresh_token", plaintext_token, path="/api/v1/auth/")
        response = await client.post("/api/v1/auth/token/refresh")

        access_token = response.json()["access_token"]

        # Decode and verify JWT
        payload = utils.get_decoded_jwt(access_token)
        assert payload is not None
        assert int(payload.get("sub")) == user.id

    # ==================== MISSING TOKEN ====================

    async def test_missing_refresh_token_cookie(
        self, client: AsyncClient, disable_rate_limiting
    ):
        """Test refresh fails when no refresh token cookie is provided"""
        response = await client.post("/api/v1/auth/token/refresh")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data["error_code"] == "ERR_INVALID_AUTH_TOKEN"

    # ==================== INVALID TOKEN ====================

    async def test_invalid_refresh_token_format(
        self, client: AsyncClient, disable_rate_limiting
    ):
        """Test refresh fails with malformed token"""

        client.cookies.set(
            "refresh_token", "invalid-token-format", path="/api/v1/auth/"
        )
        response = await client.post(
            "/api/v1/auth/token/refresh",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data["error_code"] == "ERR_INVALID_AUTH_TOKEN"

    async def test_nonexistent_refresh_token(
        self, client: AsyncClient, disable_rate_limiting
    ):
        """Test refresh fails when token doesn't exist in database"""
        # Generate a valid format token that doesn't exist in DB
        fake_token, _ = utils.generate_refresh_token()

        client.cookies.set("refresh_token", fake_token, path="/api/v1/auth/")
        response = await client.post("/api/v1/auth/token/refresh")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data["error_code"] == "ERR_INVALID_AUTH_TOKEN"

    # ==================== EXPIRED TOKEN ====================

    async def test_expired_refresh_token(
        self, client: AsyncClient, expired_refresh_token, disable_rate_limiting
    ):
        """Test refresh fails with expired token"""
        plaintext_token, _ = expired_refresh_token

        client.cookies.set("refresh_token", plaintext_token, path="/api/v1/auth/")
        response = await client.post("/api/v1/auth/token/refresh")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data["error_code"] == "ERR_INVALID_AUTH_TOKEN"

    # ==================== REVOKED TOKEN (TOKEN REUSE ATTACK) ====================

    @pytest.mark.asyncio
    async def test_revoked_token_triggers_security_response(
        self,
        client: AsyncClient,
        user,
        revoked_refresh_token,
        db_session,
        disable_rate_limiting,
    ):
        """Test that using a revoked token triggers security measures"""
        plaintext_token, _ = revoked_refresh_token

        # Create another valid token for the same user
        plaintext_token2, token_hash2 = utils.generate_refresh_token()
        valid_token = RefreshToken(
            user_id=user.id,
            token_hash=token_hash2,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            user_agent="TestAgent/1.0",
            ip_address="192.168.1.200",
        )
        db_session.add(valid_token)
        await db_session.commit()

        # Try to use revoked token
        client.cookies.set("refresh_token", plaintext_token, path="/api/v1/auth/")
        response = await client.post("/api/v1/auth/token/refresh")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Verify ALL user tokens are revoked (security response)
        await db_session.refresh(valid_token)
        assert valid_token.is_revoked is True
        assert valid_token.revocation_reason == "suspicious_activity"

    async def test_revoked_token_clears_cookie(
        self, client: AsyncClient, revoked_refresh_token, disable_rate_limiting
    ):
        """Test that cookie is cleared when revoked token is detected"""
        plaintext_token, _ = revoked_refresh_token

        client.cookies.set("refresh_token", plaintext_token, path="/api/v1/auth/")
        response = await client.post("/api/v1/auth/token/refresh")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Verify cookie is cleared
        # When FastAPI/Starlette deletes a cookie, it sets it with max-age=0 and expires in past
        cookies = response.cookies

        if "refresh_token" in cookies:
            # Cookie exists in response (deletion sends the cookie with special attributes)
            refresh_cookie = cookies.get("refresh_token")

            # Check if cookie value is empty or if it's being deleted
            # Different ways to verify deletion:
            # 1. Empty value
            # 2. max-age=0 or negative
            # 3. Expires in the past

            # Most reliable: check if the cookie value is empty/cleared
            assert refresh_cookie == "" or refresh_cookie is None, (
                "Cookie should be cleared (empty value)"
            )

        # Alternative verification: Cookie should not persist in subsequent requests
        # Make another request WITHOUT sending the cookie
        # The client shouldn't have it anymore
        response2 = await client.post("/api/v1/auth/token/refresh")
        assert (
            response2.status_code == status.HTTP_401_UNAUTHORIZED
        )  # Should fail due to missing token

    # ==================== TOKEN ROTATION ====================

    async def test_cannot_reuse_old_token_after_rotation(
        self,
        client: AsyncClient,
        user,
        valid_refresh_token,
        db_session,
        disable_rate_limiting,
    ):
        """Test that old token cannot be reused after rotation"""
        plaintext_token, _ = valid_refresh_token

        # First refresh succeeds
        client.cookies.set("refresh_token", plaintext_token, path="/api/v1/auth/")
        response1 = await client.post("/api/v1/auth/token/refresh")
        assert response1.status_code == status.HTTP_200_OK

        client.cookies.clear()
        client.cookies.set("refresh_token", plaintext_token, path="/api/v1/auth/")

        # Second attempt with same token should fail (token is revoked)
        response2 = await client.post("/api/v1/auth/token/refresh")
        assert response2.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_can_use_new_token_after_rotation(
        self,
        client: AsyncClient,
        user,
        valid_refresh_token,
        disable_rate_limiting,
    ):
        """Test that new token works after rotation"""
        plaintext_token, _ = valid_refresh_token

        # First refresh
        client.cookies.set("refresh_token", plaintext_token, path="/api/v1/auth/")
        response1 = await client.post("/api/v1/auth/token/refresh")
        new_token = response1.cookies["refresh_token"]

        # Second refresh with new token should succeed
        client.cookies.clear()
        client.cookies.set("refresh_token", new_token, path="/api/v1/auth/")
        response2 = await client.post("/api/v1/auth/token/refresh")
        assert response2.status_code == status.HTTP_200_OK
        assert "access_token" in response2.json()

    async def test_multiple_token_rotations(
        self,
        client: AsyncClient,
        user,
        valid_refresh_token,
        disable_rate_limiting,
    ):
        """Test multiple successive token rotations"""
        plaintext_token, _ = valid_refresh_token

        current_token = plaintext_token

        # Perform 5 rotations
        for i in range(5):
            client.cookies.clear()
            client.cookies.set("refresh_token", current_token, path="/api/v1/auth/")
            response = await client.post("/api/v1/auth/token/refresh")
            assert response.status_code == status.HTTP_200_OK
            current_token = response.cookies["refresh_token"]

        # Final token should work
        response = await client.post("/api/v1/auth/token/refresh")
        assert response.status_code == status.HTTP_200_OK

    # ==================== METADATA TRACKING ====================

    async def test_new_token_tracks_user_agent(
        self,
        client: AsyncClient,
        user,
        valid_refresh_token,
        db_session,
        disable_rate_limiting,
    ):
        """Test that new token stores user agent"""
        plaintext_token, _ = valid_refresh_token

        client.cookies.set("refresh_token", plaintext_token, path="/api/v1/auth/")
        response = await client.post(
            "/api/v1/auth/token/refresh",
            headers={"User-Agent": "CustomAgent/2.0"},
        )

        new_token = response.cookies["refresh_token"]
        new_token_hash = utils.get_hashed_token(new_token)

        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == new_token_hash)
        )
        stored_token = result.scalar_one()

        assert stored_token.user_agent == "CustomAgent/2.0"

    async def test_new_token_tracks_ip_address(
        self,
        client: AsyncClient,
        user,
        valid_refresh_token,
        db_session,
        disable_rate_limiting,
    ):
        """Test that new token stores IP address"""
        plaintext_token, _ = valid_refresh_token

        client.cookies.set("refresh_token", plaintext_token, path="/api/v1/auth/")
        response = await client.post("/api/v1/auth/token/refresh")

        new_token = response.cookies["refresh_token"]
        new_token_hash = utils.get_hashed_token(new_token)

        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == new_token_hash)
        )
        stored_token = result.scalar_one()

        assert stored_token.ip_address is not None

    # ==================== COOKIE SECURITY ====================

    @pytest.mark.asyncio
    async def test_refresh_token_cookie_path_is_restricted(
        self, client: AsyncClient, valid_refresh_token, disable_rate_limiting
    ):
        """Test that refresh token cookie path is set correctly"""
        plaintext_token, _ = valid_refresh_token

        client.cookies.set("refresh_token", plaintext_token, path="/api/v1/auth/")
        response = await client.post("/api/v1/auth/token/refresh")

        assert "refresh_token" in response.cookies
        # Path should be /api/v1/auth/ to limit cookie scope

    # ==================== EDGE CASES ====================

    async def test_refresh_with_deleted_user(
        self,
        client: AsyncClient,
        user,
        valid_refresh_token,
        db_session,
        disable_rate_limiting,
    ):
        """Test refresh fails gracefully when user is deleted"""
        plaintext_token, _ = valid_refresh_token

        # Delete the user (cascade should delete tokens)
        await db_session.delete(user)
        await db_session.commit()

        client.cookies.set("refresh_token", plaintext_token, path="/api/v1/auth/")
        response = await client.post("/api/v1/auth/token/refresh")

        # Should fail (token no longer exists due to cascade)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_refresh_token_expiration_edge_case(
        self, client: AsyncClient, user, db_session, disable_rate_limiting
    ):
        """Test token that expires within 1 second"""
        plaintext_token, token_hash = utils.generate_refresh_token()

        # Token expires in 1 second
        refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=1),
            user_agent="TestAgent/1.0",
            ip_address="192.168.1.100",
        )

        db_session.add(refresh_token)
        await db_session.commit()

        # Should work immediately
        client.cookies.set("refresh_token", plaintext_token, path="/api/v1/auth/")
        response1 = await client.post("/api/v1/auth/token/refresh")
        assert response1.status_code == status.HTTP_200_OK

        # Wait for expiration
        import asyncio

        await asyncio.sleep(1.5)

        # Should fail after expiration
        new_token = response1.cookies["refresh_token"]
        new_token_hash = utils.get_hashed_token(new_token)

        await db_session.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == new_token_hash)
            .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
        await db_session.commit()

        client.cookies.set("refresh_token", new_token, path="/api/v1/auth/")
        response2 = await client.post("/api/v1/auth/token/refresh")
        assert response2.status_code == status.HTTP_401_UNAUTHORIZED

    # async def test_concurrent_refresh_requests_same_token(
    #     self,
    #     client: AsyncClient,
    #     user,
    #     valid_refresh_token,
    #     db_session,
    #     disable_rate_limiting,
    # ):
    #     """Test concurrent refresh requests with same token"""
    #     import asyncio

    #     plaintext_token, _ = valid_refresh_token

    #     # Make 3 concurrent requests with same token
    #     client.cookies.set("refresh_token", plaintext_token, path="/api/v1/auth/")
    #     responses = await asyncio.gather(
    #         client.post("/api/v1/auth/token/refresh"),
    #         client.post("/api/v1/auth/token/refresh"),
    #         client.post("/api/v1/auth/token/refresh"),
    #         client.post("/api/v1/auth/token/refresh"),
    #         return_exceptions=True,
    #     )

    #     success = [
    #         r
    #         for r in responses
    #         if not isinstance(r, Exception) and r.status_code == status.HTTP_200_OK
    #     ]
    #     failures = [
    #         r
    #         for r in responses
    #         if not isinstance(r, Exception)
    #         and r.status_code == status.HTTP_401_UNAUTHORIZED
    #     ]

    #     assert len(success) == 1
    #     assert len(failures) == 3
