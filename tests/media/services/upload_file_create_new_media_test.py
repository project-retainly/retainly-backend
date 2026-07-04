import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.validations.file_validator import AnalyzedFile
from app.media.services import MediaService
from app.media.utils import MediaStatus, StaticDirs
from tests.file_factory import FileFactory, FilePresets
from tests.users.factories import UserFactory


class TestMediaServiceUploadFileAndCreateMedia:
    @pytest.fixture
    def media_service(self, db_session: AsyncSession):
        return MediaService(db_session)

    async def test_uploads_file_and_creates_media_successfully(
        self, media_service, db_session
    ):
        user = await UserFactory.create()
        upload_file = FileFactory.create(
            file_type=FilePresets.JPEG, filename="photo.jpg", size_bytes=5000
        )
        analyzed_file = AnalyzedFile(file=upload_file)
        media = await media_service.upload_file_and_create_media(
            analyzed_file, user.id, StaticDirs.Uploads.TEMP
        )
        assert media.filename.endswith(".jpg")
        assert media.media_type == "image/jpeg"
        assert media.size_bytes == 5000
        assert media.user_id == user.id
        assert media.status == MediaStatus.ACTIVE
        assert media.file_path.startswith(StaticDirs.Uploads.TEMP)

    async def test_uses_custom_directory(self, media_service, db_session):
        user = await UserFactory.create()
        upload_file = FileFactory.create(
            file_type=FilePresets.PNG, filename="avatar.png", size_bytes=3000
        )
        analyzed_file = AnalyzedFile(file=upload_file)
        custom_dir = "avatars"
        media = await media_service.upload_file_and_create_media(
            analyzed_file, user.id, custom_dir
        )
        assert media.file_path.startswith(custom_dir)

    async def test_creates_unique_filenames_for_duplicates(
        self, media_service, db_session
    ):
        user = await UserFactory.create()
        upload_file1 = FileFactory.create(
            file_type=FilePresets.PDF, filename="document.pdf", size_bytes=2000
        )
        upload_file2 = FileFactory.create(
            file_type=FilePresets.PDF, filename="document.pdf", size_bytes=2000
        )
        analyzed_file1 = AnalyzedFile(file=upload_file1)
        analyzed_file2 = AnalyzedFile(file=upload_file2)

        media1 = await media_service.upload_file_and_create_media(
            analyzed_file1, user.id
        )
        media2 = await media_service.upload_file_and_create_media(
            analyzed_file2, user.id
        )
        assert media1.filename != media2.filename
        assert media1.file_path != media2.file_path
