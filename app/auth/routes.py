from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import auth_guard
from app.auth.rate_limiter import RateLimitDep
from app.common.schemas_common import MessageResponse
from app.core.database import get_db
from app.core.exceptions import AppError, AppException
from app.core.logger import get_logger
from app.core.settings import settings
from app.core.utils import use_flow
from app.mail.tasks import (
    send_password_change_notification_email_task,
    send_password_reset_email_task,
    send_verification_email_task,
)
from app.users.schemas import UserPublic
from app.users.services import UserService
from app.users.utils import UserStatus

from .contexts import AuthContext
from .messages import AuthMessages
from .schemas import (
    ChangePasswordRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    Token,
)
from .services import AuthService
from .utils import create_access_token, get_hashed_token, verify_password

logger = get_logger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["Auth"])


@use_flow("docs/flows/auth/login_flow.md")
@auth_router.post(
    path="/token",
    status_code=status.HTTP_200_OK,
    response_model=Token | UserPublic,
    summary="Verifies the credentials and grants the access token.",
)
async def login_for_access_token(
    request: Request,
    response: Response,
    _=RateLimitDep(key="login", limit=5, minutes=1),
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    username = form_data.username
    logger.info("login_attempt", username=username)

    user = await UserService(db=db).get_user_by_email_or_username(
        email=username, username=username
    )

    if user is None:
        logger.warning("login_failed_user_not_found", username=username)
        raise AppException(error=AppError.AUTH_FAILED)

    user_password = user.password
    login_password = form_data.password

    if not verify_password(login_password, user_password):
        logger.warning("login_failed_invalid_password", username=username)
        raise AppException(error=AppError.AUTH_FAILED)

    auth_service = AuthService(db=db)

    await auth_service.assert_user_can_login(user)

    (
        plain_text_refresh_token,
        refresh_token,
    ) = await auth_service.create_refresh_token(request=request, user_id=user.id)

    response.set_cookie(
        key="refresh_token",
        value=plain_text_refresh_token,
        path="/api/v1/auth/",
        httponly=True,
        secure=not settings.DEBUG,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_SECONDS,
    )

    access_token = create_access_token(subject=user.id)
    logger.info("login_successful", user_id=user.id)
    return Token(access_token=access_token, token_type="bearer")


@use_flow("docs/flows/auth/logout_flow.md")
@auth_router.post(
    path="/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logs out the user by blacklisting the access token.",
)
async def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias="refresh_token"),
    db: AsyncSession = Depends(get_db),
    auth_cxt: AuthContext = Depends(auth_guard),
    _=RateLimitDep(key="logout", limit=20, minutes=1),
):
    user_id = auth_cxt.user.id
    logger.info("logout_attempt", user_id=user_id)
    auth_service = AuthService(db=db)

    await auth_service.blacklist_jwt_token(
        jwt_context=auth_cxt.jwt,
        user_id=user_id,
    )

    if refresh_token is not None:
        hashed_token = get_hashed_token(refresh_token)

        async with db.begin_nested():
            stored_token = await auth_service.get_refresh_token(
                hashed_token=hashed_token
            )

            if stored_token and not stored_token.is_revoked:
                await auth_service.revoke_refresh_token(
                    request=request,
                    response=response,
                    stored_token=stored_token,
                    token_replaced_by="",
                    reason="user_logout",
                )

    logger.info("logout_successful", user_id=user_id)
    return


@use_flow("docs/flows/auth/verification_flow.md")
@auth_router.get(
    path="/verify/{token}",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponse,
    summary="Verifies the user email by activation token.",
)
async def verify_user_email(
    token: str,
    _=RateLimitDep(key="verify_email", limit=5, minutes=60),
    db: AsyncSession = Depends(get_db),
):
    logger.info("verifying_email")
    auth_service = AuthService(db=db)
    result = await auth_service.verify_and_get_user_id_from_token(token)

    if result is None:
        logger.warning("verify_email_failed_invalid_token")
        raise AppException(error=AppError.BAD_REQUEST)

    user_id, issued_at = result

    user = await UserService(db=db).get_user_by_id(user_id=user_id)

    if user is None:
        logger.warning("verify_email_failed_user_not_found", user_id=user_id)
        raise AppException(error=AppError.NOT_FOUND)

    if user.status == UserStatus.ACTIVE:
        logger.info("verify_email_already_active", user_id=user_id)
        return MessageResponse(message=AuthMessages.ACCOUNT_ALREADY_VERIFIED)

    # already marked for expired or deleted users cannot be verified
    if user.status != UserStatus.PENDING:
        logger.warning(
            "verify_email_failed_invalid_status",
            user_id=user_id,
            status=user.status,
        )
        raise AppException(error=AppError.BAD_REQUEST)

    # invalidate old tokens
    if issued_at < int(user.updated_at.timestamp()):
        logger.warning("verify_email_failed_token_expired_by_update", user_id=user_id)
        raise AppException(error=AppError.BAD_REQUEST)

    user.status = UserStatus.ACTIVE
    db.add(user)
    await db.commit()

    logger.info("verify_email_success", user_id=user_id)
    return MessageResponse(message=AuthMessages.ACCOUNT_VERIFY_SUCCESS)


@use_flow("docs/flows/auth/resend_verification.md")
@auth_router.post(
    path="/resend-verification",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponse,
    summary="Resends verification email.",
)
async def resend_verification(
    payload: ResendVerificationRequest,
    _=RateLimitDep(key="resend_verification", limit=3, minutes=60),
    db: AsyncSession = Depends(get_db),
):
    logger.info("resend_verification_request", email=payload.email)
    user = await UserService(db=db).get_user_by_email_or_username(email=payload.email)

    # Do not leak existence
    if not user:
        logger.info("resend_verification_user_not_found_no_leak", email=payload.email)
        return MessageResponse(message=AuthMessages.GENERIC_VERIFICATION_SENT)

    # Already verified
    if user.status == UserStatus.ACTIVE:
        logger.info("resend_verification_already_active", user_id=user.id)
        return MessageResponse(message=AuthMessages.ACCOUNT_ALREADY_VERIFIED)

    # already marked for expired or deleted users cannot be verified
    if user.status != UserStatus.PENDING:
        logger.info(
            "resend_verification_invalid_status",
            user_id=user.id,
            status=user.status,
        )
        return MessageResponse(message=AuthMessages.GENERIC_VERIFICATION_SENT)

    # check if the user is within the grace period
    # to be able to generate a new token.
    expiry_time = user.updated_at + timedelta(
        hours=settings.UNVERIFIED_USER_GRACE_PERIOD_HOURS
    )
    now = datetime.now(timezone.utc)

    if expiry_time < now:
        logger.info("resend_verification_grace_period_expired", user_id=user.id)
        user.status = UserStatus.EXPIRED
        user.deleted_at = now
        await db.commit()
        return MessageResponse(message=AuthMessages.GENERIC_VERIFICATION_SENT)

    # Start new verification window
    user.updated_at = now
    await db.commit()

    auth_service = AuthService(db=db)

    verify_link = await auth_service.create_email_verification_link(
        user_id=user.id,
        user_updated_at=user.updated_at,
    )

    email = user.email

    send_verification_email_task.delay(email=email, link=verify_link)

    logger.info("resend_verification_email_sent", user_id=user.id)
    return MessageResponse(message=AuthMessages.GENERIC_VERIFICATION_SENT)


@use_flow("docs/flows/auth/refresh_token_flow.md")
@auth_router.post(
    path="/token/refresh",
    status_code=status.HTTP_200_OK,
    response_model=Token,
    summary="Refreshes the access token using a valid refresh token.",
)
async def refresh_access_token(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias="refresh_token"),
    db: AsyncSession = Depends(get_db),
):
    if refresh_token is None:
        logger.warning("refresh_token_missing")
        raise AppException(error=AppError.INVALID_AUTH_TOKEN)

    hashed_token = get_hashed_token(refresh_token)

    auth_service = AuthService(db=db)

    stored_token = await auth_service.get_refresh_token(hashed_token=hashed_token)

    if stored_token is None:
        logger.warning("refresh_token_not_found_in_db")
        raise AppException(error=AppError.INVALID_AUTH_TOKEN)

    if stored_token.is_revoked:
        logger.warning(
            "refresh_token_revoked_reuse_attempt", user_id=stored_token.user_id
        )
        # Revoked token request detected, revoke all tokens for this user logic here.
        async with db.begin_nested():
            await auth_service.revoke_all_refresh_tokens_for_user(
                request=request,
                response=response,
                reason="suspicious_activity",
                user_id=stored_token.user_id,
            )
        raise AppException(error=AppError.INVALID_AUTH_TOKEN)

    if stored_token.is_expired:
        logger.warning("refresh_token_expired", user_id=stored_token.user_id)
        raise AppException(error=AppError.INVALID_AUTH_TOKEN)

    async with db.begin_nested():
        (
            plain_text_refresh_token,
            new_refresh_token,
        ) = await auth_service.create_refresh_token(
            request=request, user_id=stored_token.user_id
        )

        await auth_service.revoke_refresh_token(
            request=request,
            response=response,
            stored_token=stored_token,
            token_replaced_by=new_refresh_token.token_hash,
            reason="rotation",
        )

    access_token = create_access_token(subject=new_refresh_token.user_id)

    # Set the new refresh token in HttpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=plain_text_refresh_token,
        path="/api/v1/auth/",
        httponly=True,
        secure=not settings.DEBUG,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_SECONDS,
    )

    logger.info("refresh_token_success", user_id=new_refresh_token.user_id)
    return Token(access_token=access_token, token_type="bearer")


@use_flow("docs/flows/auth/forgot_password/email_reset_link.md")
@auth_router.post(
    path="/forgot-password",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponse,
    summary="Sends a password reset link to the user's email.",
)
async def forgot_password(
    payload: ResendVerificationRequest,
    _=RateLimitDep(key="forgot_password", limit=1, minutes=1),
    db: AsyncSession = Depends(get_db),
):
    logger.info("forgot_password_request", email=payload.email)
    user = await UserService(db=db).get_active_user_by_email(email=payload.email)

    if not user:
        logger.info("forgot_password_user_not_found_no_leak", email=payload.email)
        return MessageResponse(message=AuthMessages.GENERIC_PASSWORD_RESET_SENT)

    auth_service = AuthService(db=db)

    reset_link = await auth_service.create_password_reset_link(
        user_id=user.id,
    )
    email = user.email
    user_name = user.username
    send_password_reset_email_task.delay(
        email=email, link=reset_link, user_name=user_name
    )

    logger.info("forgot_password_email_sent", user_id=user.id)
    return MessageResponse(message=AuthMessages.GENERIC_PASSWORD_RESET_SENT)


@use_flow("docs/flows/auth/forgot_password/verify_reset_link.md")
@auth_router.post(
    path="/reset-password/",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponse,
    summary="Resets user password using reset token.",
)
async def verify_password_reset_token(
    request: Request,
    response: Response,
    payload: ResetPasswordRequest,
    _=RateLimitDep(key="verify_password_reset_token", limit=5, minutes=10),
    db: AsyncSession = Depends(get_db),
):
    logger.info("verify_password_reset_token")
    auth_service = AuthService(db=db)
    user_id = await auth_service.verify_and_get_user_id_from_password_reset_token(
        payload.token
    )

    user = await UserService(db=db).get_active_user_by_id(user_id=user_id)

    if user is None:
        logger.warning("verify_password_reset_user_not_found", user_id=user_id)
        raise AppException(error=AppError.INVALID_VERIFICATION_TOKEN)

    await auth_service.update_password_for_user(
        user=user, new_plain_password=payload.new_password
    )

    await auth_service.revoke_all_refresh_tokens_for_user(
        request=request,
        response=response,
        reason="password_reset",
        user_id=user.id,
    )
    await db.commit()

    await auth_service.delete_password_reset_token(token=payload.token)

    logger.info("password_reset_success", user_id=user.id)
    return MessageResponse(message=AuthMessages.PASSWORD_RESET_SUCCESS)


@use_flow("docs/flows/auth/change_password.md")
@auth_router.post(
    path="/change-password/",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponse,
    summary="Changes user password for authenticated users.",
)
async def change_password(
    request: Request,
    response: Response,
    payload: ChangePasswordRequest,
    auth_cxt: AuthContext = Depends(auth_guard),
    db: AsyncSession = Depends(get_db),
):
    user = auth_cxt.user
    logger.info("change_password_request", user_id=user.id)
    auth_service = AuthService(db=db)

    if not verify_password(
        plain_password=payload.current_password, hashed_password=user.password
    ):
        logger.warning("change_password_invalid_current", user_id=user.id)
        raise AppException(error=AppError.INVALID_CURRENT_PASSWORD)

    await auth_service.update_password_for_user(
        user=user, new_plain_password=payload.new_password
    )

    await auth_service.revoke_all_refresh_tokens_for_user(
        request=request,
        response=response,
        reason="password_change",
        user_id=user.id,
    )
    await db.commit()

    await auth_service.blacklist_jwt_token(
        jwt_context=auth_cxt.jwt,
        user_id=user.id,
    )
    email = user.email
    user_name = user.username
    send_password_change_notification_email_task.delay(
        email=email, user_name=user_name
    )

    logger.info("change_password_success", user_id=user.id)
    return MessageResponse(message=AuthMessages.PASSWORD_CHANGE_SUCCESS)
