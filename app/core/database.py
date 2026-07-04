from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .settings import settings


# 1. Base class for all models
class Base(DeclarativeBase):
    pass


# 2. Async engine for FastAPI
engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=settings.SQL_LOGS,
    pool_pre_ping=True,
)

# 3. Sync engine for Celery workers
celery_engine = create_engine(
    settings.SYNC_DATABASE_URL,
    echo=settings.SQL_LOGS,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# 4. Session factories
SessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)

CelerySessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=celery_engine,
    expire_on_commit=False,
)


# 5. Async dependency for FastAPI routes
async def get_db():
    """Async dependency that yields a database session for FastAPI routes."""
    async with SessionLocal() as db:
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()


# 6. Sync context manager for Celery tasks
@contextmanager
def get_celery_db():
    """Sync context manager that yields a database session for Celery tasks."""
    db = CelerySessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
