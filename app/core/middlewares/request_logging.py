import time
import uuid
from contextvars import ContextVar

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logger import get_logger
from app.core.settings import settings

# Context variable to store request_id across async calls
request_id_var: ContextVar[str] = ContextVar("request_id", default=None)

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = str(uuid.uuid4())

        # Store in context variable (accessible anywhere in this request)
        request_id_var.set(request_id)

        # Also store in request state (optional, for dependencies)
        request.state.request_id = request_id

        # Start timer
        start_time = time.perf_counter()

        agent = (
            request.headers.get("user-agent")
            if settings.DEBUG
            else request.headers.get("x-forwarded-for")
        )
        client_ip = request.client.host if request.client else None

        # Log request start
        logger.info(
            "request_started",
            agent=agent,
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client=client_ip,
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Log request completion
            logger.info(
                "request_completed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                client=client_ip,
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            logger.error(
                "request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
                error_type=type(e).__name__,  # Add exception type
                client=client_ip,
                duration_ms=duration_ms,
                exc_info=True,  # ← This captures the full stack trace!
            )
            raise


def get_request_id() -> str:
    """Get current request ID from context"""
    return request_id_var.get()
