import json
from collections import defaultdict

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logger import get_logger
from app.core.settings import settings

from .exceptions import AppError

logger = get_logger(__name__)


async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catch-all for unexpected exceptions.
    Logs full stack trace for debugging.
    """
    logger.error(
        "unhandled_exception",
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        path=request.url.path,
        method=request.method,
        exc_info=True,  # Captures full stack trace
    )

    if settings.DEBUG:
        raise exc

    return JSONResponse(
        status_code=500,
        content={
            "error_code": "ERR_INTERNAL_SERVER",
            "message": "Internal server error",
            "extra": {},
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Handle HTTP exceptions (4xx and 5xx).
    Logs based on severity level.
    """
    # Determine log level based on status code
    if exc.status_code >= 500:
        # Server errors - always log as ERROR with stack trace
        logger.error(
            "http_exception_5xx",
            status_code=exc.status_code,
            path=request.url.path,
            method=request.method,
            detail=str(exc.detail),
            exc_info=True,  # Include stack trace for 5xx errors
        )

        if settings.DEBUG:
            raise exc
    else:
        # Client errors (4xx) - log as WARNING (expected errors)
        logger.warning(
            "http_exception_4xx",
            status_code=exc.status_code,
            path=request.url.path,
            method=request.method,
            detail=str(exc.detail),
        )

    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail
        if isinstance(exc.detail, dict)
        else {
            "error_code": "ERR_GENERIC",
            "message": str(exc.detail),
            "extra": {},
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle request validation errors (422).
    Logs validation failures for monitoring.
    """
    error_list = exc.errors()
    formatted_errors = defaultdict(list)

    for error in error_list:
        field_name = error["loc"][-1]
        msg = error["msg"]

        if field_name == "email":
            clean_msg = "Invalid email." + msg[msg.find(":") + 1 :]
        else:
            # Remove Pydantic's default prefix
            clean_msg = error["msg"].replace("Value error, ", "")

        # Try to parse the message as a list of errors
        try:
            parsed_msg = json.loads(clean_msg)
            if isinstance(parsed_msg, list):
                formatted_errors[field_name].extend(parsed_msg)
            else:
                formatted_errors[field_name].append(clean_msg)
        except (json.JSONDecodeError, TypeError):
            formatted_errors[field_name].append(clean_msg)

    content = {
        "error_code": AppError.VALIDATION_ERROR.error_code,
        "message": AppError.VALIDATION_ERROR.message,
        "errors": formatted_errors,
    }

    logger.warning(
        "validation_error",
        path=request.url.path,
        method=request.method,
        error_count=len(error_list),
        errors=content,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=content
    )
