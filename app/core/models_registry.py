# 1. Import the Base (The Host)
import app.auth.models as auth_models
import app.media.models as media_models
import app.posts.models as post_models

# 2. Import every single model (The Guests)
# This forces them to "register" with Base.metadata
import app.users.models as user_models
from app.core.database import Base  # type: ignore  # noqa: F821

# Optional: Export them so you can import them from here if you want
__all__ = [
    "Base",
    "auth_models",
    "user_models",
    "post_models",
    "media_models",
]
