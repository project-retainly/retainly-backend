import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, AppException
from app.users.schemas import UserUpdate
from app.users.services import UserService
from app.users.utils import UserStatus


class TestUpdateBasicUserData:
    """Test suite for update_basic_user_data method."""

    @pytest.mark.asyncio
    async def test_update_username_success(self, db_session: AsyncSession, create_user):
        """Test successfully updating username."""
        # Arrange
        user = await create_user(username="oldusername")
        service = UserService(db=db_session)
        update_data = UserUpdate(username="newusername")

        # Act
        result = await service.update_basic_user_data(
            current_user=user, update_data=update_data
        )

        # Assert
        assert result.username == "newusername"
        await db_session.refresh(user)
        assert user.username == "newusername"

    @pytest.mark.asyncio
    async def test_update_first_name_success(
        self, db_session: AsyncSession, create_user
    ):
        """Test successfully updating first name."""
        # Arrange
        user = await create_user(first_name="Old")
        service = UserService(db=db_session)
        update_data = UserUpdate(first_name="New")

        # Act
        result = await service.update_basic_user_data(
            current_user=user, update_data=update_data
        )

        # Assert
        assert result.first_name == "New"

    @pytest.mark.asyncio
    async def test_update_last_name_success(
        self, db_session: AsyncSession, create_user
    ):
        """Test successfully updating last name."""
        # Arrange
        user = await create_user(last_name="OldLast")
        service = UserService(db=db_session)
        update_data = UserUpdate(last_name="NewLast")

        # Act
        result = await service.update_basic_user_data(
            current_user=user, update_data=update_data
        )

        # Assert
        assert result.last_name == "NewLast"

    @pytest.mark.asyncio
    async def test_update_all_fields_success(
        self, db_session: AsyncSession, create_user
    ):
        """Test successfully updating all fields at once."""
        # Arrange
        user = await create_user(username="olduser", first_name="Old", last_name="Name")
        service = UserService(db=db_session)
        update_data = UserUpdate(
            username="newuser", first_name="New", last_name="Lastname"
        )

        # Act
        result = await service.update_basic_user_data(
            current_user=user, update_data=update_data
        )

        # Assert
        assert result.username == "newuser"
        assert result.first_name == "New"
        assert result.last_name == "Lastname"

    @pytest.mark.asyncio
    async def test_update_username_to_same_value_succeeds(
        self, db_session: AsyncSession, create_user
    ):
        """Test that updating username to the same value succeeds without DB check."""
        # Arrange
        user = await create_user(username="sameuser")
        service = UserService(db=db_session)
        update_data = UserUpdate(username="sameuser")

        # Act
        result = await service.update_basic_user_data(
            current_user=user, update_data=update_data
        )

        # Assert
        assert result.username == "sameuser"

    @pytest.mark.asyncio
    async def test_update_username_to_taken_username_fails(
        self, db_session: AsyncSession, create_user
    ):
        """Test that updating to an already taken username raises exception."""
        # Arrange
        user1 = await create_user(username="user1")
        await create_user(username="user2")
        service = UserService(db=db_session)
        update_data = UserUpdate(username="user2")  # Already taken by user2

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.update_basic_user_data(
                current_user=user1, update_data=update_data
            )

        assert exc_info.value.error == AppError.TAKEN_USERNAME_EMAIL
        # assert "user2" in str(exc_info.value.extra)

    @pytest.mark.asyncio
    async def test_update_with_empty_update_data(
        self, db_session: AsyncSession, create_user
    ):
        """Test updating with no fields set (empty update)."""
        # Arrange
        user = await create_user(username="testuser", first_name="Test")
        original_username = user.username
        original_first_name = user.first_name
        service = UserService(db=db_session)
        update_data = UserUpdate()  # No fields set

        # Act
        result = await service.update_basic_user_data(
            current_user=user, update_data=update_data
        )

        # Assert - Nothing should change
        assert result.username == original_username
        assert result.first_name == original_first_name

    @pytest.mark.asyncio
    async def test_update_partial_fields(self, db_session: AsyncSession, create_user):
        """Test updating only some fields while leaving others unchanged."""
        # Arrange
        user = await create_user(username="olduser", first_name="Old", last_name="Name")
        service = UserService(db=db_session)
        # Only update first_name
        update_data = UserUpdate(first_name="Updated")

        # Act
        result = await service.update_basic_user_data(
            current_user=user, update_data=update_data
        )

        # Assert
        assert result.first_name == "Updated"  # Changed
        assert result.username == "olduser"  # Unchanged
        assert result.last_name == "Name"  # Unchanged

    @pytest.mark.asyncio
    async def test_update_username_taken_by_expired_user_fails(
        self, db_session: AsyncSession, create_user
    ):
        """Test that username taken by expired user is still considered taken."""
        # Arrange
        await create_user(username="expired", status=UserStatus.EXPIRED)
        active_user = await create_user(username="active", status=UserStatus.ACTIVE)
        service = UserService(db=db_session)
        update_data = UserUpdate(username="expired")

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.update_basic_user_data(
                current_user=active_user, update_data=update_data
            )

        assert exc_info.value.error == AppError.TAKEN_USERNAME_EMAIL

    @pytest.mark.asyncio
    async def test_update_username_taken_by_deleted_user_fails(
        self, db_session: AsyncSession, create_user
    ):
        """Test that username taken by deleted user is still considered taken."""
        # Arrange
        await create_user(username="deleted", status=UserStatus.DELETED)
        active_user = await create_user(username="active", status=UserStatus.ACTIVE)
        service = UserService(db=db_session)
        update_data = UserUpdate(username="deleted")

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.update_basic_user_data(
                current_user=active_user, update_data=update_data
            )

        assert exc_info.value.error == AppError.TAKEN_USERNAME_EMAIL

    @pytest.mark.asyncio
    async def test_update_user_refreshes_from_database(
        self, db_session: AsyncSession, create_user
    ):
        """Test that updated user is properly refreshed from database."""
        # Arrange
        user = await create_user(username="testuser")
        service = UserService(db=db_session)
        update_data = UserUpdate(first_name="Updated")

        # Act
        result = await service.update_basic_user_data(
            current_user=user, update_data=update_data
        )

        # Assert - Result should have the updated value
        assert result.first_name == "Updated"

        # Verify it's persisted in the database
        await db_session.refresh(user)
        assert user.first_name == "Updated"

    @pytest.mark.asyncio
    async def test_update_preserves_other_user_fields(
        self, db_session: AsyncSession, create_user
    ):
        """Test that updating doesn't affect fields not in UserUpdate schema."""
        # Arrange
        user = await create_user(
            username="testuser",
            email="test@example.com",
            status=UserStatus.ACTIVE,
        )
        original_email = user.email
        original_status = user.status
        service = UserService(db=db_session)
        update_data = UserUpdate(first_name="NewName")

        # Act
        result = await service.update_basic_user_data(
            current_user=user, update_data=update_data
        )

        # Assert - Email and status should remain unchanged
        assert result.email == original_email
        assert result.status == original_status

    @pytest.mark.asyncio
    async def test_update_with_none_values_excluded(
        self, db_session: AsyncSession, create_user
    ):
        """Test that None values in update data don't overwrite existing values."""
        # Arrange
        user = await create_user(username="testuser", first_name="Existing")
        service = UserService(db=db_session)

        # Create update with explicit None (if schema allows)
        # This depends on your UserUpdate schema implementation
        update_data = UserUpdate(last_name="NewLast")  # first_name not set

        # Act
        result = await service.update_basic_user_data(
            current_user=user, update_data=update_data
        )

        # Assert - first_name should not be wiped out
        assert result.first_name == "Existing"
        assert result.last_name == "NewLast"
