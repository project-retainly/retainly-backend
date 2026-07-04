from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.posts.factories import PostFactory
from tests.users.factories import UserFactory


class TestGetAllPostsRoute:
    url = "/api/v1/posts/"

    async def test_get_all_posts_empty(
        self, auth_client: AsyncClient, disable_rate_limiting
    ):
        response = await auth_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    async def test_get_all_posts_with_data(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user = auth_client.user
        await PostFactory.create_batch(5, owner=user)
        await db_session.commit()

        response = await auth_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) == 5

    async def test_get_all_posts_pagination_limit(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user = auth_client.user
        await PostFactory.create_batch(10, owner=user)
        await db_session.commit()

        response = await auth_client.get(self.url, params={"limit": 5})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) <= 5

    async def test_get_all_posts_pagination_offset(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user = auth_client.user
        await PostFactory.create_batch(10, owner=user)
        await db_session.commit()

        response = await auth_client.get(self.url, params={"offset": 5, "limit": 5})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) <= 5

    async def test_get_all_posts_without_auth(
        self, client: AsyncClient, disable_rate_limiting
    ):
        response = await client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_all_posts_multiple_users(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user1 = auth_client.user
        user2 = await UserFactory.create()
        await db_session.commit()

        await PostFactory.create_batch(3, owner=user1)
        await PostFactory.create_batch(2, owner=user2)
        await db_session.commit()

        response = await auth_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] >= 3

    async def test_get_all_posts_ordering(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user = auth_client.user
        await PostFactory.create_batch(5, owner=user)
        await db_session.commit()

        response = await auth_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        items = data["items"]
        if len(items) > 1:
            assert items[0]["created_at"] >= items[-1]["created_at"]
