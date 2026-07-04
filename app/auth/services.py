import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import redis
from app.core.exceptions import AppError, AppException
from app.core.logger import get_logger
from app.core.settings import settings
from app.users.models import User
from app.users.utils import UserStatus

from . import constants, utils
from .models import RefreshToken

logger = get_logger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_email_verification_link(
        self, user_id: int, user_updated_at: datetime
    ):
        logger.info("creating_email_verification_link", user_id=user_id)
        expiry_time = user_updated_at + timedelta(
            hours=settings.UNVERIFIED_USER_GRACE_PERIOD_HOURS
        )
        token = secrets.token_urlsafe(32)

        now = datetime.now(timezone.utc)

        payload = {"user_id": user_id, "issued_at": int(now.timestamp())}
        ttl = int((expiry_time - now).total_seconds())

        await redis.client.set(
            f"{constants.VERIFICATION_PREFIX}{token}",
            json.dumps(payload),
            ex=ttl,
        )

        verify_link = f"{settings.BACKEND_HOST_URL}/api/v1/auth/verify/{token}"

        return verify_link

    async def verify_and_get_user_id_from_token(
        self,
        token: str,
    ) -> Optional[tuple[int, int]]:
        logger.info("verifying_token")
        redis_key = f"{constants.VERIFICATION_PREFIX}{token}"

        raw = await redis.client.get(redis_key)

        if raw is None:
            logger.warning("token_not_found_in_redis")
            return None

        try:
            data = json.loads(raw)
            user_id = int(data["user_id"])
            issued_at = int(data["issued_at"])
        except (KeyError, ValueError, json.JSONDecodeError):
            logger.error("corrupted_token_data")
            # Corrupted token data
            await redis.client.delete(redis_key)
            return None

        # One-time use token
        await redis.client.delete(redis_key)

        logger.info("token_verified", user_id=user_id)
        return user_id, issued_at

    async def blacklist_jwt_token(self, jwt_context, user_id) -> None:
        logger.info("blacklisting_jwt_token", user_id=user_id, jti=jwt_context.jti)
        await redis.client.set(
            name=f"{constants.BLACKLIST_PREFIX}{jwt_context.jti}",
            value=user_id,
            ex=jwt_context.remaining_seconds,
        )

    async def assert_user_can_login(self, user) -> bool | None:
        """
        Validates whether the user account is allowed to authenticate.

        Raises:
            AppException: if account status is not ACTIVE.
        """
        if user.status == UserStatus.ACTIVE:
            return True

        logger.warning("user_cannot_login", user_id=user.id, status=user.status)

        if user.status in [
            UserStatus.PENDING,
            UserStatus.EXPIRED,
            UserStatus.DELETED,
        ]:
            raise AppException(error=AppError.AUTH_FAILED)

        # Safety fallback for unknown states
        raise AppException(error=AppError.INTERNAL_ERROR)

    async def get_refresh_token(
        self,
        hashed_token: str,
    ) -> RefreshToken | None:
        query = select(RefreshToken).where(RefreshToken.token_hash == hashed_token)

        result = await self.db.execute(query)
        return result.scalars().first()

    async def create_refresh_token(
        self, request: Request, user_id: int
    ) -> tuple[str, RefreshToken]:
        """Creates and stores a new refresh token in the database."""
        logger.info("creating_refresh_token", user_id=user_id)

        plaintext_token, token_hash = utils.generate_refresh_token()

        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=settings.REFRESH_TOKEN_EXPIRE_SECONDS
        )

        new_refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=request.headers.get("User-Agent"),
            ip_address=request.client.host if request.client else None,
        )

        self.db.add(new_refresh_token)

        return plaintext_token, new_refresh_token

    async def revoke_refresh_token(
        self,
        request: Request,
        response: Response,
        stored_token: RefreshToken,
        token_replaced_by: str,
        reason: str,
    ) -> None:
        """Revokes a refresh token and updates its metadata."""
        logger.info("revoking_refresh_token", token_id=stored_token.id, reason=reason)
        stored_token.revoke(
            reason=reason, request=request, token_replaced_by=token_replaced_by
        )

        self.db.add(stored_token)

        # Clear the cookie on the client side
        response.delete_cookie(
            key="refresh_token",
            path="/api/v1/auth/",
            secure=not settings.DEBUG,
            httponly=True,
            samesite="strict",
        )

    async def revoke_all_refresh_tokens_for_user(
        self,
        request: Request,
        response: Response,
        user_id: int,
        reason: str,
    ) -> None:
        """Revokes all active refresh tokens for a user."""
        logger.info("revoking_all_refresh_tokens", user_id=user_id, reason=reason)
        query = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
        )
        active_tokens = query.scalars().all()

        for token in active_tokens:
            token.revoke(reason=reason, request=request)
            self.db.add(token)

        # Clear the cookie on the client side
        response.delete_cookie(
            key="refresh_token",
            path="/api/v1/auth/",
            secure=not settings.DEBUG,
            httponly=True,
            samesite="strict",
        )

    async def create_password_reset_link(
        self,
        user_id: int,
    ) -> str:
        logger.info("creating_password_reset_link", user_id=user_id)
        now = datetime.now(timezone.utc)

        expiry_time = now + timedelta(
            minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        )
        token = secrets.token_urlsafe(32)

        payload = {"user_id": user_id, "issued_at": now.timestamp()}
        ttl = int((expiry_time - now).total_seconds())

        await redis.client.set(
            f"{constants.PASSWORD_RESET_PREFIX}{token}",
            json.dumps(payload),
            ex=ttl,
        )

        verify_link = f"{settings.BACKEND_HOST_URL}/api/v1/auth/reset-password/{token}"

        return verify_link

    async def verify_and_get_user_id_from_password_reset_token(self, token: str) -> int:
        redis_key = f"{constants.PASSWORD_RESET_PREFIX}{token}"

        raw = await redis.client.get(redis_key)

        if raw is None:
            logger.warning("invalid_password_reset_token_not_found")
            raise AppException(error=AppError.INVALID_VERIFICATION_TOKEN)

        try:
            data = json.loads(raw)
            user_id = int(data["user_id"])
        except (KeyError, ValueError, json.JSONDecodeError):
            logger.error("corrupted_password_reset_token")
            # Corrupted token data
            await redis.client.delete(redis_key)
            raise AppException(error=AppError.INVALID_VERIFICATION_TOKEN)

        # One-time use token, but do not delete immediately to allow
        # for password reset flow to complete
        # await redis.client.delete(redis_key)

        return user_id

    async def delete_password_reset_token(self, token: str) -> None:
        redis_key = f"{constants.PASSWORD_RESET_PREFIX}{token}"
        await redis.client.delete(redis_key)

    async def update_password_for_user(
        self, user: User, new_plain_password: str
    ) -> None:
        logger.info("updating_password_for_user", user_id=user.id)
        new_hashed_password = utils.get_password_hash(new_plain_password)
        if user.password == new_hashed_password:
            logger.warning("new_password_same_as_old", user_id=user.id)
            raise AppException(error=AppError.OLD_PASSWORD_SAME_AS_NEW)
        user.password = new_hashed_password
        self.db.add(user)
