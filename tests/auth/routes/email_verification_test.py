import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status
from httpx import AsyncClient

from app.auth import constants
from app.auth.messages import AuthMessages
from app.users.utils import UserStatus
from tests.users.factories import UserFactory


class TestVerifyUserEmail:
    """Test suite for email verification endpoint."""

    BASE_URL = "/api/v1/auth/verify"

    @pytest.fixture
    async def pending_user(self):
        """Create a pending user for verification tests."""
        user = await UserFactory.create(status=UserStatus.PENDING)
        return user

    @pytest.fixture
    async def active_user(self):
        """Create an already active user."""
        user = await UserFactory.create(status=UserStatus.ACTIVE)
        return user

    @pytest.fixture
    async def expired_user(self):
        """Create an expired user."""
        user = await UserFactory.create(status=UserStatus.EXPIRED)
        return user

    @pytest.fixture
    async def deleted_user(self):
        """Create a deleted user."""
        user = await UserFactory.create(status=UserStatus.DELETED)
        return user

    async def create_verification_token(
        self,
        fake_redis_client,
        user_id: int,
        issued_at: int,
        token: str = "valid_token",
    ):
        """Helper to create a verification token in Redis."""
        redis_key = f"{constants.VERIFICATION_PREFIX}{token}"
        data = json.dumps({"user_id": user_id, "issued_at": issued_at})
        await fake_redis_client.set(redis_key, data)

    # ====================
    # HAPPY PATH TESTS
    # ====================

    @pytest.mark.asyncio
    async def test_verify_email_success(
        self,
        client: AsyncClient,
        pending_user,
        fake_redis_client,
        db_session,
        disable_rate_limiting,
    ):
        """Test successful email verification for a pending user."""
        # Arrange
        token = "valid_verification_token"
        issued_at = int(pending_user.created_at.timestamp())
        await self.create_verification_token(
            fake_redis_client, pending_user.id, issued_at, token
        )

        # Act
        response = await client.get(f"{self.BASE_URL}/{token}")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "message" in data
        assert (
            "success" in data["message"].lower()
            or "verified" in data["message"].lower()
        )

        # Verify user status changed to ACTIVE
        await db_session.refresh(pending_user)
        assert pending_user.status == UserStatus.ACTIVE

        # Verify token was deleted (one-time use)
        redis_key = f"{constants.VERIFICATION_PREFIX}{token}"
        token_exists = await fake_redis_client.get(redis_key)
        assert token_exists is None

    @pytest.mark.asyncio
    async def test_verify_already_active_user(
        self,
        client: AsyncClient,
        active_user,
        fake_redis_client,
        disable_rate_limiting,
    ):
        """Test verification of an already active user returns appropriate message."""
        # Arrange
        token = "token_for_active_user"
        issued_at = int(active_user.created_at.timestamp())
        await self.create_verification_token(
            fake_redis_client, active_user.id, issued_at, token
        )

        # Act
        response = await client.get(f"{self.BASE_URL}/{token}")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == AuthMessages.ACCOUNT_ALREADY_VERIFIED

        # Token should still be deleted
        redis_key = f"{constants.VERIFICATION_PREFIX}{token}"
        token_exists = await fake_redis_client.get(redis_key)
        assert token_exists is None

    # ====================
    # INVALID TOKEN TESTS
    # ====================

    @pytest.mark.asyncio
    async def test_verify_with_nonexistent_token(
        self, client: AsyncClient, disable_rate_limiting
    ):
        """Test verification with a token that doesn't exist in Redis."""
        # Act
        response = await client.get(f"{self.BASE_URL}/nonexistent_token")

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_verify_with_corrupted_token_data_missing_user_id(
        self, client: AsyncClient, fake_redis_client, disable_rate_limiting
    ):
        """Test verification with corrupted token data (missing user_id)."""
        # Arrange
        token = "corrupted_token_no_user_id"
        redis_key = f"{constants.VERIFICATION_PREFIX}{token}"
        # Missing user_id field
        corrupted_data = json.dumps({"issued_at": 1234567890})
        await fake_redis_client.set(redis_key, corrupted_data)

        # Act
        response = await client.get(f"{self.BASE_URL}/{token}")

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Verify corrupted token was cleaned up
        token_exists = await fake_redis_client.get(redis_key)
        assert token_exists is None

    @pytest.mark.asyncio
    async def test_verify_with_corrupted_token_data_missing_issued_at(
        self, client: AsyncClient, fake_redis_client, disable_rate_limiting
    ):
        """Test verification with corrupted token data (missing issued_at)."""
        # Arrange
        token = "corrupted_token_no_issued_at"
        redis_key = f"{constants.VERIFICATION_PREFIX}{token}"
        # Missing issued_at field
        corrupted_data = json.dumps({"user_id": 123})
        await fake_redis_client.set(redis_key, corrupted_data)

        # Act
        response = await client.get(f"{self.BASE_URL}/{token}")

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Verify corrupted token was cleaned up
        token_exists = await fake_redis_client.get(redis_key)
        assert token_exists is None

    @pytest.mark.asyncio
    async def test_verify_with_invalid_json_token(
        self, client: AsyncClient, fake_redis_client, disable_rate_limiting
    ):
        """Test verification with token containing invalid JSON."""
        # Arrange
        token = "invalid_json_token"
        redis_key = f"{constants.VERIFICATION_PREFIX}{token}"
        await fake_redis_client.set(redis_key, "not valid json{{{")

        # Act
        response = await client.get(f"{self.BASE_URL}/{token}")

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Verify corrupted token was cleaned up
        token_exists = await fake_redis_client.get(redis_key)
        assert token_exists is None

    @pytest.mark.asyncio
    async def test_verify_with_non_integer_user_id(
        self, client: AsyncClient, fake_redis_client, disable_rate_limiting
    ):
        """Test verification with non-integer user_id in token."""
        # Arrange
        token = "token_with_string_user_id"
        redis_key = f"{constants.VERIFICATION_PREFIX}{token}"
        invalid_data = json.dumps(
            {
                "user_id": "not_an_integer",
                "issued_at": 1234567890,
            }
        )
        await fake_redis_client.set(redis_key, invalid_data)

        # Act
        response = await client.get(f"{self.BASE_URL}/{token}")

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Verify corrupted token was cleaned up
        token_exists = await fake_redis_client.get(redis_key)
        assert token_exists is None

    @pytest.mark.asyncio
    async def test_verify_with_non_integer_issued_at(
        self, client: AsyncClient, fake_redis_client, disable_rate_limiting
    ):
        """Test verification with non-integer issued_at in token."""
        # Arrange
        token = "token_with_string_issued_at"
        redis_key = f"{constants.VERIFICATION_PREFIX}{token}"
        invalid_data = json.dumps({"user_id": 123, "issued_at": "not_an_integer"})
        await fake_redis_client.set(redis_key, invalid_data)

        # Act
        response = await client.get(f"{self.BASE_URL}/{token}")

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Verify corrupted token was cleaned up
        token_exists = await fake_redis_client.get(redis_key)
        assert token_exists is None

    # ====================
    # USER NOT FOUND TESTS
    # ====================

    @pytest.mark.asyncio
    async def test_verify_with_nonexistent_user_id(
        self, client: AsyncClient, fake_redis_client, disable_rate_limiting
    ):
        """Test verification with a user_id that doesn't exist in database."""
        # Arrange
        token = "token_for_nonexistent_user"
        nonexistent_user_id = 999999
        issued_at = int(datetime.now(timezone.utc).timestamp())
        await self.create_verification_token(
            fake_redis_client, nonexistent_user_id, issued_at, token
        )

        # Act
        response = await client.get(f"{self.BASE_URL}/{token}")

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Token should still be deleted (one-time use)
        redis_key = f"{constants.VERIFICATION_PREFIX}{token}"
        token_exists = await fake_redis_client.get(redis_key)
        assert token_exists is None

    # ====================
    # USER STATUS TESTS
    # ====================

    @pytest.mark.asyncio
    async def test_verify_expired_user_fails(
        self,
        client: AsyncClient,
        expired_user,
        fake_redis_client,
        db_session,
        disable_rate_limiting,
    ):
        """Test that expired users cannot be verified."""
        # Arrange
        token = "token_for_expired_user"
        issued_at = int(expired_user.created_at.timestamp())
        await self.create_verification_token(
            fake_redis_client, expired_user.id, issued_at, token
        )

        # Act
        response = await client.get(f"{self.BASE_URL}/{token}")

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Verify user status remains EXPIRED
        await db_session.refresh(expired_user)
        assert expired_user.status == UserStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_verify_deleted_user_fails(
        self,
        client: AsyncClient,
        deleted_user,
        fake_redis_client,
        db_session,
        disable_rate_limiting,
    ):
        """Test that deleted users cannot be verified."""
        # Arrange
        token = "token_for_deleted_user"
        issued_at = int(deleted_user.created_at.timestamp())
        await self.create_verification_token(
            fake_redis_client, deleted_user.id, issued_at, token
        )

        # Act
        response = await client.get(f"{self.BASE_URL}/{token}")

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Verify user status remains DELETED
        await db_session.refresh(deleted_user)
        assert deleted_user.status == UserStatus.DELETED

    # ====================
    # TOKEN INVALIDATION TESTS
    # ====================

    @pytest.mark.asyncio
    async def test_verify_with_old_token_after_user_update(
        self,
        client: AsyncClient,
        pending_user,
        fake_redis_client,
        db_session,
        disable_rate_limiting,
    ):
        """Test that tokens issued before user.updated_at are rejected."""
        # Arrange
        # Create a token with issued_at BEFORE the user's updated_at
        old_issued_at = int((pending_user.updated_at - timedelta(hours=1)).timestamp())
        token = "old_token"
        await self.create_verification_token(
            fake_redis_client, pending_user.id, old_issued_at, token
        )

        # Act
        response = await client.get(f"{self.BASE_URL}/{token}")

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Verify user status remains PENDING
        await db_session.refresh(pending_user)
        assert pending_user.status == UserStatus.PENDING

    @pytest.mark.asyncio
    async def test_verify_with_token_issued_exactly_at_updated_at(
        self,
        client: AsyncClient,
        pending_user,
        fake_redis_client,
        db_session,
        disable_rate_limiting,
    ):
        """Test that token issued exactly at updated_at timestamp is accepted."""
        # Arrange
        # Token issued at exactly the same time as updated_at
        issued_at = int(pending_user.updated_at.timestamp())
        token = "exact_time_token"
        await self.create_verification_token(
            fake_redis_client, pending_user.id, issued_at, token
        )

        # Act
        response = await client.get(f"{self.BASE_URL}/{token}")

        # Assert
        assert response.status_code == status.HTTP_200_OK

        # Verify user status changed to ACTIVE
        await db_session.refresh(pending_user)
        assert pending_user.status == UserStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_verify_with_future_token(
        self,
        client: AsyncClient,
        pending_user,
        fake_redis_client,
        db_session,
        disable_rate_limiting,
    ):
        """Test that tokens with future issued_at are accepted (should pass timestamp check)."""
        # Arrange
        future_issued_at = int(
            (pending_user.updated_at + timedelta(hours=1)).timestamp()
        )
        token = "future_token"
        await self.create_verification_token(
            fake_redis_client, pending_user.id, future_issued_at, token
        )

        # Act
        response = await client.get(f"{self.BASE_URL}/{token}")

        # Assert
        assert response.status_code == status.HTTP_200_OK

        # Verify user status changed to ACTIVE
        await db_session.refresh(pending_user)
        assert pending_user.status == UserStatus.ACTIVE

    # ====================
    # ONE-TIME TOKEN TESTS
    # ====================

    @pytest.mark.asyncio
    async def test_verify_token_cannot_be_reused(
        self,
        client: AsyncClient,
        pending_user,
        fake_redis_client,
        db_session,
        disable_rate_limiting,
    ):
        """Test that verification token can only be used once."""
        # Arrange
        token = "one_time_token"
        issued_at = int(pending_user.created_at.timestamp())
        await self.create_verification_token(
            fake_redis_client, pending_user.id, issued_at, token
        )

        # Act - First verification
        response1 = await client.get(f"{self.BASE_URL}/{token}")

        # Assert - First verification succeeds
        assert response1.status_code == status.HTTP_200_OK

        # Reset user to PENDING for second attempt
        pending_user.status = UserStatus.PENDING
        db_session.add(pending_user)
        await db_session.commit()

        # Act - Second verification with same token
        response2 = await client.get(f"{self.BASE_URL}/{token}")

        # Assert - Second verification fails
        assert response2.status_code == status.HTTP_400_BAD_REQUEST

    # ====================
    # RATE LIMITING TESTS
    # ====================

    @pytest.mark.asyncio
    async def test_verify_email_rate_limiting(
        self, client: AsyncClient, pending_user, fake_redis_client
    ):
        """Test that rate limiting is enforced (5 requests per 60 minutes)."""
        # Arrange
        token = "rate_limit_token"
        issued_at = int(pending_user.created_at.timestamp())

        # Act - Make 6 requests (limit is 5)
        responses = []
        for i in range(6):
            # Create a fresh token for each attempt
            current_token = f"{token}_{i}"
            await self.create_verification_token(
                fake_redis_client, pending_user.id, issued_at, current_token
            )
            response = await client.get(f"{self.BASE_URL}/{current_token}")
            responses.append(response)

        # Assert - First 5 should succeed or fail based on business logic, 6th should be rate limited
        # Note: The exact behavior depends on your rate limiter implementation
        # This test assumes the 6th request gets rate limited (429 status code)
        assert responses[-1].status_code == status.HTTP_429_TOO_MANY_REQUESTS

    # ====================
    # EDGE CASES
    # ====================

    @pytest.mark.asyncio
    async def test_verify_with_empty_token(
        self, client: AsyncClient, disable_rate_limiting
    ):
        """Test verification with empty token string."""
        # Act
        response = await client.get(f"{self.BASE_URL}/")

        # Assert - Should return 404 (not found route) or 400
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        ]  # Method not allowed or not found

    @pytest.mark.asyncio
    async def test_verify_with_very_long_token(
        self,
        client: AsyncClient,
        fake_redis_client,
        pending_user,
        disable_rate_limiting,
    ):
        """Test verification with an extremely long token string."""
        # Arrange
        long_token = "a" * 10000
        issued_at = int(pending_user.created_at.timestamp())
        await self.create_verification_token(
            fake_redis_client, pending_user.id, issued_at, long_token
        )

        # Act
        response = await client.get(f"{self.BASE_URL}/{long_token}")

        # Assert - Should handle gracefully
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_414_URI_TOO_LONG,
        ]  # 414 = URI Too Long

    @pytest.mark.asyncio
    async def test_verify_with_special_characters_in_token(
        self,
        client: AsyncClient,
        fake_redis_client,
        pending_user,
        disable_rate_limiting,
    ):
        """Test verification with special characters in token."""
        # Arrange
        special_token = "token-with_special.chars!@#"
        issued_at = int(pending_user.created_at.timestamp())
        await self.create_verification_token(
            fake_redis_client, pending_user.id, issued_at, special_token
        )

        # Act
        response = await client.get(f"{self.BASE_URL}/{special_token}")

        # Assert
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        ]

    @pytest.mark.asyncio
    async def test_verify_with_sql_injection_attempt(
        self, client: AsyncClient, disable_rate_limiting
    ):
        """Test that SQL injection attempts in token are safely handled."""
        # Arrange
        malicious_token = "'; DROP TABLE users; --"

        # Act
        response = await client.get(f"{self.BASE_URL}/{malicious_token}")

        # Assert - Should fail safely without SQL injection
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ]

    @pytest.mark.asyncio
    async def test_verify_concurrent_requests_same_token(
        self,
        client: AsyncClient,
        pending_user,
        fake_redis_client,
        db_session,
        disable_rate_limiting,
    ):
        """Test concurrent verification requests with the same token."""
        import asyncio

        # Arrange
        token = "concurrent_token"
        issued_at = int(pending_user.created_at.timestamp())
        await self.create_verification_token(
            fake_redis_client, pending_user.id, issued_at, token
        )

        # Act - Send concurrent requests
        tasks = [client.get(f"{self.BASE_URL}/{token}") for _ in range(3)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Assert - Only one should succeed (200), others should fail (400)
        success_count = sum(
            1
            for r in responses
            if not isinstance(r, Exception) and r.status_code == status.HTTP_200_OK
        )
        assert success_count == 1, "Only one concurrent request should succeed"

        # Verify user was only activated once
        await db_session.refresh(pending_user)
        assert pending_user.status == UserStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_verify_with_zero_user_id(
        self, client: AsyncClient, fake_redis_client, disable_rate_limiting
    ):
        """Test verification with user_id = 0."""
        # Arrange
        token = "zero_user_id_token"
        issued_at = int(datetime.now(timezone.utc).timestamp())
        await self.create_verification_token(fake_redis_client, 0, issued_at, token)

        # Act
        response = await client.get(f"{self.BASE_URL}/{token}")

        # Assert
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ]

    @pytest.mark.asyncio
    async def test_verify_with_negative_user_id(
        self, client: AsyncClient, fake_redis_client, disable_rate_limiting
    ):
        """Test verification with negative user_id."""
        # Arrange
        token = "negative_user_id_token"
        issued_at = int(datetime.now(timezone.utc).timestamp())
        await self.create_verification_token(fake_redis_client, -1, issued_at, token)

        # Act
        response = await client.get(f"{self.BASE_URL}/{token}")

        # Assert
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ]

    @pytest.mark.asyncio
    async def test_verify_with_negative_issued_at(
        self,
        client: AsyncClient,
        pending_user,
        fake_redis_client,
        disable_rate_limiting,
    ):
        """Test verification with negative issued_at timestamp."""
        # Arrange
        token = "negative_issued_at_token"
        await self.create_verification_token(
            fake_redis_client, pending_user.id, -1, token
        )

        # Act
        response = await client.get(f"{self.BASE_URL}/{token}")

        # Assert
        assert (
            response.status_code == status.HTTP_400_BAD_REQUEST
        )  # Should fail timestamp validation

    # ====================
    # BOUNDARY TESTS
    # ====================

    @pytest.mark.asyncio
    async def test_verify_with_max_int_user_id(
        self, client: AsyncClient, fake_redis_client, disable_rate_limiting
    ):
        """Test verification with maximum integer user_id."""
        # Arrange
        token = "max_int_token"
        max_int = 2147483647  # Max 32-bit signed integer
        issued_at = int(datetime.now(timezone.utc).timestamp())
        await self.create_verification_token(
            fake_redis_client, max_int, issued_at, token
        )

        # Act
        response = await client.get(f"{self.BASE_URL}/{token}")

        # Assert
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ]

    @pytest.mark.asyncio
    async def test_verify_with_timestamp_at_epoch(
        self,
        client: AsyncClient,
        pending_user,
        fake_redis_client,
        disable_rate_limiting,
    ):
        """Test verification with issued_at at Unix epoch (0)."""
        # Arrange
        token = "epoch_token"
        await self.create_verification_token(
            fake_redis_client, pending_user.id, 0, token
        )

        # Act
        response = await client.get(f"{self.BASE_URL}/{token}")

        # Assert
        assert (
            response.status_code == status.HTTP_400_BAD_REQUEST
        )  # Should fail as it's before user.updated_at
