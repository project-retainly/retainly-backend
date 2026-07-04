from enum import Enum


class MediaStatus(str, Enum):
    PENDING = "pending"  # Reserved, but file not confirmed yet
    ACTIVE = "active"  # File exists and is ready to view
    FAILED = "failed"  # Upload failed
    DELETED = "deleted"  # Soft-deleted, file may still exist but is not active

    def __repr__(self):
        return self.value


class StaticDirs:
    """
    Centralized registry of all static file paths.
    Usage: StaticDirs.UPLOADS.AVATARS -> 'uploads/avatars'
    """

    class Uploads:
        ROOT = "uploads"
        AVATARS = "uploads/avatars"
        POSTS = "uploads/posts"
        TEMP = "uploads/temp"

    class Assets:
        ROOT = "assets"
        DEFAULTS = "assets/defaults"
        BRAND = "assets/brand"
        EMAIL_IMAGES = "assets/email_images"

    class Exports:
        ROOT = "exports"


class StaticFiles:
    """
    Centralized registry of all static file paths.
    Usage: StaticFiles.DEFAULT_AVATAR -> 'assets/defaults/default_avatar.png'
    """

    DEFAULT_AVATAR = f"{StaticDirs.Assets.DEFAULTS}/default_avatar.png"


def extract_image_blocks(editor_json):
    blocks = []

    for block in editor_json.get("blocks", []):
        if block.get("type") != "image":
            continue

        file_data = block.get("data", {}).get("file", {})

        blocks.append({
            "block_id": block.get("id"),
            "media_id": file_data.get("media_id"),
        })

    return blocks
