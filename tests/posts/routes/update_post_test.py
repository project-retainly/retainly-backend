import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.posts.factories import PostFactory
from tests.users.factories import UserFactory


class TestUpdatePostRoute:
    @pytest.fixture
    def url(self):
        return "/api/v1/posts/{id}"

    async def test_update_post_success(
        self,
        url: str,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user, slug="update-test")
        await db_session.commit()

        payload = {"title": "Updated Title"}
        response = await auth_client.put(url.format(id=post.id), json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["title"] == "Updated Title"

    async def test_update_post_full_payload(
        self,
        url: str,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)
        await db_session.commit()

        payload = {
            "title": "New Title",
            "content": {"blocks": [{"type": "header", "data": {"text": "Updated"}}]},
            "summary": "Updated summary",
            "status": "published",
            "featured_image": "https://new-image.com/img.jpg",
        }
        response = await auth_client.put(url.format(id=post.id), json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["title"] == payload["title"]
        assert data["summary"] == payload["summary"]

    async def test_update_post_partial_payload(
        self,
        url: str,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user, title="Original")
        await db_session.commit()

        payload = {"summary": "Only updating summary"}
        response = await auth_client.put(url.format(id=post.id), json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["summary"] == payload["summary"]

    async def test_update_post_not_found(
        self, url: str, auth_client: AsyncClient, disable_rate_limiting
    ):
        payload = {"title": "Won't work"}
        response = await auth_client.put(url.format(id="nonexistent-id"), json=payload)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_update_post_without_auth(
        self,
        url: str,
        client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user = await UserFactory.create()
        post = await PostFactory.create(owner=user)
        await db_session.commit()

        payload = {"title": "Unauthorized update"}
        response = await client.put(url.format(id=post.id), json=payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_update_post_different_owner(
        self,
        url: str,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        other_user = await UserFactory.create()
        post = await PostFactory.create(owner=other_user)
        await db_session.commit()

        payload = {"title": "Trying to update someone else's post"}
        response = await auth_client.put(url.format(id=post.id), json=payload)
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ]

    async def test_update_post_change_status_to_published(
        self,
        url: str,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user, status="draft")
        await db_session.commit()

        payload = {"status": "published"}
        response = await auth_client.put(url.format(id=post.id), json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "published"

    async def test_update_post_invalid_payload(
        self,
        url: str,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)
        await db_session.commit()

        payload = {"content": "not a dict"}
        response = await auth_client.put(url.format(id=post.id), json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_update_post_empty_title(
        self,
        url: str,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        disable_rate_limiting,
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)
        await db_session.commit()

        payload = {"title": ""}
        response = await auth_client.put(url.format(id=post.id), json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
