from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import utils
from app.core.exceptions import AppError, AppException
from app.core.logger import get_logger
from app.core.validations.file_validator import AnalyzedFile
from app.media.services import MediaService  # Avoid circular import
from app.media.utils import StaticDirs

from .models import User, UserStatus
from .schemas import UserCreate, UserUpdate

logger = get_logger(__name__)


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_user_by_email(self, email: str) -> User | None:
        query = select(User).where(User.email == email)
        user = (await self.db.execute(query)).scalar_one_or_none()
        if user and user.status == UserStatus.ACTIVE:
            return user

        return None

    async def get_active_user_by_id(self, user_id: int) -> User | None:
        query = select(User).where(User.id == user_id)
        user = (await self.db.execute(query)).scalar_one_or_none()
        if user and user.status == UserStatus.ACTIVE:
            return user

        return None

    async def get_user_by_email_or_username(
        self, email: str | None = None, username: str | None = None
    ) -> User | None:
        if email:
            query = select(User).where(User.email == email)
            user = (await self.db.execute(query)).scalar_one_or_none()
            if user:
                return user

        if username:
            query = select(User).where(User.username == username)
            return (await self.db.execute(query)).scalar_one_or_none()

        return None

    async def create_new_user(self, user_in: UserCreate) -> User:
        """
        Handles all the business logic for creating a user: hashing,
        model creation, and database commit.
        """
        logger.info("creating_new_user", email=user_in.email, username=user_in.username)

        existing_user = await self.get_user_by_email_or_username(
            email=user_in.email, username=user_in.username
        )

        hashed_password = utils.get_password_hash(user_in.password)

        if existing_user:
            # Block active and pending accounts
            if existing_user.status in (
                UserStatus.ACTIVE,
                UserStatus.PENDING,
            ):
                logger.warning(
                    "user_creation_failed_taken",
                    email=user_in.email,
                    username=user_in.username,
                    status=existing_user.status,
                )
                raise AppException(
                    error=AppError.TAKEN_USERNAME_EMAIL,
                    extra={
                        "email": user_in.email,
                        "username": user_in.username,
                    },
                )

            # Reuse account only if status is expired → update fields and reset lifecycle
            if existing_user.status == UserStatus.EXPIRED:
                logger.info("reusing_expired_account", user_id=existing_user.id)
                data = user_in.model_dump(exclude={"password"}, exclude_unset=True)

                # Update only changed fields
                for field, value in data.items():
                    if getattr(existing_user, field) != value:
                        setattr(existing_user, field, value)

                # Reset account lifecycle
                existing_user.password = hashed_password
                existing_user.status = UserStatus.PENDING

                # manually(Optional) set updated_at as this is this
                # starts the new email verification grace period
                existing_user.updated_at = datetime.now(timezone.utc)

                existing_user.deleted_at = None

                await self.db.commit()
                await self.db.refresh(existing_user)

                logger.info("expired_account_reused", user_id=existing_user.id)
                return existing_user

        # No user exists → create new
        new_user = User(
            **user_in.model_dump(exclude={"password"}),
            password=hashed_password,
            status=UserStatus.PENDING,
        )

        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)

        logger.info("user_created_pending", user_id=new_user.id)
        return new_user

    async def get_user_by_id(self, user_id: int) -> User | None:
        """
        Service function to get a single user by their primary key.
        """

        return await self.db.get(User, user_id)

    async def check_username_taken(self, username: str) -> bool:
        user = await self.get_user_by_email_or_username(username=username)
        return user is not None

    async def update_basic_user_data(self, current_user: User, update_data: UserUpdate):
        """
        Updates username, first_name, and last_name with validation.
        """
        logger.info("updating_basic_user_data", user_id=current_user.id)
        # 1. Convert Pydantic model to a dict, excluding None values
        #    (exclude_unset=True ensures we don't wipe existing data with None)
        data_dict = update_data.model_dump(exclude_unset=True)

        if "username" in data_dict:
            new_username = data_dict["username"]

            # Check 1: Is it the SAME username they already have?
            # (Optimization: Don't query DB if they didn't actually change it)
            if new_username == current_user.username:
                del data_dict["username"]

            # Check 2: Is the new username taken by SOMEONE ELSE?
            elif await self.check_username_taken(new_username):
                logger.warning(
                    "username_update_failed_taken",
                    user_id=current_user.id,
                    new_username=new_username,
                )
                raise AppException(
                    error=AppError.TAKEN_USERNAME_EMAIL,
                    extra={"username": new_username},
                )

        for key, value in data_dict.items():
            setattr(current_user, key, value)

        await self.db.commit()
        await self.db.refresh(current_user)

        logger.info("basic_user_data_updated", user_id=current_user.id)
        return current_user

    async def update_profile_image(
        self, user: User, analyzed_file: AnalyzedFile
    ) -> User:
        """
        Updates the user's profile image with the given analyzed file.
        """
        logger.info("updating_profile_image", user_id=user.id)

        # 1. Initialize Media Service
        # (Best practice: Dependency Inject this in __init__ if possible)
        media_service = MediaService(self.db)

        # 2. HANDLE CLEANUP
        # If we don't do this, we get "Orphaned Files" forever.
        if user.profile_image:
            logger.info(
                "deleting_old_profile_image",
                user_id=user.id,
                media_id=user.profile_image.id,
            )
            await media_service.delete_media(user.profile_image)

        # 3. UPLOAD NEW IMAGE
        new_media = await media_service.upload_file_and_create_media(
            analyzed_file, user_id=user.id, directory=StaticDirs.Uploads.AVATARS
        )

        # 4. LINK & SAVE
        # SQLAlchemy magic: This updates the foreign key automatically
        user.profile_image = new_media

        # 5. COMMIT
        # We commit to save the new link and the deletion of the old record
        await self.db.commit()
        await self.db.refresh(user)

        logger.info("profile_image_updated", user_id=user.id, media_id=new_media.id)
        return user
