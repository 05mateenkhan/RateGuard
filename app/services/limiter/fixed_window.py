import math
import time
from datetime import datetime, timezone
from app.services.limiter.base import BaseLimiter, LimiterResult

class FixedWindowLimiter(BaseLimiter):
    async def check(self, identifier: str, policy_id: str, limit: int, window: int, **kwargs) -> LimiterResult:
        now = time.time()
        current_window = math.floor(now / window)

        # Key pattern: fw:{policy_id}:{identifier}:{bucket}
        key = f"fw:{policy_id}:{identifier}:{current_window}"

        # Atomic increment
        count = await self.redis.incr(key)

        # Set expiration on first request of the window
        if count == 1:
            await self.redis.expire(key, window)

        allowed = count <= limit

        # Calculate reset time (start of next window)
        reset_timestamp = (current_window + 1) * window
        reset_at = datetime.fromtimestamp(reset_timestamp, tz=timezone.utc)

        return LimiterResult(
            allowed=allowed,
            remaining=max(0, limit - count),
            limit=limit,
            reset_at=reset_at
        )
