import time
from datetime import datetime, timezone
from app.services.limiter.base import BaseLimiter, LimiterResult

# Lua script for Token Bucket to ensure atomicity
TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local burst = tonumber(ARGV[3])
local now = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or burst
local last_refill = tonumber(bucket[2]) or now

-- Calculate refill
local elapsed = math.max(0, now - last_refill)
local refill = elapsed * (limit / window)
tokens = math.min(burst, tokens + refill)

if tokens >= 1 then
    tokens = tokens - 1
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, window * 2)
    return {1, tokens} -- Allowed, remaining
else
    return {0, tokens} -- Blocked, remaining
end
"""

class TokenBucketLimiter(BaseLimiter):
    def __init__(self, redis_client):
        super().__init__(redis_client)
        # Register the script with Redis to get a SHA1 hash
        self._script_sha = None

    async def _get_script_sha(self):
        if not self._script_sha:
            self._script_sha = await self.redis.script_load(TOKEN_BUCKET_LUA)
        return self._script_sha

    async def check(self, identifier: str, policy_id: str, limit: int, window: int, **kwargs) -> LimiterResult:
        now = time.time()
        key = f"tb:{policy_id}:{identifier}"
        burst = kwargs.get("burst_capacity", limit)

        sha = await self._get_script_sha()

        # Execute script: keys=[key], args=[limit, window, burst, now]
        result = await self.redis.evalsha(sha, 1, key, limit, window, burst, now)

        allowed_int, remaining_tokens = result
        allowed = bool(allowed_int)

        # Reset time is approximate: when the bucket will have at least 1 token
        # refill_rate = limit / window.
        # time_to_next_token = 1 / refill_rate = window / limit
        # if tokens < 1, we wait for (1 - tokens) / (limit/window)
        time_to_reset = (1 - remaining_tokens) * (window / limit) if not allowed else 0
        reset_at = datetime.fromtimestamp(now + max(time_to_reset, 1), tz=timezone.utc)

        return LimiterResult(
            allowed=allowed,
            remaining=int(remaining_tokens),
            limit=limit,
            reset_at=reset_at
        )
