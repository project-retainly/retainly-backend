import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.schemas import UserCreate, UserUpdate
from app.users.services import UserService
from app.users.utils import UserStatus


class TestUserServiceIntegration:
    """Integration tests for UserService methods working together."""

    @pytest.mark.asyncio
    async def test_create_user_then_retrieve_by_id(self, db_session: AsyncSession):
        """Test creating a user and then retrieving it by ID."""
        # Arrange
        service = UserService(db=db_session)
        user_data = UserCreate(
            email="integration@example.com",
            username="integrationuser",
            first_name="Integration",
            password="Password123!!",
        )

        # Act
        created_user = await service.create_new_user(user_in=user_data)
        retrieved_user = await service.get_user_by_id(user_id=created_user.id)

        # Assert
        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.email == "integration@example.com"
        assert retrieved_user.username == "integrationuser"

    @pytest.mark.asyncio
    async def test_create_user_then_check_username_taken(
        self, db_session: AsyncSession
    ):
        """Test creating a user and then checking if username is taken."""
        # Arrange
        service = UserService(db=db_session)
        user_data = UserCreate(
            email="test@example.com",
            username="testuser",
            first_name="Test",
            password="Password123!!",
        )

        # Act
        await service.create_new_user(user_in=user_data)
        is_taken = await service.check_username_taken(username="testuser")

        # Assert
        assert is_taken is True

    @pytest.mark.asyncio
    async def test_create_user_then_update_username(self, db_session: AsyncSession):
        """Test creating a user and then updating their username."""
        # Arrange
        service = UserService(db=db_session)
        user_data = UserCreate(
            email="test@example.com",
            username="originaluser",
            first_name="Test",
            password="Password123!!",
        )

        # Act
        created_user = await service.create_new_user(user_in=user_data)
        update_data = UserUpdate(username="updateduser")
        updated_user = await service.update_basic_user_data(
            current_user=created_user, update_data=update_data
        )

        # Assert
        assert updated_user.username == "updateduser"

    @pytest.mark.asyncio
    async def test_full_user_lifecycle_expired_to_recreated(
        self, db_session: AsyncSession, create_user
    ):
        """Test full lifecycle: create user, expire it, then recreate with same email."""
        # Arrange
        service = UserService(db=db_session)

        # Create and expire user
        expired_user = await create_user(
            email="lifecycle@example.com",
            username="lifecycleuser",
            status=UserStatus.EXPIRED,
        )
        old_id = expired_user.id

        # Act - Recreate with same email
        new_user_data = UserCreate(
            email="lifecycle@example.com",
            username="newlifecycleuser",
            first_name="NewLifecycle",
            password="Newpassword123!",
        )
        recreated_user = await service.create_new_user(user_in=new_user_data)

        # Assert
        assert recreated_user.id == old_id  # Reused account
        assert recreated_user.username == "newlifecycleuser"
        assert recreated_user.status == UserStatus.PENDING
        assert recreated_user.deleted_at is None
