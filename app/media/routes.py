from fastapi import APIRouter

from app.core.logger import get_logger

logger = get_logger(__name__)

media_router = APIRouter(prefix="/media", tags=["Media"])
