from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi_pagination import LimitOffsetParams

from app.core.exceptions import AppError, AppException
from app.posts.services import PostService
from tests.posts.factories import PostFactory
from tests.users.factories import UserFactory


@pytest.mark.asyncio
class TestGetPostBySlugOrIdService:
    async def test_get_by_id_success(self, db_session):
        user = await UserFactory.create()
        post = await PostFactory.create(owner=user)
        service = PostService(db_session)

        fetched_post = await service.get_post_by_id(user_id=user.id, post_id=post.id)
        assert fetched_post.id == post.id

    async def test_get_post_not_found_by_id(self, db_session):
        user = await UserFactory.create()
        service = PostService(db_session)

        with pytest.raises(AppException) as exc:
            await service.get_post_by_id(user_id=user.id, post_id="nonexistent-id")
        assert exc.value.error == AppError.NOT_FOUND

    async def test_get_post_wrong_user(self, db_session):
        owner = await UserFactory.create()
        other_user = await UserFactory.create()
        post = await PostFactory.create(owner=owner)
        service = PostService(db_session)

        with pytest.raises(AppException) as exc:
            await service.get_post_by_id(user_id=other_user.id, post_id=post.id)
        assert exc.value.error == AppError.NOT_FOUND

    async def test_missing_identifiers(self, db_session):
        user = await UserFactory.create()
        service = PostService(db_session)

        with pytest.raises(AppException) as exc:
            await service.get_post_by_id(user_id=user.id)
        assert exc.value.error == AppError.BAD_REQUEST


@pytest.mark.asyncio
class TestGetAllPostsService:
    async def test_get_all_posts_pagination(self, db_session):
        user = await UserFactory.create()
        service = PostService(db_session)

        # Create 3 posts
        p1 = await PostFactory.create(owner=user, created_at=datetime(2023, 1, 1))
        p2 = await PostFactory.create(owner=user, created_at=datetime(2023, 1, 2))
        p3 = await PostFactory.create(owner=user, created_at=datetime(2023, 1, 3))

        # MOCK PAGINATION PARAMS
        # Since we are not in a request context, fastapi-pagination cannot find params.
        # We patch `resolve_params` to return LimitOffsetParams(limit=50, offset=0).
        with patch("fastapi_pagination.api.resolve_params") as mock_resolve:
            mock_resolve.return_value = LimitOffsetParams(limit=50, offset=0)

            page = await service.get_all_posts(user_id=user.id)

        assert page.total == 3
        assert page.items[0].id == p3.id  # Ordered by desc
        assert page.items[1].id == p2.id
        assert page.items[2].id == p1.id

    async def test_get_all_posts_filters_other_users(self, db_session):
        user = await UserFactory.create()
        other_user = await UserFactory.create()

        await PostFactory.create(owner=user)
        await PostFactory.create(owner=other_user)

        service = PostService(db_session)

        with patch("fastapi_pagination.api.resolve_params") as mock_resolve:
            mock_resolve.return_value = LimitOffsetParams(limit=50, offset=0)

            page = await service.get_all_posts(user_id=user.id)

        assert page.total == 1
        assert page.items[0].user_id == user.id
