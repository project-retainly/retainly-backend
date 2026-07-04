from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.contexts import AuthContext, JwtContext
from app.core import redis
from app.core.database import get_db
from app.core.exceptions import AppError, AppException
from app.core.logger import get_logger
from app.core.utils import use_flow
from app.users.models import User

from . import constants, utils

logger = get_logger(__name__)

# auto_error set to False to handle missing token manually in the below logic
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


@use_flow("docs/flows/auth/auth_guard.md")
async def get_optional_auth_context(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> AuthContext | None:
    if token is None:
        return None

    try:
        decoded_jwt = utils.get_decoded_jwt(token)

        jwt_context = JwtContext.from_payload(decoded_jwt)

        is_blacklisted = await redis.client.exists(
            f"{constants.BLACKLIST_PREFIX}{jwt_context.jti}"
        )

        if is_blacklisted:
            logger.warning("token_is_blacklisted", jti=jwt_context.jti)
            raise JWTError

        user_id = jwt_context.sub

        current_user = await db.get(User, user_id)

        if current_user is None:
            logger.warning("user_not_found_for_token", user_id=user_id)
            raise JWTError

    except JWTError:
        logger.warning("jwt_error_in_auth_context")
        return None

    return AuthContext(user=current_user, jwt=jwt_context)


async def auth_guard(
    auth_context: AuthContext | None = Depends(get_optional_auth_context),
) -> AuthContext:
    if auth_context is None:
        raise AppException(
            error=AppError.AUTH_FAILED,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth_context
