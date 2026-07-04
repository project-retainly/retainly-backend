import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.services import UserService


class TestGetUserByEmailOrUsername:
    """Test suite for get_user_by_email_or_username method."""

    @pytest.mark.asyncio
    async def test_get_user_by_email_success(
        self, db_session: AsyncSession, create_user
    ):
        """Test retrieving user by email returns correct user."""
        # Arrange
        user = await create_user(email="test@example.com", username="testuser")
        service = UserService(db=db_session)

        # Act
        result = await service.get_user_by_email_or_username(email="test@example.com")

        # Assert
        assert result is not None
        assert result.id == user.id
        assert result.email == user.email
        assert result.username == user.username

    @pytest.mark.asyncio
    async def test_get_user_by_username_success(
        self, db_session: AsyncSession, create_user
    ):
        """Test retrieving user by username returns correct user."""
        # Arrange
        user = await create_user(email="test@example.com", username="testuser")
        service = UserService(db=db_session)

        # Act
        result = await service.get_user_by_email_or_username(username="testuser")

        # Assert
        assert result is not None
        assert result.id == user.id
        assert result.email == user.email
        assert result.username == user.username

    @pytest.mark.asyncio
    async def test_get_user_by_email_and_username_success(
        self, db_session: AsyncSession, create_user
    ):
        """Test retrieving user with both email and username."""
        # Arrange
        user = await create_user(email="test@example.com", username="testuser")
        service = UserService(db=db_session)

        # Act
        result = await service.get_user_by_email_or_username(
            email="test@example.com", username="testuser"
        )

        # Assert
        assert result is not None
        assert result.id == user.id

    @pytest.mark.asyncio
    async def test_get_user_by_email_not_found(self, db_session: AsyncSession):
        """Test retrieving user by non-existent email returns None."""
        # Arrange
        service = UserService(db=db_session)

        # Act
        result = await service.get_user_by_email_or_username(
            email="nonexistent@example.com"
        )

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_username_not_found(self, db_session: AsyncSession):
        """Test retrieving user by non-existent username returns None."""
        # Arrange
        service = UserService(db=db_session)

        # Act
        result = await service.get_user_by_email_or_username(username="nonexistent")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_with_no_parameters(self, db_session: AsyncSession):
        """Test calling method with no parameters returns None."""
        # Arrange
        service = UserService(db=db_session)

        # Act
        result = await service.get_user_by_email_or_username()

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_matches_email_from_multiple_users(
        self, db_session: AsyncSession, create_user
    ):
        """Test that correct user is returned when multiple users exist."""
        # Arrange
        user1 = await create_user(email="user1@example.com", username="user1")
        await create_user(email="user2@example.com", username="user2")
        service = UserService(db=db_session)

        # Act
        result = await service.get_user_by_email_or_username(email="user1@example.com")

        # Assert
        assert result is not None
        assert result.id == user1.id
        assert result.email == "user1@example.com"

    @pytest.mark.asyncio
    async def test_get_user_by_email_or_username_returns_first_match(
        self, db_session: AsyncSession, create_user
    ):
        """Test that method returns user if either email or username matches."""
        # Arrange
        user1 = await create_user(email="user1@example.com", username="user1")
        user2 = await create_user(email="user2@example.com", username="user2")
        service = UserService(db=db_session)

        # Act - Email matches user1, username matches user2
        result = await service.get_user_by_email_or_username(
            email="user1@example.com", username="user2"
        )

        # Assert - Should return one of them (likely user1 based on OR logic)
        assert result is not None
        assert result.id in [user1.id, user2.id]
