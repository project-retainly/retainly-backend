import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.media.models import Media
from app.media.services import MediaService
from app.media.utils import MediaStatus
from tests.media.factories import MediaFactory


class TestMediaServiceDeleteMedia:
    @pytest.fixture
    def media_service(self, db_session: AsyncSession):
        return MediaService(db_session)

    async def test_marks_media_as_deleted(self, media_service, db_session):
        media = await MediaFactory.create()
        await media_service.delete_media(media)
        assert media.status == MediaStatus.DELETED

    async def test_does_not_commit_deletion(self, media_service, db_session):
        from sqlalchemy import select

        media = await MediaFactory.create()
        media_id = media.id
        await media_service.delete_media(media)
        await db_session.rollback()
        result = await db_session.execute(select(Media).where(Media.id == media_id))
        refreshed_media = result.scalar_one()
        assert refreshed_media.status == MediaStatus.ACTIVE

    async def test_deletes_file_from_storage(
        self, media_service, db_session, monkeypatch
    ):
        media = await MediaFactory.create()
        delete_called = False
        original_path = None

        async def mock_delete(path):
            nonlocal delete_called, original_path
            delete_called = True
            original_path = path

        monkeypatch.setattr(media_service.backend, "delete", mock_delete)
        await media_service.delete_media(media)
        assert delete_called
        assert original_path == media.file_path
