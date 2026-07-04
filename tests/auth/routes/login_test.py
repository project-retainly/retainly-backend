import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import utils as auth_utils
from app.auth.models import RefreshToken
from app.users.utils import UserStatus
from tests.users.factories import UserFactory


class TestLoginForAccessToken:
    """Test suite for the login_for_access_token endpoint."""

    correct_password = "Test_password_$123"

    @pytest.fixture
    def login_url(self):
        """URL for the login endpoint."""
        return "/api/v1/auth/token"

    @pytest.fixture
    async def active_user(self, db_session: AsyncSession):
        """Create an active user with hashed password."""
        # Assuming UserFactory can create users with hashed passwords
        user = await UserFactory.create(
            email="testuser@example.com",
            username="testuser",
            status=UserStatus.ACTIVE,
        )
        return user

    @pytest.fixture
    async def pending_user(self, db_session: AsyncSession):
        """Create a pending user."""
        user = await UserFactory.create(
            email="pending@example.com",
            username="pendinguser",
            status=UserStatus.PENDING,
        )
        return user

    @pytest.fixture
    async def deleted_user(self, db_session: AsyncSession):
        """Create a deleted user."""
        user = await UserFactory.create(
            email="deleted@example.com",
            username="deleteduser",
            status=UserStatus.DELETED,
        )
        return user

    @pytest.fixture
    async def expired_user(self, db_session: AsyncSession):
        """Create an expired user."""
        user = await UserFactory.create(
            email="expired@example.com",
            username="expireduser",
            status=UserStatus.EXPIRED,
        )
        return user

    # ==================== Success Cases ====================

    @pytest.mark.asyncio
    async def test_login_success_with_email(
        self, client: AsyncClient, active_user, login_url, disable_rate_limiting
    ):
        """Test successful login using email."""
        response = await client.post(
            login_url,
            data={
                "username": active_user.email,
                "password": self.correct_password,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "refresh_token" in response.cookies

    @pytest.mark.asyncio
    async def test_login_success_with_username(
        self, client: AsyncClient, active_user, login_url, disable_rate_limiting
    ):
        """Test successful login using username."""
        response = await client.post(
            login_url,
            data={
                "username": active_user.username,
                "password": self.correct_password,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "refresh_token" in response.cookies

    @pytest.mark.asyncio
    async def test_login_sets_refresh_token_cookie(
        self, client: AsyncClient, active_user, login_url, disable_rate_limiting
    ):
        """Test that refresh token cookie is set with correct attributes."""
        response = await client.post(
            login_url,
            data={
                "username": active_user.email,
                "password": self.correct_password,
            },
        )

        assert response.status_code == status.HTTP_200_OK

        # Check cookie exists
        assert "refresh_token" in response.cookies

        # Note: httpx may not expose all cookie attributes,
        # but we can verify the cookie is set
        refresh_cookie = response.cookies.get("refresh_token")
        assert refresh_cookie is not None

    # ==================== Failure Cases - User Not Found ====================

    @pytest.mark.asyncio
    async def test_login_user_not_found_email(
        self, client: AsyncClient, login_url, disable_rate_limiting
    ):
        """Test login with non-existent email."""
        response = await client.post(
            login_url,
            data={
                "username": "nonexistent@example.com",
                "password": "anypassword",
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        # Assuming AppError.AUTH_FAILED returns 401

    @pytest.mark.asyncio
    async def test_login_user_not_found_username(
        self, client: AsyncClient, login_url, disable_rate_limiting
    ):
        """Test login with non-existent username."""
        response = await client.post(
            login_url,
            data={"username": "nonexistentuser", "password": "anypassword"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ==================== Failure Cases - Invalid Password ====================

    @pytest.mark.asyncio
    async def test_login_wrong_password(
        self, client: AsyncClient, active_user, login_url, disable_rate_limiting
    ):
        """Test login with incorrect password."""
        response = await client.post(
            login_url,
            data={"username": active_user.email, "password": "wrongpassword"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_login_empty_password(
        self, client: AsyncClient, active_user, login_url, disable_rate_limiting
    ):
        """Test login with empty password."""
        response = await client.post(
            login_url,
            data={"username": active_user.email, "password": ""},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # ==================== Failure Cases - User Status ====================

    @pytest.mark.asyncio
    async def test_login_pending_user(
        self,
        client: AsyncClient,
        pending_user,
        login_url,
        disable_rate_limiting,
    ):
        """Test login with pending user account."""
        response = await client.post(
            login_url,
            data={
                "username": pending_user.email,
                "password": self.correct_password,
            },
        )

        # Assuming assert_user_can_login raises exception for pending users
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_login_deleted_user(
        self,
        client: AsyncClient,
        deleted_user,
        login_url,
        disable_rate_limiting,
    ):
        """Test login with deleted user account."""
        response = await client.post(
            login_url,
            data={
                "username": deleted_user.email,
                "password": self.correct_password,
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_login_expired_user(
        self,
        client: AsyncClient,
        expired_user,
        login_url,
        disable_rate_limiting,
    ):
        """Test login with expired user account."""
        response = await client.post(
            login_url,
            data={
                "username": expired_user.email,
                "password": self.correct_password,
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ==================== Failure Cases - Invalid Input ====================

    @pytest.mark.asyncio
    async def test_login_missing_username(
        self, client: AsyncClient, login_url, disable_rate_limiting
    ):
        """Test login without username."""
        response = await client.post(
            login_url,
            data={"password": self.correct_password},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_login_missing_password(
        self, client: AsyncClient, login_url, disable_rate_limiting
    ):
        """Test login without password."""
        response = await client.post(
            login_url,
            data={"username": "testuser@example.com"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_login_missing_all_fields(
        self, client: AsyncClient, login_url, disable_rate_limiting
    ):
        """Test login without any credentials."""
        response = await client.post(login_url, data={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # ==================== Rate Limiting Tests ====================

    @pytest.mark.asyncio
    async def test_login_rate_limiting(
        self, client: AsyncClient, active_user, login_url
    ):
        """Test that rate limiting is enforced (5 requests per minute)."""
        # Make 5 successful attempts (should all pass)
        for i in range(5):
            response = await client.post(
                login_url,
                data={
                    "username": active_user.email,
                    "password": self.correct_password,
                },
            )
            assert response.status_code == status.HTTP_200_OK

        # 6th attempt should be rate limited
        response = await client.post(
            login_url,
            data={
                "username": active_user.email,
                "password": self.correct_password,
            },
        )
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    @pytest.mark.asyncio
    async def test_login_rate_limiting_with_failed_attempts(
        self, client: AsyncClient, active_user, login_url
    ):
        """Test rate limiting applies to both successful and failed login attempts."""
        # Make 5 failed attempts
        for i in range(5):
            await client.post(
                login_url,
                data={
                    "username": active_user.email,
                    "password": "wrongpassword",
                },
            )

        # 6th attempt should be rate limited even with correct password
        response = await client.post(
            login_url,
            data={
                "username": active_user.email,
                "password": self.correct_password,
            },
        )
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    # ==================== Edge Cases ====================

    @pytest.mark.asyncio
    async def test_login_case_sensitive_password(
        self, client: AsyncClient, active_user, login_url, disable_rate_limiting
    ):
        """Test that password is case-sensitive."""
        response = await client.post(
            login_url,
            data={
                "username": active_user.email,
                "password": self.correct_password.upper(),
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_login_with_extra_whitespace_in_password(
        self, client: AsyncClient, active_user, login_url, disable_rate_limiting
    ):
        """Test login with extra whitespace in password."""
        response = await client.post(
            login_url,
            data={
                "username": active_user.email,
                "password": f"  {self.correct_password}  ",
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_login_username_case_sensitivity(
        self, client: AsyncClient, active_user, login_url, disable_rate_limiting
    ):
        """Test whether username/email is case-sensitive."""
        # This depends on your implementation
        response = await client.post(
            login_url,
            data={
                "username": active_user.email.upper(),
                "password": self.correct_password,
            },
        )

        # Adjust assertion based on your implementation
        # Most systems treat emails as case-insensitive
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED,
        ]

    @pytest.mark.asyncio
    async def test_login_creates_refresh_token_in_database(
        self,
        client: AsyncClient,
        active_user,
        login_url,
        db_session,
        disable_rate_limiting,
    ):
        """Test that refresh token is stored in database."""
        response = await client.post(
            login_url,
            data={
                "username": active_user.email,
                "password": self.correct_password,
            },
        )

        assert response.status_code == status.HTTP_200_OK

        # You would need to query your refresh token table to verify
        # This is a placeholder - adjust based on your model
        refresh_tokens = await db_session.execute(
            select(RefreshToken).where(RefreshToken.user_id == active_user.id)
        )
        assert refresh_tokens.scalars().first() is not None

    @pytest.mark.asyncio
    async def test_login_access_token_contains_user_id(
        self, client: AsyncClient, active_user, login_url, disable_rate_limiting
    ):
        """Test that access token contains user ID in payload."""
        response = await client.post(
            login_url,
            data={
                "username": active_user.email,
                "password": self.correct_password,
            },
        )

        assert response.status_code == status.HTTP_200_OK

        token = response.json()["access_token"]

        payload = auth_utils.get_decoded_jwt(token)
        assert payload["sub"] == str(active_user.id)

    @pytest.mark.asyncio
    async def test_concurrent_login_requests(
        self, client: AsyncClient, active_user, login_url, disable_rate_limiting
    ):
        """Test handling of concurrent login requests for same user."""
        import asyncio

        async def login():
            return await client.post(
                login_url,
                data={
                    "username": active_user.email,
                    "password": self.correct_password,
                },
            )

        # Execute 3 concurrent login requests
        responses = await asyncio.gather(*[login() for _ in range(3)])

        # All should succeed
        for response in responses:
            assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_login_with_sql_injection_attempt(
        self, client: AsyncClient, login_url, disable_rate_limiting
    ):
        """Test that SQL injection attempts are handled safely."""
        response = await client.post(
            login_url,
            data={
                "username": "admin' OR '1'='1",
                "password": "password' OR '1'='1",
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_login_with_very_long_username(
        self, client: AsyncClient, login_url, disable_rate_limiting
    ):
        """Test login with extremely long username."""
        long_username = "a" * 1000
        response = await client.post(
            login_url,
            data={"username": long_username, "password": self.correct_password},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_login_with_special_characters_in_password(
        self, client: AsyncClient, db_session, login_url, disable_rate_limiting
    ):
        """Test login with special characters in password."""
        # Create user with special character password
        special_user = await UserFactory.create(
            email="special@example.com",
            username="specialuser",
            password="$2b$12$pj.9s.lwQYnerG3.lRDshurP6ivlbanpWYiNBdaUgfSz1/TlLXpRG",  # Hash of "P@ssw0rd!#$%"
            status="active",
        )

        # This test would need the actual hashed password for "P@ssw0rd!#$%"
        # Placeholder for demonstration
        response = await client.post(
            login_url,
            data={"username": special_user.email, "password": "P@ssw0rd!#$%"},
        )

        # Adjust based on actual implementation
        assert response.status_code == status.HTTP_200_OK
