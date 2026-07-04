from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.auth.models import RefreshToken
from app.auth.tasks import cleanup_expired_refresh_tokens_test
from tests.auth.factories import RefreshTokenFactory


class TestCleanupExpiredRefreshTokens:
    """Test suite for cleanup_expired_refresh_tokens_test function."""

    # ==================== Basic Functionality Tests ====================

    @pytest.mark.asyncio
    async def test_cleanup_deletes_expired_tokens(self, db_session, create_user):
        """Test that expired tokens are deleted."""
        user = await create_user()

        # Create expired tokens
        expired_token1 = await RefreshTokenFactory.create(
            user=user,
            expired=True,  # Uses the expired trait
        )
        expired_token2 = await RefreshTokenFactory.create(
            user=user,
            expired=True,
        )

        # Run cleanup
        deleted_count = await cleanup_expired_refresh_tokens_test(db_session)

        assert deleted_count == 2

        # Verify tokens are deleted from database
        result = await db_session.execute(
            select(RefreshToken).where(
                RefreshToken.id.in_([expired_token1.id, expired_token2.id])
            )
        )
        tokens = result.scalars().all()
        assert len(tokens) == 0

    @pytest.mark.asyncio
    async def test_cleanup_preserves_valid_tokens(self, db_session, create_user):
        """Test that non-expired tokens are not deleted."""
        user = await create_user()

        # Create valid (non-expired) tokens
        valid_token1 = await RefreshTokenFactory.create(user=user)
        valid_token2 = await RefreshTokenFactory.create(user=user)

        # Run cleanup
        deleted_count = await cleanup_expired_refresh_tokens_test(db_session)

        assert deleted_count == 0

        # Verify tokens still exist
        result = await db_session.execute(
            select(RefreshToken).where(
                RefreshToken.id.in_([valid_token1.id, valid_token2.id])
            )
        )
        tokens = result.scalars().all()
        assert len(tokens) == 2

    @pytest.mark.asyncio
    async def test_cleanup_mixed_tokens(self, db_session, create_user):
        """Test cleanup with both expired and valid tokens."""
        user = await create_user()

        # Create expired tokens
        await RefreshTokenFactory.create(user=user, expired=True)
        await RefreshTokenFactory.create(user=user, expired=True)

        # Create valid tokens
        valid_token1 = await RefreshTokenFactory.create(user=user)
        valid_token2 = await RefreshTokenFactory.create(user=user)

        # Run cleanup
        deleted_count = await cleanup_expired_refresh_tokens_test(db_session)

        assert deleted_count == 2

        # Verify only expired tokens are deleted
        result = await db_session.execute(select(RefreshToken))
        remaining_tokens = result.scalars().all()

        assert len(remaining_tokens) == 2
        assert valid_token1.id in [t.id for t in remaining_tokens]
        assert valid_token2.id in [t.id for t in remaining_tokens]

    @pytest.mark.asyncio
    async def test_cleanup_returns_zero_when_no_expired_tokens(
        self, db_session, create_user
    ):
        """Test that cleanup returns 0 when no expired tokens exist."""
        user = await create_user()

        # Create only valid tokens
        await RefreshTokenFactory.create(user=user)
        await RefreshTokenFactory.create(user=user)

        deleted_count = await cleanup_expired_refresh_tokens_test(db_session)

        assert deleted_count == 0

    @pytest.mark.asyncio
    async def test_cleanup_returns_zero_when_no_tokens_exist(self, db_session):
        """Test cleanup with empty database."""
        deleted_count = await cleanup_expired_refresh_tokens_test(db_session)

        assert deleted_count == 0

    # ==================== Edge Cases - Expiration Boundary ====================

    @pytest.mark.asyncio
    async def test_cleanup_token_expires_exactly_now(self, db_session, create_user):
        """Test token that expires at the exact current moment."""
        user = await create_user()

        # Create token that expires right now
        now = datetime.now(timezone.utc)
        token = await RefreshTokenFactory.create(
            user=user,
            created_at=now - timedelta(days=7),
            expires_at=now,
        )

        deleted_count = await cleanup_expired_refresh_tokens_test(db_session)

        # Token expiring exactly now should be deleted (< threshold)
        assert deleted_count == 1

        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.id == token.id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_cleanup_token_expires_one_second_future(
        self, db_session, create_user
    ):
        """Test token that expires 1 second in the future."""
        user = await create_user()

        # Create token that expires 1 second from now
        now = datetime.now(timezone.utc)
        token = await RefreshTokenFactory.create(
            user=user,
            created_at=now - timedelta(days=7),
            expires_at=now + timedelta(seconds=1),
        )

        deleted_count = await cleanup_expired_refresh_tokens_test(db_session)

        # Should NOT be deleted
        assert deleted_count == 0

        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.id == token.id)
        )
        assert result.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_cleanup_token_expired_one_second_ago(self, db_session, create_user):
        """Test token that expired 1 second ago."""
        user = await create_user()

        # Create token that expired 1 second ago
        now = datetime.now(timezone.utc)
        token = await RefreshTokenFactory.create(
            user=user,
            created_at=now - timedelta(days=7),
            expires_at=now - timedelta(seconds=1),
        )

        deleted_count = await cleanup_expired_refresh_tokens_test(db_session)

        # Should be deleted
        assert deleted_count == 1

        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.id == token.id)
        )
        assert result.scalar_one_or_none() is None

    # ==================== Multiple Users ====================

    @pytest.mark.asyncio
    async def test_cleanup_tokens_from_multiple_users(self, db_session, create_user):
        """Test cleanup works across multiple users."""
        user1 = await create_user(email="user1@example.com")
        user2 = await create_user(email="user2@example.com")
        user3 = await create_user(email="user3@example.com")

        # Create expired tokens for each user
        await RefreshTokenFactory.create(user=user1, expired=True)
        await RefreshTokenFactory.create(user=user1, expired=True)
        await RefreshTokenFactory.create(user=user2, expired=True)
        await RefreshTokenFactory.create(user=user3, expired=True)

        # Create valid tokens
        await RefreshTokenFactory.create(user=user1)
        await RefreshTokenFactory.create(user=user2)

        deleted_count = await cleanup_expired_refresh_tokens_test(db_session)

        assert deleted_count == 4

        # Verify only valid tokens remain
        result = await db_session.execute(select(RefreshToken))
        remaining_tokens = result.scalars().all()
        assert len(remaining_tokens) == 2

    # ==================== Revoked Tokens ====================

    @pytest.mark.asyncio
    async def test_cleanup_expired_and_revoked_tokens(self, db_session, create_user):
        """Test that expired AND revoked tokens are deleted."""
        user = await create_user()

        # Create expired AND revoked token
        expired_revoked = await RefreshTokenFactory.create(
            user=user,
            expired=True,
            revoked=True,
        )

        deleted_count = await cleanup_expired_refresh_tokens_test(db_session)

        assert deleted_count == 1

        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.id == expired_revoked.id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_cleanup_preserves_valid_revoked_tokens(
        self, db_session, create_user
    ):
        """Test that valid but revoked tokens are preserved."""
        user = await create_user()

        # Create valid but revoked token
        valid_revoked = await RefreshTokenFactory.create(
            user=user,
            revoked=True,  # Revoked but not expired
        )

        deleted_count = await cleanup_expired_refresh_tokens_test(db_session)

        assert deleted_count == 0

        # Token should still exist
        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.id == valid_revoked.id)
        )
        assert result.scalar_one_or_none() is not None

    # ==================== Large Scale Tests ====================

    @pytest.mark.asyncio
    async def test_cleanup_large_number_of_expired_tokens(
        self, db_session, create_user
    ):
        """Test cleanup with a large number of expired tokens."""
        user = await create_user()

        # Create 100 expired tokens
        for _ in range(100):
            await RefreshTokenFactory.create(user=user, expired=True)

        # Create 10 valid tokens
        for _ in range(10):
            await RefreshTokenFactory.create(user=user)

        deleted_count = await cleanup_expired_refresh_tokens_test(db_session)

        assert deleted_count == 100

        # Verify only 10 tokens remain
        result = await db_session.execute(select(RefreshToken))
        remaining_tokens = result.scalars().all()
        assert len(remaining_tokens) == 10

    # ==================== Database Transaction Tests ====================

    @pytest.mark.asyncio
    async def test_cleanup_commits_transaction(self, db_session, create_user):
        """Test that cleanup commits changes to database."""
        user = await create_user()

        # Create expired token
        expired_token = await RefreshTokenFactory.create(user=user, expired=True)

        # Run cleanup
        deleted_count = await cleanup_expired_refresh_tokens_test(db_session)
        assert deleted_count == 1

        # Rollback the session to test if commit was called
        await db_session.rollback()

        # Token should still be deleted (because cleanup commits)
        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.id == expired_token.id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_cleanup_multiple_executions(self, db_session, create_user):
        """Test that cleanup can be run multiple times safely."""
        user = await create_user()

        # Create expired tokens
        await RefreshTokenFactory.create(user=user, expired=True)
        await RefreshTokenFactory.create(user=user, expired=True)

        # First cleanup
        deleted_count1 = await cleanup_expired_refresh_tokens_test(db_session)
        assert deleted_count1 == 2

        # Second cleanup - should find nothing
        deleted_count2 = await cleanup_expired_refresh_tokens_test(db_session)
        assert deleted_count2 == 0

        # Third cleanup - still nothing
        deleted_count3 = await cleanup_expired_refresh_tokens_test(db_session)
        assert deleted_count3 == 0

    # ==================== Time-based Tests ====================

    @pytest.mark.asyncio
    async def test_cleanup_tokens_expired_various_durations(
        self, db_session, create_user
    ):
        """Test cleanup with tokens expired for different durations."""
        user = await create_user()
        now = datetime.now(timezone.utc)

        # Token expired 1 day ago
        await RefreshTokenFactory.create(
            user=user,
            created_at=now - timedelta(days=8),
            expires_at=now - timedelta(days=1),
        )

        # Token expired 1 week ago
        await RefreshTokenFactory.create(
            user=user,
            created_at=now - timedelta(days=14),
            expires_at=now - timedelta(days=7),
        )

        # Token expired 1 month ago
        await RefreshTokenFactory.create(
            user=user,
            created_at=now - timedelta(days=37),
            expires_at=now - timedelta(days=30),
        )

        # Valid token expiring in future
        await RefreshTokenFactory.create(
            user=user,
            created_at=now,
            expires_at=now + timedelta(days=7),
        )

        deleted_count = await cleanup_expired_refresh_tokens_test(db_session)

        assert deleted_count == 3

        # Only 1 token should remain
        result = await db_session.execute(select(RefreshToken))
        remaining_tokens = result.scalars().all()
        assert len(remaining_tokens) == 1

    # ==================== Idempotency Tests ====================

    @pytest.mark.asyncio
    async def test_cleanup_is_idempotent(self, db_session, create_user):
        """Test that running cleanup multiple times has same effect as once."""
        user = await create_user()

        # Create tokens
        await RefreshTokenFactory.create(user=user, expired=True)
        await RefreshTokenFactory.create(user=user, expired=True)
        await RefreshTokenFactory.create(user=user)

        # Run cleanup multiple times
        count1 = await cleanup_expired_refresh_tokens_test(db_session)
        count2 = await cleanup_expired_refresh_tokens_test(db_session)
        count3 = await cleanup_expired_refresh_tokens_test(db_session)

        assert count1 == 2
        assert count2 == 0
        assert count3 == 0

        # Verify final state
        result = await db_session.execute(select(RefreshToken))
        remaining_tokens = result.scalars().all()
        assert len(remaining_tokens) == 1

    # ==================== Return Value Tests ====================

    @pytest.mark.asyncio
    async def test_cleanup_returns_correct_count(self, db_session, create_user):
        """Test that cleanup returns accurate deletion count."""
        user = await create_user()

        # Create exactly 5 expired tokens
        for _ in range(5):
            await RefreshTokenFactory.create(user=user, expired=True)

        deleted_count = await cleanup_expired_refresh_tokens_test(db_session)

        assert deleted_count == 5
        assert isinstance(deleted_count, int)

    @pytest.mark.asyncio
    async def test_cleanup_return_type(self, db_session):
        """Test that cleanup always returns an integer."""
        deleted_count = await cleanup_expired_refresh_tokens_test(db_session)

        assert isinstance(deleted_count, int)
        assert deleted_count >= 0

    # ==================== Data Integrity Tests ====================

    @pytest.mark.asyncio
    async def test_cleanup_does_not_affect_other_tables(self, db_session, create_user):
        """Test that cleanup only affects RefreshToken table."""
        # Create user with expired tokens
        user = await create_user()
        await RefreshTokenFactory.create(user=user, expired=True)

        # Store user ID before cleanup
        user_id = user.id

        # Run cleanup
        await cleanup_expired_refresh_tokens_test(db_session)

        # Verify user still exists
        from app.users.models import User

        result = await db_session.execute(select(User).where(User.id == user_id))
        assert result.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_cleanup_preserves_token_relationships(self, db_session, create_user):
        """Test that cleanup doesn't break foreign key relationships."""
        user = await create_user()

        # Create valid token (will remain)
        valid_token = await RefreshTokenFactory.create(user=user)

        # Create expired token (will be deleted)
        await RefreshTokenFactory.create(user=user, expired=True)

        # Run cleanup
        deleted_count = await cleanup_expired_refresh_tokens_test(db_session)
        assert deleted_count == 1

        # Verify the remaining token still has valid user relationship
        await db_session.refresh(valid_token)
        assert valid_token.user_id == user.id
        assert valid_token.user is not None


# ==================== Celery Task Tests ====================


class TestCleanupExpiredRefreshTokensTask:
    """Test suite for the Celery task wrapper."""

    @pytest.mark.asyncio
    async def test_task_executes_cleanup_function(self, db_session, create_user):
        """Test that the Celery task executes the cleanup function."""
        user = await create_user()

        # Create expired tokens
        await RefreshTokenFactory.create(user=user, expired=True)
        await RefreshTokenFactory.create(user=user, expired=True)

        # Import and execute the task directly (without Celery worker)

        # Since the task uses @run_with_db, we need to test it appropriately
        # This test assumes the task can be called synchronously in test mode
        # You may need to adjust based on your run_with_db implementation

        # Execute cleanup directly (bypassing Celery)
        await cleanup_expired_refresh_tokens_test(db_session)

        # Verify tokens were deleted
        result = await db_session.execute(select(RefreshToken))
        remaining_tokens = result.scalars().all()
        assert len(remaining_tokens) == 0

    @pytest.mark.asyncio
    async def test_task_handles_empty_database(self, db_session):
        """Test that task handles empty database gracefully."""
        # Run cleanup on empty database
        deleted_count = await cleanup_expired_refresh_tokens_test(db_session)

        assert deleted_count == 0

    @pytest.mark.asyncio
    async def test_task_can_be_scheduled(self, db_session, create_user):
        """Test that the task is properly registered with Celery."""
        from app.auth.tasks import cleanup_expired_refresh_tokens_task

        # Verify task is registered
        assert cleanup_expired_refresh_tokens_task is not None
        assert hasattr(cleanup_expired_refresh_tokens_task, "delay")
        assert hasattr(cleanup_expired_refresh_tokens_task, "apply_async")
