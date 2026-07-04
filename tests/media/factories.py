import factory
from async_factory_boy.factory.sqlalchemy import AsyncSQLAlchemyFactory

from app.core.settings import settings
from app.media import models
from app.media.utils import MediaStatus
from tests.file_factory import FileFactory, FilePresets
from tests.users.factories import UserFactory


class MediaFactory(AsyncSQLAlchemyFactory):
    class Meta:
        model = models.Media
        sqlalchemy_session_persistence = "commit"

    user = factory.SubFactory(UserFactory)

    status = MediaStatus.ACTIVE
    media_type = FilePresets.JPEG.mime
    filename = factory.Sequence(lambda n: f"gen_image_{n}.jpg")

    # Unique path to avoid collisions
    file_path = factory.Sequence(
        lambda n: f"uploads/user_{n}/2024/gen_image_{n}.jpg"
    )

    size_bytes = len(FilePresets.JPEG.header) + 1000

    class Params:
        is_image = factory.Trait(
            media_type=FilePresets.JPEG.mime,
            filename=factory.Sequence(lambda n: f"photo_{n}.jpg"),
            size_bytes=len(FilePresets.JPEG.header) + 5000,
        )
        is_pdf = factory.Trait(
            media_type=FilePresets.PDF.mime,
            filename=factory.Sequence(lambda n: f"contract_{n}.pdf"),
            size_bytes=len(FilePresets.PDF.header) + 500,
        )
        is_text = factory.Trait(
            media_type=FilePresets.TEXT.mime,
            filename=factory.Sequence(lambda n: f"note_{n}.txt"),
            size_bytes=len(FilePresets.TEXT.header) + 100,
        )

    @classmethod
    async def _create(cls, model_class, *args, **kwargs):
        """
        1. Create the DB record (awaiting it properly).
        2. Create the physical file on disk.
        3. Return the object.
        """
        # A. Create the DB Record
        obj = await super()._create(model_class, *args, **kwargs)

        # B. Prepare the Real File
        preset = FilePresets.JPEG
        if obj.media_type == FilePresets.PDF.mime:
            preset = FilePresets.PDF
        elif obj.media_type == FilePresets.TEXT.mime:
            preset = FilePresets.TEXT
        elif obj.media_type == FilePresets.PNG.mime:
            preset = FilePresets.PNG

        # Generate fake bytes in memory
        upload_file = FileFactory.create(
            file_type=preset, filename=obj.filename, size_bytes=obj.size_bytes
        )

        # C. Write to Disk (Synchronously is fine/safer here)
        full_disk_path = settings.MEDIA_DIR / obj.file_path
        full_disk_path.parent.mkdir(parents=True, exist_ok=True)

        # Read directly from the BytesIO object (synchronous)
        content = upload_file.file.read()
        full_disk_path.write_bytes(content)

        return obj
