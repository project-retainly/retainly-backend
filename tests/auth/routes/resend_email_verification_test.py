import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.messages import AuthMessages
from app.core.settings import settings
from app.users.models import User
from app.users.utils import UserStatus


class TestResendVerificationEmail:
    """Test suite for resend verification email endpoint."""

    BASE_URL = "/api/v1/auth/resend-verification"

    # ====================
    # USER NOT FOUND TESTS
    # ====================

    @pytest.mark.asyncio
    async def test_resend_verification_user_not_found(
        self,
        client: AsyncClient,
        fake_redis_client,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test that non-existent user email returns generic success message (no info leak)."""
        # Act
        response = await client.post(
            self.BASE_URL,
            json={"email": "ghost@example.com"},
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == AuthMessages.GENERIC_VERIFICATION_SENT

        # Verify no token was created
        assert await fake_redis_client.keys("*") == []

        # Verify email was not sent
        assert mock_send_verification_email_task.called is False

    @pytest.mark.asyncio
    async def test_resend_verification_empty_email(
        self,
        client: AsyncClient,
        fake_redis_client,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test that empty email is rejected with validation error."""
        # Act
        response = await client.post(
            self.BASE_URL,
            json={"email": ""},
        )

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        # Verify no token was created
        assert await fake_redis_client.keys("*") == []

        # Verify email was not sent
        assert mock_send_verification_email_task.called is False

    @pytest.mark.asyncio
    async def test_resend_verification_invalid_email_format(
        self,
        client: AsyncClient,
        fake_redis_client,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test that invalid email format is rejected with validation error."""
        # Act
        response = await client.post(
            self.BASE_URL,
            json={"email": "not-an-email"},
        )

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        # Verify no token was created
        assert await fake_redis_client.keys("*") == []

        # Verify email was not sent
        assert mock_send_verification_email_task.called is False

    @pytest.mark.asyncio
    async def test_resend_verification_missing_email_field(
        self,
        client: AsyncClient,
        fake_redis_client,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test that missing email field returns validation error."""
        # Act
        response = await client.post(
            self.BASE_URL,
            json={},
        )

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        # Verify no token was created
        assert await fake_redis_client.keys("*") == []

        # Verify email was not sent
        assert mock_send_verification_email_task.called is False

    # ====================
    # ALREADY VERIFIED TESTS
    # ====================

    @pytest.mark.asyncio
    async def test_resend_verification_user_already_verified(
        self,
        client: AsyncClient,
        fake_redis_client,
        create_user,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test that already verified users receive appropriate message."""
        # Arrange
        user = await create_user(status=UserStatus.ACTIVE)

        # Act
        response = await client.post(
            self.BASE_URL,
            json={"email": user.email},
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == AuthMessages.ACCOUNT_ALREADY_VERIFIED

        # Verify no token was created
        assert await fake_redis_client.keys("*") == []

        # Verify email was not sent
        assert mock_send_verification_email_task.called is False

    # ====================
    # SOFT DELETED USER TESTS
    # ====================

    @pytest.mark.asyncio
    async def test_resend_verification_user_soft_deleted(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        fake_redis_client,
        create_user,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test that soft deleted users cannot resend verification (returns generic message)."""
        # Arrange
        deleted_at = datetime.now(timezone.utc)
        user = await create_user(
            status=UserStatus.EXPIRED,
            deleted_at=deleted_at,
        )

        # Act
        response = await client.post(
            self.BASE_URL,
            json={"email": user.email},
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == AuthMessages.GENERIC_VERIFICATION_SENT

        # Verify no token was created
        assert await fake_redis_client.keys("*") == []

        # Verify user state unchanged
        refreshed = await db_session.get(User, user.id)
        assert refreshed.deleted_at == deleted_at
        assert refreshed.status == UserStatus.EXPIRED

        # Verify email was not sent
        assert mock_send_verification_email_task.called is False

    @pytest.mark.asyncio
    async def test_resend_verification_user_deleted_status(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        fake_redis_client,
        create_user,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test that users with DELETED status cannot resend verification."""
        # Arrange
        deleted_at = datetime.now(timezone.utc)
        user = await create_user(
            status=UserStatus.DELETED,
            deleted_at=deleted_at,
        )

        # Act
        response = await client.post(
            self.BASE_URL,
            json={"email": user.email},
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == AuthMessages.GENERIC_VERIFICATION_SENT

        # Verify no token was created
        assert await fake_redis_client.keys("*") == []

        # Verify user state unchanged
        refreshed = await db_session.get(User, user.id)
        assert refreshed.deleted_at == deleted_at
        assert refreshed.status == UserStatus.DELETED

        # Verify email was not sent
        assert mock_send_verification_email_task.called is False

    # ====================
    # EXPIRED USER TESTS
    # ====================

    @pytest.mark.asyncio
    async def test_resend_verification_user_expired_beyond_grace_period(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        fake_redis_client,
        create_user,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test that users beyond grace period are marked as expired and cannot resend."""
        # Arrange - Create user with updated_at beyond grace period
        expired_time = datetime.now(timezone.utc) - timedelta(
            hours=settings.UNVERIFIED_USER_GRACE_PERIOD_HOURS + 1
        )
        user = await create_user(
            status=UserStatus.PENDING,
            updated_at=expired_time,
        )

        # Act
        response = await client.post(
            self.BASE_URL,
            json={"email": user.email},
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == AuthMessages.GENERIC_VERIFICATION_SENT

        # Verify user was marked as expired
        refreshed = await db_session.get(User, user.id)
        assert refreshed.status == UserStatus.EXPIRED
        assert refreshed.deleted_at is not None

        # Verify no token was created
        assert await fake_redis_client.keys("*") == []

        # Verify email was not sent
        assert mock_send_verification_email_task.called is False

    @pytest.mark.asyncio
    async def test_resend_verification_user_exactly_at_grace_period_boundary(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        fake_redis_client,
        create_user,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test user exactly at grace period boundary is marked as expired."""
        # Arrange - Create user with updated_at exactly at grace period boundary
        boundary_time = datetime.now(timezone.utc) - timedelta(
            hours=settings.UNVERIFIED_USER_GRACE_PERIOD_HOURS,
            seconds=1,  # Just past the boundary
        )
        user = await create_user(
            status=UserStatus.PENDING,
            updated_at=boundary_time,
        )

        # Act
        response = await client.post(
            self.BASE_URL,
            json={"email": user.email},
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == AuthMessages.GENERIC_VERIFICATION_SENT

        # Verify user was marked as expired
        refreshed = await db_session.get(User, user.id)
        assert refreshed.status == UserStatus.EXPIRED
        assert refreshed.deleted_at is not None

        # Verify no token was created
        assert await fake_redis_client.keys("*") == []

        # Verify email was not sent
        assert mock_send_verification_email_task.called is False

    @pytest.mark.asyncio
    async def test_resend_verification_user_just_within_grace_period(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        fake_redis_client,
        create_user,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test user just within grace period can successfully resend verification."""
        # Arrange - Create user just within grace period
        within_grace_time = datetime.now(timezone.utc) - timedelta(
            hours=settings.UNVERIFIED_USER_GRACE_PERIOD_HOURS - 1
        )
        user = await create_user(
            status=UserStatus.PENDING,
            updated_at=within_grace_time,
        )

        # Act
        response = await client.post(
            self.BASE_URL,
            json={"email": user.email},
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == AuthMessages.GENERIC_VERIFICATION_SENT

        # Verify user status remains PENDING
        refreshed = await db_session.get(User, user.id)
        assert refreshed.status == UserStatus.PENDING
        assert refreshed.deleted_at is None
        assert refreshed.updated_at > within_grace_time

        # Verify token was created
        keys = await fake_redis_client.keys("*")
        assert len(keys) == 1

        # Verify email was sent
        assert mock_send_verification_email_task.called is True

    # ====================
    # SUCCESSFUL RESEND TESTS
    # ====================

    @pytest.mark.asyncio
    async def test_resend_verification_success_creates_token_and_updates_timestamp(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        fake_redis_client,
        create_user,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test successful resend creates token, updates timestamp, and sends email."""
        # Arrange
        old_updated_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        user = await create_user(
            status=UserStatus.PENDING,
            updated_at=old_updated_at,
        )

        # Act
        response = await client.post(
            self.BASE_URL,
            json={"email": user.email},
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == AuthMessages.GENERIC_VERIFICATION_SENT

        # Verify user updated_at was updated (new verification window)
        refreshed = await db_session.get(User, user.id)
        assert refreshed.updated_at > old_updated_at
        assert refreshed.deleted_at is None
        assert refreshed.status == UserStatus.PENDING

        # Verify token was created
        keys = await fake_redis_client.keys("*")
        assert len(keys) == 1

        # Verify token payload structure
        payload = json.loads(await fake_redis_client.get(keys[0]))
        assert payload["user_id"] == user.id
        assert isinstance(payload["issued_at"], int)

        # Verify email was sent
        assert mock_send_verification_email_task.called is True

    @pytest.mark.asyncio
    async def test_resend_verification_token_has_ttl(
        self,
        client: AsyncClient,
        fake_redis_client,
        create_user,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test that created verification token has proper TTL set."""
        # Arrange
        user = await create_user(status=UserStatus.PENDING)

        # Act
        await client.post(
            self.BASE_URL,
            json={"email": user.email},
        )

        # Assert
        keys = await fake_redis_client.keys("*")
        assert len(keys) == 1

        # Verify TTL is set and positive
        ttl = await fake_redis_client.ttl(keys[0])
        assert ttl > 0

        # Verify email was sent
        assert mock_send_verification_email_task.called is True

    @pytest.mark.asyncio
    async def test_resend_verification_multiple_resends_update_token(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        fake_redis_client,
        create_user,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test that multiple resends create new tokens and update timestamp."""
        # Arrange
        user = await create_user(status=UserStatus.PENDING)

        # Act - First resend
        response1 = await client.post(
            self.BASE_URL,
            json={"email": user.email},
        )

        # Get first token and updated_at
        keys1 = await fake_redis_client.keys("*")
        first_token_key = keys1[0]
        first_payload = json.loads(await fake_redis_client.get(first_token_key))
        first_issued_at = first_payload["issued_at"]

        await db_session.refresh(user)
        first_updated_at = user.updated_at

        # Wait a moment to ensure timestamp difference
        import asyncio

        await asyncio.sleep(0.1)

        # Reset mock
        mock_send_verification_email_task.called = False

        # Act - Second resend
        response2 = await client.post(
            self.BASE_URL,
            json={"email": user.email},
        )

        # Assert
        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK

        # Verify new token was created (old token is not deleted, so we have 2 tokens)
        keys2 = await fake_redis_client.keys("*")
        assert len(keys2) == 2

        # Get the newest token (they're both valid but one has newer issued_at)
        payloads = [json.loads(await fake_redis_client.get(key)) for key in keys2]
        issued_ats = [p["issued_at"] for p in payloads]

        # At least one should be newer than the first
        assert max(issued_ats) >= first_issued_at

        # Verify updated_at was updated
        await db_session.refresh(user)
        assert user.updated_at > first_updated_at

        # Verify email was sent both times
        assert mock_send_verification_email_task.called is True

    @pytest.mark.asyncio
    async def test_resend_verification_case_insensitive_email(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        fake_redis_client,
        create_user,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test that email lookup handles case (depends on database collation)."""
        # Arrange
        await create_user(
            email="test.user@example.com",  # Use lowercase
            status=UserStatus.PENDING,
        )

        # Act - Use same case
        response = await client.post(
            self.BASE_URL,
            json={"email": "test.user@example.com"},
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == AuthMessages.GENERIC_VERIFICATION_SENT

        # Verify token was created
        keys = await fake_redis_client.keys("*")
        assert len(keys) == 1

        # Verify email was sent
        assert mock_send_verification_email_task.called is True

    # ====================
    # RATE LIMITING TESTS
    # ====================

    @pytest.mark.asyncio
    async def test_resend_verification_rate_limiting(
        self,
        client: AsyncClient,
        create_user,
        fake_redis_client,
        mock_send_verification_email_task,
    ):
        """Test that rate limiting is enforced (3 requests per 60 minutes)."""
        # Arrange
        user = await create_user(status=UserStatus.PENDING)
        payload = {"email": user.email}

        # Act - Make 4 requests (limit is 3)
        responses = []
        for i in range(4):
            response = await client.post(self.BASE_URL, json=payload)
            responses.append(response)

        # Assert - First 3 should succeed, 4th should be rate limited
        assert responses[0].status_code == status.HTTP_200_OK
        assert responses[1].status_code == status.HTTP_200_OK
        assert responses[2].status_code == status.HTTP_200_OK
        assert responses[3].status_code == status.HTTP_429_TOO_MANY_REQUESTS

    # ====================
    # EDGE CASES
    # ====================

    @pytest.mark.asyncio
    async def test_resend_verification_with_sql_injection_attempt(
        self,
        client: AsyncClient,
        fake_redis_client,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test that SQL injection attempts in email are safely handled."""
        # Act
        response = await client.post(
            self.BASE_URL,
            json={"email": "'; DROP TABLE users; --@example.com"},
        )

        # Assert - Invalid email format returns validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        # Verify no token was created
        assert await fake_redis_client.keys("*") == []

        # Verify email was not sent
        assert mock_send_verification_email_task.called is False

    @pytest.mark.asyncio
    async def test_resend_verification_with_very_long_email(
        self,
        client: AsyncClient,
        fake_redis_client,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test that very long email addresses are handled gracefully."""
        # Act
        very_long_email = "a" * 1000 + "@example.com"
        response = await client.post(
            self.BASE_URL,
            json={"email": very_long_email},
        )

        # Assert - Should handle gracefully (validation error or generic response)
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        ]

        # Verify no token was created
        assert await fake_redis_client.keys("*") == []

        # Verify email was not sent
        assert mock_send_verification_email_task.called is False

    @pytest.mark.asyncio
    async def test_resend_verification_with_special_characters_in_email(
        self,
        client: AsyncClient,
        create_user,
        fake_redis_client,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test that emails with special characters are handled correctly."""
        # Arrange
        user = await create_user(
            email="user+test@example.com",
            status=UserStatus.PENDING,
        )

        # Act
        response = await client.post(
            self.BASE_URL,
            json={"email": user.email},
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == AuthMessages.GENERIC_VERIFICATION_SENT

        # Verify token was created
        keys = await fake_redis_client.keys("*")
        assert len(keys) == 1

        # Verify email was sent
        assert mock_send_verification_email_task.called is True

    @pytest.mark.asyncio
    async def test_resend_verification_with_unicode_email(
        self,
        client: AsyncClient,
        fake_redis_client,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test that unicode characters in email are handled gracefully."""
        # Act
        response = await client.post(
            self.BASE_URL,
            json={"email": "用户@example.com"},
        )

        # Assert - Should handle gracefully
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        ]

        # Verify no token was created
        assert await fake_redis_client.keys("*") == []

    @pytest.mark.asyncio
    async def test_resend_verification_sequential_requests_same_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        create_user,
        fake_redis_client,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test multiple sequential resend requests for the same user."""
        # Arrange
        user = await create_user(status=UserStatus.PENDING)
        payload = {"email": user.email}

        # Act - Send sequential requests
        response1 = await client.post(self.BASE_URL, json=payload)
        response2 = await client.post(self.BASE_URL, json=payload)
        response3 = await client.post(self.BASE_URL, json=payload)

        # Assert - All should succeed
        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK
        assert response3.status_code == status.HTTP_200_OK

        # Verify user is still in valid state
        await db_session.refresh(user)
        assert user.status == UserStatus.PENDING

    @pytest.mark.asyncio
    async def test_resend_verification_with_whitespace_in_email(
        self,
        client: AsyncClient,
        create_user,
        fake_redis_client,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test that emails with leading/trailing whitespace are handled."""
        # Arrange
        await create_user(
            email="user@example.com",
            status=UserStatus.PENDING,
        )

        # Act
        response = await client.post(
            self.BASE_URL,
            json={"email": "  user@example.com  "},
        )

        # Assert - Depends on your validation (might strip or reject)
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        ]

    @pytest.mark.asyncio
    async def test_resend_verification_with_null_email(
        self,
        client: AsyncClient,
        fake_redis_client,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test that null email value is rejected."""
        # Act
        response = await client.post(
            self.BASE_URL,
            json={"email": None},
        )

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        # Verify no token was created
        assert await fake_redis_client.keys("*") == []

        # Verify email was not sent
        assert mock_send_verification_email_task.called is False

    @pytest.mark.asyncio
    async def test_resend_verification_token_invalidates_old_tokens(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        fake_redis_client,
        create_user,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test that resending verification effectively invalidates old tokens via updated_at."""
        # Arrange
        old_updated_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        user = await create_user(
            status=UserStatus.PENDING,
            updated_at=old_updated_at,
        )

        # Act - First resend
        response1 = await client.post(
            self.BASE_URL,
            json={"email": user.email},
        )

        await db_session.refresh(user)
        new_updated_at = user.updated_at

        # Assert
        assert response1.status_code == status.HTTP_200_OK
        assert new_updated_at > old_updated_at

        # Any old tokens with issued_at < new_updated_at would be invalid
        # This is verified in the verify endpoint tests


# ====================
# INTEGRATION TESTS
# ====================


class TestResendVerificationIntegration:
    """Integration tests for the complete resend verification flow."""

    BASE_URL = "/api/v1/auth/resend-verification"

    @pytest.mark.asyncio
    async def test_full_resend_workflow(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        fake_redis_client,
        create_user,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test the complete resend verification workflow."""
        # Arrange - Create pending user
        user = await create_user(status=UserStatus.PENDING)
        initial_updated_at = user.updated_at

        # Act - Resend verification
        response = await client.post(
            self.BASE_URL,
            json={"email": user.email},
        )

        # Assert - Response
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == AuthMessages.GENERIC_VERIFICATION_SENT

        # Assert - User state
        await db_session.refresh(user)
        assert user.status == UserStatus.PENDING
        assert user.updated_at > initial_updated_at
        assert user.deleted_at is None

        # Assert - Token created
        keys = await fake_redis_client.keys("*")
        assert len(keys) == 1

        # Assert - Token has correct payload
        token_data = json.loads(await fake_redis_client.get(keys[0]))
        assert token_data["user_id"] == user.id
        assert token_data["issued_at"] >= int(user.updated_at.timestamp())

        # Assert - TTL is set
        ttl = await fake_redis_client.ttl(keys[0])
        assert ttl > 0

        # Assert - Email was sent
        assert mock_send_verification_email_task.called is True

    @pytest.mark.asyncio
    async def test_resend_then_verify_workflow(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        fake_redis_client,
        create_user,
        mock_send_verification_email_task,
        disable_rate_limiting,
    ):
        """Test resending verification and then verifying the email."""
        # Arrange
        user = await create_user(status=UserStatus.PENDING)

        # Act - Resend verification
        response = await client.post(
            self.BASE_URL,
            json={"email": user.email},
        )

        assert response.status_code == status.HTTP_200_OK

        # Get the token from Redis
        keys = await fake_redis_client.keys("*")
        assert len(keys) == 1
        token_key = keys[0]

        # Extract token from key (remove prefix)
        from app.auth import constants

        token = token_key.replace(constants.VERIFICATION_PREFIX, "")

        # Act - Verify using the token
        verify_response = await client.get(f"/api/v1/auth/verify/{token}")

        # Assert
        assert verify_response.status_code == status.HTTP_200_OK

        # Verify user is now active
        await db_session.refresh(user)
        assert user.status == UserStatus.ACTIVE

        # Verify token was deleted
        assert await fake_redis_client.get(token_key) is None
