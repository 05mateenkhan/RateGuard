import time
from datetime import datetime, timezone
from app.services.limiter.base import BaseLimiter, LimiterResult

class SlidingLogLimiter(BaseLimiter):
    async def check(self, identifier: str, policy_id: str, limit: int, window: int, **kwargs) -> LimiterResult:
        now = time.time()
        key = f"sl:{policy_id}:{identifier}"

        # Atomic pipeline to prevent race conditions
        async with self.redis.pipeline(transaction=True) as pipe:
            # 1. Remove timestamps older than the window
            pipe.zremrangebyscore(key, 0, now - window)
            # 2. Count current requests in the window
            pipe.zcard(key)
            # 3. Set TTL for the set
            pipe.expire(key, window)

            results = await pipe.execute()

        current_count = results[1]
        allowed = current_count < limit

        if allowed:
            # Only add the request if it's allowed
            await self.redis.zadd(key, {str(now): now})
            current_count += 1

        # Reset time is the oldest member + window, or now + window if empty
        # For simplicity in sliding log, we use now + window.
        reset_at = datetime.fromtimestamp(now + window, tz=timezone.utc)

        return LimiterResult(
            allowed=allowed,
            remaining=max(0, limit - current_count),
            limit=limit,
            reset_at=reset_at
        )
