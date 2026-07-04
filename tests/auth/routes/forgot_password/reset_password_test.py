import json
from unittest.mock import patch

import pytest
from fastapi import status

from app.auth.constants import PASSWORD_RESET_PREFIX
from app.auth.messages import AuthMessages
from app.core.exceptions import AppError
from app.users.utils import UserStatus
from tests.auth.factories import RefreshTokenFactory
from tests.users.factories import UserFactory


class TestVerifyPasswordResetTokenRoute:
    endpoint = "/api/v1/auth/reset-password/"

    @pytest.mark.asyncio
    async def test_reset_password_success(
        self, client, db_session, fake_redis_client, disable_rate_limiting
    ):
        user = await UserFactory.create(status=UserStatus.ACTIVE)
        old_password = user.password
        reset_token = "valid_reset_token_123"
        redis_key = f"{PASSWORD_RESET_PREFIX}{reset_token}"

        await fake_redis_client.set(
            redis_key, json.dumps({"user_id": user.id}), ex=3600
        )

        payload = {
            "token": reset_token,
            "new_password": "NewSecurePassword123!",
        }

        response = await client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == AuthMessages.PASSWORD_RESET_SUCCESS

        await db_session.refresh(user)
        assert user.password != old_password

        token_exists = await fake_redis_client.get(redis_key)
        assert token_exists is None

    @pytest.mark.asyncio
    async def test_reset_password_invalid_token_not_in_redis(
        self, client, disable_rate_limiting
    ):
        payload = {
            "token": "nonexistent_token",
            "new_password": "NewPassword123!",
        }

        response = await client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["message"] == AppError.INVALID_VERIFICATION_TOKEN.message

    @pytest.mark.asyncio
    async def test_reset_password_corrupted_token_data_no_user_id(
        self, client, fake_redis_client, disable_rate_limiting
    ):
        reset_token = "corrupted_token"
        redis_key = f"{PASSWORD_RESET_PREFIX}{reset_token}"

        await fake_redis_client.set(redis_key, json.dumps({"invalid_key": "value"}))

        payload = {"token": reset_token, "new_password": "NewPassword123!"}

        response = await client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["message"] == AppError.INVALID_VERIFICATION_TOKEN.message

        token_exists = await fake_redis_client.get(redis_key)
        assert token_exists is None

    @pytest.mark.asyncio
    async def test_reset_password_corrupted_token_data_invalid_json(
        self, client, fake_redis_client, disable_rate_limiting
    ):
        reset_token = "corrupted_json_token"
        redis_key = f"{PASSWORD_RESET_PREFIX}{reset_token}"

        await fake_redis_client.set(redis_key, "not_a_valid_json")

        payload = {"token": reset_token, "new_password": "NewPassword123!"}

        response = await client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["message"] == AppError.INVALID_VERIFICATION_TOKEN.message

        token_exists = await fake_redis_client.get(redis_key)
        assert token_exists is None

    @pytest.mark.asyncio
    async def test_reset_password_corrupted_token_data_invalid_user_id_type(
        self, client, fake_redis_client, disable_rate_limiting
    ):
        reset_token = "invalid_user_id_token"
        redis_key = f"{PASSWORD_RESET_PREFIX}{reset_token}"

        await fake_redis_client.set(redis_key, json.dumps({"user_id": "not_an_int"}))

        payload = {"token": reset_token, "new_password": "NewPassword123!"}

        response = await client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["message"] == AppError.INVALID_VERIFICATION_TOKEN.message

        token_exists = await fake_redis_client.get(redis_key)
        assert token_exists is None

    @pytest.mark.asyncio
    async def test_reset_password_user_not_found(
        self, client, fake_redis_client, disable_rate_limiting
    ):
        reset_token = "valid_token_nonexistent_user"
        redis_key = f"{PASSWORD_RESET_PREFIX}{reset_token}"

        await fake_redis_client.set(redis_key, json.dumps({"user_id": 99999}))

        payload = {"token": reset_token, "new_password": "NewPassword123!"}

        response = await client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["message"] == AppError.INVALID_VERIFICATION_TOKEN.message

    @pytest.mark.asyncio
    async def test_reset_password_user_not_active(
        self, client, fake_redis_client, disable_rate_limiting
    ):
        user = await UserFactory.create(status=UserStatus.PENDING)
        reset_token = "valid_token_inactive_user"
        redis_key = f"{PASSWORD_RESET_PREFIX}{reset_token}"

        await fake_redis_client.set(
            redis_key, json.dumps({"user_id": user.id}), ex=3600
        )

        payload = {"token": reset_token, "new_password": "NewPassword123!"}

        response = await client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["message"] == AppError.INVALID_VERIFICATION_TOKEN.message

    @pytest.mark.asyncio
    async def test_reset_password_same_as_old_password(
        self, client, db_session, fake_redis_client, disable_rate_limiting
    ):
        user = await UserFactory.create(status=UserStatus.ACTIVE)
        old_password_hash = user.password
        reset_token = "valid_token"
        redis_key = f"{PASSWORD_RESET_PREFIX}{reset_token}"

        await fake_redis_client.set(
            redis_key, json.dumps({"user_id": user.id}), ex=3600
        )

        with patch("app.auth.utils.get_password_hash", return_value=old_password_hash):
            payload = {
                "token": reset_token,
                "new_password": "Test_password_$123",
            }

            response = await client.post(self.endpoint, json=payload)

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert (
                response.json()["message"] == AppError.OLD_PASSWORD_SAME_AS_NEW.message
            )

    @pytest.mark.asyncio
    async def test_reset_password_revokes_all_refresh_tokens(
        self, client, db_session, fake_redis_client, disable_rate_limiting
    ):
        user = await UserFactory.create(status=UserStatus.ACTIVE)
        token1 = await RefreshTokenFactory.create(user=user)
        token2 = await RefreshTokenFactory.create(user=user)

        reset_token = "valid_reset_token"
        redis_key = f"{PASSWORD_RESET_PREFIX}{reset_token}"

        await fake_redis_client.set(
            redis_key, json.dumps({"user_id": user.id}), ex=3600
        )

        payload = {"token": reset_token, "new_password": "NewPassword123!"}

        response = await client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_200_OK

        await db_session.refresh(token1)
        await db_session.refresh(token2)

        assert token1.revoked_at is not None
        assert token1.revocation_reason == "password_reset"
        assert token2.revoked_at is not None
        assert token2.revocation_reason == "password_reset"

    @pytest.mark.asyncio
    async def test_reset_password_validation_error_missing_fields(
        self, client, disable_rate_limiting
    ):
        payload = {}

        response = await client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_reset_password_validation_error_empty_token(
        self, client, disable_rate_limiting
    ):
        payload = {"token": "", "new_password": "NewPassword123!"}

        response = await client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_reset_password_validation_error_empty_password(
        self, client, disable_rate_limiting
    ):
        payload = {"token": "valid_token", "new_password": ""}

        response = await client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
