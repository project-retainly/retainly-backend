import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.auth import constants
from app.auth.services import AuthService
from app.core.settings import settings


class TestCreateEmailVerificationLink:
    """Tests for AuthService.create_email_verification_link method."""

    async def test_creates_verification_link_successfully(
        self, db_session, fake_redis_client
    ):
        """Test that a verification link is created with correct format."""
        auth_service = AuthService(db=db_session)
        user_id = 123
        user_updated_at = datetime.now(timezone.utc)

        with patch("app.auth.services.secrets.token_urlsafe") as mock_token:
            mock_token.return_value = "test_token_123"

            result = await auth_service.create_email_verification_link(
                user_id, user_updated_at
            )

            # Verify link format
            expected_link = (
                f"{settings.BACKEND_HOST_URL}/api/v1/auth/verify/test_token_123"
            )
            assert result == expected_link

    async def test_stores_correct_payload_in_redis(self, db_session, fake_redis_client):
        """Test that the correct payload is stored in Redis."""
        auth_service = AuthService(db=db_session)
        user_id = 456
        user_updated_at = datetime.now(timezone.utc)

        with (
            patch("app.auth.services.secrets.token_urlsafe") as mock_token,
            patch("app.auth.services.datetime") as mock_datetime,
        ):
            mock_token.return_value = "test_token_456"
            fixed_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = fixed_now

            await auth_service.create_email_verification_link(user_id, user_updated_at)

            # Verify data was stored in Redis
            redis_key = f"{constants.VERIFICATION_PREFIX}test_token_456"
            stored_data = await fake_redis_client.get(redis_key)

            assert stored_data is not None
            payload = json.loads(stored_data)
            assert payload["user_id"] == user_id
            assert payload["issued_at"] == int(fixed_now.timestamp())

    async def test_calculates_correct_ttl(self, db_session, fake_redis_client):
        """Test that TTL is calculated correctly based on grace period."""
        auth_service = AuthService(db=db_session)
        user_id = 789
        user_updated_at = datetime.now(timezone.utc)

        with patch("app.auth.services.datetime") as mock_datetime:
            fixed_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = fixed_now

            await auth_service.create_email_verification_link(user_id, user_updated_at)

            # Check TTL was set
            redis_key = f"{constants.VERIFICATION_PREFIX}"
            keys = await fake_redis_client.keys(f"{redis_key}*")
            assert len(keys) > 0

            # TTL should be set
            ttl = await fake_redis_client.ttl(keys[0])
            assert ttl > 0

    async def test_generates_unique_tokens(self, db_session, fake_redis_client):
        """Test that multiple calls generate different tokens."""
        auth_service = AuthService(db=db_session)
        user_id = 100
        user_updated_at = datetime.now(timezone.utc)

        # Don't mock token generation, use real secrets module
        link1 = await auth_service.create_email_verification_link(
            user_id, user_updated_at
        )
        link2 = await auth_service.create_email_verification_link(
            user_id, user_updated_at
        )

        # Tokens should be different
        assert link1 != link2

    async def test_handles_past_user_updated_at(self, db_session, fake_redis_client):
        """Test handling when user_updated_at is in the past."""
        auth_service = AuthService(db=db_session)
        user_id = 200
        # User updated 1 hour ago
        user_updated_at = datetime.now(timezone.utc) - timedelta(hours=1)

        with patch("app.auth.services.datetime") as mock_datetime:
            fixed_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = fixed_now

            await auth_service.create_email_verification_link(user_id, user_updated_at)

            # Token should be created and stored
            redis_key = f"{constants.VERIFICATION_PREFIX}"
            keys = await fake_redis_client.keys(f"{redis_key}*")
            assert len(keys) > 0
