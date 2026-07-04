from celery import Task

from app.core.logger import get_logger

logger = get_logger(__name__)


class LoggedRetryTask(Task):
    def on_success(self, retval, task_id, args, kwargs):
        logger.info(
            "celery_task_success",
            task_name=self.name,
            task_id=task_id,
            retval=retval,
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(
            "celery_task_retry",
            task_name=self.name,
            task_id=task_id,
            attempt=self.request.retries,
            error=str(exc),
        )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            "celery_task_failure",
            task_name=self.name,
            task_id=task_id,
            retries=self.request.retries,
            error=str(exc),
        )
