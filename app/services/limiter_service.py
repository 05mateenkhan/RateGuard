from app.services.limiter.fixed_window import FixedWindowLimiter
from app.services.limiter.sliding_log import SlidingLogLimiter
from app.services.limiter.token_bucket import TokenBucketLimiter
from app.services.limiter.sliding_counter import SlidingWindowCounterLimiter
from app.services.limiter.base import BaseLimiter

class LimiterService:
    """
    Dispatcher service that selects the appropriate rate limiting algorithm
    based on the policy configuration.
    """
    def __init__(self, redis_client):
        self.redis = redis_client
        self._limiters = {
            "fixed_window": FixedWindowLimiter,
            "sliding_log": SlidingLogLimiter,
            "token_bucket": TokenBucketLimiter,
            "sliding_counter": SlidingWindowCounterLimiter,
        }

    def get_limiter(self, algorithm: str) -> BaseLimiter:
        limiter_class = self._limiters.get(algorithm)
        if not limiter_class:
            # Default to fixed window if algorithm is unknown
            limiter_class = FixedWindowLimiter

        return limiter_class(self.redis)
