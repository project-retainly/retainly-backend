from fastapi import status
from httpx import AsyncClient


class TestCreatePostRoute:
    url = "/api/v1/posts/"

    async def test_create_post_success(
        self, auth_client: AsyncClient, disable_rate_limiting
    ):
        payload = {
            "title": "My New Post",
            "content": {"blocks": [{"type": "paragraph", "data": {"text": "Hello"}}]},
            "summary": "A test summary",
            "status": "draft",
        }
        response = await auth_client.post(self.url, json=payload)
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["title"] == payload["title"]
        assert "id" in data

    async def test_create_post_with_published_status(
        self, auth_client: AsyncClient, disable_rate_limiting
    ):
        payload = {
            "title": "Published Post",
            "content": {"blocks": [{"type": "paragraph", "data": {"text": "Content"}}]},
            "summary": "Summary",
            "status": "published",
        }
        response = await auth_client.post(self.url, json=payload)
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["status"] == "published"
        assert data["published_at"] is not None

    async def test_create_post_without_auth(
        self, client: AsyncClient, disable_rate_limiting
    ):
        payload = {
            "title": "Unauthorized Post",
            "content": {"blocks": []},
        }
        response = await client.post(self.url, json=payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_create_post_missing_required_fields(
        self, auth_client: AsyncClient, disable_rate_limiting
    ):
        payload = {"title": "Missing Content"}
        response = await auth_client.post(self.url, json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_create_post_empty_title(
        self, auth_client: AsyncClient, disable_rate_limiting
    ):
        payload = {
            "title": "",
            "content": {"blocks": []},
        }
        response = await auth_client.post(self.url, json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_create_post_invalid_content_type(
        self, auth_client: AsyncClient, disable_rate_limiting
    ):
        payload = {
            "title": "Test",
            "content": "not a dict",
        }
        response = await auth_client.post(self.url, json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_create_post_minimal_payload(
        self, auth_client: AsyncClient, disable_rate_limiting
    ):
        payload = {
            "title": "Minimal Post",
            "content": {"blocks": []},
        }
        response = await auth_client.post(self.url, json=payload)
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["title"] == payload["title"]
