import pytest

from app.users.models import UserStatus
from app.users.services import UserService
from tests.users.factories import UserFactory


class TestGetActiveUserByEmailService:
    @pytest.mark.asyncio
    async def test_get_active_user_by_email_success(self, db_session):
        user = await UserFactory.create(status=UserStatus.ACTIVE)
        await db_session.commit()

        service = UserService(db=db_session)
        result = await service.get_active_user_by_email(email=user.email)

        assert result is not None
        assert result.id == user.id
        assert result.email == user.email
        assert result.status == UserStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_get_active_user_by_email_pending_user(self, db_session):
        user = await UserFactory.create(status=UserStatus.PENDING)
        await db_session.commit()

        service = UserService(db=db_session)
        result = await service.get_active_user_by_email(email=user.email)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_user_by_email_deleted_user(self, db_session):
        user = await UserFactory.create(status=UserStatus.DELETED)
        await db_session.commit()

        service = UserService(db=db_session)
        result = await service.get_active_user_by_email(email=user.email)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_user_by_email_expired_user(self, db_session):
        user = await UserFactory.create(status=UserStatus.EXPIRED)
        await db_session.commit()

        service = UserService(db=db_session)
        result = await service.get_active_user_by_email(email=user.email)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_user_by_email_nonexistent(self, db_session):
        service = UserService(db=db_session)
        result = await service.get_active_user_by_email(email="nonexistent@example.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_user_by_email_case_sensitive(self, db_session):
        await UserFactory.create(status=UserStatus.ACTIVE, email="test@example.com")
        await db_session.commit()

        service = UserService(db=db_session)
        result = await service.get_active_user_by_email(email="TEST@EXAMPLE.COM")

        assert result is None
