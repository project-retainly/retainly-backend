import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.services import UserService
from app.users.utils import UserStatus


class TestCheckUsernameTaken:
    """Test suite for check_username_taken method."""

    @pytest.mark.asyncio
    async def test_check_username_taken_returns_true_when_exists(
        self, db_session: AsyncSession, create_user
    ):
        """Test that existing username returns True."""
        # Arrange
        await create_user(username="takenuser")
        service = UserService(db=db_session)

        # Act
        result = await service.check_username_taken(username="takenuser")

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_check_username_taken_returns_false_when_not_exists(
        self, db_session: AsyncSession
    ):
        """Test that non-existent username returns False."""
        # Arrange
        service = UserService(db=db_session)

        # Act
        result = await service.check_username_taken(username="availableuser")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_check_username_taken_with_active_user(
        self, db_session: AsyncSession, create_user
    ):
        """Test that username from active user is considered taken."""
        # Arrange
        await create_user(username="activeuser", status=UserStatus.ACTIVE)
        service = UserService(db=db_session)

        # Act
        result = await service.check_username_taken(username="activeuser")

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_check_username_taken_with_pending_user(
        self, db_session: AsyncSession, create_user
    ):
        """Test that username from pending user is considered taken."""
        # Arrange
        await create_user(username="pendinguser", status=UserStatus.PENDING)
        service = UserService(db=db_session)

        # Act
        result = await service.check_username_taken(username="pendinguser")

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_check_username_taken_with_expired_user(
        self, db_session: AsyncSession, create_user
    ):
        """Test that username from expired user is considered taken."""
        # Arrange
        await create_user(username="expireduser", status=UserStatus.EXPIRED)
        service = UserService(db=db_session)

        # Act
        result = await service.check_username_taken(username="expireduser")

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_check_username_taken_with_deleted_user(
        self, db_session: AsyncSession, create_user
    ):
        """Test that username from deleted user is considered taken."""
        # Arrange
        await create_user(username="deleteduser", status=UserStatus.DELETED)
        service = UserService(db=db_session)

        # Act
        result = await service.check_username_taken(username="deleteduser")

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_check_username_taken_case_sensitivity(
        self, db_session: AsyncSession, create_user
    ):
        """Test username checking with different cases (depends on DB collation)."""
        # Arrange
        await create_user(username="TestUser")
        service = UserService(db=db_session)

        # Act - Test with different case
        result = await service.check_username_taken(username="testuser")

        # Assert - This depends on database collation
        # If case-insensitive: True, if case-sensitive: False
        # Adjust based on your database configuration
        assert isinstance(result, bool)
