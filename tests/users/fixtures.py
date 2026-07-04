import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from .factories import UserFactory


@pytest.fixture(scope="function")
async def create_user(db_session: AsyncSession):
    async def _create_user(**kwargs):
        user = UserFactory.build(**kwargs)
        db_session.add(user)
        await db_session.commit()

        return user

    return _create_user
