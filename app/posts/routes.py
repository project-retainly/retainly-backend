from fastapi import APIRouter, Depends, Path, status
from fastapi_pagination import LimitOffsetPage
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.contexts import AuthContext
from app.auth.dependencies import auth_guard
from app.auth.rate_limiter import RateLimitDep
from app.core.database import get_db
from app.core.logger import get_logger
from app.core.utils import use_flow
from app.core.validations.file_validator import AnalyzedFile
from app.media.schemas import MediaPublic
from app.media.services import MediaService
from app.media.utils import MediaStatus, StaticDirs

from .constants import FEATURED_IMAGE_MAX_SIZE_MB as FI_MAX_MB
from .schemas import PostCreate, PostListResponse, PostResponse, PostUpdate
from .services import PostService

logger = get_logger(__name__)

post_router = APIRouter(prefix="/posts", tags=["Posts"])


@use_flow("docs/flows/posts/create_post.md")
@post_router.post(
    path="/",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new post",
)
async def create_post(
    post_in: PostCreate,
    auth_cxt: AuthContext = Depends(auth_guard),
    db: AsyncSession = Depends(get_db),
    _=RateLimitDep(key="create_post", limit=10, minutes=60),
):
    user_id = auth_cxt.user.id
    logger.info("create_post_request", user_id=user_id, title=post_in.title)
    service = PostService(db)
    result = await service.create_new_post(post_in=post_in, user_id=user_id)
    logger.info("create_post_success", user_id=user_id, post_id=result.id)
    return result


@use_flow("docs/flows/posts/get_posts_flow.md")
@post_router.get(
    path="/",
    response_model=LimitOffsetPage[PostListResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all posts without full content (Lightweight List view)",
)
async def get_all_posts(
    auth_cxt: AuthContext = Depends(auth_guard),
    db: AsyncSession = Depends(get_db),
    _=RateLimitDep(key="get_all_posts", limit=60, minutes=1),
):
    user_id = auth_cxt.user.id
    logger.info("get_all_posts_request", user_id=user_id)
    service = PostService(db)
    return await service.get_all_posts(user_id=user_id)


@use_flow("docs/flows/posts/get_post_detail_flow.md")
@post_router.get(
    path="/{id}",
    response_model=PostResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a single post by ID (Detail view)",
)
async def get_post_detail(
    id: str = Path(..., description="The unique ID of the post"),
    auth_cxt: AuthContext = Depends(auth_guard),
    db: AsyncSession = Depends(get_db),
    _=RateLimitDep(key="get_post_detail", limit=60, minutes=1),
):
    user_id = auth_cxt.user.id
    logger.info("get_post_detail_request", user_id=user_id, id=id)
    service = PostService(db)
    return await service.get_post_by_id(post_id=id, user_id=user_id)


@use_flow("docs/flows/posts/update_post.md")
@post_router.put(
    path="/{id}",
    response_model=PostResponse,
    status_code=status.HTTP_200_OK,
    summary="Update post by ID",
)
async def update_post(
    post_update: PostUpdate,
    id: str = Path(..., description="The unique ID of the post"),
    auth_cxt: AuthContext = Depends(auth_guard),
    db: AsyncSession = Depends(get_db),
    _=RateLimitDep(key="update_post", limit=15, minutes=1),
):
    user_id = auth_cxt.user.id
    logger.info("update_post_request", user_id=user_id, id=id)
    service = PostService(db)
    result = await service.update_post(
        post_id=id, post_update=post_update, user_id=user_id
    )
    logger.info("update_post_success", user_id=user_id, id=id, slug=result.slug)
    return result


@use_flow("docs/flows/posts/delete_post.md")
@post_router.delete(
    path="/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete post by ID",
)
async def delete_post(
    id: str = Path(..., description="The unique ID of the post"),
    auth_cxt: AuthContext = Depends(auth_guard),
    db: AsyncSession = Depends(get_db),
    _=RateLimitDep(key="update_post", limit=5, minutes=1),
):
    user_id = auth_cxt.user.id
    logger.info("delete_post_request", user_id=user_id, id=id)
    service = PostService(db)
    await service.soft_delete_post(post_id=id, user_id=user_id)
    logger.info("delete_post_success", user_id=user_id, id=id)
    return


@use_flow("docs/flows/users/update_featured_image.md")
@post_router.put(
    path="/{id}/featured-image",
    status_code=status.HTTP_200_OK,
    response_model=PostResponse,
    summary="Update the post's featured image.",
)
async def update_featured_image(
    id: str = Path(..., description="The unique ID of the post"),
    analyzed_file: AnalyzedFile = Depends(),
    auth_cxt: AuthContext = Depends(auth_guard),
    db: AsyncSession = Depends(get_db),
    _=RateLimitDep(key="update_featured_image", limit=5, minutes=1),
):
    user_id = auth_cxt.user.id
    logger.info("update_featured_image_request", user_id=user_id, id=id)
    analyzed_file.validate_for_image_file(MAX_MB=FI_MAX_MB)

    service = PostService(db)

    post = await service.get_post_by_id(post_id=id, user_id=user_id)

    result = await service.update_featured_image(post=post, analyzed_file=analyzed_file)
    logger.info("update_featured_image_success", user_id=user_id, id=id)
    return result


@use_flow("docs/flows/posts/get_public_posts.md")
@post_router.get(
    path="/public/",
    response_model=LimitOffsetPage[PostListResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all published posts (Public List view)",
)
async def get_public_posts(
    db: AsyncSession = Depends(get_db),
    _=RateLimitDep(key="get_public_posts", limit=60, minutes=1),
):
    logger.info("get_public_posts_request")
    service = PostService(db)
    return await service.get_public_posts()


@use_flow("docs/flows/posts/get_public_post_detail.md")
@post_router.get(
    path="/public/{id}",
    response_model=PostResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a single published post by ID (Public Detail view)",
)
async def get_public_post_detail(
    id: str = Path(..., description="The unique ID of the post"),
    db: AsyncSession = Depends(get_db),
    _=RateLimitDep(key="get_public_post_detail", limit=60, minutes=1),
):
    logger.info("get_public_post_detail_request", id=id)
    service = PostService(db)
    return await service.get_public_post_by_id(post_id=id)


@use_flow("docs/flows/posts/upload_inline_image.md")
@post_router.post(
    path="/{id}/images",
    response_model=MediaPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an inline image for a specific post",
)
async def upload_post_inline_image(
    id: str = Path(..., description="The unique ID of the post"),
    analyzed_file: AnalyzedFile = Depends(),
    auth_cxt: AuthContext = Depends(auth_guard),
    db: AsyncSession = Depends(get_db),
    _=RateLimitDep(key="upload_post_inline_image", limit=10, minutes=1),
):
    user_id = auth_cxt.user.id
    logger.info("upload_post_inline_image_request", user_id=user_id, post_id=id)

    # Verify post exists and user has access
    post_service = PostService(db)
    await post_service.get_post_by_id(post_id=id, user_id=user_id)

    analyzed_file.validate_for_image_file(MAX_MB=5)

    media_service = MediaService(db)
    media = await media_service.upload_file_and_create_media(
        analyzed_file=analyzed_file,
        user_id=user_id,
        directory=f"{StaticDirs.Uploads.POSTS}/{id}",
        media_status=MediaStatus.PENDING,
    )

    await db.commit()
    await db.refresh(media)

    logger.info(
        "upload_post_inline_image_success",
        user_id=user_id,
        post_id=id,
        media_id=media.id,
    )
    return media
