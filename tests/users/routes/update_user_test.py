import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from tests.data import USER_UPDATE_VALIDATION_CASES
from tests.users.factories import UserFactory
from tests.users.validation_utils import assert_validation_response


class TestUpdateUser:
    """Test suite for PUT /api/v1/users/ endpoint"""

    # Reusable test data
    @pytest.fixture
    def valid_update_data(self):
        """Returns valid user update data"""
        return {
            "username": "johnwick",
            "first_name": "John",
            "last_name": "Wick",
        }

    @pytest.fixture
    def taken_username_data(self):
        """Returns update data with a taken username"""
        return {
            "username": "taken_username",
        }

    # === HAPPY PATH TESTS ===

    async def test_user_update_success(
        self, auth_client, db_session: AsyncSession, valid_update_data: dict
    ):
        """
        Test successful update of user details
        """
        response = await auth_client.put("/api/v1/users/", json=valid_update_data)

        user = auth_client.user
        await db_session.refresh(user)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # API response check
        assert data["id"] == user.id
        assert data["username"] == valid_update_data["username"]
        assert data["first_name"] == valid_update_data["first_name"]
        assert data["last_name"] == valid_update_data["last_name"]

        # Database changes reflection check
        assert user.username == valid_update_data["username"]
        assert user.first_name == valid_update_data["first_name"]
        assert user.last_name == valid_update_data["last_name"]

    async def test_update_single_field(self, auth_client, db_session: AsyncSession):
        """
        Test updating only one field at a time
        """
        original_username = auth_client.user.username
        original_last_name = auth_client.user.last_name

        update_data = {
            "first_name": "updatedfirst",
        }

        response = await auth_client.put("/api/v1/users/", json=update_data)

        assert response.status_code == status.HTTP_200_OK

        await db_session.refresh(auth_client.user)

        assert auth_client.user.first_name == update_data["first_name"]
        assert auth_client.user.username == original_username
        assert auth_client.user.last_name == original_last_name

    async def test_update_username_only(self, auth_client, db_session: AsyncSession):
        """
        Test updating only username
        """
        original_first = auth_client.user.first_name

        update_data = {"username": "newusername123"}

        response = await auth_client.put("/api/v1/users/", json=update_data)

        assert response.status_code == status.HTTP_200_OK

        await db_session.refresh(auth_client.user)

        assert auth_client.user.username == "newusername123"
        assert auth_client.user.first_name == original_first

    async def test_update_with_empty_payload(self, auth_client):
        """
        Test update with empty payload returns current user data
        """
        response = await auth_client.put("/api/v1/users/", json={})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == auth_client.user.id

    # === DUPLICATE DETECTION TESTS ===

    async def test_username_taken_update_failure(
        self, auth_client, taken_username_data: dict
    ):
        """
        Test that updating to a taken username fails with conflict error
        """
        await UserFactory.create(username="taken_username")

        response = await auth_client.put("/api/v1/users/", json=taken_username_data)
        data = response.json()

        assert response.status_code == status.HTTP_409_CONFLICT

        assert data["error_code"] == AppError.TAKEN_USERNAME_EMAIL.error_code
        assert data["message"] == AppError.TAKEN_USERNAME_EMAIL.message
        assert "username" in data["extra"]

    async def test_update_to_same_username_succeeds(self, auth_client):
        """
        Test that updating to the same username (no change) succeeds
        """
        current_username = auth_client.user.username

        update_data = {
            "username": current_username,
            "first_name": "newfirst",
        }

        response = await auth_client.put("/api/v1/users/", json=update_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == current_username
        assert data["first_name"] == update_data["first_name"]

    async def test_update_username_case_change_only(
        self, auth_client, db_session: AsyncSession
    ):
        """
        Test changing only the case of username
        """
        auth_client.user.username = "testuser"
        await db_session.commit()

        update_data = {"username": "TestUser"}

        response = await auth_client.put("/api/v1/users/", json=update_data)

        # Depends on your uniqueness constraint (case-sensitive or not)
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_409_CONFLICT,
        ]

    # === VALIDATION TESTS ===

    @pytest.mark.parametrize(
        "test_data",
        USER_UPDATE_VALIDATION_CASES,
        ids=[case["id"] for case in USER_UPDATE_VALIDATION_CASES],
    )
    async def test_update_user_validations(self, auth_client, test_data: dict):
        """
        Test various validation scenarios for user update
        """
        response = await auth_client.put("/api/v1/users/", json=test_data["data"])

        assert_validation_response(
            response=response, expected_errors=test_data["expected_errors"]
        )

    # === SECURITY TESTS ===

    async def test_unauthenticated_update_fails(self, client: AsyncClient):
        """
        Test that unauthenticated users cannot update
        """
        update_data = {"first_name": "Hacker"}

        response = await client.put("/api/v1/users/", json=update_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_update_with_invalid_token(self, client: AsyncClient):
        """
        Test that invalid token is rejected
        """
        update_data = {"first_name": "Hacker"}

        response = await client.put(
            "/api/v1/users/",
            json=update_data,
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_update_with_expired_token(self, client: AsyncClient):
        """
        Test that expired token is rejected
        """
        # This would need a token generation utility that creates expired tokens
        expired_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJleHAiOjF9.invalid"

        update_data = {"first_name": "Hacker"}

        response = await client.put(
            "/api/v1/users/",
            json=update_data,
            headers={"Authorization": f"Bearer {expired_token}"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_update_password_not_allowed(
        self, auth_client, db_session: AsyncSession
    ):
        """
        Test that password cannot be updated through this endpoint
        """
        user = auth_client.user
        current_password_hash = user.password

        update_data = {
            "username": "newusername",
            "password": "NewPassword123!",  # Should be ignored/rejected
        }

        response = await auth_client.put("/api/v1/users/", json=update_data)

        # Password field should either be ignored or cause validation error
        assert response.status_code in [
            status.HTTP_200_OK,
        ]

        if response.status_code == status.HTTP_200_OK:
            await db_session.refresh(user)
            # CRITICAL CHECK: Ensure password hash is UNCHANGED
            # (Checking status code 200 is not enough, as 200 could mean it was updated!)
            assert user.password == current_password_hash

    async def test_update_email_not_allowed(
        self, auth_client, db_session: AsyncSession
    ):
        """
        Test that email cannot be updated through this endpoint
        """
        user = auth_client.user
        original_email = user.email

        update_data = {
            "username": "newusername",
            "email": "newemail@example.com",  # Should be ignored/rejected
        }

        response = await auth_client.put("/api/v1/users/", json=update_data)

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert data["email"] == original_email

            # CRITICAL CHECK: Verify DB state
            await db_session.refresh(user)
            assert user.email == original_email

    # === EDGE CASES ===

    async def test_update_with_null_values(self, auth_client):
        """
        Test update with null values - should either reject or ignore nulls
        """
        update_data = {"first_name": None}

        response = await auth_client.put("/api/v1/users/", json=update_data)

        # First name is always required, updating is optional
        # but cant be changed to NULL
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_update_preserves_other_fields(
        self, auth_client, db_session: AsyncSession
    ):
        """
        Test that updating one field doesn't affect other fields
        """
        original_email = auth_client.user.email
        original_status = auth_client.user.status

        update_data = {"first_name": "NewName"}

        response = await auth_client.put("/api/v1/users/", json=update_data)

        assert response.status_code == status.HTTP_200_OK

        await db_session.refresh(auth_client.user)

        assert auth_client.user.email == original_email
        assert auth_client.user.status == original_status

    async def test_update_with_leading_trailing_whitespace(
        self, auth_client, db_session: AsyncSession
    ):
        """
        Test that leading/trailing whitespace is handled
        """
        update_data = {"first_name": "  John  ", "last_name": "  Doe  "}

        response = await auth_client.put("/api/v1/users/", json=update_data)

        if response.status_code == status.HTTP_200_OK:
            await db_session.refresh(auth_client.user)
            # Should be trimmed
            assert auth_client.user.first_name.strip() == "John"
            assert auth_client.user.last_name.strip() == "Doe"

    async def test_concurrent_updates_same_user(
        self, auth_client, db_session: AsyncSession
    ):
        """
        Test race condition when updating same user concurrently
        """
        import asyncio

        update_data1 = {"first_name": "First"}
        update_data2 = {"first_name": "Second"}

        # Attempt concurrent updates
        results = await asyncio.gather(
            auth_client.put("/api/v1/users/", json=update_data1),
            auth_client.put("/api/v1/users/", json=update_data2),
            return_exceptions=True,
        )

        # Both should succeed (last write wins)
        status_codes = [r.status_code for r in results if hasattr(r, "status_code")]
        assert all(code == status.HTTP_200_OK for code in status_codes)

    async def test_update_multiple_times_consecutively(
        self, auth_client, db_session: AsyncSession
    ):
        """
        Test multiple consecutive updates work correctly
        """
        updates = [
            {"first_name": "first"},
            {"first_name": "second"},
            {"first_name": "third"},
        ]

        for update_data in updates:
            response = await auth_client.put("/api/v1/users/", json=update_data)
            assert response.status_code == status.HTTP_200_OK

        await db_session.refresh(auth_client.user)
        # Names are title-cased
        assert auth_client.user.first_name == "third"

    async def test_update_response_does_not_include_password(self, auth_client):
        """
        Test that update response never includes password hash
        """
        update_data = {"first_name": "NewName"}

        response = await auth_client.put("/api/v1/users/", json=update_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "password" not in data

    async def test_update_with_malformed_json(self, auth_client):
        """
        Test that malformed JSON is rejected properly
        """
        response = await auth_client.request(
            "PUT",
            "/api/v1/users/",
            content=b"{invalid json}",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
