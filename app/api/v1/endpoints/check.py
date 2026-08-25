from fastapi import APIRouter, Depends, HTTPException, Response, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import Dict, Any

from app.api.deps import get_current_client
from app.db.session import get_db
from app.db.models.client import Client
from app.db.redis import get_redis
from app.services.limiter_service import LimiterService
from app.services.cache_service import PolicyCacheService
from app.services.stats_service import StatsService
import redis.asyncio as redis

router = APIRouter()

@router.post("/check")
async def check_rate_limit(
    response: Response,
    identifier: str,
    resource_key: str,
    background_tasks: BackgroundTasks,
    client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
    redis: redis.Redis = Depends(get_redis)
):
    # 1. Get Policy Config (Using formalized CacheService)
    cache_service = PolicyCacheService(redis)
    policy_cfg = await cache_service.get_policy(str(client.id), resource_key, db)

    if not policy_cfg:
        # Default policy if none exists
        policy_cfg = {
            "id": "default",
            "algorithm": "fixed_window",
            "limit_count": 100,
            "window_seconds": 60,
            "burst_capacity": 100
        }

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

    # 4. Track Usage (Non-blocking)
    stats_service = StatsService(redis)
    background_tasks.add_task(stats_service.track_request, policy_cfg["id"], result.allowed)

    # 5. Set Headers (GitHub/Stripe style)
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
