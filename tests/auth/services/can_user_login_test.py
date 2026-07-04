from unittest.mock import Mock

import pytest

from app.auth.services import AuthService
from app.core.exceptions import AppError, AppException
from app.users.utils import UserStatus


class TestAssertUserCanLogin:
    """Tests for AuthService.assert_user_can_login method."""

    async def test_allows_active_user_to_login(self, db_session):
        auth_service = AuthService(db=db_session)
        mock_user = Mock(status=UserStatus.ACTIVE)

        result = await auth_service.assert_user_can_login(mock_user)
        assert result is True

    @pytest.mark.parametrize(
        "status, expected_error",
        [
            (UserStatus.PENDING, AppError.AUTH_FAILED),
            (UserStatus.EXPIRED, AppError.AUTH_FAILED),
            (UserStatus.DELETED, AppError.AUTH_FAILED),
            ("UNKNOWN_STATUS", AppError.INTERNAL_ERROR),
            (None, AppError.INTERNAL_ERROR),
        ],
        ids=["pending", "expired", "deleted", "unknown", "none"],
    )
    async def test_rejects_invalid_user_statuses(
        self, db_session, status, expected_error
    ):
        auth_service = AuthService(db=db_session)
        mock_user = Mock(status=status)

        with pytest.raises(AppException) as exc_info:
            await auth_service.assert_user_can_login(mock_user)

        exc_info.value.error == expected_error
