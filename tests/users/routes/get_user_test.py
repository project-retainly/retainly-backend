from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.users.factories import UserFactory


class TestGetUser:
    """Test suite for GET /api/v1/users/ endpoint"""

    # === HAPPY PATH TESTS ===

    async def test_get_user_success(self, auth_client):
        """
        Test successful retrieval of current user details
        """
        response = await auth_client.get("/api/v1/users/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response contains user data
        assert "id" in data
        assert data["id"] == auth_client.user.id
        assert data["email"] == auth_client.user.email
        assert data["username"] == auth_client.user.username

        # Ensure password is not exposed
        assert "password" not in data

    async def test_get_user_returns_all_public_fields(self, auth_client):
        """
        Test that all expected public fields are returned
        """
        response = await auth_client.get("/api/v1/users/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        expected_fields = ["id", "email", "username"]
        for field in expected_fields:
            assert field in data

    async def test_get_user_with_complete_profile(self, auth_client):
        """
        Test getting user with all optional fields filled via API update
        """
        # Update via API to avoid lazy loading issues
        update_data = {"first_name": "john", "last_name": "doe"}
        update_response = await auth_client.put("/api/v1/users/", json=update_data)
        assert update_response.status_code == status.HTTP_200_OK

        response = await auth_client.get("/api/v1/users/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["first_name"] == update_data["first_name"]
        assert data["last_name"] == update_data["last_name"]

    async def test_get_user_multiple_times(self, auth_client):
        """
        Test that getting user info multiple times returns consistent data
        """
        response1 = await auth_client.get("/api/v1/users/")
        response2 = await auth_client.get("/api/v1/users/")

        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK

        assert response1.json() == response2.json()

    # === AUTHENTICATION TESTS ===

    async def test_get_user_unauthenticated(self, client: AsyncClient):
        """
        Test that unauthenticated requests are rejected
        """
        response = await client.get("/api/v1/users/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_user_with_invalid_token(self, client: AsyncClient):
        """
        Test that requests with invalid tokens are rejected
        """
        response = await client.get(
            "/api/v1/users/",
            headers={"Authorization": "Bearer invalid_token_here"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_user_with_malformed_token(self, client: AsyncClient):
        """
        Test that malformed tokens are rejected
        """
        malformed_tokens = [
            "Bearer ",
            "Bearer",
            "invalid",
            "Bearer token with spaces",
            "",
        ]

        for token in malformed_tokens:
            response = await client.get(
                "/api/v1/users/",
                headers={"Authorization": token},
            )

            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_user_without_bearer_prefix(self, client: AsyncClient):
        """
        Test that token without 'Bearer' prefix is rejected
        """
        response = await client.get(
            "/api/v1/users/",
            headers={"Authorization": "some_token_without_bearer"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_user_with_expired_token(self, client: AsyncClient):
        """
        Test that expired tokens are rejected
        """
        expired_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJleHAiOjF9.invalid"

        response = await client.get(
            "/api/v1/users/",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # === SECURITY TESTS ===

    async def test_get_user_password_never_returned(
        self, auth_client, db_session: AsyncSession
    ):
        """
        Test that password hash is never included in response
        """
        # Make sure user has a password in DB
        assert auth_client.user.password is not None

        response = await auth_client.get("/api/v1/users/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Password should never be in response
        assert "password" not in data
        assert "password_hash" not in data
        assert "hashed_password" not in data

    async def test_get_user_only_returns_own_data(
        self, auth_client, db_session: AsyncSession
    ):
        """
        Test that user can only see their own data, not other users'
        """
        # Create another user
        other_user = await UserFactory.create(
            username="otheruser", email="other@example.com"
        )

        response = await auth_client.get("/api/v1/users/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should return authenticated user's data
        assert data["id"] == auth_client.user.id
        assert data["id"] != other_user.id

    async def test_get_user_no_sql_injection_through_token(self, client: AsyncClient):
        """
        Test that SQL injection attempts through token are handled
        """
        injection_token = "Bearer 1' OR '1'='1"

        response = await client.get(
            "/api/v1/users/",
            headers={"Authorization": injection_token},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # === EDGE CASES ===

    async def test_get_user_after_concurrent_update(self, auth_client):
        """
        Test that GET returns fresh data after updates
        """
        # Update user data via API
        update_data = {"first_name": "updated"}
        update_response = await auth_client.put("/api/v1/users/", json=update_data)
        assert update_response.status_code == status.HTTP_200_OK

        response = await auth_client.get("/api/v1/users/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["first_name"] == update_data["first_name"]

    async def test_get_user_response_content_type(self, auth_client):
        """
        Test that response has correct content type
        """
        response = await auth_client.get("/api/v1/users/")

        assert response.status_code == status.HTTP_200_OK
        assert "application/json" in response.headers["content-type"]

    async def test_get_user_case_insensitive_header(self, auth_client):
        """
        Test that authorization header is case-insensitive
        """
        # Get the token from auth_client
        token = auth_client.headers.get("Authorization", "").replace("Bearer ", "")

        # Try with different case variations
        response = await auth_client.get(
            "/api/v1/users/",
            headers={"authorization": f"Bearer {token}"},  # lowercase
        )

        assert response.status_code == status.HTTP_200_OK

    async def test_get_user_with_query_parameters_ignored(self, auth_client):
        """
        Test that query parameters are ignored (if any)
        """
        response = await auth_client.get("/api/v1/users/?user_id=999&admin=true")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should still return authenticated user's data
        assert data["id"] == auth_client.user.id

    async def test_get_user_idempotent(self, auth_client):
        """
        Test that GET is idempotent (multiple calls don't change state)
        """
        responses = []
        for _ in range(5):
            response = await auth_client.get("/api/v1/users/")
            responses.append(response.json())

        # All responses should be identical
        assert all(r == responses[0] for r in responses)

    async def test_get_user_does_not_modify_database(self, auth_client):
        """
        Test that GET request doesn't modify any database state
        """
        # Get initial state
        initial_response = await auth_client.get("/api/v1/users/")
        assert initial_response.status_code == status.HTTP_200_OK
        initial_data = initial_response.json()

        # Make another GET request
        response = await auth_client.get("/api/v1/users/")

        assert response.status_code == status.HTTP_200_OK

        # Data should be identical
        assert response.json() == initial_data

    async def test_get_user_performance_multiple_requests(self, auth_client):
        """
        Test that multiple GET requests complete successfully
        """
        import asyncio

        # Make multiple concurrent requests
        responses = await asyncio.gather(
            *[auth_client.get("/api/v1/users/") for _ in range(10)]
        )

        # All should succeed
        assert all(r.status_code == status.HTTP_200_OK for r in responses)

    async def test_get_user_with_extra_headers(self, auth_client):
        """
        Test that extra headers don't interfere with request
        """
        response = await auth_client.get(
            "/api/v1/users/",
            headers={
                "X-Custom-Header": "value",
                "User-Agent": "TestClient",
            },
        )

        assert response.status_code == status.HTTP_200_OK
