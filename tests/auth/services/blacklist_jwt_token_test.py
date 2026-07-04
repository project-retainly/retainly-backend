import time

import pytest

from app.auth import constants
from app.auth.contexts import JwtContext
from app.auth.services import AuthService


class TestBlacklistJwtToken:
    """Tests for AuthService.blacklist_jwt_token method."""

    async def test_blacklists_token_successfully(self, db_session, fake_redis_client):
        """Test that JWT token is successfully blacklisted."""
        auth_service = AuthService(db=db_session)
        user_id = 123
        # Create a real JwtContext with exp 3600 seconds in the future
        jwt_context = JwtContext(
            sub=user_id, jti="unique-jwt-id-123", exp=int(time.time()) + 3600
        )

        await auth_service.blacklist_jwt_token(jwt_context, user_id)

        # Verify token was stored in Redis
        redis_key = f"{constants.BLACKLIST_PREFIX}{jwt_context.jti}"
        stored_value = await fake_redis_client.get(redis_key)
        assert stored_value == str(user_id)

    async def test_uses_correct_redis_key_prefix(self, db_session, fake_redis_client):
        """Test that the correct Redis key prefix is used."""
        auth_service = AuthService(db=db_session)
        user_id = 456

        jwt_context = JwtContext(
            sub=user_id, jti="test-jti-789", exp=int(time.time()) + 3600
        )

        await auth_service.blacklist_jwt_token(jwt_context, user_id)

        redis_key = f"{constants.BLACKLIST_PREFIX}test-jti-789"
        assert await fake_redis_client.exists(redis_key) == 1

    async def test_stores_user_id_as_value(self, db_session, fake_redis_client):
        """Test that user_id is stored as the value."""
        auth_service = AuthService(db=db_session)
        user_id = 999

        jwt_context = JwtContext(
            sub=user_id, jti="jti-999", exp=int(time.time()) + 3600
        )

        await auth_service.blacklist_jwt_token(jwt_context, user_id)

        redis_key = f"{constants.BLACKLIST_PREFIX}jti-999"
        stored_value = await fake_redis_client.get(redis_key)
        assert stored_value == str(user_id)

    async def test_sets_correct_expiry(self, db_session, fake_redis_client):
        """Test that the correct expiry time is set."""
        auth_service = AuthService(db=db_session)
        user_id = 111

        # Token expires in 7200 seconds (2 hours)
        jwt_context = JwtContext(
            sub=user_id, jti="jti-111", exp=int(time.time()) + 7200
        )

        await auth_service.blacklist_jwt_token(jwt_context, user_id)

        redis_key = f"{constants.BLACKLIST_PREFIX}jti-111"
        ttl = await fake_redis_client.ttl(redis_key)

        # TTL should be close to 7200 (allowing for small execution time difference)
        assert 7190 < ttl <= 7200

    async def test_handles_zero_remaining_seconds(self, db_session, fake_redis_client):
        """Test handling when token has zero remaining seconds (already expired).

        NOTE: Currently, the implementation will raise an error when trying to
        blacklist an expired token because Redis doesn't accept 0 or negative
        expiry times. This might be acceptable since expired tokens don't need
        to be blacklisted.

        If you want to handle this gracefully, the implementation should check:
        if jwt_context.remaining_seconds <= 0:
            return  # or log that token is already expired
        """
        auth_service = AuthService(db=db_session)
        user_id = 222

        # Token that expires right now (remaining_seconds = 0)
        jwt_context = JwtContext(sub=user_id, jti="jti-222", exp=int(time.time()))

        # Verify the context is expired
        assert jwt_context.is_expired is True
        assert jwt_context.remaining_seconds == 0

        # Redis will raise an error for 0 or negative expiry times
        # This is expected behavior - expired tokens shouldn't be blacklisted
        with pytest.raises(Exception):  # Could be ResponseError or similar
            await auth_service.blacklist_jwt_token(jwt_context, user_id)

    async def test_handles_negative_remaining_seconds(
        self, db_session, fake_redis_client
    ):
        """Test handling when token has negative exp time (expired in the past).

        NOTE: Same as test_handles_zero_remaining_seconds - the implementation
        currently raises an error for expired tokens, which might be acceptable.
        """
        auth_service = AuthService(db=db_session)
        user_id = 333

        # Token that expired 100 seconds ago
        # Note: JwtContext.remaining_seconds returns max(0, ...) so it will be 0
        jwt_context = JwtContext(sub=user_id, jti="jti-333", exp=int(time.time()) - 100)

        # Verify that remaining_seconds is clamped to 0
        assert jwt_context.remaining_seconds == 0
        assert jwt_context.is_expired is True

        # Redis will raise an error for 0 or negative expiry times
        # This is expected behavior - expired tokens shouldn't be blacklisted
        with pytest.raises(Exception):  # Could be ResponseError or similar
            await auth_service.blacklist_jwt_token(jwt_context, user_id)

    async def test_handles_very_small_remaining_seconds(
        self, db_session, fake_redis_client
    ):
        """Test handling when token has just 1-2 seconds remaining."""
        auth_service = AuthService(db=db_session)
        user_id = 444

        # Token that expires in 2 seconds
        jwt_context = JwtContext(sub=user_id, jti="jti-444", exp=int(time.time()) + 2)

        # Should be able to blacklist even with very short TTL
        await auth_service.blacklist_jwt_token(jwt_context, user_id)

        redis_key = f"{constants.BLACKLIST_PREFIX}jti-444"
        stored_value = await fake_redis_client.get(redis_key)
        assert stored_value == str(user_id)

        # TTL should be 1-2 seconds
        ttl = await fake_redis_client.ttl(redis_key)
        assert 0 < ttl <= 2

    async def test_blacklist_different_user_ids(self, db_session, fake_redis_client):
        """Test blacklisting tokens for different users."""
        auth_service = AuthService(db=db_session)

        # Blacklist token for user 100
        jwt_context_1 = JwtContext(
            sub=100, jti="jti-user-100", exp=int(time.time()) + 3600
        )
        await auth_service.blacklist_jwt_token(jwt_context_1, 100)

        # Blacklist token for user 200
        jwt_context_2 = JwtContext(
            sub=200, jti="jti-user-200", exp=int(time.time()) + 3600
        )
        await auth_service.blacklist_jwt_token(jwt_context_2, 200)

        # Verify both are stored correctly
        redis_key_1 = f"{constants.BLACKLIST_PREFIX}jti-user-100"
        redis_key_2 = f"{constants.BLACKLIST_PREFIX}jti-user-200"

        assert await fake_redis_client.get(redis_key_1) == "100"
        assert await fake_redis_client.get(redis_key_2) == "200"

    async def test_blacklist_with_varying_expiry_times(
        self, db_session, fake_redis_client
    ):
        """Test blacklisting tokens with different expiry times."""
        auth_service = AuthService(db=db_session)
        user_id = 444

        # Short-lived token (5 minutes)
        jwt_context_short = JwtContext(
            sub=user_id, jti="jti-short", exp=int(time.time()) + 300
        )
        await auth_service.blacklist_jwt_token(jwt_context_short, user_id)

        # Long-lived token (24 hours)
        jwt_context_long = JwtContext(
            sub=user_id, jti="jti-long", exp=int(time.time()) + 86400
        )
        await auth_service.blacklist_jwt_token(jwt_context_long, user_id)

        # Verify different TTLs
        redis_key_short = f"{constants.BLACKLIST_PREFIX}jti-short"
        redis_key_long = f"{constants.BLACKLIST_PREFIX}jti-long"

        ttl_short = await fake_redis_client.ttl(redis_key_short)
        ttl_long = await fake_redis_client.ttl(redis_key_long)

        assert 290 < ttl_short <= 300
        assert 86390 < ttl_long <= 86400

    async def test_jti_uniqueness(self, db_session, fake_redis_client):
        """Test that each JTI is unique and doesn't overwrite previous entries."""
        auth_service = AuthService(db=db_session)

        # Create two contexts with different JTIs
        jwt_context_1 = JwtContext(
            sub=555, jti="unique-jti-001", exp=int(time.time()) + 3600
        )
        jwt_context_2 = JwtContext(
            sub=555, jti="unique-jti-002", exp=int(time.time()) + 3600
        )

        await auth_service.blacklist_jwt_token(jwt_context_1, 555)
        await auth_service.blacklist_jwt_token(jwt_context_2, 555)

        # Both should exist independently
        redis_key_1 = f"{constants.BLACKLIST_PREFIX}unique-jti-001"
        redis_key_2 = f"{constants.BLACKLIST_PREFIX}unique-jti-002"

        assert await fake_redis_client.exists(redis_key_1) == 1
        assert await fake_redis_client.exists(redis_key_2) == 1
