import json
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.policy import Policy
from typing import Optional, Dict, Any

class PolicyCacheService:
    """
    Handles caching and invalidation of rate-limiting policies in Redis.
    """
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.ttl = 3600 # 1 hour

    async def get_policy(self, client_id: str, resource_key: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
        cache_key = f"policy_cache:{client_id}:{resource_key}"

        # 1. Attempt to get from cache
        cached_data = await self.redis.get(cache_key)
        if cached_data:
            return json.loads(cached_data)

        # 2. Cache miss: Query Database
        result = await db.execute(
            select(Policy).where(Policy.client_id == client_id, Policy.resource_key == resource_key)
        )
        policy = result.scalar_one_or_none()

        if not policy:
            return None

        # 3. Format and Cache
        policy_data = {
            "id": str(policy.id),
            "algorithm": policy.algorithm,
            "limit_count": policy.limit_count,
            "window_seconds": policy.window_seconds,
            "burst_capacity": policy.burst_capacity or policy.limit_count,
        }

        await self.redis.setex(cache_key, self.ttl, json.dumps(policy_data))
        return policy_data

    async def invalidate_policy(self, client_id: str, resource_key: str):
        """
        Removes a policy from the cache when it is updated or deleted.
        """
        cache_key = f"policy_cache:{client_id}:{resource_key}"
        await self.redis.delete(cache_key)
