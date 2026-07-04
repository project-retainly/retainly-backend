from typing import cast

from sqlalchemy import delete
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import OperationalError

from app.celery import celery_app
from app.celery.utils import LoggedRetryTask
from app.core.database import get_celery_db
from app.core.logger import get_logger

from .models import Post
from .utils import PostStatus

logger = get_logger(__name__)


async def cleanup_deleted_posts_test(db):
    stmt = delete(Post).where(Post.status == PostStatus.DELETED)
    result = cast(
        CursorResult, await db.execute(stmt)
    )  # tells the linter to trust the CursorResult type
    await db.commit()
    deleted_count = result.rowcount or 0
    return deleted_count


def cleanup_deleted_posts(db):
    stmt = delete(Post).where(Post.status == PostStatus.DELETED)
    result = cast(
        CursorResult, db.execute(stmt)
    )  # tells the linter to trust the CursorResult type
    db.commit()
    deleted_count = result.rowcount or 0
    return deleted_count


@celery_app.task(
    bind=True,
    base=LoggedRetryTask,
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_jitter=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 5},
)
def cleanup_deleted_posts_task(self):
    logger.info(
        "cleanup_deleted_posts_task_start",
        attempt=self.request.retries + 1,
    )
    with get_celery_db() as db:
        deleted_count = cleanup_deleted_posts(db)

    logger.info(
        "cleanup_deleted_posts_end",
        deleted_count=deleted_count,
    )
    return deleted_count
