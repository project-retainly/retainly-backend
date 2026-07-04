from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.settings import settings


async def create_test_database():
    url = settings.ASYNC_DATABASE_URL
    base_url, db_name = url.rsplit("/", 1)

    admin_engine = create_async_engine(
        base_url + "/postgres",
        isolation_level="AUTOCOMMIT",
    )

    try:
        async with admin_engine.begin() as conn:
            await conn.execute(text(f"CREATE DATABASE {db_name}"))
    except Exception as e:
        if "already exists" in str(e).lower():
            pass
        else:
            raise
    finally:
        await admin_engine.dispose()
