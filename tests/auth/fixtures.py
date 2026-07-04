from typing import AsyncGenerator
from unittest.mock import Mock

import pytest
from fastapi import Request
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.utils import create_access_token
from app.core.models_registry import user_models


@pytest.fixture(scope="function", name="get_auth_client")
async def get_authenticated_client(
    db_session: AsyncSession, client: AsyncGenerator[AsyncClient | None]
):
    async def _get_client(user: user_models.User):
        token: str = create_access_token(user.id)

        client.headers["Authorization"] = f"Bearer {token}"

        client.user = user
        return client

    return _get_client


@pytest.fixture(scope="function", name="auth_client")
async def authenticated_client(create_user, get_auth_client):
    user = await create_user()
    return await get_auth_client(user)


@pytest.fixture(scope="function", name="request_factory_agent_ipv4")
async def mocked_request_with_user_agent_and_host_factory(faker):
    async def _get_mocked_request():
        mock_request = Mock(spec=Request)

        mock_request.headers = {"User-Agent": faker.user_agent()}
        mock_request.client.host = faker.ipv4()

        return mock_request

    return _get_mocked_request
