from fastapi import Depends, Request

from app.core import redis
from app.core.exceptions import AppError, AppException
from app.core.logger import get_logger

from .contexts import AuthContext
from .dependencies import get_optional_auth_context

logger = get_logger(__name__)


class CompositeRateLimiter:
    def __init__(self, key_prefix: str, limit: int, minutes: int):
        self.key_prefix = key_prefix
        self.limit = limit
        self.window = minutes * 60  # Convert minutes to seconds

    async def __call__(
        self,
        request: Request,
        auth_cxt: AuthContext | None = Depends(get_optional_auth_context),
    ):
        ip_addr = request.client.host

        # We will prepare a list of keys to check
        keys_to_check = []

        # 1. ALWAYS check the IP Address (Global IP Limit)
        # Prevents: Many users abusing from one IP
        keys_to_check.append(f"limiter:{self.key_prefix}:ip:{ip_addr}")

        # 2. IF LOGGED IN, check the User ID (Global User Limit)
        # Prevents: One user rotating IPs, or One user abusing from many devices
        if auth_cxt and auth_cxt.user:
            keys_to_check.append(f"limiter:{self.key_prefix}:user:{auth_cxt.user.id}")

        # 3. Use a Redis Pipeline to check ALL keys in ONE network request (High Performance)
        async with redis.client.pipeline(transaction=True) as pipe:
            for key in keys_to_check:
                pipe.incr(key)
                pipe.ttl(key)

            # Execute all commands at once
            results = await pipe.execute()

        # 4. Analyze Results
        # Results list comes back as: [incr_1, ttl_1, incr_2, ttl_2, ...]
        for i, key in enumerate(keys_to_check):
            # The count is at index i*2, the TTL is at index i*2 + 1
            current_count = results[i * 2]
            current_ttl = results[i * 2 + 1]

            # A. Handle Expiry / Zombie Keys
            if current_count == 1 or current_ttl == -1:
                # If it's new or zombie, set the expiry
                await redis.client.expire(key, self.window)

            # B. Check Limit
            if current_count > self.limit:
                logger.warning(
                    "rate_limit_exceeded",
                    key=key,
                    count=current_count,
                    limit=self.limit,
                )
                raise AppException(
                    error=AppError.TOO_MANY_REQUESTS,
                    headers={"Retry-After": str(self.window)},
                )

        return True


def RateLimitDep(key: str, limit: int, minutes: int):
    return Depends(CompositeRateLimiter(key_prefix=key, limit=limit, minutes=minutes))
