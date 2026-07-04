import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.posts.utils import PostStatus
from tests.posts.factories import PostFactory
from tests.users.factories import UserFactory


class TestDeletePostRoute:
    @pytest.fixture
    def url(self):
        return "/api/v1/posts/{id}"

    async def test_delete_post_success(
        self,
        url: str,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)
        await db_session.commit()

        response = await auth_client.delete(url.format(id=post.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_delete_post_not_found(
        self, url: str, auth_client: AsyncClient, disable_rate_limiting
    ):
        response = await auth_client.delete(url.format(id="nonexistent-id"))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_post_without_auth(
        self,
        url: str,
        client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user = await UserFactory.create()
        post = await PostFactory.create(owner=user)
        await db_session.commit()

        response = await client.delete(url.format(id=post.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_delete_post_different_owner(
        self,
        url: str,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        other_user = await UserFactory.create()
        post = await PostFactory.create(owner=other_user)
        await db_session.commit()

        response = await auth_client.delete(url.format(id=post.id))
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ]

    async def test_delete_post_published_status(
        self,
        url: str,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user, status="published")
        await db_session.commit()

        response = await auth_client.delete(url.format(id=post.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_delete_post_verify_soft_delete(
        self,
        url: str,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)
        await db_session.commit()

        response = await auth_client.delete(url.format(id=post.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

        get_response = await auth_client.get(url.format(id=post.id))
        assert get_response.status_code == status.HTTP_200_OK
        data = get_response.json()
        assert data.get("status") == PostStatus.DELETED
