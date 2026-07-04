from pathlib import Path
from typing import ClassVar

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )
    REGISTRATION_OPEN: bool
    BACKEND_DIR: ClassVar[Path] = Path(__file__).resolve().parent.parent.parent

    APP_DIR: ClassVar[Path] = BACKEND_DIR / "app"

    # --- MEDIA STORAGE SETTINGS ---

    # default to local "static" folder, can be overridden by env var
    MEDIA_DIR: Path = BACKEND_DIR / "STORAGE"

    # If True, will use S3 or other cloud storage instead of local filesystem
    USE_CLOUD_STORAGE: bool

    # --- DEFAULT SETTINGS ---
    DEBUG: bool
    SQL_LOGS: bool
    BACKEND_HOST: str
    BACKEND_PORT: int
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "https://gajeet.dev",
        "https://www.gajeet.dev",
    ]

    @computed_field
    @property
    def BACKEND_HOST_URL(self) -> str:
        if self.DEBUG:
            return f"http://{self.BACKEND_HOST}:{self.BACKEND_PORT}"

        # In production, make sure BACKEND_HOST includes 'https://'
        # or add it here manually: f"https://{self.BACKEND_HOST}"
        return f"http://{self.BACKEND_HOST}"

    # --- MAIL SETTINGS ---
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str

    # --- SECURITY ---
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    UNVERIFIED_USER_GRACE_PERIOD_HOURS: int
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int

    # --- REDIS ---
    REDIS_PROTOCOL: str
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: str | int
    REDIS_USERNAME: str
    REDIS_PASSWORD: str

    # --- DATABASE ---
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    DB_HOST: str
    DB_PORT: int

    @computed_field
    @property
    def REFRESH_TOKEN_EXPIRE_SECONDS(self) -> int:
        return self.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

    @computed_field
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Async SQLAlchemy connection string"""
        return (
            f"postgresql+asyncpg://"
            f"{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD}@"
            f"{self.DB_HOST}:"
            f"{self.DB_PORT}/"
            f"{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def REDIS_URL(self) -> str:
        """Redis connection string"""
        auth = ""
        if self.REDIS_USERNAME and self.REDIS_PASSWORD:
            auth = f"{self.REDIS_USERNAME}:{self.REDIS_PASSWORD}@"
        elif self.REDIS_PASSWORD:
            auth = f":{self.REDIS_PASSWORD}@"
        return (
            f"{self.REDIS_PROTOCOL}://"
            f"{auth}"
            f"{self.REDIS_HOST}:"
            f"{self.REDIS_PORT}/"
            f"{self.REDIS_DB}"
        )

    @computed_field
    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Sync SQLAlchemy connection string for Celery workers"""
        return (
            f"postgresql+psycopg2://"
            f"{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD}@"
            f"{self.DB_HOST}:"
            f"{self.DB_PORT}/"
            f"{self.POSTGRES_DB}"
        )


settings = Settings()

if settings.DEBUG:
    print("--- Running in DEVELOPMENT Mode ---")
