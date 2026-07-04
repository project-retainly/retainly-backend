from unittest.mock import patch

import pytest

from app.core.exceptions import AppError, AppException
from app.users.utils import UserStatus
from tests.users.factories import UserFactory


class TestUpdatePasswordForUserService:
    @pytest.mark.asyncio
    async def test_update_password_success(self, db_session):
        from app.auth.services import AuthService

        service = AuthService(db=db_session)
        user = await UserFactory.create(status=UserStatus.ACTIVE)
        old_password = user.password
        new_password = "NewSecurePassword123!"

        await service.update_password_for_user(user, new_password)

        assert user.password != old_password

    @pytest.mark.asyncio
    async def test_update_password_same_as_old(self, db_session):
        from app.auth.services import AuthService

        service = AuthService(db=db_session)
        user = await UserFactory.create(status=UserStatus.ACTIVE)
        old_password_hash = user.password

        with patch("app.auth.utils.get_password_hash", return_value=old_password_hash):
            with pytest.raises(AppException) as exc_info:
                await service.update_password_for_user(user, "SamePassword")

            assert exc_info.value.error == AppError.OLD_PASSWORD_SAME_AS_NEW
