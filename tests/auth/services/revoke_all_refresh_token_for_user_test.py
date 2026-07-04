from unittest.mock import Mock

from fastapi import Request, Response

from app.auth.services import AuthService
from app.core.settings import settings
from tests.auth.factories import RefreshTokenFactory
from tests.users.factories import UserFactory


class TestRevokeAllRefreshTokensForUser:
    """Tests for AuthService.revoke_all_refresh_tokens_for_user method."""

    async def test_revokes_all_active_tokens(
        self, db_session, request_factory_agent_ipv4
    ):
        """Test that all active tokens are revoked."""
        auth_service = AuthService(db=db_session)
        user = await UserFactory.create()

        # Create multiple active tokens
        token1 = await RefreshTokenFactory.create(user=user)
        token2 = await RefreshTokenFactory.create(user=user)
        token3 = await RefreshTokenFactory.create(user=user)

        mock_request = await request_factory_agent_ipv4()
        mock_response = Mock(spec=Response)
        reason = "password_change"

        await auth_service.revoke_all_refresh_tokens_for_user(
            mock_request, mock_response, user.id, reason
        )
        await db_session.commit()

        await db_session.refresh(token1)
        await db_session.refresh(token2)
        await db_session.refresh(token3)

        # Verify all tokens were revoked
        assert token1.revoked_at is not None
        assert token2.revoked_at is not None
        assert token3.revoked_at is not None

    async def test_handles_no_active_tokens(self, db_session):
        """Test handling when user has no active tokens."""

        auth_service = AuthService(db=db_session)
        user = await UserFactory.create()

        mock_request = Mock(spec=Request)
        mock_response = Mock(spec=Response)
        reason = "security_check"

        # Should not raise an error
        await auth_service.revoke_all_refresh_tokens_for_user(
            mock_request, mock_response, user.id, reason
        )

        # Should still delete cookie
        mock_response.delete_cookie.assert_called_once()

    async def test_deletes_cookie(self, db_session):
        """Test that refresh token cookie is deleted."""

        auth_service = AuthService(db=db_session)
        user = await UserFactory.create()

        mock_request = Mock(spec=Request)
        mock_response = Mock(spec=Response)
        reason = "user_logout"

        await auth_service.revoke_all_refresh_tokens_for_user(
            mock_request, mock_response, user.id, reason
        )

        mock_response.delete_cookie.assert_called_once_with(
            key="refresh_token",
            path="/api/v1/auth/",
            secure=not settings.DEBUG,
            httponly=True,
            samesite="strict",
        )

    async def test_only_revokes_active_non_expired_tokens(
        self, db_session, request_factory_agent_ipv4
    ):
        """Test that only active and non-expired tokens are revoked."""

        user = await UserFactory.create()

        # Create active token
        active_token = await RefreshTokenFactory.create(user=user)

        # Create already revoked token
        revoked_token = await RefreshTokenFactory.create(user=user, revoked=True)

        # Create expired token
        expired_token = await RefreshTokenFactory.create(user=user, expired=True)

        # Get initial revoked_at values
        initial_revoked_at = revoked_token.revoked_at

        auth_service = AuthService(db=db_session)
        mock_request = await request_factory_agent_ipv4()
        mock_response = Mock(spec=Response)
        reason = "security"

        await auth_service.revoke_all_refresh_tokens_for_user(
            mock_request, mock_response, user.id, reason
        )
        await db_session.commit()

        await db_session.refresh(active_token)
        await db_session.refresh(revoked_token)
        await db_session.refresh(expired_token)

        # Only active_token should have been revoked
        assert active_token.revoked_at is not None
        # Already revoked token should not be re-revoked
        assert revoked_token.revoked_at == initial_revoked_at
        # Expired token should not be revoked
        assert expired_token.revoked_at is None

    async def test_doesnt_affect_other_users_tokens(
        self, db_session, request_factory_agent_ipv4
    ):
        """Test that revoking tokens for one user doesn't affect another user's tokens."""

        auth_service = AuthService(db=db_session)

        user1 = await UserFactory.create()
        user2 = await UserFactory.create()

        token_user1 = await RefreshTokenFactory.create(user=user1)
        token_user2 = await RefreshTokenFactory.create(user=user2)

        mock_response = Mock(spec=Response)
        mock_request = await request_factory_agent_ipv4()
        reason = "user1_logout"

        await auth_service.revoke_all_refresh_tokens_for_user(
            mock_request, mock_response, user1.id, reason
        )
        await db_session.commit()

        await db_session.refresh(token_user1)
        await db_session.refresh(token_user2)

        # Only user1's token should be revoked
        assert token_user1.revoked_at is not None
        assert token_user2.revoked_at is None
