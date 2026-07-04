import logging
from typing import AsyncGenerator

import pytest
import structlog
from faker import Faker
from fakeredis import FakeAsyncRedis
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.auth.rate_limiter import CompositeRateLimiter
from app.core import models_registry  # noqa: F401
from app.core import redis as redis_module
from app.core.database import Base, get_db
from app.core.main import app  # noqa: F401
from app.core.settings import settings
from tests.utils import create_test_database

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(50)  # 50 = CRITICAL
)
# silence httpx request logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@pytest.fixture(scope="session", autouse=True)
async def setup_test_db():
    await create_test_database()
    yield


@pytest.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(
        settings.ASYNC_DATABASE_URL,
        connect_args={"command_timeout": 5},
    )

    # Create tables for this specific test run
    async with engine.begin() as conn:
        await conn.execute(text("DROP TYPE IF EXISTS user_status CASCADE"))
        await conn.execute(
            text("""
            CREATE TYPE user_status AS ENUM (
                'pending', 'active', 'expired', 'deleted'
            )
        """)
        )
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Tear down tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    connection = await test_engine.connect()
    transaction = await connection.begin()

    # expire_on_commit=False is CRITICAL for tests to avoid "Zombie Objects"
    session_factory = async_sessionmaker(bind=connection, expire_on_commit=False)
    session = session_factory()

    yield session

    # 2. Cleanup
    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest.fixture(scope="function", autouse=True)
async def fake_redis_client(monkeypatch):
    fake = FakeAsyncRedis(decode_responses=True)

    monkeypatch.setattr(redis_module, "client", fake)

    yield fake

    await fake.flushdb()
    await fake.aclose()


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides = {}


@pytest.fixture(scope="function", autouse=True)
async def setup_factories(db_session):
    """Configure all factories with the test database session."""
    from tests.auth.factories import RefreshTokenFactory
    from tests.media.factories import MediaFactory
    from tests.posts.factories import PostFactory
    from tests.users.factories import UserFactory

    # Set the session for all factories
    UserFactory._meta.sqlalchemy_session = db_session
    PostFactory._meta.sqlalchemy_session = db_session
    MediaFactory._meta.sqlalchemy_session = db_session
    RefreshTokenFactory._meta.sqlalchemy_session = db_session

    yield

    # Clean up (reset to None after test)
    UserFactory._meta.sqlalchemy_session = None
    PostFactory._meta.sqlalchemy_session = None
    MediaFactory._meta.sqlalchemy_session = None
    RefreshTokenFactory._meta.sqlalchemy_session = None


pytest_plugins = [
    "tests.users.fixtures",
    "tests.auth.fixtures",
]


@pytest.fixture(autouse=True)
def mock_send_verification_email_task(monkeypatch):
    class FakeTask:
        def __init__(self):
            self.called = False

        def delay(self, *args, **kwargs):
            self.called = True

    task = FakeTask()

    PATCH_PATHS = [
        "app.auth.routes.send_verification_email_task",
        "app.users.routes.send_verification_email_task",
        # add more if needed
    ]

    for path in PATCH_PATHS:
        monkeypatch.setattr(path, task, raising=False)

    return task


@pytest.fixture(autouse=True)
def mock_send_password_reset_email_task(monkeypatch):
    class FakeTask:
        def __init__(self):
            self.called = False

        def delay(self, *args, **kwargs):
            self.called = True

    task = FakeTask()

    PATCH_PATHS = [
        "app.auth.routes.send_password_reset_email_task",
        # add more if needed
    ]

    for path in PATCH_PATHS:
        monkeypatch.setattr(path, task, raising=False)

    return task


@pytest.fixture(autouse=True)
def mock_send_password_change_notification_email_task(monkeypatch):
    class FakeTask:
        def __init__(self):
            self.called = False

        def delay(self, *args, **kwargs):
            self.called = True

    task = FakeTask()

    PATCH_PATHS = [
        "app.auth.routes.send_password_change_notification_email_task",
        # add more if needed
    ]

    for path in PATCH_PATHS:
        monkeypatch.setattr(path, task, raising=False)

    return task


@pytest.fixture
def disable_rate_limiting(monkeypatch):
    """
    Patches the RateLimiter to instantly return True without hitting Redis.
    Use this in functional tests where you don't care about rate limits.
    """

    async def mock_call(self, request: Request, auth_cxt=None):
        return True

    # We patch the class method itself, so ALL instances are disabled
    monkeypatch.setattr(CompositeRateLimiter, "__call__", mock_call)


@pytest.fixture(scope="function")
async def faker():
    return Faker()


@pytest.fixture(autouse=True)
def setup_pagination():
    from fastapi_pagination import add_pagination

    from app.core.main import app

    add_pagination(app)
    yield


@pytest.fixture()
def celery_sync_db():
    from app.core.database import get_celery_db

    with get_celery_db() as db:
        yield db
