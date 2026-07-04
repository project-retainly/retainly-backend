import io
from dataclasses import dataclass
from typing import Optional

from fastapi import UploadFile


@dataclass
class FileType:
    mime: str
    extension: str
    header: bytes


class FilePresets:
    # 1. JPEG: SOI (FF D8) + APP0 Marker (FF E0) + Length (00 10) + 'JFIF' identifier
    # This ensures magic detects it as a valid JFIF JPEG.
    JPEG = FileType(
        "image/jpeg",
        ".jpg",
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00",
    )

    # 2. PNG: Signature + IHDR Chunk (Width=1, Height=1, BitDepth=8, Color=6)
    # The zeros after this header will just look like extra data, which is valid.
    PNG = FileType(
        "image/png",
        ".png",
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89",
    )

    # 3. PDF: Standard Header
    PDF = FileType("application/pdf", ".pdf", b"%PDF-1.4\n%    ")

    # 4. TEXT: Plain text
    TEXT = FileType("text/plain", ".txt", b"Just some text.")

    # 5. MALICIOUS
    MALICIOUS_PHP = FileType("text/x-php", ".php", b"<?php echo 'hack'; ?>")


class FileFactory:
    """
    A sophisticated factory to generate FastAPI UploadFile objects
    with real byte content, correct magic headers, and specific sizes.
    """

    @staticmethod
    def create(
        file_type: FileType = FilePresets.JPEG,
        size_mb: float = 0,
        size_bytes: Optional[int] = None,
        filename: Optional[str] = None,
        spoof_extension: Optional[str] = None,
        spoof_mime: Optional[str] = None,
    ) -> UploadFile:
        """
        :param file_type: One of FilePresets (JPEG, PNG, etc.)
        :param size_mb: Size in Megabytes (generates padding)
        :param size_bytes: Exact size in bytes (overrides size_mb)
        :param filename: Custom filename
        :param spoof_extension: Use a different extension than the real type (e.g. 'virus.jpg')
        :param spoof_mime: Send a fake Content-Type header
        """

        # 1. Calculate final size
        final_size = (
            size_bytes if size_bytes is not None else int(size_mb * 1024 * 1024)
        )

        # 2. Build Content (Header + Padding)
        header = file_type.header
        padding_needed = max(0, final_size - len(header))
        content = header + b"0" * padding_needed

        # 3. Determine Filename
        ext = spoof_extension if spoof_extension else file_type.extension
        name = filename if filename else f"test_file{ext}"

        # 4. Create File-Like Object
        file_obj = io.BytesIO(content)
        file_obj.name = name

        # 5. Determine Header MIME (User-provided vs Real)
        mime = spoof_mime if spoof_mime else file_type.mime

        # 6. Return FastAPI UploadFile
        # seek(0) is handled by Starlette/FastAPI usually, but good practice here
        file_obj.seek(0)
        return UploadFile(file=file_obj, filename=name, headers={"content-type": mime})

    @staticmethod
    def set_content(upload_file: UploadFile, content: bytes) -> None:
        """
        Completely replaces the content of an UploadFile object.

        This handles the tricky part of BytesIO:
        1. Seeks to 0.
        2. Overwrites content.
        3. TRUNCATES the file (removes any old trailing bytes).
        4. Resets seek to 0 so it's ready to be read by the app.
        """
        # We access the underlying .file (BytesIO) directly because
        # the FastAPI wrapper doesn't expose .truncate()
        upload_file.file.seek(0)
        upload_file.file.write(content)
        upload_file.file.truncate()
        upload_file.file.seek(0)
