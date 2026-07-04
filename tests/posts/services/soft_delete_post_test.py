import pytest

from app.core.exceptions import AppError, AppException
from app.posts.services import PostService
from app.posts.utils import PostStatus
from tests.posts.factories import PostFactory
from tests.users.factories import UserFactory


@pytest.mark.asyncio
class TestSoftDeletePostService:
    async def test_soft_delete_success(self, db_session):
        user = await UserFactory.create()
        post = await PostFactory.create(owner=user, status=PostStatus.PUBLISHED)
        service = PostService(db_session)

        await service.soft_delete_post(post_id=post.id, user_id=user.id)

        await db_session.refresh(post)
        assert post.status == PostStatus.DELETED
        assert post.deleted_at is not None

    async def test_soft_delete_not_found(self, db_session):
        user = await UserFactory.create()
        service = PostService(db_session)

        with pytest.raises(AppException) as exc:
            await service.soft_delete_post(post_id="nonexistent-id", user_id=user.id)
        assert exc.value.error == AppError.NOT_FOUND

    async def test_soft_delete_wrong_user(self, db_session):
        owner = await UserFactory.create()
        other_user = await UserFactory.create()
        post = await PostFactory.create(owner=owner)
        service = PostService(db_session)

        with pytest.raises(AppException) as exc:
            await service.soft_delete_post(post_id=post.id, user_id=other_user.id)
        assert exc.value.error == AppError.NOT_FOUND
