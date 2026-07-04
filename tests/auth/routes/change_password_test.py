import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.messages import AuthMessages


class TestChangePasswordRoute:
    endpoint = "/api/v1/auth/change-password/"

    @pytest.mark.asyncio
    async def test_change_password_success(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        mock_send_password_change_notification_email_task,
    ):
        payload = {
            "current_password": "Test_password_$123",
            "new_password": "New_password_$456",
        }

        response = await auth_client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == AuthMessages.PASSWORD_CHANGE_SUCCESS
        assert mock_send_password_change_notification_email_task.called is True

    @pytest.mark.asyncio
    async def test_change_password_invalid_current_password(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
    ):
        payload = {
            "current_password": "WrongPassword123!",
            "new_password": "New_password_$456",
        }

        response = await auth_client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_change_password_unauthenticated(
        self,
        client: AsyncClient,
    ):
        payload = {
            "current_password": "Test_password_$123",
            "new_password": "New_password_$456",
        }

        response = await client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_change_password_missing_current_password(
        self,
        auth_client: AsyncClient,
    ):
        payload = {
            "new_password": "New_password_$456",
        }

        response = await auth_client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_change_password_missing_new_password(
        self,
        auth_client: AsyncClient,
    ):
        payload = {
            "current_password": "Test_password_$123",
        }

        response = await auth_client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_change_password_empty_payload(
        self,
        auth_client: AsyncClient,
    ):
        payload = {}

        response = await auth_client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_change_password_same_as_current(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        mock_send_password_change_notification_email_task,
    ):
        payload = {
            "current_password": "Test_password_$123",
            "new_password": "Test_password_$123",
        }

        response = await auth_client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_200_OK
        assert mock_send_password_change_notification_email_task.called is True

    @pytest.mark.asyncio
    async def test_change_password_weak_new_password(
        self,
        auth_client: AsyncClient,
    ):
        payload = {
            "current_password": "Test_password_$123",
            "new_password": "weak",
        }

        response = await auth_client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_change_password_null_values(
        self,
        auth_client: AsyncClient,
    ):
        payload = {
            "current_password": None,
            "new_password": None,
        }

        response = await auth_client.post(self.endpoint, json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
