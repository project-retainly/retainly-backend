import json
from datetime import datetime, timezone

import pytest

from app.auth import constants
from app.auth.services import AuthService
from app.core.settings import settings
from app.users.models import UserStatus
from tests.users.factories import UserFactory


class TestCreatePasswordResetLinkService:
    @pytest.mark.asyncio
    async def test_create_password_reset_link_success(
        self, db_session, fake_redis_client
    ):
        user = await UserFactory.create(status=UserStatus.ACTIVE)
        await db_session.commit()

        service = AuthService(db=db_session)
        reset_link = await service.create_password_reset_link(user_id=user.id)

        assert reset_link.startswith(
            f"{settings.BACKEND_HOST_URL}/api/v1/auth/reset-password/"
        )
        token = reset_link.split("/")[-1]
        assert len(token) > 0

    @pytest.mark.asyncio
    async def test_create_password_reset_link_stores_in_redis(
        self, db_session, fake_redis_client
    ):
        user = await UserFactory.create(status=UserStatus.ACTIVE)
        await db_session.commit()

        service = AuthService(db=db_session)
        reset_link = await service.create_password_reset_link(user_id=user.id)

        token = reset_link.split("/")[-1]
        redis_key = f"{constants.PASSWORD_RESET_PREFIX}{token}"

        stored_data = await fake_redis_client.get(redis_key)
        assert stored_data is not None

        payload = json.loads(stored_data)
        assert payload["user_id"] == user.id
        assert "issued_at" in payload

    @pytest.mark.asyncio
    async def test_create_password_reset_link_sets_correct_ttl(
        self, db_session, fake_redis_client
    ):
        user = await UserFactory.create(status=UserStatus.ACTIVE)
        await db_session.commit()

        service = AuthService(db=db_session)
        reset_link = await service.create_password_reset_link(user_id=user.id)

        token = reset_link.split("/")[-1]
        redis_key = f"{constants.PASSWORD_RESET_PREFIX}{token}"

        ttl = await fake_redis_client.ttl(redis_key)
        expected_ttl = settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES * 60

        assert ttl > 0
        assert abs(ttl - expected_ttl) <= 2

    @pytest.mark.asyncio
    async def test_create_password_reset_link_payload_contains_issued_at(
        self, db_session, fake_redis_client
    ):
        user = await UserFactory.create(status=UserStatus.ACTIVE)
        await db_session.commit()

        before_creation = datetime.now(timezone.utc)
        service = AuthService(db=db_session)
        reset_link = await service.create_password_reset_link(user_id=user.id)
        after_creation = datetime.now(timezone.utc)

        token = reset_link.split("/")[-1]
        redis_key = f"{constants.PASSWORD_RESET_PREFIX}{token}"

        stored_data = await fake_redis_client.get(redis_key)
        payload = json.loads(stored_data)

        issued_at = datetime.fromtimestamp(payload["issued_at"], tz=timezone.utc)
        assert before_creation <= issued_at <= after_creation

    @pytest.mark.asyncio
    async def test_create_password_reset_link_generates_unique_tokens(
        self, db_session, fake_redis_client
    ):
        user = await UserFactory.create(status=UserStatus.ACTIVE)
        await db_session.commit()

        service = AuthService(db=db_session)
        link1 = await service.create_password_reset_link(user_id=user.id)
        link2 = await service.create_password_reset_link(user_id=user.id)

        token1 = link1.split("/")[-1]
        token2 = link2.split("/")[-1]

        assert token1 != token2

    @pytest.mark.asyncio
    async def test_create_password_reset_link_for_different_users(
        self, db_session, fake_redis_client
    ):
        user1 = await UserFactory.create(status=UserStatus.ACTIVE)
        user2 = await UserFactory.create(status=UserStatus.ACTIVE)
        await db_session.commit()

        service = AuthService(db=db_session)
        link1 = await service.create_password_reset_link(user_id=user1.id)
        link2 = await service.create_password_reset_link(user_id=user2.id)

        token1 = link1.split("/")[-1]
        token2 = link2.split("/")[-1]

        redis_key1 = f"{constants.PASSWORD_RESET_PREFIX}{token1}"
        redis_key2 = f"{constants.PASSWORD_RESET_PREFIX}{token2}"

        payload1 = json.loads(await fake_redis_client.get(redis_key1))
        payload2 = json.loads(await fake_redis_client.get(redis_key2))

        assert payload1["user_id"] == user1.id
        assert payload2["user_id"] == user2.id
