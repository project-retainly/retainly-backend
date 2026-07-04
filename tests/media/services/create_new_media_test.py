import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.media.models import Media
from app.media.services import MediaService
from app.media.utils import MediaStatus
from tests.users.factories import UserFactory


class TestMediaServiceCreateNewMedia:
    @pytest.fixture
    def media_service(self, db_session: AsyncSession):
        return MediaService(db_session)

    async def test_creates_media_record_successfully(self, media_service, db_session):
        user = await UserFactory.create()
        media_data = {
            "filename": "test.jpg",
            "media_type": "image/jpeg",
            "size_bytes": 1024,
            "file_path": "uploads/test.jpg",
            "user_id": user.id,
            "status": MediaStatus.ACTIVE,
        }
        media = await media_service.create_new_media(media_data)
        assert media.filename == "test.jpg"
        assert media.media_type == "image/jpeg"
        assert media.size_bytes == 1024
        assert media.user_id == user.id
        assert media.status == MediaStatus.ACTIVE

    async def test_does_not_commit_to_database(self, media_service, db_session):
        from sqlalchemy import select

        user = await UserFactory.create()
        media_data = {
            "filename": "uncommitted.jpg",
            "media_type": "image/jpeg",
            "size_bytes": 2048,
            "file_path": "uploads/uncommitted.jpg",
            "user_id": user.id,
            "status": MediaStatus.ACTIVE,
        }
        await media_service.create_new_media(media_data)
        await db_session.rollback()
        result = await db_session.execute(
            select(Media).where(Media.filename == "uncommitted.jpg")
        )
        assert result.scalar_one_or_none() is None
