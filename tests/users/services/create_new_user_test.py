from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, AppException
from app.users.schemas import UserCreate
from app.users.services import UserService
from app.users.utils import UserStatus


class TestCreateNewUser:
    """Test suite for create_new_user method."""

    @pytest.mark.asyncio
    async def test_create_new_user_success(self, db_session: AsyncSession):
        """Test successful creation of a new user."""
        # Arrange
        service = UserService(db=db_session)
        user_data = UserCreate(
            email="newuser@example.com",
            username="newuser",
            first_name="John",
            password="SecurePass123!",
            last_name="Doe",
        )

        # Act
        result = await service.create_new_user(user_in=user_data)

        # Assert
        assert result is not None
        assert result.id is not None
        assert result.email == "newuser@example.com"
        assert result.username == "newuser"
        assert result.first_name == "John"
        assert result.last_name == "Doe"
        assert result.status == UserStatus.PENDING
        assert result.password != "SecurePass123!"  # Password should be hashed
        assert result.deleted_at is None

    @pytest.mark.asyncio
    async def test_create_new_user_password_is_hashed(self, db_session: AsyncSession):
        """Test that user password is properly hashed."""
        # Arrange
        service = UserService(db=db_session)
        plain_password = "MyPassword123!"
        user_data = UserCreate(
            email="user@example.com",
            username="testuser",
            first_name="Test",
            password=plain_password,
        )

        # Act
        result = await service.create_new_user(user_in=user_data)

        # Assert
        assert result.password != plain_password
        assert result.password.startswith("$2b$")  # bcrypt hash format

    @pytest.mark.asyncio
    async def test_create_user_with_existing_active_email_fails(
        self, db_session: AsyncSession, create_user
    ):
        """Test that creating user with existing active email raises exception."""
        # Arrange
        await create_user(
            email="taken@example.com",
            username="existing",
            status=UserStatus.ACTIVE,
        )
        service = UserService(db=db_session)
        user_data = UserCreate(
            email="taken@example.com",
            username="newuser",
            first_name="New",
            password="Password123!!",
        )

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.create_new_user(user_in=user_data)

        assert exc_info.value.error == AppError.TAKEN_USERNAME_EMAIL

    @pytest.mark.asyncio
    async def test_create_user_with_existing_active_username_fails(
        self, db_session: AsyncSession, create_user
    ):
        """Test that creating user with existing active username raises exception."""
        # Arrange
        await create_user(
            email="existing@example.com",
            username="takenuser",
            status=UserStatus.ACTIVE,
        )
        service = UserService(db=db_session)
        user_data = UserCreate(
            email="new@example.com",
            username="takenuser",
            first_name="New",
            password="Password123!",
        )

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.create_new_user(user_in=user_data)

        assert exc_info.value.error == AppError.TAKEN_USERNAME_EMAIL

    @pytest.mark.asyncio
    async def test_create_user_with_existing_pending_email_fails(
        self, db_session: AsyncSession, create_user
    ):
        """Test that creating user with existing pending email raises exception."""
        # Arrange
        await create_user(
            email="pending@example.com",
            username="pending",
            status=UserStatus.PENDING,
        )
        service = UserService(db=db_session)
        user_data = UserCreate(
            email="pending@example.com",
            username="newuser",
            first_name="New",
            password="Password123!",
        )

        # Act & Assert
        with pytest.raises(AppException) as exc_info:
            await service.create_new_user(user_in=user_data)

        assert exc_info.value.error == AppError.TAKEN_USERNAME_EMAIL

    @pytest.mark.asyncio
    async def test_create_user_reuses_expired_account_by_email(
        self, db_session: AsyncSession, create_user
    ):
        """Test that expired user account is reused when creating user with same email."""
        # Arrange
        old_deleted_at = datetime.now(timezone.utc)
        expired_user = await create_user(
            email="expired@example.com",
            username="olduser",
            status=UserStatus.EXPIRED,
            deleted_at=old_deleted_at,
            first_name="Old",
            last_name="Name",
        )
        old_user_id = expired_user.id
        old_user_hashed_password = expired_user.password

        service = UserService(db=db_session)
        user_data = UserCreate(
            email="expired@example.com",
            username="newusername",
            password="NewPassword123!",
            first_name="New",
            last_name="User",
        )

        # Act
        result = await service.create_new_user(user_in=user_data)

        # Assert - Same user ID (reused account)
        assert result.id == old_user_id
        assert result.email == "expired@example.com"
        assert result.username == "newusername"  # Updated
        assert result.first_name == "New"  # Updated
        assert result.last_name == "User"  # Updated
        assert result.status == UserStatus.PENDING  # Reset
        assert result.deleted_at is None  # Reset
        assert result.password != old_user_hashed_password

    @pytest.mark.asyncio
    async def test_create_user_reuses_expired_account_by_username(
        self, db_session: AsyncSession, create_user
    ):
        """Test that expired user account is reused when creating user with same username."""
        # Arrange
        expired_user = await create_user(
            email="old@example.com",
            username="expireduser",
            status=UserStatus.EXPIRED,
            deleted_at=datetime.now(timezone.utc),
        )
        old_user_id = expired_user.id

        service = UserService(db=db_session)
        user_data = UserCreate(
            email="new@example.com",
            username="expireduser",
            first_name="New",
            password="NewPassword123!",
        )

        # Act
        result = await service.create_new_user(user_in=user_data)

        # Assert
        assert result.id == old_user_id
        assert result.email == "new@example.com"  # Updated
        assert result.username == "expireduser"
        assert result.status == UserStatus.PENDING

    @pytest.mark.asyncio
    async def test_create_user_reuse_updates_timestamp(
        self, db_session: AsyncSession, create_user
    ):
        """Test that reusing expired account updates the updated_at timestamp."""
        # Arrange
        old_time = datetime.now(timezone.utc)
        await create_user(
            email="expired@example.com",
            username="expired",
            status=UserStatus.EXPIRED,
            updated_at=old_time,
        )

        service = UserService(db=db_session)
        user_data = UserCreate(
            email="expired@example.com",
            username="newuser",
            first_name="New",
            password="Password123!@",
        )

        # Act
        result = await service.create_new_user(user_in=user_data)

        # Assert
        assert result.updated_at > old_time

    @pytest.mark.asyncio
    async def test_create_user_with_deleted_status_creates_new_user(
        self, db_session: AsyncSession, create_user
    ):
        """Test that user with DELETED status does not get reused (new user created)."""
        # Arrange
        old_user = await create_user(
            email="deleted@example.com",
            username="deleted",
            status=UserStatus.DELETED,
        )

        service = UserService(db=db_session)
        user_data = UserCreate(
            email="deleted@example.com",
            username="deleted",
            first_name="Deleted",
            password="Password123!!",
        )

        # Or if your implementation allows it, verify new user is created
        result = await service.create_new_user(user_in=user_data)
        assert result.id != old_user.id

    @pytest.mark.asyncio
    async def test_create_user_only_updates_changed_fields_on_reuse(
        self, db_session: AsyncSession, create_user
    ):
        """Test that only changed fields are updated when reusing expired account."""
        # Arrange
        await create_user(
            email="expired@example.com",
            username="olduser",
            first_name="Original",
            last_name="Name",
            status=UserStatus.EXPIRED,
        )

        service = UserService(db=db_session)
        # Only update username, keep other fields same
        user_data = UserCreate(
            email="expired@example.com",
            username="newuser",
            password="Password123!@",
            first_name="Original",  # Same as before
            last_name="Name",  # Same as before
        )

        # Act
        result = await service.create_new_user(user_in=user_data)

        # Assert
        assert result.username == "newuser"  # Updated
        assert result.first_name == "Original"  # Unchanged
        assert result.last_name == "Name"  # Unchanged

    @pytest.mark.asyncio
    async def test_create_user_with_optional_last_name(self, db_session: AsyncSession):
        """Test creating user with only required fields (last_name is optional)."""
        # Arrange
        service = UserService(db=db_session)
        user_data = UserCreate(
            email="minimal@example.com",
            username="minimal",
            first_name="Minimal",
            password="Password123!!",
        )

        # Act
        result = await service.create_new_user(user_in=user_data)

        # Assert
        assert result is not None
        assert result.email == "minimal@example.com"
        assert result.username == "minimal"
        assert result.first_name == "Minimal"
        assert result.last_name is None
