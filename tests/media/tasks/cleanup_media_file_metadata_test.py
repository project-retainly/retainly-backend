from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.media.models import Media
from app.media.tasks import cleanup_deleted_media_file_metadata_test
from app.media.utils import MediaStatus
from app.users.models import User
from tests.media.factories import MediaFactory


class TestCleanupDeletedMediaFileMetadata:
    async def test_cleanup_deletes_deleted_media(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        await MediaFactory.create_batch(
            2, user=user, status=MediaStatus.DELETED
        )

        count = await cleanup_deleted_media_file_metadata_test(db_session)

        assert count == 2
        result = await db_session.execute(select(Media))
        assert result.scalars().all() == []

    async def test_cleanup_preserves_active_media(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        await MediaFactory.create_batch(3, user=user, status=MediaStatus.ACTIVE)

        count = await cleanup_deleted_media_file_metadata_test(db_session)

        assert count == 0
        result = await db_session.execute(select(Media))
        assert len(result.scalars().all()) == 3

    async def test_cleanup_mixed_statuses(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        await MediaFactory.create_batch(
            2, user=user, status=MediaStatus.DELETED
        )
        await MediaFactory.create_batch(2, user=user, status=MediaStatus.ACTIVE)

        count = await cleanup_deleted_media_file_metadata_test(db_session)

        assert count == 2
        result = await db_session.execute(select(Media))
        remaining = result.scalars().all()
        assert len(remaining) == 2
        assert all(m.status != MediaStatus.DELETED for m in remaining)

    async def test_cleanup_returns_zero_when_no_deleted_media(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        await MediaFactory.create_batch(2, user=user, status=MediaStatus.ACTIVE)

        count = await cleanup_deleted_media_file_metadata_test(db_session)

        assert count == 0

    async def test_cleanup_returns_zero_when_no_media_exist(
        self, db_session: AsyncSession
    ):
        count = await cleanup_deleted_media_file_metadata_test(db_session)

        assert count == 0

    async def test_cleanup_returns_correct_count(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        await MediaFactory.create_batch(
            7, user=user, status=MediaStatus.DELETED
        )

        count = await cleanup_deleted_media_file_metadata_test(db_session)

        assert count == 7

    async def test_cleanup_return_type(self, db_session: AsyncSession):
        count = await cleanup_deleted_media_file_metadata_test(db_session)

        assert isinstance(count, int)

    async def test_cleanup_is_idempotent(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        await MediaFactory.create(user=user, status=MediaStatus.DELETED)

        first_count = await cleanup_deleted_media_file_metadata_test(db_session)
        second_count = await cleanup_deleted_media_file_metadata_test(
            db_session
        )

        assert first_count == 1
        assert second_count == 0

    async def test_cleanup_multiple_executions(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()

        await MediaFactory.create(user=user, status=MediaStatus.DELETED)
        count1 = await cleanup_deleted_media_file_metadata_test(db_session)
        assert count1 == 1

        await MediaFactory.create_batch(
            3, user=user, status=MediaStatus.DELETED
        )
        count2 = await cleanup_deleted_media_file_metadata_test(db_session)
        assert count2 == 3

        count3 = await cleanup_deleted_media_file_metadata_test(db_session)
        assert count3 == 0

    async def test_cleanup_commits_transaction(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        await MediaFactory.create(user=user, status=MediaStatus.DELETED)

        await cleanup_deleted_media_file_metadata_test(db_session)

        result = await db_session.execute(
            select(Media).where(Media.status == MediaStatus.DELETED)
        )
        assert result.scalars().all() == []

    async def test_cleanup_media_from_multiple_users(
        self, db_session: AsyncSession, create_user
    ):
        user1 = await create_user()
        user2 = await create_user()
        user3 = await create_user()

        await MediaFactory.create(user=user1, status=MediaStatus.DELETED)
        await MediaFactory.create(user=user2, status=MediaStatus.DELETED)
        await MediaFactory.create(user=user3, status=MediaStatus.ACTIVE)

        count = await cleanup_deleted_media_file_metadata_test(db_session)

        assert count == 2
        result = await db_session.execute(select(Media))
        remaining = result.scalars().all()
        assert len(remaining) == 1
        assert remaining[0].status != MediaStatus.DELETED

    async def test_cleanup_large_number_of_deleted_media(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        await MediaFactory.create_batch(
            100, user=user, status=MediaStatus.DELETED
        )

        count = await cleanup_deleted_media_file_metadata_test(db_session)

        assert count == 100
        result = await db_session.execute(select(Media))
        assert result.scalars().all() == []

    async def test_cleanup_does_not_affect_other_tables(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        await MediaFactory.create(user=user, status=MediaStatus.DELETED)

        await cleanup_deleted_media_file_metadata_test(db_session)

        result = await db_session.execute(
            select(User).where(User.id == user.id)
        )
        assert result.scalar_one_or_none() is not None

    async def test_cleanup_only_deleted_status_targeted(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        await MediaFactory.create(user=user, status=MediaStatus.DELETED)
        await MediaFactory.create(user=user, status=MediaStatus.ACTIVE)

        count = await cleanup_deleted_media_file_metadata_test(db_session)

        assert count == 1
        result = await db_session.execute(select(Media))
        statuses = {m.status for m in result.scalars().all()}
        assert MediaStatus.DELETED not in statuses
        assert MediaStatus.ACTIVE in statuses

    async def test_cleanup_works_across_media_types(
        self, db_session: AsyncSession, create_user
    ):
        """Ensures cleanup targets deleted status regardless of file type."""
        user = await create_user()
        await MediaFactory.create(
            user=user, status=MediaStatus.DELETED, is_image=True
        )
        await MediaFactory.create(
            user=user, status=MediaStatus.DELETED, is_pdf=True
        )
        await MediaFactory.create(
            user=user, status=MediaStatus.DELETED, is_text=True
        )
        await MediaFactory.create(
            user=user, status=MediaStatus.ACTIVE, is_image=True
        )

        count = await cleanup_deleted_media_file_metadata_test(db_session)

        assert count == 3
        result = await db_session.execute(select(Media))
        remaining = result.scalars().all()
        assert len(remaining) == 1
        assert remaining[0].status == MediaStatus.ACTIVE
