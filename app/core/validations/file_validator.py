import mimetypes
import os
from typing import Annotated

import magic
from fastapi import File, UploadFile

from app.core.exceptions import AppError, AppException

from .messages import Msg


class AnalyzedFile:
    """
    A generic file analyzer dependency.

    1. Reads the REAL file signature (Magic Numbers).
    2. Calculates the REAL size (Bytes).
    3. Corrects the file extension based on the real MIME type.
    4. Resets the file cursor so the Service layer can read it fresh.
    """

    def __init__(
        self,
        file: Annotated[UploadFile, File(..., description="Any file upload")],
    ):
        self.file = file
        self.name: str = os.path.splitext(file.filename)[0]  # name without extension
        self.extension: str = ""
        self.media_type: str = ""
        self.size_bytes: int = 0
        self.filename_with_extension: str = ""

        # Run analysis immediately upon injection
        self._analyze_metadata()

    def _get_size(self):
        # Move cursor to the end to get actual byte count
        self.file.file.seek(0, 2)
        size = self.file.file.tell()

        # Reset cursor to start (Crucial!)
        self.file.file.seek(0)

        if size == 0:
            raise AppException(error=AppError.EMPTY_FILE)

        return size

    def _get_media_type(self):
        # Read the first 2KB (Header) to find the magic number signature
        header_sample = self.file.file.read(2048)

        if not header_sample:
            raise AppException(error=AppError.FILE_CORRUPTED)

        # python-magic detects the true type (ignoring the user's Content-Type header)
        media_type = magic.from_buffer(header_sample, mime=True)

        # RESET cursor again so the next consumer reads from 0
        self.file.file.seek(0)

        return media_type

    def _get_extension(self):
        # If the user uploads "image.php" but it's a JPEG, we force ".jpg"
        # If the system can't guess, we fall back to the user's extension
        # Use mimetypes to guess the extension from the real content type
        guessed_ext = mimetypes.guess_extension(self.media_type)

        if guessed_ext:
            return guessed_ext

        # Fallback: Extract from original filename
        _, ext = os.path.splitext(self.file.filename)
        return ext

    def _analyze_metadata(self):
        # 1. CALCULATE REAL SIZE
        self.size_bytes = self._get_size()

        # 2. DETERMINE REAL CONTENT TYPE
        self.media_type = self._get_media_type()

        # 3. NORMALIZE EXTENSION ️
        self.extension = self._get_extension()

        # 4. UPDATE FILENAME TO MATCH REAL EXTENSION
        self.filename_with_extension = f"{self.name}{self.extension}"

    def validate_for_image_file(self, MAX_MB: int = 5):
        """Optional helper: Call this in your route if you specifically need an image."""
        allowed_types = ["image/jpeg", "image/png", "image/webp"]

        if self.media_type not in allowed_types:
            raise AppException(
                error=AppError.INVALID_FILE_TYPE,
                message=Msg.FILE_INVALID_TYPE.format(
                    type=self.media_type, allowed_types=", ".join(allowed_types)
                ),
            )

        if self.size_bytes > MAX_MB * 1024 * 1024:
            raise AppException(
                error=AppError.TOO_LARGE_FILE,
                message=Msg.FILE_TOO_LARGE.format(max_mb=MAX_MB),
            )
