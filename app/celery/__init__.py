from celery import Celery
from celery.schedules import crontab
from celery.signals import beat_init, worker_process_init

from app.core import models_registry  # noqa: F401
from app.core.logger import setup_logging
from app.core.settings import settings

celery_app = Celery(
    main="retainly", broker=settings.REDIS_URL, backend=settings.REDIS_URL
)

celery_app.autodiscover_tasks(
    ["app.auth", "app.users", "app.posts", "app.mail", "app.media"]
)


# Called when each worker process starts
@worker_process_init.connect
def init_worker(**kwargs):
    setup_logging()


# Called when beat starts
@beat_init.connect
def init_beat(**kwargs):
    setup_logging()


CELERY_BEAT_SCHEDULE = {
    "cleanup-expired-users-daily": {
        "task": "app.users.tasks.cleanup_expired_unverified_users_task",
        "schedule": crontab(hour=2, minute=0),
    },
    "cleanup-expired-refresh-tokens-daily": {
        "task": "app.auth.tasks.cleanup_expired_refresh_tokens_task",
        "schedule": crontab(hour=2, minute=0),
    },
    "cleanup_deleted_media_file_metadata": {
        "task": "app.media.tasks.cleanup_deleted_media_file_metadata_task",
        "schedule": crontab(hour=2, minute=0),
    },
    "cleanup_deleted_posts": {
        "task": "app.posts.tasks.cleanup_deleted_posts_task",
        "schedule": crontab(hour=2, minute=0),
    },
}

celery_app.conf.beat_schedule = CELERY_BEAT_SCHEDULE
