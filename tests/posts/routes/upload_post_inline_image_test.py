from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.file_factory import FileFactory, FilePresets
from tests.posts.factories import PostFactory
from tests.users.factories import UserFactory


class TestUploadPostInlineImageRoute:
    endpoint_template = "api/v1/posts/{id}/images"

    def get_endpoint(self, id: str) -> str:
        return self.endpoint_template.format(id=id)

    async def test_success_upload_inline_image(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)

        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=1)

        response = await auth_client.post(
            self.get_endpoint(post.id),
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert "url" in data
        assert data["filename"].endswith(".jpg")
        assert f"/uploads/posts/{post.id}/" in data["url"]

    async def test_failure_post_not_found(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=1)

        response = await auth_client.post(
            self.get_endpoint("non-existent-id"),
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_failure_unauthorized_user_cannot_upload_to_others_post(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        other_user = await UserFactory.create()
        post = await PostFactory.create(owner=other_user)

        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=1)

        response = await auth_client.post(
            self.get_endpoint(post.id),
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_failure_invalid_file_type(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)

        file = FileFactory.create(file_type=FilePresets.PDF, size_mb=1)

        response = await auth_client.post(
            self.get_endpoint(post.id),
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE

    async def test_failure_file_too_large(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)

        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=6)  # Max is 5MB

        response = await auth_client.post(
            self.get_endpoint(post.id),
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
