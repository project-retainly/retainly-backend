from unittest.mock import Mock

from fastapi import Request, Response

from app.auth.services import AuthService
from app.core.settings import settings
from tests.auth.factories import RefreshTokenFactory
from tests.users.factories import UserFactory


class TestRevokeRefreshToken:
    """Tests for AuthService.revoke_refresh_token method."""

    async def test_revokes_token_successfully(
        self, db_session, request_factory_agent_ipv4
    ):
        """Test successful token revocation."""
        auth_service = AuthService(db=db_session)
        user = await UserFactory.create()
        stored_token = await RefreshTokenFactory.create(user=user)

        mock_request = await request_factory_agent_ipv4()
        mock_response = Mock(spec=Response)
        token_replaced_by = "new_token_hash"
        reason = "token_rotation"

        await auth_service.revoke_refresh_token(
            mock_request, mock_response, stored_token, token_replaced_by, reason
        )

        # Verify revoke was called
        assert stored_token.revoked_at is not None
        assert stored_token.revocation_reason == reason

    async def test_deletes_cookie_with_correct_parameters(self, db_session):
        """Test that cookie is deleted with correct parameters."""

        auth_service = AuthService(db=db_session)
        stored_token = await RefreshTokenFactory.create()

        mock_request = Mock(spec=Request)
        mock_response = Mock(spec=Response)
        token_replaced_by = "hash"
        reason = "revocation"

        await auth_service.revoke_refresh_token(
            mock_request, mock_response, stored_token, token_replaced_by, reason
        )

        mock_response.delete_cookie.assert_called_once_with(
            key="refresh_token",
            path="/api/v1/auth/",
            secure=not settings.DEBUG,
            httponly=True,
            samesite="strict",
        )

    async def test_handles_different_revocation_reasons(
        self, db_session, request_factory_agent_ipv4
    ):
        """Test handling of different revocation reasons."""
        auth_service = AuthService(db=db_session)
        user = await UserFactory.create()

        reasons = [
            "user_logout",
            "token_rotation",
            "security_breach",
            "admin_action",
        ]

        for reason in reasons:
            stored_token = await RefreshTokenFactory.create(user=user)

            mock_request = await request_factory_agent_ipv4()
            mock_response = Mock(spec=Response)

            await auth_service.revoke_refresh_token(
                mock_request, mock_response, stored_token, "hash", reason
            )

            assert stored_token.revocation_reason == reason
