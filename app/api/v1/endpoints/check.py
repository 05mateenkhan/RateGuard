from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import Dict, Any

from app.api.deps import get_current_client
from app.db.session import get_db
from app.db.models.client import Client
from app.db.redis import get_redis
from app.services.limiter_service import LimiterService
import redis.asyncio as redis
import json

router = APIRouter()

async def get_policy_config(client_id: str, resource_key: str, db: AsyncSession, redis: redis.Redis) -> Dict[str, Any]:
    """
    Retrieves policy configuration using a cache-aside pattern.
    """
    cache_key = f"policy_cache:{client_id}:{resource_key}"
    cached_policy = await redis.get(cache_key)

    if cached_policy:
        return json.loads(cached_policy)

    # Cache miss: Query Postgres
    from app.db.models.policy import Policy # Local import to avoid circular dependency
    result = await db.execute(
        select(Policy).where(Policy.client_id == client_id, Policy.resource_key == resource_key)
    )
    policy = result.scalar_one_or_none()

    if not policy:
        # Default policy if none exists
        return {
            "algorithm": "fixed_window",
            "limit_count": 100,
            "window_seconds": 60,
            "burst_capacity": 100
        }

    policy_data = {
        "id": str(policy.id),
        "algorithm": policy.algorithm,
        "limit_count": policy.limit_count,
        "window_seconds": policy.window_seconds,
        "burst_capacity": policy.burst_capacity or policy.limit_count,
    }

    # Cache for 1 hour
    await redis.setex(cache_key, 3600, json.dumps(policy_data))
    return policy_data

@router.post("/check")
async def check_rate_limit(
    response: Response,
    identifier: str,
    resource_key: str,
    client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
    redis: redis.Redis = Depends(get_redis)
):
    # 1. Get Policy Config (Cached)
    policy_cfg = await get_policy_config(str(client.id), resource_key, db, redis)

    # 2. Dispatch to Limiter
    limiter_service = LimiterService(redis)
    limiter = limiter_service.get_limiter(policy_cfg["algorithm"])

    # 3. Execute Check
    result = await limiter.check(
        identifier=identifier,
        policy_id=policy_cfg["id"],
        limit=policy_cfg["limit_count"],
        window=policy_cfg["window_seconds"],
        burst_capacity=policy_cfg.get("burst_capacity")
    )

    # 4. Set Headers (GitHub/Stripe style)
    response.headers["X-RateLimit-Limit"] = str(result.limit)
    response.headers["X-RateLimit-Remaining"] = str(result.remaining)
    response.headers["X-RateLimit-Reset"] = result.reset_at.isoformat()

    if not result.allowed:
        response.headers["Retry-After"] = str(int((result.reset_at - datetime.now(result.reset_at.tzinfo)).total_seconds()))
        return {
            "allowed": False,
            "remaining": result.remaining,
            "limit": result.limit,
            "reset_at": result.reset_at
        }

    return {
        "allowed": True,
        "remaining": result.remaining,
        "limit": result.limit,
        "reset_at": result.reset_at
    }
