from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.posts.models import Post
from app.posts.tasks import cleanup_deleted_posts_test
from app.users.models import User
from tests.posts.factories import PostFactory


class TestCleanupDeletedPosts:
    async def test_cleanup_deletes_deleted_posts(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        await PostFactory.create_batch(2, owner=user, status="deleted")

        count = await cleanup_deleted_posts_test(db_session)

        assert count == 2
        result = await db_session.execute(select(Post))
        assert len(result.scalars().all()) == 0

    async def test_cleanup_preserves_draft_posts(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        await PostFactory.create_batch(2, owner=user, status="draft")

        count = await cleanup_deleted_posts_test(db_session)

        assert count == 0
        result = await db_session.execute(select(Post))
        assert len(result.scalars().all()) == 2

    async def test_cleanup_preserves_published_posts(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        await PostFactory.create(owner=user, status="published")

        count = await cleanup_deleted_posts_test(db_session)

        assert count == 0
        result = await db_session.execute(select(Post))
        assert len(result.scalars().all()) == 1

    async def test_cleanup_mixed_statuses(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        await PostFactory.create(owner=user, status="deleted")
        await PostFactory.create(owner=user, status="deleted")
        await PostFactory.create(owner=user, status="draft")
        await PostFactory.create(owner=user, status="published")

        count = await cleanup_deleted_posts_test(db_session)

        assert count == 2
        result = await db_session.execute(select(Post))
        remaining = result.scalars().all()
        assert len(remaining) == 2
        assert all(p.status != "deleted" for p in remaining)

    async def test_cleanup_returns_zero_when_no_deleted_posts(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        await PostFactory.create(owner=user, status="draft")
        await PostFactory.create(owner=user, status="published")

        count = await cleanup_deleted_posts_test(db_session)

        assert count == 0

    async def test_cleanup_returns_zero_when_no_posts_exist(
        self, db_session: AsyncSession
    ):
        count = await cleanup_deleted_posts_test(db_session)

        assert count == 0

    async def test_cleanup_returns_correct_count(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        num_deleted = 5
        await PostFactory.create_batch(
            num_deleted, owner=user, status="deleted"
        )

        count = await cleanup_deleted_posts_test(db_session)

        assert count == num_deleted

    async def test_cleanup_return_type(self, db_session: AsyncSession):
        count = await cleanup_deleted_posts_test(db_session)

        assert isinstance(count, int)

    async def test_cleanup_posts_from_multiple_users(
        self, db_session: AsyncSession, create_user
    ):
        user1 = await create_user()
        user2 = await create_user()
        user3 = await create_user()

        await PostFactory.create(owner=user1, status="deleted")
        await PostFactory.create(owner=user2, status="deleted")
        await PostFactory.create(owner=user3, status="draft")

        count = await cleanup_deleted_posts_test(db_session)

        assert count == 2
        result = await db_session.execute(select(Post))
        remaining = result.scalars().all()
        assert len(remaining) == 1
        assert remaining[0].status != "deleted"

    async def test_cleanup_is_idempotent(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        await PostFactory.create(owner=user, status="deleted")

        first_count = await cleanup_deleted_posts_test(db_session)
        second_count = await cleanup_deleted_posts_test(db_session)

        assert first_count == 1
        assert second_count == 0

    async def test_cleanup_multiple_executions(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()

        await PostFactory.create(owner=user, status="deleted")
        count1 = await cleanup_deleted_posts_test(db_session)
        assert count1 == 1

        await PostFactory.create_batch(2, owner=user, status="deleted")
        count2 = await cleanup_deleted_posts_test(db_session)
        assert count2 == 2

        count3 = await cleanup_deleted_posts_test(db_session)
        assert count3 == 0

    async def test_cleanup_commits_transaction(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        await PostFactory.create(owner=user, status="deleted")

        await cleanup_deleted_posts_test(db_session)

        # After cleanup, a fresh query should confirm deletion persisted
        result = await db_session.execute(
            select(Post).where(Post.status == "deleted")
        )
        assert result.scalars().all() == []

    async def test_cleanup_large_number_of_deleted_posts(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        await PostFactory.create_batch(100, owner=user, status="deleted")

        count = await cleanup_deleted_posts_test(db_session)

        assert count == 100
        result = await db_session.execute(select(Post))
        assert result.scalars().all() == []

    async def test_cleanup_does_not_affect_other_tables(
        self, db_session: AsyncSession, create_user
    ):
        user = await create_user()
        await PostFactory.create(owner=user, status="deleted")

        await cleanup_deleted_posts_test(db_session)

        # The user should still exist after post cleanup
        result = await db_session.execute(
            select(User).where(User.id == user.id)
            # adjust to your actual User model import path
        )
        assert result.scalar_one_or_none() is not None

    async def test_cleanup_only_deleted_status_targeted(
        self, db_session: AsyncSession, create_user
    ):
        """
        Ensures only PostStatus.DELETED is removed,
        not other 'soft delete' patterns.
        """
        user = await create_user()
        await PostFactory.create(owner=user, status="deleted")
        await PostFactory.create(owner=user, status="draft")
        await PostFactory.create(owner=user, status="published")

        count = await cleanup_deleted_posts_test(db_session)

        assert count == 1
        result = await db_session.execute(select(Post))
        statuses = {p.status for p in result.scalars().all()}
        assert "deleted" not in statuses
        assert "draft" in statuses
        assert "published" in statuses
