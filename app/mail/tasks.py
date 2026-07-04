import asyncio

from app.celery import celery_app


@celery_app.task
def send_verification_email_task(email: str, link: str):
    from .services import verification_email

    asyncio.run(verification_email(email=email, link=link))


@celery_app.task
def send_password_reset_email_task(email: str, link: str, user_name: str):
    from .services import send_password_reset_email

    asyncio.run(
        send_password_reset_email(email=email, reset_link=link, user_name=user_name)
    )


@celery_app.task
def send_password_change_notification_email_task(email: str, user_name: str):
    from .services import send_password_change_notification_email

    asyncio.run(
        send_password_change_notification_email(email=email, user_name=user_name)
    )
