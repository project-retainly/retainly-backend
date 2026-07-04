from app.auth.services import AuthService
from tests.auth.factories import RefreshTokenFactory


class TestGetRefreshToken:
    """Tests for AuthService.get_refresh_token method."""

    async def test_returns_none_when_token_not_found(self, db_session):
        """Test that None is returned when token is not found."""
        auth_service = AuthService(db=db_session)
        hashed_token = "nonexistent_token_hash"

        result = await auth_service.get_refresh_token(hashed_token)

        assert result is None

    async def test_query_uses_correct_hash(self, db_session):
        """Test that the query uses the correct token hash."""

        auth_service = AuthService(db=db_session)

        # Create multiple tokens
        token1 = await RefreshTokenFactory.create()
        token2 = await RefreshTokenFactory.create()
        # await db_session.flush()

        # Should retrieve only the specific token
        result = await auth_service.get_refresh_token(token1.token_hash)

        assert result.id == token1.id
        assert result.id != token2.id
