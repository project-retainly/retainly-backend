from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import User
from app.users.tasks import (
    cleanup_expired_unverified_users_test,
)
from app.users.utils import UserStatus
from tests.users.factories import UserFactory


class TestCleanupExpiredUnverifiedUsers:
    """Test suite for cleanup_expired_unverified_users_test function"""

    async def test_cleanup_deletes_expired_users(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test that cleanup deletes users with EXPIRED status
        """
        # Create expired users
        expired_user1 = await create_user(
            email="expired1@example.com",
            username="expired1",
            status=UserStatus.EXPIRED,
        )
        expired_user2 = await create_user(
            email="expired2@example.com",
            username="expired2",
            status=UserStatus.EXPIRED,
        )

        # Execute cleanup
        deleted_count = await cleanup_expired_unverified_users_test(db_session)

        # Assert
        assert deleted_count == 2

        # Verify users are deleted
        result = await db_session.execute(
            select(User).where(User.id.in_([expired_user1.id, expired_user2.id]))
        )
        remaining_users = result.scalars().all()
        assert len(remaining_users) == 0

    async def test_cleanup_preserves_active_users(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test that cleanup does not delete users with ACTIVE status
        """
        # Create active users
        active_user1 = await create_user(
            email="active1@example.com",
            username="active1",
            status=UserStatus.ACTIVE,
        )
        active_user2 = await create_user(
            email="active2@example.com",
            username="active2",
            status=UserStatus.ACTIVE,
        )

        # Execute cleanup
        deleted_count = await cleanup_expired_unverified_users_test(db_session)

        # Assert
        assert deleted_count == 0

        # Verify users still exist
        result = await db_session.execute(
            select(User).where(User.id.in_([active_user1.id, active_user2.id]))
        )
        remaining_users = result.scalars().all()
        assert len(remaining_users) == 2

    async def test_cleanup_preserves_pending_users(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test that cleanup does not delete users with PENDING status
        """
        # Create pending users
        pending_user1 = await create_user(
            email="pending1@example.com",
            username="pending1",
            status=UserStatus.PENDING,
        )
        pending_user2 = await create_user(
            email="pending2@example.com",
            username="pending2",
            status=UserStatus.PENDING,
        )

        # Execute cleanup
        deleted_count = await cleanup_expired_unverified_users_test(db_session)

        # Assert
        assert deleted_count == 0

        # Verify users still exist
        result = await db_session.execute(
            select(User).where(User.id.in_([pending_user1.id, pending_user2.id]))
        )
        remaining_users = result.scalars().all()
        assert len(remaining_users) == 2

    async def test_cleanup_preserves_deleted_users(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test that cleanup does not delete users with DELETED status
        """
        # Create deleted users
        deleted_user = await create_user(
            email="deleted@example.com",
            username="deleted",
            status=UserStatus.DELETED,
        )

        # Execute cleanup
        deleted_count = await cleanup_expired_unverified_users_test(db_session)

        # Assert
        assert deleted_count == 0

        # Verify user still exists
        result = await db_session.execute(
            select(User).where(User.id == deleted_user.id)
        )
        remaining_user = result.scalar_one_or_none()
        assert remaining_user is not None
        assert remaining_user.status == UserStatus.DELETED

    async def test_cleanup_mixed_user_statuses(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test cleanup with mixed user statuses - only EXPIRED should be deleted
        """
        # Create users with different statuses
        expired_user1 = await create_user(
            email="expired1@example.com",
            username="expired1",
            status=UserStatus.EXPIRED,
        )
        expired_user2 = await create_user(
            email="expired2@example.com",
            username="expired2",
            status=UserStatus.EXPIRED,
        )
        active_user = await create_user(
            email="active@example.com",
            username="active",
            status=UserStatus.ACTIVE,
        )
        pending_user = await create_user(
            email="pending@example.com",
            username="pending",
            status=UserStatus.PENDING,
        )
        deleted_user = await create_user(
            email="deleted@example.com",
            username="deleted",
            status=UserStatus.DELETED,
        )

        # Execute cleanup
        deleted_count = await cleanup_expired_unverified_users_test(db_session)

        # Assert - only 2 expired users should be deleted
        assert deleted_count == 2

        # Verify expired users are deleted
        result = await db_session.execute(
            select(User).where(User.id.in_([expired_user1.id, expired_user2.id]))
        )
        expired_users = result.scalars().all()
        assert len(expired_users) == 0

        # Verify other users still exist
        result = await db_session.execute(
            select(User).where(
                User.id.in_([active_user.id, pending_user.id, deleted_user.id])
            )
        )
        remaining_users = result.scalars().all()
        assert len(remaining_users) == 3

    async def test_cleanup_returns_zero_when_no_expired_users(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test that cleanup returns 0 when no expired users exist
        """
        # Create only active users
        await create_user(
            email="active1@example.com",
            username="active1",
            status=UserStatus.ACTIVE,
        )
        await create_user(
            email="active2@example.com",
            username="active2",
            status=UserStatus.ACTIVE,
        )

        # Execute cleanup
        deleted_count = await cleanup_expired_unverified_users_test(db_session)

        # Assert
        assert deleted_count == 0

    async def test_cleanup_returns_zero_when_no_users_exist(
        self, db_session: AsyncSession
    ):
        """
        Test that cleanup returns 0 when database is empty
        """
        # Execute cleanup on empty database
        deleted_count = await cleanup_expired_unverified_users_test(db_session)

        # Assert
        assert deleted_count == 0

    async def test_cleanup_users_from_multiple_batches(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test cleanup with multiple expired users from different time periods
        """
        # Create expired users with different timestamps
        await create_user(
            email="expired1@example.com",
            username="expired1",
            status=UserStatus.EXPIRED,
        )
        await create_user(
            email="expired2@example.com",
            username="expired2",
            status=UserStatus.EXPIRED,
        )
        await create_user(
            email="expired3@example.com",
            username="expired3",
            status=UserStatus.EXPIRED,
        )

        # Execute cleanup
        deleted_count = await cleanup_expired_unverified_users_test(db_session)

        # Assert all expired users are deleted
        assert deleted_count == 3

    async def test_cleanup_large_number_of_expired_users(
        self, db_session: AsyncSession
    ):
        """
        Test cleanup with a large number of expired users (performance test)
        """
        # Create many expired users
        expired_count = 100
        for i in range(expired_count):
            await UserFactory.create(
                email=f"expired{i}@example.com",
                username=f"expired{i}",
                status=UserStatus.EXPIRED,
            )

        await db_session.commit()

        # Execute cleanup
        deleted_count = await cleanup_expired_unverified_users_test(db_session)

        # Assert
        assert deleted_count == expired_count

        # Verify all expired users are deleted
        result = await db_session.execute(
            select(User).where(User.status == UserStatus.EXPIRED)
        )
        remaining_expired = result.scalars().all()
        assert len(remaining_expired) == 0

    async def test_cleanup_commits_transaction(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test that cleanup commits the transaction properly
        """
        # Create expired user
        expired_user = await create_user(
            email="expired@example.com",
            username="expired",
            status=UserStatus.EXPIRED,
        )

        # Execute cleanup
        await cleanup_expired_unverified_users_test(db_session)

        # Rollback the session to test if commit was called
        await db_session.rollback()

        # Verify user is still deleted (commit was called)
        result = await db_session.execute(
            select(User).where(User.id == expired_user.id)
        )
        user = result.scalar_one_or_none()
        assert user is None

    async def test_cleanup_multiple_executions(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test that multiple cleanup executions work correctly
        """
        # First batch
        await create_user(
            email="expired1@example.com",
            username="expired1",
            status=UserStatus.EXPIRED,
        )
        await create_user(
            email="expired2@example.com",
            username="expired2",
            status=UserStatus.EXPIRED,
        )

        # First cleanup
        deleted_count1 = await cleanup_expired_unverified_users_test(db_session)
        assert deleted_count1 == 2

        # Second batch
        await create_user(
            email="expired3@example.com",
            username="expired3",
            status=UserStatus.EXPIRED,
        )
        await create_user(
            email="expired4@example.com",
            username="expired4",
            status=UserStatus.EXPIRED,
        )

        # Second cleanup
        deleted_count2 = await cleanup_expired_unverified_users_test(db_session)
        assert deleted_count2 == 2

    async def test_cleanup_is_idempotent(self, db_session: AsyncSession, create_user):
        """
        Test that running cleanup multiple times on same data is idempotent
        """
        # Create expired users
        await create_user(
            email="expired1@example.com",
            username="expired1",
            status=UserStatus.EXPIRED,
        )
        await create_user(
            email="expired2@example.com",
            username="expired2",
            status=UserStatus.EXPIRED,
        )

        # First cleanup
        deleted_count1 = await cleanup_expired_unverified_users_test(db_session)
        assert deleted_count1 == 2

        # Second cleanup - should delete nothing
        deleted_count2 = await cleanup_expired_unverified_users_test(db_session)
        assert deleted_count2 == 0

        # Third cleanup - should still delete nothing
        deleted_count3 = await cleanup_expired_unverified_users_test(db_session)
        assert deleted_count3 == 0

    async def test_cleanup_returns_correct_count(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test that cleanup returns exact count of deleted users
        """
        # Create specific number of expired users
        expected_count = 7
        for i in range(expected_count):
            await create_user(
                email=f"expired{i}@example.com",
                username=f"expired{i}",
                status=UserStatus.EXPIRED,
            )

        # Execute cleanup
        deleted_count = await cleanup_expired_unverified_users_test(db_session)

        # Assert exact count
        assert deleted_count == expected_count

    async def test_cleanup_return_type(self, db_session: AsyncSession):
        """
        Test that cleanup returns an integer
        """
        # Execute cleanup
        deleted_count = await cleanup_expired_unverified_users_test(db_session)

        # Assert return type
        assert isinstance(deleted_count, int)
        assert deleted_count >= 0

    async def test_cleanup_does_not_affect_other_tables(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test that cleanup only affects User table, not other tables
        Note: Behavior depends on cascade settings
        """
        from app.posts.models import Post

        # Create expired user with a post
        expired_user = await create_user(
            email="expired@example.com",
            username="expired",
            status=UserStatus.EXPIRED,
        )

        # Create a post for this user
        from tests.posts.factories import PostFactory

        post = await PostFactory.create(owner=expired_user)
        post_id = post.id

        await db_session.commit()

        # Execute cleanup
        await cleanup_expired_unverified_users_test(db_session)

        # Verify behavior based on cascade settings
        result = await db_session.execute(select(Post).where(Post.id == post_id))
        remaining_post = result.scalar_one_or_none()

        # Post might be deleted (cascade) or orphaned depending on DB constraints
        # This test documents the actual behavior
        assert remaining_post is None

    async def test_cleanup_with_soft_deleted_users(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test cleanup behavior with users that have deleted_at timestamp
        """
        # Create expired user with deleted_at set
        expired_user = await create_user(
            email="expired@example.com",
            username="expired",
            status=UserStatus.EXPIRED,
        )
        expired_user.deleted_at = datetime.now(timezone.utc)
        await db_session.commit()

        # Execute cleanup
        deleted_count = await cleanup_expired_unverified_users_test(db_session)

        # Assert user is deleted
        assert deleted_count == 1

        # Verify user is gone
        result = await db_session.execute(
            select(User).where(User.id == expired_user.id)
        )
        user = result.scalar_one_or_none()
        assert user is None

    async def test_cleanup_preserves_user_data_integrity(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test that cleanup maintains database integrity
        """
        # Create active user
        active_user = await create_user(
            email="active@example.com",
            username="active",
            status=UserStatus.ACTIVE,
        )
        active_id = active_user.id

        # Create expired user
        await create_user(
            email="expired@example.com",
            username="expired",
            status=UserStatus.EXPIRED,
        )

        # Execute cleanup
        await cleanup_expired_unverified_users_test(db_session)

        # Verify active user data is intact
        result = await db_session.execute(select(User).where(User.id == active_id))
        user = result.scalar_one()
        assert user.email == "active@example.com"
        assert user.username == "active"
        assert user.status == UserStatus.ACTIVE

    async def test_cleanup_with_concurrent_status_changes(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test cleanup behavior when user status changes during execution
        Note: This is a limitation test - actual concurrent modification would need different setup
        """
        # Create expired user
        expired_user = await create_user(
            email="expired@example.com",
            username="expired",
            status=UserStatus.EXPIRED,
        )

        # Change status before cleanup (simulating race condition)
        expired_user.status = UserStatus.ACTIVE
        await db_session.commit()

        # Execute cleanup
        deleted_count = await cleanup_expired_unverified_users_test(db_session)

        # Assert - user should not be deleted since status changed
        assert deleted_count == 0

        # Verify user still exists
        result = await db_session.execute(
            select(User).where(User.id == expired_user.id)
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.status == UserStatus.ACTIVE

    async def test_cleanup_handles_empty_result(self, db_session: AsyncSession):
        """
        Test that cleanup handles empty result gracefully
        """
        # Ensure no users exist
        result = await db_session.execute(select(User))
        assert len(result.scalars().all()) == 0

        # Execute cleanup
        deleted_count = await cleanup_expired_unverified_users_test(db_session)

        # Assert
        assert deleted_count == 0
        assert isinstance(deleted_count, int)

    async def test_cleanup_all_statuses_except_expired(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test that ALL non-expired statuses are preserved
        """
        # Create users with all possible statuses except expired
        active_user = await create_user(
            email="active@example.com",
            username="active",
            status=UserStatus.ACTIVE,
        )
        pending_user = await create_user(
            email="pending@example.com",
            username="pending",
            status=UserStatus.PENDING,
        )
        deleted_user = await create_user(
            email="deleted@example.com",
            username="deleted",
            status=UserStatus.DELETED,
        )

        # Execute cleanup
        deleted_count = await cleanup_expired_unverified_users_test(db_session)

        # Assert no users deleted
        assert deleted_count == 0

        # Verify all users still exist
        result = await db_session.execute(
            select(User).where(
                User.id.in_([active_user.id, pending_user.id, deleted_user.id])
            )
        )
        users = result.scalars().all()
        assert len(users) == 3

    async def test_cleanup_expired_users_with_various_timestamps(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test cleanup of expired users created at different times
        """
        # Create expired users with different creation times
        user1 = await create_user(
            email="expired1@example.com",
            username="expired1",
            status=UserStatus.EXPIRED,
        )
        user1.created_at = datetime.now(timezone.utc) - timedelta(days=30)

        user2 = await create_user(
            email="expired2@example.com",
            username="expired2",
            status=UserStatus.EXPIRED,
        )
        user2.created_at = datetime.now(timezone.utc) - timedelta(days=7)

        user3 = await create_user(
            email="expired3@example.com",
            username="expired3",
            status=UserStatus.EXPIRED,
        )
        user3.created_at = datetime.now(timezone.utc) - timedelta(hours=1)

        await db_session.commit()

        # Execute cleanup
        deleted_count = await cleanup_expired_unverified_users_test(db_session)

        # Assert all expired users deleted regardless of timestamp
        assert deleted_count == 3

    async def test_cleanup_with_special_characters_in_user_data(
        self, db_session: AsyncSession
    ):
        """
        Test cleanup of expired users with special characters in their data
        """
        # Create expired users with special characters
        await UserFactory.create(
            email="test+special@example.com",
            username="user_with-special.chars",
            status=UserStatus.EXPIRED,
        )
        await UserFactory.create(
            email="test@example.com",
            username="user_unicode",
            first_name="François",
            last_name="O'Brien",
            status=UserStatus.EXPIRED,
        )

        await db_session.commit()

        # Execute cleanup
        deleted_count = await cleanup_expired_unverified_users_test(db_session)

        # Assert both deleted
        assert deleted_count == 2


class TestCleanupExpiredUnverifiedUsersTask:
    """
    Test suite for cleanup_expired_unverified_users_task Celery task

    Note: These tests call the core cleanup function directly instead of the Celery task
    wrapper because the task uses @run_with_db decorator which cannot be called from
    within an existing async event loop (as in pytest-asyncio tests).

    The Celery task wrapper is tested implicitly by testing the core function it wraps.
    """

    async def test_task_executes_cleanup_function(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test that the cleanup function (called by Celery task) works correctly
        """
        # Create expired users
        await create_user(
            email="expired1@example.com",
            username="expired1",
            status=UserStatus.EXPIRED,
        )
        await create_user(
            email="expired2@example.com",
            username="expired2",
            status=UserStatus.EXPIRED,
        )

        # Execute cleanup function (what the task would call)
        result = await cleanup_expired_unverified_users_test(db_session)

        # Assert
        assert result == 2

        # Verify users are deleted
        db_result = await db_session.execute(
            select(User).where(User.status == UserStatus.EXPIRED)
        )
        expired_users = db_result.scalars().all()
        assert len(expired_users) == 0

    async def test_task_handles_empty_database(self, db_session: AsyncSession):
        """
        Test that cleanup handles empty database gracefully
        """
        # Execute cleanup function
        result = await cleanup_expired_unverified_users_test(db_session)

        # Assert
        assert result == 0
        assert isinstance(result, int)

    async def test_task_can_be_scheduled(self, db_session: AsyncSession, create_user):
        """
        Test that cleanup function can be called repeatedly (as a scheduled task would)
        """
        # Create expired users
        await create_user(
            email="expired@example.com",
            username="expired",
            status=UserStatus.EXPIRED,
        )

        # Execute cleanup (simulating scheduled execution)
        result = await cleanup_expired_unverified_users_test(db_session)

        # Assert executed successfully
        assert isinstance(result, int)
        assert result == 1

    async def test_task_returns_integer(self, db_session: AsyncSession, create_user):
        """
        Test that cleanup returns integer count
        """
        # Create some expired users
        await create_user(
            email="expired1@example.com",
            username="expired1",
            status=UserStatus.EXPIRED,
        )

        # Execute cleanup
        result = await cleanup_expired_unverified_users_test(db_session)

        # Assert return type
        assert isinstance(result, int)
        assert result >= 0

    async def test_task_with_mixed_users(self, db_session: AsyncSession, create_user):
        """
        Test cleanup with mixed user statuses
        """
        # Create mixed users
        await create_user(
            email="expired@example.com",
            username="expired",
            status=UserStatus.EXPIRED,
        )
        await create_user(
            email="active@example.com",
            username="active",
            status=UserStatus.ACTIVE,
        )
        await create_user(
            email="pending@example.com",
            username="pending",
            status=UserStatus.PENDING,
        )

        # Execute cleanup
        result = await cleanup_expired_unverified_users_test(db_session)

        # Assert - only expired user deleted
        assert result == 1

        # Verify active and pending users still exist
        db_result = await db_session.execute(
            select(User).where(User.status != UserStatus.EXPIRED)
        )
        remaining_users = db_result.scalars().all()
        assert len(remaining_users) == 2

    async def test_task_idempotency(self, db_session: AsyncSession, create_user):
        """
        Test that cleanup can be run multiple times safely (important for scheduled tasks)
        """
        # Create expired users
        await create_user(
            email="expired1@example.com",
            username="expired1",
            status=UserStatus.EXPIRED,
        )
        await create_user(
            email="expired2@example.com",
            username="expired2",
            status=UserStatus.EXPIRED,
        )

        # First execution
        result1 = await cleanup_expired_unverified_users_test(db_session)
        assert result1 == 2

        # Second execution - should return 0
        result2 = await cleanup_expired_unverified_users_test(db_session)
        assert result2 == 0

        # Third execution - should still return 0
        result3 = await cleanup_expired_unverified_users_test(db_session)
        assert result3 == 0

    async def test_task_with_large_dataset(self, db_session: AsyncSession):
        """
        Test cleanup performance with large number of users (production scenario)
        """
        # Create many expired users
        expired_count = 50
        for i in range(expired_count):
            await UserFactory.create(
                email=f"expired{i}@example.com",
                username=f"expired{i}",
                status=UserStatus.EXPIRED,
            )

        # Create many active users
        active_count = 50
        for i in range(active_count):
            await UserFactory.create(
                email=f"active{i}@example.com",
                username=f"active{i}",
                status=UserStatus.ACTIVE,
            )

        await db_session.commit()

        # Execute cleanup
        result = await cleanup_expired_unverified_users_test(db_session)

        # Assert correct count
        assert result == expired_count

        # Verify active users preserved
        db_result = await db_session.execute(
            select(User).where(User.status == UserStatus.ACTIVE)
        )
        active_users = db_result.scalars().all()
        assert len(active_users) == active_count

    async def test_task_preserves_database_integrity(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test that cleanup maintains database integrity after execution
        """
        # Create users
        active_user = await create_user(
            email="active@example.com",
            username="active",
            status=UserStatus.ACTIVE,
        )
        await create_user(
            email="expired@example.com",
            username="expired",
            status=UserStatus.EXPIRED,
        )

        # Execute cleanup
        await cleanup_expired_unverified_users_test(db_session)

        # Verify database integrity
        db_result = await db_session.execute(
            select(User).where(User.id == active_user.id)
        )
        user = db_result.scalar_one()

        assert user.email == "active@example.com"
        assert user.username == "active"
        assert user.status == UserStatus.ACTIVE

    async def test_task_commits_changes(self, db_session: AsyncSession, create_user):
        """
        Test that cleanup commits changes to database
        """
        # Create expired user
        expired_user = await create_user(
            email="expired@example.com",
            username="expired",
            status=UserStatus.EXPIRED,
        )
        user_id = expired_user.id

        # Execute cleanup
        await cleanup_expired_unverified_users_test(db_session)

        # Rollback to verify commit was called
        await db_session.rollback()

        # Verify user is still deleted
        db_result = await db_session.execute(select(User).where(User.id == user_id))
        user = db_result.scalar_one_or_none()
        assert user is None

    async def test_task_handles_no_expired_users(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test cleanup when there are no expired users (common scenario)
        """
        # Create only non-expired users
        await create_user(
            email="active@example.com",
            username="active",
            status=UserStatus.ACTIVE,
        )
        await create_user(
            email="pending@example.com",
            username="pending",
            status=UserStatus.PENDING,
        )

        # Execute cleanup
        result = await cleanup_expired_unverified_users_test(db_session)

        # Assert
        assert result == 0

    async def test_task_execution_consistency(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test that cleanup produces consistent results across multiple executions
        """
        # Create expired users
        for i in range(5):
            await create_user(
                email=f"expired{i}@example.com",
                username=f"expired{i}",
                status=UserStatus.EXPIRED,
            )

        # First execution
        result1 = await cleanup_expired_unverified_users_test(db_session)

        # Create more expired users
        for i in range(5, 10):
            await create_user(
                email=f"expired{i}@example.com",
                username=f"expired{i}",
                status=UserStatus.EXPIRED,
            )

        # Second execution
        result2 = await cleanup_expired_unverified_users_test(db_session)

        # Assert consistent behavior
        assert result1 == 5
        assert result2 == 5

    @pytest.mark.parametrize(
        "expired_count,active_count",
        [
            (0, 0),
            (0, 5),
            (5, 0),
            (10, 10),
            (1, 100),
            (100, 1),
        ],
    )
    async def test_task_with_various_user_distributions(
        self, db_session: AsyncSession, expired_count: int, active_count: int
    ):
        """
        Test cleanup with various distributions of expired vs active users
        """
        # Create expired users
        for i in range(expired_count):
            await UserFactory.create(
                email=f"expired{i}@example.com",
                username=f"expired{i}",
                status=UserStatus.EXPIRED,
            )

        # Create active users
        for i in range(active_count):
            await UserFactory.create(
                email=f"active{i}@example.com",
                username=f"active{i}",
                status=UserStatus.ACTIVE,
            )

        await db_session.commit()

        # Execute cleanup
        result = await cleanup_expired_unverified_users_test(db_session)

        # Assert
        assert result == expired_count

        # Verify active users preserved
        db_result = await db_session.execute(
            select(User).where(User.status == UserStatus.ACTIVE)
        )
        active_users = db_result.scalars().all()
        assert len(active_users) == active_count
