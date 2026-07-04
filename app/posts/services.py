import uuid
from datetime import datetime, timezone

from fastapi_pagination import LimitOffsetPage
from fastapi_pagination.ext.sqlalchemy import apaginate
from slugify import slugify
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, AppException
from app.core.logger import get_logger
from app.core.validations.file_validator import AnalyzedFile
from app.media.models import Media, MediaUsage
from app.media.services import MediaService  # Avoid circular import
from app.media.utils import MediaStatus, StaticDirs, extract_image_blocks

from .models import Post
from .schemas import PostCreate, PostUpdate
from .utils import PostStatus

logger = get_logger(__name__)


class PostService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_new_post(self, post_in: PostCreate, user_id: int) -> Post:
        logger.info("creating_new_post", user_id=user_id, title=post_in.title)
        post_data = post_in.model_dump()

        # If the user is creating the post immediately as PUBLISHED, set the timestamp.
        if post_data.get("status") == PostStatus.PUBLISHED:
            post_data["published_at"] = datetime.now(timezone.utc)

        # 1. Generate unique slug
        slug = await self._get_unique_slug(post_in.title)

        # 2. Create Post
        db_post = Post(**post_data, slug=slug, user_id=user_id)

        # 3. Commit to DB
        self.db.add(db_post)

        # Sync inline media from content
        await self.sync_post_media(post_id=db_post.id, editor_json=db_post.content)

        await self.db.commit()
        await self.db.refresh(db_post)

        logger.info("post_created", post_id=db_post.id, slug=db_post.slug)
        return db_post

    async def get_post_by_id(
        self,
        user_id: int,
        post_id: str | None = None,
    ) -> Post:
        logger.debug("getting_post", user_id=user_id, post_id=post_id)
        query = select(Post).filter_by(user_id=user_id)
        if post_id:
            query = query.filter_by(id=post_id)
        else:
            logger.error("get_post_missing_identifiers", user_id=user_id)
            raise AppException(error=AppError.BAD_REQUEST, extra={"msg": "Provide id"})

        post = (await self.db.execute(query)).scalar_one_or_none()

        if not post:
            logger.warning("post_not_found", user_id=user_id, identifier=post_id)
            raise AppException(error=AppError.NOT_FOUND, extra={"identifier": post_id})

        return post

    async def get_all_posts(self, user_id) -> LimitOffsetPage[Post]:
        logger.debug("getting_all_posts", user_id=user_id)
        query = select(Post).filter_by(user_id=user_id).order_by(Post.created_at.desc())
        return await apaginate(self.db, query)

    async def get_public_posts(self) -> LimitOffsetPage[Post]:
        logger.debug("getting_public_posts")
        query = (
            select(Post)
            .filter_by(status=PostStatus.PUBLISHED)
            .order_by(Post.published_at.desc())
        )
        return await apaginate(self.db, query)

    async def get_public_post_by_id(self, post_id: str) -> Post:
        logger.debug("getting_public_post_detail", post_id=post_id)
        query = select(Post).filter_by(id=post_id, status=PostStatus.PUBLISHED)
        post = (await self.db.execute(query)).scalar_one_or_none()

        if not post:
            logger.warning("public_post_not_found", post_id=post_id)
            raise AppException(error=AppError.NOT_FOUND, extra={"post_id": post_id})

        return post

    async def update_post(
        self, post_id: str, post_update: PostUpdate, user_id: int
    ) -> Post:
        logger.info("updating_post", user_id=user_id, post_id=post_id)
        post = await self.get_post_by_id(post_id=post_id, user_id=user_id)

        update_data = post_update.model_dump(exclude_unset=True)

        # Automatically regenerate slug if title is updated
        if "title" in update_data:
            new_slug = await self._get_unique_slug(update_data["title"])
            update_data["slug"] = new_slug
            logger.info("post_slug_auto_updated", post_id=post.id, new_slug=new_slug)

        for key, value in update_data.items():
            setattr(post, key, value)

            # Special logic: If status changes to PUBLISHED for the first time, set the date
            if (
                key == "status"
                and value == PostStatus.PUBLISHED
                and not post.published_at
            ):
                logger.info("post_status_changed_to_published", post_id=post.id)
                post.published_at = datetime.now(timezone.utc)

        # Sync inline media if content changed
        if "content" in update_data:
            await self.sync_post_media(post_id=post.id, editor_json=post.content)

        self.db.add(post)
        await self.db.commit()
        await self.db.refresh(post)

        logger.info("post_updated", post_id=post.id, slug=post.slug)
        return post

    async def soft_delete_post(self, post_id: str, user_id: int):
        logger.info("soft_deleting_post", user_id=user_id, post_id=post_id)
        from datetime import datetime, timezone

        query = (
            update(Post)
            .filter_by(id=post_id, user_id=user_id)
            .values(status=PostStatus.DELETED, deleted_at=datetime.now(timezone.utc))
            .returning(Post.id)
        )
        result = await self.db.execute(query)
        deleted_id = result.scalar_one_or_none()
        if not deleted_id:
            logger.warning(
                "soft_delete_failed_not_found", user_id=user_id, post_id=post_id
            )
            raise AppException(error=AppError.NOT_FOUND, extra={"id": post_id})

        await self.db.commit()
        logger.info("post_soft_deleted", post_id=deleted_id)

    async def update_featured_image(
        self, post: Post, analyzed_file: AnalyzedFile
    ) -> Post:
        """
        Updates the post's featured image with the given analyzed file.
        """
        logger.info("updating_featured_image", post_id=post.id, user_id=post.user_id)

        # 1. Initialize Media Service
        media_service = MediaService(self.db)

        # 2. HANDLE CLEANUP
        if post.featured_image:
            logger.info(
                "deleting_old_featured_image",
                post_id=post.id,
                media_id=post.featured_image.id,
            )
            await media_service.delete_media(post.featured_image)

        # 3. UPLOAD NEW IMAGE
        # We use post.id for the directory because it is immutable (unlike slug)
        directory = f"{StaticDirs.Uploads.POSTS}/{post.id}"

        new_media = await media_service.upload_file_and_create_media(
            analyzed_file, user_id=post.user_id, directory=directory
        )

        # 4. LINK & SAVE
        post.featured_image = new_media

        # 5. COMMIT
        await self.db.commit()
        await self.db.refresh(post)

        logger.info("featured_image_updated", post_id=post.id, media_id=new_media.id)
        return post


    async def sync_post_media(
        self,
        post_id: str,
        editor_json: dict,
    ):
        # 1. Extract image blocks
        blocks = extract_image_blocks(editor_json)

        if not blocks:
            return

        # ---------------------------------------
        # 2. Validate + collect media_ids
        # ---------------------------------------
        media_ids = []

        for b in blocks:
            media_id = b.get("media_id")

            if not media_id:
                raise ValueError(f"Missing media_id for block {b.get('block_id')}")

            media_ids.append(media_id)

        # ---------------------------------------
        # 3. Fetch media records
        # ---------------------------------------
        result = await self.db.execute(select(Media).where(Media.id.in_(media_ids)))
        media_rows = result.scalars().all()

        media_map = {m.id: m for m in media_rows}

        # Optional strict check: ensure all IDs exist
        if len(media_map) != len(set(media_ids)):
            missing = set(media_ids) - set(media_map.keys())
            raise ValueError(f"Invalid media_ids: {missing}")

        # ---------------------------------------
        # 4. Fetch existing usages
        # ---------------------------------------
        result = await self.db.execute(
            select(MediaUsage).where(
                MediaUsage.entity_type == "post",
                MediaUsage.entity_id == post_id,
                MediaUsage.field_name == "inline",
                MediaUsage.is_active.is_(True),
            )
        )
        existing_usages = result.scalars().all()

        old_map = {u.block_id: u for u in existing_usages}

        # ---------------------------------------
        # 5. New block map
        # ---------------------------------------
        new_map = {b["block_id"]: b for b in blocks}

        # ------------------------
        # 6. HANDLE REMOVED BLOCKS
        # ------------------------
        removed_blocks = set(old_map) - set(new_map)

        for block_id in removed_blocks:
            old_map[block_id].is_active = False

        # ------------------------
        # 7. HANDLE NEW BLOCKS
        # ------------------------
        new_blocks = set(new_map) - set(old_map)

        for block_id in new_blocks:
            media_id = new_map[block_id]["media_id"]

            self.db.add(
                MediaUsage(
                    media_id=media_id,
                    entity_type="post",
                    entity_id=post_id,
                    field_name="inline",
                    block_id=block_id,
                    is_active=True,
                )
            )

        # ------------------------
        # 8. HANDLE REPLACEMENTS
        # ------------------------
        common_blocks = set(new_map) & set(old_map)

        for block_id in common_blocks:
            old_usage = old_map[block_id]
            new_media_id = new_map[block_id]["media_id"]

            if new_media_id != old_usage.media_id:
                # deactivate old
                old_usage.is_active = False

                # add new mapping
                self.db.add(
                    MediaUsage(
                        media_id=new_media_id,
                        entity_type="post",
                        entity_id=post_id,
                        field_name="inline",
                        block_id=block_id,
                        is_active=True,
                    )
                )

        # ------------------------
        # 9. ACTIVATE USED MEDIA
        # ------------------------
        await self.db.execute(
            update(Media).where(Media.id.in_(media_ids)).values(status=MediaStatus.ACTIVE)
        )

    def _trim_slug(self, slug: str, max_length: int) -> str:
        if len(slug) <= max_length:
            return slug.rstrip("-")

        trimmed = slug[:max_length]

        last_dash = trimmed.rfind("-")

        if last_dash == -1:
            return trimmed.rstrip("-")

        return trimmed[:last_dash].rstrip("-")

    async def _get_unique_slug(self, title: str) -> str:
        MAX_LENGTH = 80
        SUFFIX_LENGTH = 8

        # 1. Use your existing slugify
        base_slug = slugify(title)

        # 2. Fallback if empty
        if not base_slug:
            base_slug = "post"

        # 3. Intelligent trimming (instead of [:80])
        base_slug = self._trim_slug(base_slug, MAX_LENGTH)

        # 4. Check clean slug
        query = select(Post).filter_by(slug=base_slug)
        existing_post = (await self.db.execute(query)).scalar_one_or_none()

        if not existing_post:
            return base_slug

        logger.info("slug_collision_detected", base_slug=base_slug)

        # 5. Collision handling
        while True:
            suffix = uuid.uuid4().hex[:SUFFIX_LENGTH]

            # ensure final length stays within limit
            allowed_base_length = MAX_LENGTH - (SUFFIX_LENGTH + 1)

            trimmed_base = self._trim_slug(base_slug, allowed_base_length)

            candidate_slug = f"{trimmed_base}-{suffix}"

            query = select(Post).filter_by(slug=candidate_slug)
            existing_post = (await self.db.execute(query)).scalar_one_or_none()

            if not existing_post:
                logger.info("unique_slug_generated", slug=candidate_slug)
                return candidate_slug
