import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.services import UserService
from app.users.utils import UserStatus


class TestGetUserById:
    """Test suite for get_user_by_id method."""

    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self, db_session: AsyncSession, create_user):
        """Test retrieving user by ID returns correct user."""
        # Arrange
        user = await create_user(email="test@example.com", username="testuser")
        service = UserService(db=db_session)

        # Act
        result = await service.get_user_by_id(user_id=user.id)

        # Assert
        assert result is not None
        assert result.id == user.id
        assert result.email == user.email
        assert result.username == user.username

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, db_session: AsyncSession):
        """Test retrieving user by non-existent ID returns None."""
        # Arrange
        service = UserService(db=db_session)
        non_existent_id = 999999

        # Act
        result = await service.get_user_by_id(user_id=non_existent_id)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_id_with_zero(self, db_session: AsyncSession):
        """Test retrieving user with ID 0 returns None."""
        # Arrange
        service = UserService(db=db_session)

        # Act
        result = await service.get_user_by_id(user_id=0)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_id_with_negative_id(self, db_session: AsyncSession):
        """Test retrieving user with negative ID returns None."""
        # Arrange
        service = UserService(db=db_session)

        # Act
        result = await service.get_user_by_id(user_id=-1)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_id_retrieves_all_statuses(
        self, db_session: AsyncSession, create_user
    ):
        """Test that get_user_by_id retrieves users regardless of status."""
        # Arrange
        service = UserService(db=db_session)

        active_user = await create_user(status=UserStatus.ACTIVE)
        pending_user = await create_user(status=UserStatus.PENDING)
        expired_user = await create_user(status=UserStatus.EXPIRED)
        deleted_user = await create_user(status=UserStatus.DELETED)

        # Act & Assert
        assert await service.get_user_by_id(user_id=active_user.id) is not None
        assert await service.get_user_by_id(user_id=pending_user.id) is not None
        assert await service.get_user_by_id(user_id=expired_user.id) is not None
        assert await service.get_user_by_id(user_id=deleted_user.id) is not None

    @pytest.mark.asyncio
    async def test_get_user_by_id_from_multiple_users(
        self, db_session: AsyncSession, create_user
    ):
        """Test retrieving specific user when multiple users exist."""
        # Arrange
        await create_user(email="user1@example.com", username="user1")
        user2 = await create_user(email="user2@example.com", username="user2")
        await create_user(email="user3@example.com", username="user3")
        service = UserService(db=db_session)

        # Act
        result = await service.get_user_by_id(user_id=user2.id)

        # Assert
        assert result is not None
        assert result.id == user2.id
        assert result.email == "user2@example.com"
