import json

import pytest
from fastapi import status

from app.auth import constants
from app.auth.messages import AuthMessages
from app.users.models import UserStatus
from tests.users.factories import UserFactory


class TestForgotPasswordRoute:
    endpoint = "/api/v1/auth/forgot-password"

    @pytest.mark.asyncio
    async def test_forgot_password_success_active_user(
        self,
        client,
        db_session,
        disable_rate_limiting,
        mock_send_password_reset_email_task,
        fake_redis_client,
    ):
        user = await UserFactory.create(status=UserStatus.ACTIVE)
        await db_session.commit()

        response = await client.post(
            self.endpoint,
            json={"email": user.email},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == AuthMessages.GENERIC_PASSWORD_RESET_SENT

        keys = await fake_redis_client.keys(f"{constants.PASSWORD_RESET_PREFIX}*")
        assert len(keys) == 1

        stored_data = await fake_redis_client.get(keys[0])
        payload = json.loads(stored_data)
        assert payload["user_id"] == user.id

        assert mock_send_password_reset_email_task.called is True

    @pytest.mark.asyncio
    async def test_forgot_password_nonexistent_user(
        self,
        client,
        db_session,
        disable_rate_limiting,
        mock_send_password_reset_email_task,
        fake_redis_client,
    ):
        response = await client.post(
            self.endpoint,
            json={"email": "nonexistent@example.com"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == AuthMessages.GENERIC_PASSWORD_RESET_SENT

        keys = await fake_redis_client.keys(f"{constants.PASSWORD_RESET_PREFIX}*")
        assert len(keys) == 0

        assert mock_send_password_reset_email_task.called is False

    @pytest.mark.asyncio
    async def test_forgot_password_inactive_user(
        self,
        client,
        db_session,
        disable_rate_limiting,
        mock_send_password_reset_email_task,
        fake_redis_client,
    ):
        user = await UserFactory.create(status=UserStatus.PENDING)
        await db_session.commit()

        response = await client.post(
            self.endpoint,
            json={"email": user.email},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == AuthMessages.GENERIC_PASSWORD_RESET_SENT

        keys = await fake_redis_client.keys(f"{constants.PASSWORD_RESET_PREFIX}*")
        assert len(keys) == 0

        assert mock_send_password_reset_email_task.called is False

    @pytest.mark.asyncio
    async def test_forgot_password_deleted_user(
        self,
        client,
        db_session,
        disable_rate_limiting,
        mock_send_password_reset_email_task,
        fake_redis_client,
    ):
        user = await UserFactory.create(status=UserStatus.DELETED)
        await db_session.commit()

        response = await client.post(
            self.endpoint,
            json={"email": user.email},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == AuthMessages.GENERIC_PASSWORD_RESET_SENT

        keys = await fake_redis_client.keys(f"{constants.PASSWORD_RESET_PREFIX}*")
        assert len(keys) == 0

        assert mock_send_password_reset_email_task.called is False

    @pytest.mark.asyncio
    async def test_forgot_password_expired_user(
        self,
        client,
        db_session,
        disable_rate_limiting,
        mock_send_password_reset_email_task,
        fake_redis_client,
    ):
        user = await UserFactory.create(status=UserStatus.EXPIRED)
        await db_session.commit()

        response = await client.post(
            self.endpoint,
            json={"email": user.email},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == AuthMessages.GENERIC_PASSWORD_RESET_SENT

        keys = await fake_redis_client.keys(f"{constants.PASSWORD_RESET_PREFIX}*")
        assert len(keys) == 0

        assert mock_send_password_reset_email_task.called is False

    @pytest.mark.asyncio
    async def test_forgot_password_invalid_email_format(
        self,
        client,
        db_session,
        disable_rate_limiting,
        mock_send_password_reset_email_task,
        fake_redis_client,
    ):
        response = await client.post(
            self.endpoint,
            json={"email": "invalid-email"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        keys = await fake_redis_client.keys(f"{constants.PASSWORD_RESET_PREFIX}*")
        assert len(keys) == 0

        assert mock_send_password_reset_email_task.called is False

    @pytest.mark.asyncio
    async def test_forgot_password_missing_email(
        self,
        client,
        db_session,
        disable_rate_limiting,
        mock_send_password_reset_email_task,
        fake_redis_client,
    ):
        response = await client.post(
            self.endpoint,
            json={},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        keys = await fake_redis_client.keys(f"{constants.PASSWORD_RESET_PREFIX}*")
        assert len(keys) == 0

        assert mock_send_password_reset_email_task.called is False

    @pytest.mark.asyncio
    async def test_forgot_password_creates_reset_link(
        self,
        client,
        db_session,
        disable_rate_limiting,
        mock_send_password_reset_email_task,
        fake_redis_client,
    ):
        user = await UserFactory.create(status=UserStatus.ACTIVE)
        await db_session.commit()

        await client.post(
            self.endpoint,
            json={"email": user.email},
        )

        keys = await fake_redis_client.keys(f"{constants.PASSWORD_RESET_PREFIX}*")
        assert len(keys) == 1

        assert mock_send_password_reset_email_task.called is True

    @pytest.mark.asyncio
    async def test_forgot_password_rate_limit(
        self,
        client,
        db_session,
        mock_send_password_reset_email_task,
        fake_redis_client,
    ):
        user = await UserFactory.create(status=UserStatus.ACTIVE)
        await db_session.commit()

        await client.post(
            self.endpoint,
            json={"email": user.email},
        )

        keys = await fake_redis_client.keys(f"{constants.PASSWORD_RESET_PREFIX}*")
        assert len(keys) == 1

        assert mock_send_password_reset_email_task.called is True

        response = await client.post(
            self.endpoint,
            json={"email": user.email},
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
