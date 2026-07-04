import json

import pytest

from app.auth.constants import PASSWORD_RESET_PREFIX
from app.core.exceptions import AppError, AppException


class TestVerifyAndGetUserIdFromPasswordResetTokenService:
    @pytest.mark.asyncio
    async def test_verify_token_success(self, db_session, fake_redis_client):
        from app.auth.services import AuthService

        service = AuthService(db=db_session)
        token = "valid_token"
        user_id = 123
        redis_key = f"{PASSWORD_RESET_PREFIX}{token}"

        await fake_redis_client.set(redis_key, json.dumps({"user_id": user_id}))

        result = await service.verify_and_get_user_id_from_password_reset_token(token)

        assert result == user_id

    @pytest.mark.asyncio
    async def test_verify_token_not_in_redis(self, db_session):
        from app.auth.services import AuthService

        service = AuthService(db=db_session)
        token = "nonexistent_token"

        with pytest.raises(AppException) as exc_info:
            await service.verify_and_get_user_id_from_password_reset_token(token)

        assert exc_info.value.error == AppError.INVALID_VERIFICATION_TOKEN

    @pytest.mark.asyncio
    async def test_verify_token_corrupted_missing_user_id(
        self, db_session, fake_redis_client
    ):
        from app.auth.services import AuthService

        service = AuthService(db=db_session)
        token = "corrupted_token"
        redis_key = f"{PASSWORD_RESET_PREFIX}{token}"

        await fake_redis_client.set(redis_key, json.dumps({"wrong_key": "value"}))

        with pytest.raises(AppException) as exc_info:
            await service.verify_and_get_user_id_from_password_reset_token(token)

        assert exc_info.value.error == AppError.INVALID_VERIFICATION_TOKEN

        token_exists = await fake_redis_client.get(redis_key)
        assert token_exists is None

    @pytest.mark.asyncio
    async def test_verify_token_corrupted_invalid_json(
        self, db_session, fake_redis_client
    ):
        from app.auth.services import AuthService

        service = AuthService(db=db_session)
        token = "invalid_json_token"
        redis_key = f"{PASSWORD_RESET_PREFIX}{token}"

        await fake_redis_client.set(redis_key, "not_valid_json")

        with pytest.raises(AppException) as exc_info:
            await service.verify_and_get_user_id_from_password_reset_token(token)

        assert exc_info.value.error == AppError.INVALID_VERIFICATION_TOKEN

        token_exists = await fake_redis_client.get(redis_key)
        assert token_exists is None

    @pytest.mark.asyncio
    async def test_verify_token_corrupted_user_id_not_int(
        self, db_session, fake_redis_client
    ):
        from app.auth.services import AuthService

        service = AuthService(db=db_session)
        token = "invalid_user_id_token"
        redis_key = f"{PASSWORD_RESET_PREFIX}{token}"

        await fake_redis_client.set(redis_key, json.dumps({"user_id": "not_an_int"}))

        with pytest.raises(AppException) as exc_info:
            await service.verify_and_get_user_id_from_password_reset_token(token)

        assert exc_info.value.error == AppError.INVALID_VERIFICATION_TOKEN

        token_exists = await fake_redis_client.get(redis_key)
        assert token_exists is None
