import json
import logging
import sys

import structlog

from app.core.settings import settings


def add_request_id(logger, method_name, event_dict):
    """
    Processor that automatically adds request_id to every log.
    This is the magic that makes request tracing work!
    """
    # Import here to avoid circular dependency
    from app.core.middlewares.request_logging import get_request_id

    request_id = get_request_id()
    if request_id:
        event_dict["request_id"] = request_id

    return event_dict


def setup_logging():
    """
    Complete production logging setup.
    Call this ONCE when your app starts.
    """

    # Decide if we're in production or development
    is_production = settings.DEBUG is False

    # Custom processor for pretty JSON in dev
    def pretty_json_renderer(_, __, event_dict):
        if is_production:
            # Production: compact JSON (one line)
            return json.dumps(event_dict)
        else:
            # Development: pretty JSON (indented, readable)
            return json.dumps(event_dict, indent=2)

    def get_rendering_processor():
        if is_production:
            return structlog.processors.JSONRenderer()
        else:
            return structlog.dev.ConsoleRenderer(colors=True)
            # return pretty_json_renderer

    # Configure structlog
    structlog.configure(
        processors=[
            # Add log level (INFO, ERROR, etc)
            structlog.stdlib.add_log_level,
            # Add timestamp
            structlog.processors.TimeStamper(fmt="iso"),
            add_request_id,  # Add request_id to every log
            # Add file/line info for debugging
            structlog.processors.CallsiteParameterAdder(
                [
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            ),
            # If there's an exception, format it nicely
            structlog.processors.format_exc_info,
            # Production: JSON for machines
            # Development: Pretty colors for humans
            get_rendering_processor(),
        ],
        # Use standard library logger underneath
        logger_factory=structlog.stdlib.LoggerFactory(),
        # Cache the logger for performance
        cache_logger_on_first_use=True,
    )

    # Make Python's standard logging use our setup too
    # (This catches FastAPI/Uvicorn logs)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)

    # Then ONLY enable DEBUG for YOUR app
    logging.getLogger("app").setLevel(logging.DEBUG)

    # Silence noisy libraries
    # logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
    logging.getLogger("multipart.multipart").setLevel(logging.WARNING)
    logging.getLogger("passlib").setLevel(logging.WARNING)


# Helper to get a logger anywhere in your code
def get_logger(name: str = None):
    """Get a logger instance. Call this in any file."""
    return structlog.get_logger(name)
