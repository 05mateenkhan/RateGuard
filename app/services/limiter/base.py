from abc import ABC, abstractmethod
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class LimiterResult(BaseModel):
    allowed: bool
    remaining: int
    limit: int
    reset_at: datetime

class BaseLimiter(ABC):
    """
    Abstract base class for all rate limiting algorithms.
    """
    def __init__(self, redis_client):
        self.redis = redis_client

    @abstractmethod
    async def check(self, identifier: str, policy_id: str, limit: int, window: int, **kwargs) -> LimiterResult:
        """
        Evaluate if a request is allowed.

        Args:
            identifier: The unique ID of the requester (e.g., IP or user_id).
            policy_id: The ID of the policy being applied.
            limit: Max requests allowed in the window.
            window: Window size in seconds.
            **kwargs: Additional parameters (e.g., burst_capacity for token bucket).
        """
        pass
