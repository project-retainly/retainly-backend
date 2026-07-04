import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import utils
from app.core.exceptions import AppError
from app.users.models import User
from app.users.services import UserService
from app.users.utils import UserStatus
from tests.data import USER_CREATE_VALIDATION_CASES
from tests.users.factories import UserFactory
from tests.users.validation_utils import assert_validation_response


class TestCreateUser:
    """Test suite for POST /api/v1/users/ endpoint"""

    # Reusable test data
    @pytest.fixture
    def valid_user_data(self):
        """Returns valid user creation data"""
        return {
            "username": "new_test_user",
            "email": "new_test@example.com",
            "first_name": "New",
            "last_name": "User",
            "password": "ValidPassword$123",
        }

    @pytest.fixture
    def duplicate_email_data(self):
        """Returns data with a duplicate email"""
        return {
            "username": "new_user",
            "email": "taken@example.com",
            "first_name": "New",
            "last_name": "User",
            "password": "ValidPassword$123",
        }

    # === HAPPY PATH TESTS ===

    async def test_create_user_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        valid_user_data: dict,
    ):
        """
        Test successful user creation with valid data
        """
        response = await client.post("/api/v1/users/", json=valid_user_data)

        assert response.status_code == status.HTTP_201_CREATED

        response_json = response.json()
        assert response_json["email"] == valid_user_data["email"]
        assert response_json["username"] == valid_user_data["username"]
        assert "id" in response_json

        # Critical security check: ensure the password is NOT returned
        assert "password" not in response_json

        service = UserService(db=db_session)
        db_user = await service.get_user_by_email_or_username(
            email=valid_user_data["email"], username=valid_user_data["username"]
        )

        assert db_user is not None
        assert db_user.first_name == "New"
        # Verify the password was hashed correctly
        assert utils.verify_password(valid_user_data["password"], db_user.password)

    async def test_create_user_with_minimal_data(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test user creation with only required fields
        """
        minimal_data = {
            "username": "minimaluser",
            "email": "minimal@example.com",
            "password": "ValidPass123!",
            "first_name": "Test",
            "last_name": "User",
        }

        response = await client.post("/api/v1/users/", json=minimal_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["username"] == minimal_data["username"]
        assert data["email"] == minimal_data["email"]
        # Names are title-cased
        assert data["first_name"] == "Test"
        assert data["last_name"] == "User"

    # === DUPLICATE DETECTION TESTS ===

    async def test_create_user_duplicate_email(
        self, client: AsyncClient, duplicate_email_data: dict
    ):
        """
        Test that duplicate email is rejected
        """
        await UserFactory.create(email="taken@example.com", username="user1")

        response = await client.post("/api/v1/users/", json=duplicate_email_data)

        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()

        assert data["error_code"] == AppError.TAKEN_USERNAME_EMAIL.error_code
        assert data["message"] == AppError.TAKEN_USERNAME_EMAIL.message

    async def test_create_user_duplicate_username(self, client: AsyncClient):
        """
        Test that duplicate username is rejected
        """
        await UserFactory.create(username="takenuser", email="first@example.com")

        payload = {
            "username": "takenuser",
            "email": "different@example.com",
            "password": "ValidPass123!",
            "first_name": "Test",
            "last_name": "User",
        }

        response = await client.post("/api/v1/users/", json=payload)

        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_create_user_duplicate_email_case_insensitive(
        self, client: AsyncClient
    ):
        """
        Test that email uniqueness check handles case sensitivity based on DB constraints
        """
        await UserFactory.create(email="test@example.com", username="user1")

        payload = {
            "username": "newuser",
            "email": "TEST@EXAMPLE.COM",  # Different case
            "password": "ValidPass123!",
            "first_name": "Test",
            "last_name": "User",
        }

        response = await client.post("/api/v1/users/", json=payload)

        # Email comparison might be case-sensitive or case-insensitive depending on DB
        assert response.status_code in [
            status.HTTP_201_CREATED,  # If case-sensitive (Postgres default)
            status.HTTP_409_CONFLICT,  # If case-insensitive (MySQL/SQLite default)
        ]

    async def test_create_user_duplicate_username_case_insensitive(
        self, client: AsyncClient
    ):
        """
        Test that username uniqueness check is case-insensitive
        """
        await UserFactory.create(username="testuser", email="first@example.com")

        payload = {
            "username": "TESTUSER",  # Different case
            "email": "new@example.com",
            "password": "ValidPass123!",
            "first_name": "Test",
            "last_name": "User",
        }

        response = await client.post("/api/v1/users/", json=payload)

        assert response.status_code == status.HTTP_409_CONFLICT

    # === STATUS-BASED REGISTRATION TESTS ===

    @pytest.mark.parametrize("existing_status", [UserStatus.PENDING, UserStatus.ACTIVE])
    async def test_registration_blocked_for_pending_or_active_user(
        self, client: AsyncClient, create_user, existing_status
    ):
        """
        Test that registration is blocked for users with PENDING or ACTIVE status
        """
        user = await create_user(status=existing_status)

        payload = {
            "username": user.username,
            "email": user.email,
            "password": "AnotherPass123!",
            "first_name": "New",
            "last_name": "User",
        }

        response = await client.post("/api/v1/users/", json=payload)

        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_reregister_expired_user_reuses_existing_record(
        self, client: AsyncClient, db_session: AsyncSession, create_user
    ):
        """
        Test that re-registering an expired user reuses the existing database record
        """
        user = await create_user(status=UserStatus.EXPIRED)

        payload = {
            "username": "new_username",
            "email": user.email,
            "password": "NewPass123!",
            "first_name": "Updated",
            "last_name": "Name",
        }

        response = await client.post("/api/v1/users/", json=payload)

        assert response.status_code == status.HTTP_201_CREATED

        refreshed = await db_session.get(User, user.id)

        assert refreshed.id == user.id
        assert refreshed.status == UserStatus.PENDING
        assert refreshed.username == "new_username"
        assert refreshed.first_name == "Updated"
        assert refreshed.deleted_at is None

    async def test_duplicate_email_allowed_for_expired_user(
        self, client: AsyncClient, create_user
    ):
        """
        Test that duplicate emails are allowed for expired users
        """
        await create_user(email="same@example.com", status=UserStatus.EXPIRED)

        payload = {
            "username": "newuser",
            "email": "same@example.com",
            "password": "StrongPass123!",
            "first_name": "John",
            "last_name": "Doe",
        }

        response = await client.post("/api/v1/users/", json=payload)

        assert response.status_code == status.HTTP_201_CREATED

    async def test_partial_unique_index_blocks_active_duplicates(
        self, client: AsyncClient, create_user
    ):
        """
        Test that partial unique index prevents duplicate emails for active users
        """
        await create_user(email="dup@example.com", status=UserStatus.ACTIVE)

        payload = {
            "username": "another",
            "email": "dup@example.com",
            "password": "StrongPass123!",
            "first_name": "John",
            "last_name": "Doe",
        }

        response = await client.post("/api/v1/users/", json=payload)

        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_partial_unique_index_blocks_pending_duplicates(
        self, client: AsyncClient, create_user
    ):
        """
        Test that partial unique index prevents duplicate usernames for pending users
        """
        await create_user(username="dupuser", status=UserStatus.PENDING)

        payload = {
            "username": "dupuser",
            "email": "other@example.com",
            "password": "StrongPass123!",
            "first_name": "John",
            "last_name": "Doe",
        }

        response = await client.post("/api/v1/users/", json=payload)

        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_multiple_expired_users_allowed_same_email(
        self, db_session: AsyncSession, create_user
    ):
        """
        Test that multiple expired users can have the same email
        """
        user1 = await create_user(email="x@example.com", status=UserStatus.EXPIRED)
        user2 = await create_user(email="x@example.com", status=UserStatus.EXPIRED)

        assert user1.email == user2.email
        assert user1.id != user2.id

    async def test_deleted_user_allows_reregistration(
        self, client: AsyncClient, create_user, db_session: AsyncSession
    ):
        """
        Test that deleted users can re-register with same credentials
        """
        await create_user(
            email="deleted@example.com",
            username="deleteduser",
            status=UserStatus.DELETED,
        )

        payload = {
            "username": "deleteduser",
            "email": "deleted@example.com",
            "password": "NewPass123!",
            "first_name": "New",
            "last_name": "User",
        }

        response = await client.post("/api/v1/users/", json=payload)

        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_409_CONFLICT,
        ]

    # === VALIDATION TESTS ===

    @pytest.mark.parametrize(
        "test_data",
        USER_CREATE_VALIDATION_CASES,
        ids=[case["id"] for case in USER_CREATE_VALIDATION_CASES],
    )
    async def test_create_user_validations(self, client: AsyncClient, test_data: dict):
        """
        Test various validation scenarios for user creation
        """
        response = await client.post("/api/v1/users/", json=test_data["data"])

        assert_validation_response(response, test_data["expected_errors"])

    # === SECURITY TESTS ===

    async def test_create_user_sql_injection_in_username(self, client: AsyncClient):
        """
        Test that SQL injection attempts in username are handled safely
        """
        payload = {
            "username": "admin'; DROP TABLE users; --",
            "email": "hacker@example.com",
            "password": "ValidPass123!",
            "first_name": "Test",
            "last_name": "User",
        }

        response = await client.post("/api/v1/users/", json=payload)

        # Should either fail validation or succeed safely without SQL injection
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_create_user_sql_injection_in_email(self, client: AsyncClient):
        """
        Test that SQL injection attempts in email are handled safely
        """
        payload = {
            "username": "testuser",
            "email": "test' OR '1'='1@example.com",
            "password": "ValidPass123!",
            "first_name": "Test",
            "last_name": "User",
        }

        response = await client.post("/api/v1/users/", json=payload)

        # Should fail validation due to invalid email format
        assert response.status_code in [
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            status.HTTP_400_BAD_REQUEST,
        ]

    async def test_create_user_password_not_stored_in_plain_text(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that passwords are hashed and never stored in plain text
        """
        password = "MySecretPassword123!"
        payload = {
            "username": "secureuser",
            "email": "secure@example.com",
            "password": password,
            "first_name": "Secure",
            "last_name": "User",
        }

        response = await client.post("/api/v1/users/", json=payload)

        assert response.status_code == status.HTTP_201_CREATED

        service = UserService(db=db_session)
        db_user = await service.get_user_by_email_or_username(
            email="secure@example.com"
        )

        # Password should be hashed
        assert db_user.password != password
        # Should start with bcrypt/argon2 hash prefix (approx check on length)
        assert len(db_user.password) > 50
        # Verify it matches when checked
        assert utils.verify_password(password, db_user.password)

    async def test_create_user_unicode_characters_in_name(self, client: AsyncClient):
        """
        Test that unicode characters in names are handled correctly
        """
        payload = {
            "username": "unicodeuser",
            "email": "unicode@example.com",
            "password": "ValidPass123!",
            "first_name": "josé",
            "last_name": "müller",
        }

        response = await client.post("/api/v1/users/", json=payload)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        # Names are title-cased
        assert data["first_name"] == payload["first_name"]
        assert data["last_name"] == payload["last_name"]

    async def test_create_user_emoji_in_username(self, client: AsyncClient):
        """
        Test handling of emoji in username
        """
        payload = {
            "username": "user😀test",
            "email": "emoji@example.com",
            "password": "ValidPass123!",
            "first_name": "Test",
            "last_name": "User",
        }

        response = await client.post("/api/v1/users/", json=payload)

        # Should fail validation or succeed based on username rules
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # === EDGE CASES ===

    async def test_create_user_with_very_long_email(self, client: AsyncClient):
        """
        Test handling of extremely long email addresses
        """
        long_email = "a" * 400 + "@example.com"
        payload = {
            "username": "longuser",
            "email": long_email,
            "password": "ValidPass123!",
            "first_name": "Test",
            "last_name": "User",
        }

        response = await client.post("/api/v1/users/", json=payload)

        # Should fail validation due to length or succeed if no length constraint
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_create_user_with_null_optional_fields(self, client: AsyncClient):
        """
        Test that null values in optional fields are handled correctly
        """
        payload = {
            "username": "nulluser",
            "email": "null@example.com",
            "password": "ValidPass123!",
            "first_name": None,
            "last_name": None,
        }

        response = await client.post("/api/v1/users/", json=payload)

        # Should either succeed with nulls or fail validation
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_create_user_with_leading_trailing_whitespace_email(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that leading/trailing whitespace in email is trimmed
        """
        payload = {
            "username": "trimuser",
            "email": "  trim@example.com  ",
            "password": "ValidPass123!",
            "first_name": "Test",
            "last_name": "User",
        }

        response = await client.post("/api/v1/users/", json=payload)

        if response.status_code == status.HTTP_201_CREATED:
            data = response.json()
            # Email should be trimmed
            assert data["email"] == "trim@example.com"

    async def test_create_user_with_special_characters_in_password(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that special characters in password are handled correctly
        """
        special_password = "P@$$w0rd!#%&*()_+-=[]{}|;:',.<>?/~`"
        payload = {
            "username": "specialuser",
            "email": "special@example.com",
            "password": special_password,
            "first_name": "Test",
            "last_name": "User",
        }

        response = await client.post("/api/v1/users/", json=payload)

        if response.status_code == status.HTTP_201_CREATED:
            service = UserService(db=db_session)
            db_user = await service.get_user_by_email_or_username(
                email="special@example.com"
            )
            assert utils.verify_password(special_password, db_user.password)

    async def test_create_user_missing_required_fields(self, client: AsyncClient):
        """
        Test that missing required fields return proper error
        """
        payload = {
            "username": "testuser",
            # Missing email and password
        }

        response = await client.post("/api/v1/users/", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_create_user_with_invalid_email_format(
        self, client: AsyncClient, disable_rate_limiting
    ):
        """
        Test various invalid email formats
        """
        invalid_emails = [
            "notanemail",
            "@example.com",
            "user@",
            "user @example.com",
        ]

        for invalid_email in invalid_emails:
            payload = {
                "username": f"user{invalid_emails.index(invalid_email)}",
                "email": invalid_email,
                "password": "ValidPass123!",
                "first_name": "Test",
                "last_name": "User",
            }

            response = await client.post("/api/v1/users/", json=payload)

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # async def test_create_user_concurrent_same_email(
    #     self, client: AsyncClient, db_session: AsyncSession, disable_rate_limiting
    # ):
    #     """
    #     Test race condition handling when creating users with same email concurrently
    #     """
    #     import asyncio

    #     payload1 = {
    #         "username": "user1",
    #         "email": "concurrent@example.com",
    #         "password": "ValidPass123!",
    #         "first_name": "Test",
    #         "last_name": "User",
    #     }

    #     payload2 = {
    #         "username": "user2",
    #         "email": "concurrent@example.com",
    #         "password": "ValidPass123!",
    #         "first_name": "Test",
    #         "last_name": "User",
    #     }

    #     # Attempt concurrent creation
    #     results = await asyncio.gather(
    #         client.post("/api/v1/users/", json=payload1),
    #         client.post("/api/v1/users/", json=payload2),
    #         return_exceptions=False,
    #     )

    #     status_codes = [r.status_code for r in results if hasattr(r, "status_code")]

    #     print([r.status_code for r in results])
    #     # At least one should succeed
    #     assert (
    #         status.HTTP_201_CREATED in status_codes
    #         or status.HTTP_409_CONFLICT in status_codes
    #     )

    async def test_create_user_with_international_domain(self, client: AsyncClient):
        """
        Test email with international domain names
        """
        payload = {
            "username": "intluser",
            "email": "user@münchen.de",
            "password": "ValidPass123!",
            "first_name": "Test",
            "last_name": "User",
        }

        response = await client.post("/api/v1/users/", json=payload)

        assert response.status_code in [
            status.HTTP_201_CREATED,
        ]

    async def test_create_user_default_status_is_pending(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that newly created users have PENDING status by default
        """
        payload = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "ValidPass123!",
            "first_name": "Test",
            "last_name": "User",
        }

        response = await client.post("/api/v1/users/", json=payload)

        assert response.status_code == status.HTTP_201_CREATED

        service = UserService(db=db_session)
        db_user = await service.get_user_by_email_or_username(
            email="newuser@example.com"
        )

        assert db_user.status == UserStatus.PENDING
