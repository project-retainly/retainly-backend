import pytest

from app.posts.models import Post
from app.posts.schemas import PostCreate
from app.posts.services import PostService
from app.posts.utils import PostStatus
from tests.posts.factories import PostFactory
from tests.users.factories import UserFactory


@pytest.mark.asyncio
class TestCreateNewPostService:
    async def test_create_post_success(self, db_session):
        user = await UserFactory.create()
        service = PostService(db_session)

        post_in = PostCreate(
            title="My First Blog Post",
            content={"blocks": []},
            summary="A short summary",
            featured_image="http://image.com/1.jpg",
        )

        post = await service.create_new_post(post_in, user_id=user.id)

        assert post.id is not None
        assert post.title == "My First Blog Post"
        assert post.slug == "my-first-blog-post"
        assert post.user_id == user.id
        assert post.status == PostStatus.DRAFT

        db_post = await db_session.get(Post, post.id)
        assert db_post is not None


    async def test_create_post_slug_collision(self, db_session):
        user = await UserFactory.create()
        service = PostService(db_session)

        # Create first post
        await PostFactory.create(title="Duplicate Title", slug="duplicate-title")

        # Create second post with same title
        post_in = PostCreate(title="Duplicate Title", content={"blocks": []})
        post = await service.create_new_post(post_in, user_id=user.id)

        assert post.slug != "duplicate-title"
        assert post.slug.startswith("duplicate-title-")

    async def test_create_post_special_chars_slug(self, db_session):
        user = await UserFactory.create()
        service = PostService(db_session)

        post_in = PostCreate(title="??? ###", content={"blocks": []})
        post = await service.create_new_post(post_in, user_id=user.id)

        assert post.slug == "post" or post.slug.startswith("post-")
