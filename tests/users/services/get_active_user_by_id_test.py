import pytest

from app.users.utils import UserStatus
from tests.users.factories import UserFactory


class TestGetActiveUserByIdService:
    @pytest.mark.asyncio
    async def test_get_active_user_success(self, db_session):
        from app.users.services import UserService

        service = UserService(db=db_session)
        user = await UserFactory.create(status=UserStatus.ACTIVE)

        result = await service.get_active_user_by_id(user.id)

        assert result is not None
        assert result.id == user.id
        assert result.status == UserStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_get_active_user_not_found(self, db_session):
        from app.users.services import UserService

        service = UserService(db=db_session)

        result = await service.get_active_user_by_id(99999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_user_not_active_status(self, db_session):
        from app.users.services import UserService

        service = UserService(db=db_session)
        user = await UserFactory.create(status=UserStatus.PENDING)

        result = await service.get_active_user_by_id(user.id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_user_deleted_status(self, db_session):
        from app.users.services import UserService

        service = UserService(db=db_session)
        user = await UserFactory.create(status=UserStatus.DELETED)

        result = await service.get_active_user_by_id(user.id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_user_expired_status(self, db_session):
        from app.users.services import UserService

        service = UserService(db=db_session)
        user = await UserFactory.create(status=UserStatus.EXPIRED)

        result = await service.get_active_user_by_id(user.id)

        assert result is None
