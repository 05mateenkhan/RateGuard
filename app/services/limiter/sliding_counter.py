import math
import time
from datetime import datetime, timezone
from app.services.limiter.base import BaseLimiter, LimiterResult

class SlidingWindowCounterLimiter(BaseLimiter):
    async def check(self, identifier: str, policy_id: str, limit: int, window: int, **kwargs) -> LimiterResult:
        now = time.time()
        current_window_idx = math.floor(now / window)
        prev_window_idx = current_window_idx - 1

        curr_key = f"sc:{policy_id}:{identifier}:{current_window_idx}"
        prev_key = f"sc:{policy_id}:{identifier}:{prev_window_idx}"

        # Fetch both counts atomically
        counts = await self.redis.mget([curr_key, prev_key])
        curr_count = int(counts[0]) if counts[0] else 0
        prev_count = int(counts[1]) if counts[1] else 0

        # Calculate weight of the previous window
        # if window=60s and we are at 15s, weight = (60-15)/60 = 0.75
        time_elapsed_in_window = now % window
        weight = (window - time_elapsed_in_window) / window

        estimated_count = curr_count + (prev_count * weight)
        allowed = estimated_count < limit

        if allowed:
            # Increment current window
            await self.redis.incr(curr_key)
            await self.redis.expire(curr_key, window * 2)
            estimated_count += 1

        reset_at = datetime.fromtimestamp((current_window_idx + 1) * window, tz=timezone.utc)

        return LimiterResult(
            allowed=allowed,
            remaining=max(0, limit - math.ceil(estimated_count)),
            limit=limit,
            reset_at=reset_at
        )
