import json
from datetime import datetime, timezone

from app.auth import constants
from app.auth.services import AuthService


class TestVerifyAndGetUserIdFromToken:
    """Tests for AuthService.verify_and_get_user_id_from_token method."""

    async def test_successfully_verifies_valid_token(
        self, db_session, fake_redis_client
    ):
        """Test successful verification of a valid token."""
        auth_service = AuthService(db=db_session)
        token = "valid_token_123"
        user_id = 456
        issued_at = int(datetime.now(timezone.utc).timestamp())

        payload = {"user_id": user_id, "issued_at": issued_at}
        redis_key = f"{constants.VERIFICATION_PREFIX}{token}"
        await fake_redis_client.set(redis_key, json.dumps(payload))

        result = await auth_service.verify_and_get_user_id_from_token(token)

        assert result == (user_id, issued_at)

    async def test_deletes_token_after_use(self, db_session, fake_redis_client):
        """Test that token is deleted after successful verification (one-time use)."""
        auth_service = AuthService(db=db_session)
        token = "valid_token_456"
        user_id = 789
        issued_at = int(datetime.now(timezone.utc).timestamp())

        payload = {"user_id": user_id, "issued_at": issued_at}
        redis_key = f"{constants.VERIFICATION_PREFIX}{token}"
        await fake_redis_client.set(redis_key, json.dumps(payload))

        await auth_service.verify_and_get_user_id_from_token(token)

        # Verify token was deleted (one-time use)
        result = await fake_redis_client.get(redis_key)
        assert result is None

    async def test_returns_none_for_nonexistent_token(
        self, db_session, fake_redis_client
    ):
        """Test that None is returned when token doesn't exist in Redis."""
        auth_service = AuthService(db=db_session)
        token = "nonexistent_token"

        result = await auth_service.verify_and_get_user_id_from_token(token)

        assert result is None

    async def test_handles_corrupted_json_data(self, db_session, fake_redis_client):
        """Test handling of corrupted JSON data in Redis."""
        auth_service = AuthService(db=db_session)
        token = "corrupted_token"
        redis_key = f"{constants.VERIFICATION_PREFIX}{token}"

        await fake_redis_client.set(redis_key, "not valid json {{")

        result = await auth_service.verify_and_get_user_id_from_token(token)

        assert result is None
        # Should delete corrupted token
        assert await fake_redis_client.get(redis_key) is None

    async def test_handles_missing_user_id_in_payload(
        self, db_session, fake_redis_client
    ):
        """Test handling when user_id is missing from payload."""
        auth_service = AuthService(db=db_session)
        token = "invalid_payload_token"
        payload = {"issued_at": 123456789}  # Missing user_id
        redis_key = f"{constants.VERIFICATION_PREFIX}{token}"

        await fake_redis_client.set(redis_key, json.dumps(payload))

        result = await auth_service.verify_and_get_user_id_from_token(token)

        assert result is None
        # Should delete invalid token
        assert await fake_redis_client.get(redis_key) is None

    async def test_handles_missing_issued_at_in_payload(
        self, db_session, fake_redis_client
    ):
        """Test handling when issued_at is missing from payload."""
        auth_service = AuthService(db=db_session)
        token = "invalid_payload_token"
        payload = {"user_id": 123}  # Missing issued_at
        redis_key = f"{constants.VERIFICATION_PREFIX}{token}"

        await fake_redis_client.set(redis_key, json.dumps(payload))

        result = await auth_service.verify_and_get_user_id_from_token(token)

        assert result is None
        assert await fake_redis_client.get(redis_key) is None

    async def test_handles_invalid_user_id_type(self, db_session, fake_redis_client):
        """Test handling when user_id is not a valid integer."""
        auth_service = AuthService(db=db_session)
        token = "invalid_type_token"
        payload = {"user_id": "not_an_integer", "issued_at": 123456789}
        redis_key = f"{constants.VERIFICATION_PREFIX}{token}"

        await fake_redis_client.set(redis_key, json.dumps(payload))

        result = await auth_service.verify_and_get_user_id_from_token(token)

        assert result is None
        assert await fake_redis_client.get(redis_key) is None

    async def test_handles_invalid_issued_at_type(self, db_session, fake_redis_client):
        """Test handling when issued_at is not a valid integer."""
        auth_service = AuthService(db=db_session)
        token = "invalid_type_token"
        payload = {"user_id": 123, "issued_at": "not_an_integer"}
        redis_key = f"{constants.VERIFICATION_PREFIX}{token}"

        await fake_redis_client.set(redis_key, json.dumps(payload))

        result = await auth_service.verify_and_get_user_id_from_token(token)

        assert result is None
        assert await fake_redis_client.get(redis_key) is None
