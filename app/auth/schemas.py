from pydantic import BaseModel, EmailStr

from app.auth.validator_types import NonEmptyTokenRequired
from app.users.validator_types import PasswordRequired


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    email: EmailStr | None = None


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: NonEmptyTokenRequired
    new_password: PasswordRequired


class ChangePasswordRequest(BaseModel):
    current_password: PasswordRequired
    new_password: PasswordRequired
