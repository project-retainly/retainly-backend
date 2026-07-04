import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.posts.factories import PostFactory
from tests.users.factories import UserFactory


class TestGetPostDetailRoute:
    @pytest.fixture
    def url(self):
        return "/api/v1/posts/{id}"  # Updated to use ID instead of Slug

    async def test_get_post_detail_success(
        self,
        url: str,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)
        await db_session.commit()

        response = await auth_client.get(url.format(id=post.id))
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == post.id

    async def test_get_post_detail_not_found(
        self, url: str, auth_client: AsyncClient, disable_rate_limiting
    ):
        response = await auth_client.get(url.format(id="nonexistent-id"))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_post_detail_without_auth(
        self,
        url: str,
        client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user = await UserFactory.create()
        post = await PostFactory.create(owner=user)
        await db_session.commit()

        response = await client.get(url.format(id=post.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_post_detail_different_owner(
        self,
        url: str,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        other_user = await UserFactory.create()
        post = await PostFactory.create(owner=other_user)
        await db_session.commit()

        response = await auth_client.get(url.format(id=post.id))
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ]

    async def test_get_post_detail_with_full_content(
        self,
        url: str,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user = auth_client.user
        content = {
            "time": 1234567890,
            "blocks": [{"type": "paragraph", "data": {"text": "Full content"}}],
        }
        post = await PostFactory.create(owner=user, content=content)
        await db_session.commit()

        response = await auth_client.get(url.format(id=post.id))
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "content" in data

    async def test_get_post_detail_published_status(
        self,
        url: str,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user, status="published")
        await db_session.commit()

        response = await auth_client.get(url.format(id=post.id))
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "published"
