from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.media.models import Media
from app.media.utils import StaticDirs
from app.posts.constants import FEATURED_IMAGE_MAX_SIZE_MB as FI_MAX_MB
from tests.file_factory import FileFactory, FilePresets
from tests.media.factories import MediaFactory
from tests.posts.factories import PostFactory
from tests.users.factories import UserFactory


class TestUpdateFeaturedImageRoute:
    endpoint_template = "api/v1/posts/{id}/featured-image"

    def get_endpoint(self, id: str) -> str:
        return self.endpoint_template.format(id=id)

    async def test_success_upload_new_featured_image(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)

        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=2)

        response = await auth_client.put(
            self.get_endpoint(post.id),
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "featured_image" in data
        assert data["featured_image"] is not None
        assert data["featured_image"]["filename"].endswith(".jpg")

    async def test_success_replace_existing_featured_image(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)

        old_media = await MediaFactory.create(
            user_id=user.id,
            filename="old_featured.jpg",
            file_path=f"{StaticDirs.Uploads.POSTS}/{post.id}/old_featured.jpg",
        )
        post.featured_image_id = old_media.id
        await db_session.commit()
        await db_session.refresh(post)

        file = FileFactory.create(file_type=FilePresets.PNG, size_mb=1)

        response = await auth_client.put(
            self.get_endpoint(post.id),
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["featured_image"]["id"] != old_media.id
        assert data["featured_image"]["filename"].endswith(".png")

        result = await db_session.get(Media, old_media.id)
        assert result.status == "deleted"

    async def test_success_png_image_upload(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)

        file = FileFactory.create(file_type=FilePresets.PNG, size_mb=1)

        response = await auth_client.put(
            self.get_endpoint(post.id),
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["featured_image"]["filename"].endswith(".png")

    async def test_failure_unauthenticated_request(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user = await UserFactory.create()
        post = await PostFactory.create(owner=user)

        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=1)

        response = await client.put(
            self.get_endpoint(post.id),
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_failure_file_exceeds_max_size(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)

        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=FI_MAX_MB + 1)

        response = await auth_client.put(
            self.get_endpoint(post.id),
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
        assert "File size exceeds the maximum allowed" in response.json()["message"]

    async def test_failure_invalid_file_type_pdf(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)

        file = FileFactory.create(file_type=FilePresets.PDF, size_mb=1)

        response = await auth_client.put(
            self.get_endpoint(post.id),
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        assert "Invalid file type" in response.json()["message"]

    async def test_failure_invalid_file_type_text(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)

        file = FileFactory.create(file_type=FilePresets.TEXT, size_mb=1)

        response = await auth_client.put(
            self.get_endpoint(post.id),
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE

    async def test_failure_no_file_provided(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)

        response = await auth_client.put(self.get_endpoint(post.id))

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_failure_spoofed_file_extension(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)

        file = FileFactory.create(
            file_type=FilePresets.MALICIOUS_PHP,
            size_mb=1,
            spoof_extension=".jpg",
            spoof_mime="image/jpeg",
        )

        response = await auth_client.put(
            self.get_endpoint(post.id),
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE

    async def test_success_max_allowed_size(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)

        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=FI_MAX_MB)

        response = await auth_client.put(
            self.get_endpoint(post.id),
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_200_OK

    async def test_success_minimal_file_size(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)

        file = FileFactory.create(file_type=FilePresets.JPEG, size_bytes=100)

        response = await auth_client.put(
            self.get_endpoint(post.id),
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_200_OK

    async def test_success_response_includes_post_data(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)

        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=1)

        response = await auth_client.put(
            self.get_endpoint(post.id),
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == post.id
        assert data["slug"] == post.slug
        assert data["title"] == post.title
        assert "created_at" in data

    async def test_success_old_media_deleted_from_database(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        user = auth_client.user
        post = await PostFactory.create(owner=user)

        old_media = await MediaFactory.create(
            user_id=user.id,
            filename="delete_me.jpg",
            file_path=f"{StaticDirs.Uploads.POSTS}/{post.id}/delete_me.jpg",
        )
        post.featured_image_id = old_media.id
        await db_session.commit()

        old_media_id = old_media.id

        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=1)

        response = await auth_client.put(
            self.get_endpoint(post.id),
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_200_OK

        deleted_media = await db_session.get(Media, old_media_id)
        assert deleted_media.status == "deleted"

    async def test_failure_post_not_found(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=1)

        response = await auth_client.put(
            self.get_endpoint("non-existent-id"),
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_failure_unauthorized_user_cannot_update_others_post(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        other_user = await UserFactory.create()
        post = await PostFactory.create(owner=other_user)

        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=1)

        response = await auth_client.put(
            self.get_endpoint(post.id),
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
