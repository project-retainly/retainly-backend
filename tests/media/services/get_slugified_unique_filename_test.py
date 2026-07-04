import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.media.services import MediaService


class TestMediaServiceGetSlugifiedUniqueFilename:
    @pytest.fixture
    def media_service(self, db_session: AsyncSession):
        return MediaService(db_session)

    async def test_generates_unique_slugified_filename(self, media_service):
        filename = "My Test File"
        extension = ".jpg"
        result = media_service._get_slugified_unique_filename(filename, extension)
        assert result.endswith("_my-test-file.jpg")
        assert len(result.split("_")[0]) == 8

    async def test_handles_special_characters(self, media_service):
        filename = "Файл_с_кириллицей@#$%"
        extension = ".png"
        result = media_service._get_slugified_unique_filename(filename, extension)
        assert result.endswith(extension)
        assert len(result.split("_")[0]) == 8

    async def test_generates_different_ids_for_same_filename(self, media_service):
        filename = "duplicate"
        extension = ".pdf"
        result1 = media_service._get_slugified_unique_filename(filename, extension)
        result2 = media_service._get_slugified_unique_filename(filename, extension)
        assert result1 != result2
        assert result1.endswith("_duplicate.pdf")
        assert result2.endswith("_duplicate.pdf")
