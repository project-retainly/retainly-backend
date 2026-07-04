from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.contexts import AuthContext
from app.auth.dependencies import auth_guard
from app.auth.guards import registration_guard
from app.auth.rate_limiter import RateLimitDep
from app.auth.services import AuthService
from app.core.database import get_db
from app.core.logger import get_logger
from app.core.utils import use_flow
from app.core.validations.file_validator import AnalyzedFile
from app.mail.tasks import send_verification_email_task

from .constants import PROFILE_PIC_MAX_SIZE_MB as PFP_MAX_MB
from .schemas import UserCreate, UserPublic, UserUpdate
from .services import UserService

logger = get_logger(__name__)

users_router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@use_flow("docs/flows/users/create_user.md")
@users_router.post(
    path="/",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    dependencies=[Depends(registration_guard)],
)
async def create_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
    _=RateLimitDep(key="create_user", limit=5, minutes=60),
):
    logger.info("create_user_request", email=user_in.email)
    service = UserService(db)
    db_user = await service.create_new_user(user_in=user_in)

    auth_service = AuthService(db)
    verify_link = await auth_service.create_email_verification_link(
        user_id=db_user.id, user_updated_at=db_user.updated_at
    )
    email = db_user.email
    send_verification_email_task.delay(email=email, link=verify_link)

    logger.info("create_user_success", user_id=db_user.id)
    return db_user


@use_flow("docs/flows/users/user_detail.md")
@users_router.get(
    path="/",
    response_model=UserPublic,
    status_code=status.HTTP_200_OK,
    summary="Get details of the current user.",
)
async def get_user(
    auth_cxt: AuthContext = Depends(auth_guard),
    db: AsyncSession = Depends(get_db),
    _=RateLimitDep(key="user_detail", limit=60, minutes=1),
):
    user_id = auth_cxt.user.id
    logger.info("get_user_details", user_id=user_id)
    service = UserService(db)
    db_user = await service.get_user_by_id(user_id=user_id)

    return db_user


@use_flow("docs/flows/users/user_update_basic.md")
@users_router.put(
    path="/",
    status_code=status.HTTP_200_OK,
    response_model=UserPublic,
    summary="Update basic user details such as username, first and last name.",
)
async def updated_user(
    update_data: UserUpdate,
    auth_cxt: AuthContext = Depends(auth_guard),
    db: AsyncSession = Depends(get_db),
    _=RateLimitDep(key="user_basic_update", limit=10, minutes=1),
):
    user_id = auth_cxt.user.id
    logger.info("update_user_request", user_id=user_id)
    service = UserService(db)
    result = await service.update_basic_user_data(
        current_user=auth_cxt.user, update_data=update_data
    )
    logger.info("update_user_success", user_id=user_id)
    return result


@use_flow("docs/flows/users/update_profile_image.md")
@users_router.put(
    path="/profile-image",
    status_code=status.HTTP_200_OK,
    response_model=UserPublic,
    summary="Update the user's profile image.",
)
async def update_profile_image(
    analyzed_file: AnalyzedFile = Depends(),
    auth_cxt: AuthContext = Depends(auth_guard),
    db: AsyncSession = Depends(get_db),
    _=RateLimitDep(key="update_profile_image", limit=5, minutes=1),
):
    user_id = auth_cxt.user.id
    logger.info("update_profile_image_request", user_id=user_id)
    analyzed_file.validate_for_image_file(MAX_MB=PFP_MAX_MB)

    service = UserService(db)

    result = await service.update_profile_image(
        user=auth_cxt.user, analyzed_file=analyzed_file
    )
    logger.info("update_profile_image_success", user_id=user_id)
    return result
