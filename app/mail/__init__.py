from fastapi_mail import ConnectionConfig, FastMail

from app.core.settings import settings

MAIL_TEMPLATES_DIR = settings.APP_DIR / "mail" / "templates"

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    TEMPLATE_FOLDER=MAIL_TEMPLATES_DIR,
)

mail_client = FastMail(conf)
