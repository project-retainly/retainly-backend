import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.common import time_utils as TU
from app.common.constants import DateFormat as DF
from app.media.services import MediaService
from app.media.utils import StaticDirs


class TestMediaServiceGetFilePath:
    @pytest.fixture
    def media_service(self, db_session: AsyncSession):
        return MediaService(db_session)

    async def test_creates_correct_path_structure(self, media_service):
        final_filename = "test_file.jpg"
        directory = StaticDirs.Uploads.TEMP
        result = media_service._get_file_path(final_filename, directory)
        assert (
            result
            == f"{StaticDirs.Uploads.TEMP}/{TU.utc_now_format(DF.YYYYMMDD)}/{final_filename}"
        )

    async def test_uses_current_date_in_path(self, media_service):
        final_filename = "image.png"
        directory = "uploads"
        result = media_service._get_file_path(final_filename, directory)
        expected_date = TU.utc_now_format(DF.YYYYMMDD)
        assert f"/{expected_date}/" in result
