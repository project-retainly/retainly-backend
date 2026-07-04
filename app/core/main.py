from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import add_pagination
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logger import setup_logging
from app.core.middlewares.request_logging import RequestLoggingMiddleware
from app.core.settings import settings
from app.media.utils import StaticDirs

from .apis import api_v1_router
from .handlers import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Create the Static folder if it doesn't exist
    # parents=True: Creates 'backend/static' if 'backend' was missing too
    # exist_ok=True: Doesn't crash if it already exists
    if not settings.USE_CLOUD_STORAGE:
        settings.MEDIA_DIR.mkdir(parents=True, exist_ok=True)

        app.mount(
            "/media",
            StaticFiles(directory=str(settings.MEDIA_DIR)),
            name="media",
        )

    # Subdirectories to create inside the Static folder
    directory_groups = [
        StaticDirs.Uploads,
        StaticDirs.Assets,
        StaticDirs.Exports,
    ]

    # Loop through each group and create every folder defined in it
    for group in directory_groups:
        # vars(group) gives us all attributes in the class
        for key, path_str in vars(group).items():
            # Skip python internal attributes (like __module__, __doc__)
            if not key.startswith("__"):
                (settings.MEDIA_DIR / path_str).mkdir(parents=True, exist_ok=True)

    yield  # App starts running here...


setup_logging()  # Set up logging before the app starts

app = FastAPI(
    title="Retainly Backend API",
    description="The API for the Retainly project.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)  # Add request logging middleware

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

add_pagination(app)

app.include_router(api_v1_router)
