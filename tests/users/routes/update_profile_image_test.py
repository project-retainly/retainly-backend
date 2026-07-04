from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.validations.messages import Msg
from app.media.models import Media
from app.media.utils import StaticDirs
from app.users.constants import PROFILE_PIC_MAX_SIZE_MB as PFP_MAX_MB
from tests.file_factory import FileFactory, FilePresets
from tests.media.factories import MediaFactory


class TestUpdateProfileImageRoute:
    endpoint = "api/v1/users/profile-image"

    async def test_success_upload_new_profile_image(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=2)

        response = await auth_client.put(
            self.endpoint,
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "profile_image" in data
        assert data["profile_image"] is not None
        assert data["profile_image"]["filename"].endswith(".jpg")

    async def test_success_replace_existing_profile_image(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        user = auth_client.user

        old_media = await MediaFactory.create(
            user_id=user.id,
            filename="old_avatar.jpg",
            file_path=f"{StaticDirs.Uploads.AVATARS}/old_avatar.jpg",
        )
        user.profile_image_id = old_media.id
        await db_session.commit()
        await db_session.refresh(user)

        file = FileFactory.create(file_type=FilePresets.PNG, size_mb=1)

        response = await auth_client.put(
            self.endpoint,
            files={"file": (file.filename, file.file.read(), file.content_type)},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["profile_image"]["id"] != old_media.id
        assert data["profile_image"]["filename"].endswith(".png")

        result = await db_session.get(Media, old_media.id)
        assert result.status == "deleted"

    async def test_success_png_image_upload(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        file = FileFactory.create(file_type=FilePresets.PNG, size_mb=1)

        response = await auth_client.put(
            self.endpoint,
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["profile_image"]["filename"].endswith(".png")

    async def test_failure_unauthenticated_request(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=1)

        response = await client.put(
            self.endpoint,
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_failure_file_exceeds_max_size(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=6)

        response = await auth_client.put(
            self.endpoint,
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE

        assert response.json()["message"] == Msg.FILE_TOO_LARGE.format(
            max_mb=PFP_MAX_MB
        )

    async def test_failure_invalid_file_type_pdf(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        file = FileFactory.create(file_type=FilePresets.PDF, size_mb=1)

        response = await auth_client.put(
            self.endpoint,
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        assert "Invalid file type" in response.json()["message"]

    async def test_failure_invalid_file_type_text(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        file = FileFactory.create(file_type=FilePresets.TEXT, size_mb=1)

        response = await auth_client.put(
            self.endpoint,
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE

    async def test_failure_no_file_provided(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        response = await auth_client.put(self.endpoint)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_failure_spoofed_file_extension(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        file = FileFactory.create(
            file_type=FilePresets.MALICIOUS_PHP,
            size_mb=1,
            spoof_extension=".jpg",
            spoof_mime="image/jpeg",
        )

        response = await auth_client.put(
            self.endpoint,
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE

    async def test_success_max_allowed_size(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=5)

        response = await auth_client.put(
            self.endpoint,
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_200_OK

    async def test_success_minimal_file_size(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        file = FileFactory.create(file_type=FilePresets.JPEG, size_bytes=100)

        response = await auth_client.put(
            self.endpoint,
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_200_OK

    async def test_success_response_includes_user_data(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        user = auth_client.user
        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=1)

        response = await auth_client.put(
            self.endpoint,
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == user.id
        assert data["username"] == user.username
        assert data["email"] == user.email
        assert "created_at" in data

    async def test_success_old_media_deleted_from_database(
        self, auth_client: AsyncClient, db_session: AsyncSession
    ):
        user = auth_client.user

        old_media = await MediaFactory.create(
            user_id=user.id,
            filename="delete_me.jpg",
            file_path=f"{StaticDirs.Uploads.AVATARS}/delete_me.jpg",
        )
        user.profile_image_id = old_media.id
        await db_session.commit()

        old_media_id = old_media.id

        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=1)

        response = await auth_client.put(
            self.endpoint,
            files={"file": (file.filename, file.file, file.content_type)},
        )

        assert response.status_code == status.HTTP_200_OK

        deleted_media = await db_session.get(Media, old_media_id)
        assert deleted_media.status == "deleted"
