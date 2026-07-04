from fastapi import APIRouter

from app.auth.routes import auth_router
from app.media.routes import media_router
from app.posts.routes import post_router
from app.users.routes import users_router

api_v1_router = APIRouter(
    prefix="/api/v1",
)

api_v1_router.include_router(users_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(post_router)
api_v1_router.include_router(media_router)
