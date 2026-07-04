import hashlib
import secrets
import time
import uuid
from typing import Any, Union

from jose import jwt
from passlib.context import CryptContext

from app.core.settings import settings

# This creates our single, reusable "context" for password hashing.
# We tell it to use 'bcrypt' as the default hashing algorithm.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """
    Hashes a plain-text password using bcrypt.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a hashed password.
    Returns True if they match, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_decoded_jwt(token: str) -> dict[str, Any]:
    """
    Decodes a JWT token and returns its payload.

    Args:
        token: The JWT token to decode.
    Returns:
        dict: The decoded JWT payload.
    """
    decoded_jwt = jwt.decode(
        token=token,
        key=settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    return decoded_jwt


def get_hashed_token(token: str) -> str:
    """
    Hashes a token using SHA256 for secure storage.

    Args:
        token: The plain-text token to hash.
    Returns:
        str: The SHA256 hash of the token.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def generate_refresh_token() -> str:
    """
    Generate a secure refresh token.

    Returns:
        str: The token hash
    """
    # Generate cryptographically secure random token
    plaintext_token = secrets.token_urlsafe(32)  # 256 bits of entropy

    # Hash it for storage.
    token_hash = get_hashed_token(plaintext_token)

    return plaintext_token, token_hash


def create_access_token(subject: Union[str, Any]) -> str:
    now = int(time.time())

    sub = str(subject)
    jti = str(uuid.uuid4())
    exp = int(now + settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60)

    to_encode = {"exp": exp, "sub": sub, "jti": jti}

    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )

    return encoded_jwt
