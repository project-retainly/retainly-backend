import redis.asyncio as redis

from app.core.settings import settings

client = redis.from_url(url=settings.REDIS_URL, decode_responses=True)
