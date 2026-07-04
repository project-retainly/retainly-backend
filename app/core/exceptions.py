from dataclasses import dataclass
from enum import Enum

from fastapi import HTTPException, status


# 1. Define what an Error looks like
@dataclass
class ErrorDetail:
    code: str
    message: str
    status_code: int


# 2. The Single Source of Truth
class AppError(Enum):
    # --- Generic Errors ---
    NOT_FOUND = ErrorDetail(
        "ERR_404",
        "The requested resource was not found.",
        status.HTTP_404_NOT_FOUND,
    )
    VALIDATION_ERROR = ErrorDetail(
        "ERR_422",
        "The given data is invalid.",
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
    INTERNAL_ERROR = ErrorDetail(
        "ERR_500",
        "An unexpected server error occurred.",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    BAD_REQUEST = ErrorDetail("ERR_400", "Invalid input.", status.HTTP_400_BAD_REQUEST)

    TOO_MANY_REQUESTS = ErrorDetail(
        "ERR_429",
        "Too many requests. Please try again after some time.",
        status.HTTP_429_TOO_MANY_REQUESTS,
    )

    # --- Auth Errors ---
    AUTH_FAILED = ErrorDetail(
        "ERR_AUTH_FAILED",
        "Invalid username or password.",
        status.HTTP_401_UNAUTHORIZED,
    )
    INVALID_AUTH_TOKEN = ErrorDetail(
        "ERR_INVALID_AUTH_TOKEN",
        "Missing, expired or invalid token.",
        status.HTTP_401_UNAUTHORIZED,
    )
    FORBIDDEN = ErrorDetail("ERR_403", "Permission denied.", status.HTTP_403_FORBIDDEN)
    SPAM_LOGIN = ErrorDetail(
        "ERR_SPAM_LOGIN",
        "Too many login attempts.",
        status.HTTP_429_TOO_MANY_REQUESTS,
    )

    # --- Business Logic Errors ---
    TAKEN_USERNAME_EMAIL = ErrorDetail(
        "ERR_TAKEN_USERNAME_EMAIL",
        "Username or email already taken.",
        status.HTTP_409_CONFLICT,
    )

    ACCOUNT_INACTIVE = ErrorDetail(
        "ERR_ACCOUNT_INACTIVE",
        "Account not activated. Email not verified.",
        status.HTTP_403_FORBIDDEN,
    )

    ACCOUNT_EXPIRED = ErrorDetail(
        "ERR_ACCOUNT_EXPIRED",
        "Account grace period expired. Please register again.",
        status.HTTP_400_BAD_REQUEST,
    )

    OLD_PASSWORD_SAME_AS_NEW = ErrorDetail(
        "ERR_OLD_PASSWORD_SAME_AS_NEW",
        "New password cannot be the same as the old password.",
        status.HTTP_400_BAD_REQUEST,
    )

    INVALID_VERIFICATION_TOKEN = ErrorDetail(
        "ERR_INVALID_VERIFICATION_TOKEN",
        "Invalid verification token.",
        status.HTTP_400_BAD_REQUEST,
    )

    INVALID_CURRENT_PASSWORD = ErrorDetail(
        "ERR_INVALID_CURRENT_PASSWORD",
        "Current password is incorrect.",
        status.HTTP_400_BAD_REQUEST,
    )

    EMPTY_FILE = ErrorDetail(
        "ERR_EMPTY_FILE",
        "Uploaded file is empty.",
        status.HTTP_400_BAD_REQUEST,
    )

    FILE_CORRUPTED = ErrorDetail(
        "ERR_FILE_CORRUPTED",
        "Uploaded file appears to be corrupted or unreadable.",
        status.HTTP_400_BAD_REQUEST,
    )

    INVALID_FILE_TYPE = ErrorDetail(
        "ERR_INVALID_FILE_TYPE",
        "Invalid file type.",
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    )

    TOO_LARGE_FILE = ErrorDetail(
        "ERR_TOO_LARGE_FILE",
        "File size exceeds the maximum allowed.",
        status.HTTP_413_CONTENT_TOO_LARGE,
    )

    @property
    def status_code(self):  # pragma: no cover
        return self.value.status_code

    @property
    def error_code(self):
        return self.value.code

    @property
    def message(self):
        return self.value.message

    @property
    def detail(self):  # pragma: no cover
        return {
            "error_code": self.value.code,
            "message": self.value.message,
        }


# 3. The Unified Exception Class
class AppException(HTTPException):
    def __init__(
        self,
        error: AppError,
        message: str | None = None,
        extra: dict | None = None,
        headers: dict | None = None,
    ):
        """
        Raises an exception based on the AppError enum.
        Usage: raise AppException(AppError.NOT_FOUND)
        """
        self.error = error

        final_message = message or error.value.message

        super().__init__(
            status_code=error.value.status_code,
            detail={
                "error_code": error.value.code,
                "message": final_message,
                "extra": extra or {},
            },
            headers=headers,
        )
