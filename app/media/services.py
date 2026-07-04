from uuid import uuid4

from slugify import slugify

from app.core.logger import get_logger
from app.core.storage import get_storage_backend
from app.core.validations.file_validator import AnalyzedFile

from .models import Media
from .utils import MediaStatus, StaticDirs

logger = get_logger(__name__)


class MediaService:
    def __init__(self, db):
        self.db = db
        self.backend = get_storage_backend()

    def _get_slugified_unique_filename(self, filename: str, extension: str) -> str:
        slugified_name = slugify(filename)
        unique_id = str(uuid4())[:8]
        return f"{unique_id}_{slugified_name}{extension}"

    def _get_file_path(self, final_filename: str, directory: str) -> str:
        return f"{directory}/{final_filename}"

    async def create_new_media(self, media_data: dict):
        logger.info("creating_new_media_record", filename=media_data.get("filename"))
        media = Media(**media_data)
        self.db.add(media)
        # NOTE: not committing here, will be done in the route handler
        # after all operations succeed
        return media

    async def upload_file_and_create_media(
        self,
        analyzed_file: AnalyzedFile,
        user_id: int,
        directory: str = StaticDirs.Uploads.TEMP,
        media_status: MediaStatus = MediaStatus.ACTIVE,
    ):
        logger.info(
            "uploading_file",
            user_id=user_id,
            filename=analyzed_file.name,
            directory=directory,
        )
        final_filename = self._get_slugified_unique_filename(
            analyzed_file.name, analyzed_file.extension
        )
        save_to = self._get_file_path(final_filename, directory)

        try:
            path = await self.backend.upload(analyzed_file.file, save_to)
            logger.info("file_uploaded_successfully", path=path)
        except Exception as e:
            logger.error(
                "file_upload_failed", error=str(e), filename=analyzed_file.name
            )
            raise

        media_data = {
            "filename": final_filename,
            "media_type": analyzed_file.media_type,
            "size_bytes": analyzed_file.size_bytes,
            "file_path": path,
            "user_id": user_id,
            "status": media_status,
        }
        return await self.create_new_media(media_data)

    async def delete_media(self, media: Media):
        logger.info("deleting_media", media_id=media.id, file_path=media.file_path)
        # First, delete the file from storage
        try:
            await self.backend.delete(media.file_path)
            logger.info("file_deleted_from_storage", file_path=media.file_path)
        except Exception as e:
            logger.warning(
                "file_deletion_from_storage_failed",
                error=str(e),
                file_path=media.file_path,
            )
            # We might still want to mark it as deleted in DB even if file deletion fails
            pass

        # Then, delete the record from the database
        media.status = MediaStatus.DELETED
        self.db.add(media)
        logger.info("media_record_marked_as_deleted", media_id=media.id)

        # NOTE: not committing here, will be done in the route handler after all operations succeed
