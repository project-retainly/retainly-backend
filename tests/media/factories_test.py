import pytest

from app.core.settings import settings

from .factories import MediaFactory


@pytest.mark.asyncio
async def test_factory_creates_real_disk_assets():
    # 1. Create the data (One line!)
    media = await MediaFactory(is_pdf=True)

    # ----------------------------------------------------
    # CHECK 1: Database Integrity
    # ----------------------------------------------------
    assert media.id is not None
    assert media.user.id is not None  # Real User created!
    assert media.media_type == "application/pdf"

    # ----------------------------------------------------
    # CHECK 2: Physical File Existence
    # ----------------------------------------------------
    expected_path = settings.MEDIA_DIR / media.file_path

    # print(f"Checking for file at: {expected_path}")

    assert expected_path.exists() is True
    assert expected_path.is_file() is True

    # ----------------------------------------------------
    # CHECK 3: Content Integrity
    # ----------------------------------------------------
    # Does it start with PDF magic bytes? (%PDF-1.4)
    content = expected_path.read_bytes()
    assert content.startswith(b"%PDF-1.4")
