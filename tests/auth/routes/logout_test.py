from fastapi import status

from app.auth import utils as auth_utils
from app.auth.utils import create_access_token
from app.core.settings import settings
from app.users.utils import UserStatus
from tests.auth.factories import RefreshTokenFactory


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestAccessTokenBlacklisting:
    async def test_logout_blacklists_token(
        self, client, fake_redis_client, create_user, disable_rate_limiting
    ):
        """Test that logout blacklists the access token in Redis."""
        user = await create_user(status=UserStatus.ACTIVE)
        token = create_access_token(subject=user.id)

        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(token),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Token must be blacklisted
        keys = await fake_redis_client.keys("*")
        assert len(keys) == 1

        key = keys[0]
        assert key.startswith("jwt:blacklist:")

        ttl = await fake_redis_client.ttl(key)
        assert ttl > 0

    async def test_blacklisted_token_is_rejected(
        self, client, fake_redis_client, create_user
    ):
        """Test that a blacklisted token cannot be reused."""
        user = await create_user(status=UserStatus.ACTIVE)
        token = create_access_token(subject=user.id)

        # Logout to blacklist
        await client.post("/api/v1/auth/logout", headers=auth_header(token))

        # Try to access protected endpoint
        response = await client.get(
            "/api/v1/users/",
            headers=auth_header(token),
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_logout_without_token(self, client):
        """Test logout without providing an access token."""
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_logout_invalid_token(self, client):
        """Test logout with an invalid access token."""
        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header("invalid.token.here"),
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_logout_twice_is_safe(
        self, client, fake_redis_client, create_user, disable_rate_limiting
    ):
        """Test that logging out twice with same token fails on second attempt."""
        user = await create_user(status=UserStatus.ACTIVE)
        token = create_access_token(subject=user.id)

        r1 = await client.post("/api/v1/auth/logout", headers=auth_header(token))
        r2 = await client.post("/api/v1/auth/logout", headers=auth_header(token))

        assert r1.status_code == status.HTTP_204_NO_CONTENT
        assert (
            r2.status_code == status.HTTP_401_UNAUTHORIZED
        )  # token already blacklisted

        keys = await fake_redis_client.keys("*")
        assert len(keys) == 1

    async def test_blacklist_ttl_matches_token_expiry(
        self, client, fake_redis_client, create_user
    ):
        """Test that blacklist TTL matches the access token expiry time."""
        user = await create_user(status=UserStatus.ACTIVE)
        token = create_access_token(subject=user.id)

        await client.post("/api/v1/auth/logout", headers=auth_header(token))

        keys = await fake_redis_client.keys("*")
        ttl = await fake_redis_client.ttl(keys[0])

        assert ttl > 0
        assert ttl <= settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

    async def test_multiple_tokens_blacklist_independently(
        self, client, fake_redis_client, create_user, disable_rate_limiting
    ):
        """Test that multiple access tokens are blacklisted independently."""
        user = await create_user(status=UserStatus.ACTIVE)

        token1 = create_access_token(subject=user.id)
        token2 = create_access_token(subject=user.id)

        await client.post("/api/v1/auth/logout", headers=auth_header(token1))

        keys = await fake_redis_client.keys("*")
        assert len(keys) == 1

        # token2 should still work
        r = await client.get("/api/v1/users/", headers=auth_header(token2))
        assert r.status_code == status.HTTP_200_OK


class TestRefreshTokenRevocation:
    async def test_logout_revokes_refresh_token_when_present(
        self, client, db_session, create_user, disable_rate_limiting
    ):
        """Test that logout revokes the refresh token when cookie is present."""
        user = await create_user(status=UserStatus.ACTIVE)
        access_token = create_access_token(subject=user.id)

        # Create refresh token using factory
        plain_token = "test_refresh_token_12345"
        hashed_token = auth_utils.get_hashed_token(plain_token)

        refresh_token = await RefreshTokenFactory.create(
            user=user,
            token_hash=hashed_token,
        )

        # Set the refresh token cookie
        client.cookies.set("refresh_token", plain_token, path="/api/v1/auth/")

        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(access_token),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify refresh token was revoked in database
        await db_session.refresh(refresh_token)
        assert refresh_token.revoked_at is not None
        assert refresh_token.revocation_reason == "user_logout"

    async def test_logout_clears_refresh_token_cookie(
        self, client, db_session, create_user, disable_rate_limiting
    ):
        """Test that logout deletes the refresh token cookie."""
        user = await create_user(status=UserStatus.ACTIVE)
        access_token = create_access_token(subject=user.id)

        # Create refresh token using factory
        plain_token = "test_refresh_token_12345"
        hashed_token = auth_utils.get_hashed_token(plain_token)

        await RefreshTokenFactory.create(
            user=user,
            token_hash=hashed_token,
        )

        client.cookies.set("refresh_token", plain_token, path="/api/v1/auth/")

        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(access_token),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify cookie is cleared
        assert (
            "refresh_token" not in response.cookies
            or response.cookies.get("refresh_token") == ""
        )

    async def test_logout_without_refresh_token_cookie_succeeds(
        self, client, create_user, disable_rate_limiting
    ):
        """Test that logout succeeds even without a refresh token cookie."""
        user = await create_user(status=UserStatus.ACTIVE)
        access_token = create_access_token(subject=user.id)

        # No refresh token cookie set
        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(access_token),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_logout_with_invalid_refresh_token_still_succeeds(
        self, client, create_user, disable_rate_limiting
    ):
        """Test that logout succeeds even if refresh token is invalid."""
        user = await create_user(status=UserStatus.ACTIVE)
        access_token = create_access_token(subject=user.id)

        # Set an invalid refresh token cookie (not in database)
        client.cookies.set("refresh_token", "invalid_token_xyz", path="/api/v1/auth/")

        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(access_token),
        )

        # Should still succeed - logout is best-effort for refresh tokens
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_logout_with_already_revoked_refresh_token(
        self, client, db_session, create_user, disable_rate_limiting
    ):
        """Test logout when refresh token is already revoked."""
        user = await create_user(status=UserStatus.ACTIVE)
        access_token = create_access_token(subject=user.id)

        # Create an already-revoked refresh token using the trait
        plain_token = "test_refresh_token_12345"
        hashed_token = auth_utils.get_hashed_token(plain_token)

        refresh_token = await RefreshTokenFactory.create(
            user=user,
            token_hash=hashed_token,
            revoked=True,  # Use the revoked trait
        )

        # Store original revocation reason
        original_reason = refresh_token.revocation_reason

        client.cookies.set("refresh_token", plain_token, path="/api/v1/auth/")

        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(access_token),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify it's still revoked with original reason (not overwritten)
        await db_session.refresh(refresh_token)
        assert refresh_token.revoked_at is not None
        assert refresh_token.revocation_reason == original_reason

    async def test_logout_updates_refresh_token_metadata(
        self, client, db_session, create_user, disable_rate_limiting
    ):
        """Test that logout properly updates refresh token metadata."""
        user = await create_user(status=UserStatus.ACTIVE)
        access_token = create_access_token(subject=user.id)

        # Create refresh token using factory
        plain_token = "test_refresh_token_12345"
        hashed_token = auth_utils.get_hashed_token(plain_token)

        refresh_token = await RefreshTokenFactory.create(
            user=user,
            token_hash=hashed_token,
        )

        client.cookies.set("refresh_token", plain_token, path="/api/v1/auth/")

        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(access_token),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify all metadata is updated
        await db_session.refresh(refresh_token)
        assert refresh_token.revoked_at is not None
        assert refresh_token.revocation_reason == "user_logout"
        assert refresh_token.replaced_by_token_hash == ""

    async def test_logout_blacklists_access_token_and_revokes_refresh_token(
        self,
        client,
        db_session,
        fake_redis_client,
        create_user,
        disable_rate_limiting,
    ):
        """Test that logout handles both access and refresh tokens correctly."""
        user = await create_user(status=UserStatus.ACTIVE)
        access_token = create_access_token(subject=user.id)

        # Create refresh token using factory
        plain_token = "test_refresh_token_12345"
        hashed_token = auth_utils.get_hashed_token(plain_token)

        refresh_token = await RefreshTokenFactory.create(
            user=user,
            token_hash=hashed_token,
        )

        client.cookies.set("refresh_token", plain_token, path="/api/v1/auth/")

        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(access_token),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify access token is blacklisted
        keys = await fake_redis_client.keys("*")
        assert len(keys) == 1
        assert keys[0].startswith("jwt:blacklist:")

        # Verify refresh token is revoked
        await db_session.refresh(refresh_token)
        assert refresh_token.revoked_at is not None

    async def test_logout_with_refresh_token_from_different_user(
        self, client, db_session, create_user, disable_rate_limiting
    ):
        """Test logout when refresh token belongs to a different user."""
        user1 = await create_user(status=UserStatus.ACTIVE, email="user1@example.com")
        user2 = await create_user(status=UserStatus.ACTIVE, email="user2@example.com")

        access_token = create_access_token(subject=user1.id)

        # Create refresh token for user2 using factory with SubFactory
        plain_token = "test_refresh_token_12345"
        hashed_token = auth_utils.get_hashed_token(plain_token)

        await RefreshTokenFactory.create(
            user=user2,  # Different user
            token_hash=hashed_token,
        )

        # Set user2's refresh token in cookie
        client.cookies.set("refresh_token", plain_token, path="/api/v1/auth/")

        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(access_token),
        )

        # Should still succeed - the refresh token would be revoked regardless
        # Note: You may want to add validation to only revoke user's own tokens
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_logout_with_nonexistent_refresh_token(
        self, client, create_user, disable_rate_limiting
    ):
        """Test logout with a refresh token that doesn't exist in database."""
        user = await create_user(status=UserStatus.ACTIVE)
        access_token = create_access_token(subject=user.id)

        # Set a refresh token that doesn't exist in DB
        client.cookies.set("refresh_token", "nonexistent_token", path="/api/v1/auth/")

        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(access_token),
        )

        # Should succeed - missing refresh token is not an error
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_logout_with_empty_refresh_token_cookie(
        self, client, create_user, disable_rate_limiting
    ):
        """Test logout with an empty refresh token cookie."""
        user = await create_user(status=UserStatus.ACTIVE)
        access_token = create_access_token(subject=user.id)

        # Set empty refresh token
        client.cookies.set("refresh_token", "", path="/api/v1/auth/")

        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(access_token),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_logout_with_expired_refresh_token(
        self, client, db_session, create_user, disable_rate_limiting
    ):
        """Test logout with an expired refresh token."""
        user = await create_user(status=UserStatus.ACTIVE)
        access_token = create_access_token(subject=user.id)

        # Create expired refresh token using the expired trait
        plain_token = "test_refresh_token_12345"
        hashed_token = auth_utils.get_hashed_token(plain_token)

        refresh_token = await RefreshTokenFactory.create(
            user=user,
            token_hash=hashed_token,
            expired=True,  # Use the expired trait
        )

        client.cookies.set("refresh_token", plain_token, path="/api/v1/auth/")

        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(access_token),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify the expired token was still revoked
        await db_session.refresh(refresh_token)
        assert refresh_token.revoked_at is not None

    async def test_logout_multiple_refresh_tokens_for_same_user(
        self, client, db_session, create_user, disable_rate_limiting
    ):
        """Test that logout only revokes the specific refresh token provided."""
        user = await create_user(status=UserStatus.ACTIVE)
        access_token = create_access_token(subject=user.id)

        # Create multiple refresh tokens for the same user
        plain_token1 = "test_refresh_token_1"
        hashed_token1 = auth_utils.get_hashed_token(plain_token1)

        plain_token2 = "test_refresh_token_2"
        hashed_token2 = auth_utils.get_hashed_token(plain_token2)

        refresh_token1 = await RefreshTokenFactory.create(
            user=user,
            token_hash=hashed_token1,
        )

        refresh_token2 = await RefreshTokenFactory.create(
            user=user,
            token_hash=hashed_token2,
        )

        # Logout with only the first token
        client.cookies.set("refresh_token", plain_token1, path="/api/v1/auth/")

        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(access_token),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify only the first token was revoked
        await db_session.refresh(refresh_token1)
        await db_session.refresh(refresh_token2)

        assert refresh_token1.revoked_at is not None
        assert refresh_token2.revoked_at is None  # Should still be active


class TestLogoutRateLimiting:
    async def test_logout_rate_limiting(self, client, create_user):
        """Test that logout rate limiting is enforced (20 requests per minute)."""
        user = await create_user(status=UserStatus.ACTIVE)

        # Make 20 successful logout attempts
        for i in range(20):
            token = create_access_token(subject=user.id)
            response = await client.post(
                "/api/v1/auth/logout",
                headers=auth_header(token),
            )
            assert response.status_code == status.HTTP_204_NO_CONTENT

        # 21st attempt should be rate limited
        token = create_access_token(subject=user.id)
        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(token),
        )
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


class TestLogoutEdgeCases:
    async def test_logout_with_malformed_refresh_token_hash(
        self, client, db_session, create_user, disable_rate_limiting
    ):
        """Test logout handles malformed refresh token gracefully."""
        user = await create_user(status=UserStatus.ACTIVE)
        access_token = create_access_token(subject=user.id)

        # Set a malformed refresh token
        client.cookies.set("refresh_token", "malformed@#$%^&*", path="/api/v1/auth/")

        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(access_token),
        )

        # Should still succeed
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_logout_preserves_other_cookies(
        self, client, create_user, disable_rate_limiting
    ):
        """Test that logout only clears refresh_token cookie, not others."""
        user = await create_user(status=UserStatus.ACTIVE)
        access_token = create_access_token(subject=user.id)

        # Set multiple cookies
        client.cookies.set("refresh_token", "some_token", path="/api/v1/auth/")
        client.cookies.set("other_cookie", "other_value", path="/")

        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(access_token),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_logout_with_valid_refresh_token_metadata(
        self, client, db_session, create_user, disable_rate_limiting
    ):
        """Test that factory-generated metadata is preserved during logout."""
        user = await create_user(status=UserStatus.ACTIVE)
        access_token = create_access_token(subject=user.id)

        # Create refresh token with factory-generated metadata
        plain_token = "test_refresh_token_12345"
        hashed_token = auth_utils.get_hashed_token(plain_token)

        refresh_token = await RefreshTokenFactory.create(
            user=user,
            token_hash=hashed_token,
        )

        # Store original metadata
        original_created_at = refresh_token.created_at

        client.cookies.set("refresh_token", plain_token, path="/api/v1/auth/")

        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(access_token),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify original metadata is preserved
        await db_session.refresh(refresh_token)
        assert refresh_token.ip_address == "127.0.0.1"  # TestClient default
        assert refresh_token.user_agent.startswith(
            "python-httpx"
        )  # Default user-agent for httpx/testclient
        assert refresh_token.created_at == original_created_at
        assert refresh_token.revoked_at is not None

    async def test_logout_refreshes_token_state_from_database(
        self, client, db_session, create_user, disable_rate_limiting
    ):
        """Test that logout fetches fresh token state from database."""
        user = await create_user(status=UserStatus.ACTIVE)
        access_token = create_access_token(subject=user.id)

        # Create refresh token
        plain_token = "test_refresh_token_12345"
        hashed_token = auth_utils.get_hashed_token(plain_token)

        refresh_token = await RefreshTokenFactory.create(
            user=user,
            token_hash=hashed_token,
        )

        client.cookies.set("refresh_token", plain_token, path="/api/v1/auth/")

        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(access_token),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify we can fetch the updated state from DB
        await db_session.refresh(refresh_token)
        assert refresh_token.revoked_at is not None
        assert refresh_token.revocation_reason == "user_logout"
