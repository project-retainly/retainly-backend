from datetime import datetime, timedelta, timezone

from app.auth.models import RefreshToken
from app.auth.services import AuthService
from app.core.settings import settings
from tests.users.factories import UserFactory


class TestCreateRefreshToken:
    """Tests for AuthService.create_refresh_token method."""

    async def test_creates_token_successfully(
        self, db_session, request_factory_agent_ipv4
    ):
        """Test successful creation of refresh token."""

        auth_service = AuthService(db=db_session)
        user = await UserFactory.create()

        mock_request = await request_factory_agent_ipv4()

        plaintext, stored = await auth_service.create_refresh_token(
            mock_request, user.id
        )

        assert plaintext is not None
        assert isinstance(plaintext, str)
        assert isinstance(stored, RefreshToken)
        assert stored.user_id == user.id

    async def test_sets_correct_expiry_time(
        self, db_session, request_factory_agent_ipv4
    ):
        """Test that expiry time is set correctly."""

        auth_service = AuthService(db=db_session)
        user = await UserFactory.create()

        mock_request = await request_factory_agent_ipv4()

        before = datetime.now(timezone.utc)
        _, stored = await auth_service.create_refresh_token(mock_request, user.id)
        after = datetime.now(timezone.utc)

        expected_min_expiry = before + timedelta(
            seconds=settings.REFRESH_TOKEN_EXPIRE_SECONDS
        )
        expected_max_expiry = after + timedelta(
            seconds=settings.REFRESH_TOKEN_EXPIRE_SECONDS
        )

        assert expected_min_expiry <= stored.expires_at <= expected_max_expiry

    async def test_stores_user_agent(self, db_session, request_factory_agent_ipv4):
        """Test that user agent is stored correctly."""

        auth_service = AuthService(db=db_session)
        user = await UserFactory.create()

        mock_request = await request_factory_agent_ipv4()
        request_agent = mock_request.headers.get("User-Agent")

        _, stored = await auth_service.create_refresh_token(mock_request, user.id)

        assert stored.user_agent == request_agent

    async def test_stores_ip_address(self, db_session, request_factory_agent_ipv4):
        """Test that IP address is stored correctly."""

        auth_service = AuthService(db=db_session)
        user = await UserFactory.create()

        mock_request = await request_factory_agent_ipv4()
        request_ip = mock_request.client.host

        _, stored = await auth_service.create_refresh_token(mock_request, user.id)

        assert stored.ip_address == request_ip

    async def test_handles_missing_user_agent(
        self, db_session, request_factory_agent_ipv4
    ):
        """Test handling when user agent is missing."""

        auth_service = AuthService(db=db_session)
        user = await UserFactory.create()

        mock_request = await request_factory_agent_ipv4()
        mock_request.headers = {}

        _, stored = await auth_service.create_refresh_token(mock_request, user.id)

        assert stored.user_agent is None

    async def test_handles_missing_client(self, db_session, request_factory_agent_ipv4):
        """Test handling when request.client is None."""

        auth_service = AuthService(db=db_session)
        user = await UserFactory.create()

        mock_request = await request_factory_agent_ipv4()
        mock_request.client = None

        _, stored = await auth_service.create_refresh_token(mock_request, user.id)

        assert stored.ip_address is None

    async def test_adds_token_to_database(self, db_session, request_factory_agent_ipv4):
        """Test that token is added to database session."""

        auth_service = AuthService(db=db_session)
        user = await UserFactory.create()

        mock_request = await request_factory_agent_ipv4()
        _, stored = await auth_service.create_refresh_token(mock_request, user.id)

        # Verify token is in the session (it's added but not yet committed)
        assert stored in db_session

    async def test_returns_tuple_with_both_tokens(
        self, db_session, request_factory_agent_ipv4
    ):
        """Test that method returns tuple of (plaintext, stored_token)."""

        auth_service = AuthService(db=db_session)
        user = await UserFactory.create()

        mock_request = await request_factory_agent_ipv4()

        result = await auth_service.create_refresh_token(mock_request, user.id)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)  # plaintext token
        assert isinstance(result[1], RefreshToken)  # stored token
