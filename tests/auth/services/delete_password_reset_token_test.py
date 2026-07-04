import json

import pytest

from app.auth.constants import PASSWORD_RESET_PREFIX


class TestDeletePasswordResetTokenService:
    @pytest.mark.asyncio
    async def test_delete_token_success(self, db_session, fake_redis_client):
        from app.auth.services import AuthService

        service = AuthService(db=db_session)
        token = "token_to_delete"
        redis_key = f"{PASSWORD_RESET_PREFIX}{token}"

        await fake_redis_client.set(redis_key, json.dumps({"user_id": 123}))

        await service.delete_password_reset_token(token)

        token_exists = await fake_redis_client.get(redis_key)
        assert token_exists is None

    @pytest.mark.asyncio
    async def test_delete_token_nonexistent(self, db_session, fake_redis_client):
        from app.auth.services import AuthService

        service = AuthService(db=db_session)
        token = "nonexistent_token"

        await service.delete_password_reset_token(token)

        token_exists = await fake_redis_client.get(f"{PASSWORD_RESET_PREFIX}{token}")
        assert token_exists is None
