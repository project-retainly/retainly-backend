from datetime import datetime

import pytest

from app.core.exceptions import AppError, AppException
from app.posts.schemas import PostUpdate
from app.posts.services import PostService
from app.posts.utils import PostStatus
from tests.posts.factories import PostFactory
from tests.users.factories import UserFactory


@pytest.mark.asyncio
class TestUpdatePostService:
    async def test_update_fields_success(self, db_session):
        user = await UserFactory.create()
        post = await PostFactory.create(owner=user, title="Old Title")
        service = PostService(db_session)

        update_data = PostUpdate(title="New Title", summary="Updated Summary")
        updated_post = await service.update_post(
            post_id=post.id, post_update=update_data, user_id=user.id
        )

        assert updated_post.title == "New Title"
        assert updated_post.summary == "Updated Summary"

        await db_session.refresh(post)
        assert post.title == "New Title"

    async def test_publish_post_sets_date(self, db_session):
        user = await UserFactory.create()
        post = await PostFactory.create(
            owner=user, status=PostStatus.DRAFT, published_at=None
        )
        service = PostService(db_session)

        update_data = PostUpdate(status=PostStatus.PUBLISHED)
        updated_post = await service.update_post(
            post_id=post.id, post_update=update_data, user_id=user.id
        )

        assert updated_post.status == PostStatus.PUBLISHED
        assert updated_post.published_at is not None

    async def test_republishing_does_not_reset_date(self, db_session):
        user = await UserFactory.create()
        original_date = datetime(
            2020, 1, 1, tzinfo=None
        )  # naive for simplicity in assertion
        post = await PostFactory.create(
            owner=user, status=PostStatus.PUBLISHED, published_at=original_date
        )
        service = PostService(db_session)

        update_data = PostUpdate(status=PostStatus.PUBLISHED, title="Edit")
        updated_post = await service.update_post(
            post_id=post.id, post_update=update_data, user_id=user.id
        )

        # Compare timestamps (ignoring minor tz variations if db strips them)
        assert updated_post.published_at.timestamp() == original_date.timestamp()

    async def test_update_post_not_found(self, db_session):
        user = await UserFactory.create()
        service = PostService(db_session)
        update_data = PostUpdate(title="New")

        with pytest.raises(AppException) as exc:
            await service.update_post(
                post_id="nonexistent-id", post_update=update_data, user_id=user.id
            )
        assert exc.value.error == AppError.NOT_FOUND
