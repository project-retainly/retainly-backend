from fastapi_mail import MessageSchema, MessageType

from app.mail import mail_client


async def verification_email(email: str, link: str):
    # 1. Define the data to inject into HTML
    template_data = {"link": link}

    # 2. Schema changes slightly
    message = MessageSchema(
        subject="Verify your Retainly Account",
        recipients=[email],
        template_body=template_data,
        subtype=MessageType.html,
    )

    # 3. Pass the template name here
    await mail_client.send_message(message, template_name="/email_account_verify.html")


async def send_password_reset_email(email: str, reset_link: str, user_name: str):
    template_data = {"link": reset_link, "user_name": user_name}

    message = MessageSchema(
        subject="Password Reset for Your Retainly Account",
        recipients=[email],
        template_body=template_data,
        subtype=MessageType.html,
    )

    await mail_client.send_message(message, template_name="/reset_password_link.html")


async def send_password_change_notification_email(email: str, user_name: str):
    template_data = {"user_name": user_name}

    message = MessageSchema(
        subject="Your Retainly Account Password Was Changed",
        recipients=[email],
        template_body=template_data,
        subtype=MessageType.html,
    )

    await mail_client.send_message(
        message, template_name="/password_changed_notification.html"
    )
