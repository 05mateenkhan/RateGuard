from typing import List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.models.usage import UsageLog
from app.db.redis import redis_client
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)

class StatsService:
    """
    Handles tracking and aggregating rate-limit usage stats.
    """
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def track_request(self, policy_id: str, allowed: bool):
        """
        Increments the usage counter in Redis.
        Runs as a non-blocking task in the background.
        """
        # Bucket by hour: stats:{policy_id}:{hour}:{status}
        hour_bucket = datetime.utcnow().strftime("%Y-%m-%d%H")
        status = "allowed" if allowed else "blocked"
        key = f"stats:{policy_id}:{hour_bucket}:{status}"

        await self.redis.incr(key)
        # Set TTL to 24 hours to allow for delayed flushing
        await self.redis.expire(key, 86400)

    async def flush_stats_to_db(self, db: AsyncSession):
        """
        Scans Redis for usage stats and persists them to PostgreSQL.
        """
        cursor = 0
        processed_keys = []

        # 1. Scan for all stats keys
        while True:
            cursor, keys = await self.redis.scan(cursor=cursor, match="stats:*")
            if not keys:
                break

            for key in keys:
                # Parse key: stats:{policy_id}:{hour_bucket}:{status}
                parts = key.split(":")
                if len(parts) != 4:
                    continue

                policy_id, hour_bucket, status = parts[1], parts[2], parts[3]
                count = int(await self.redis.get(key) or 0)

                # Convert hour_bucket (YYYY-MM-DDHH) to datetime
                try:
                    window_start = datetime.strptime(hour_bucket, "%Y-%m-%d%H")
                except ValueError:
                    continue

                # 2. Update or Create UsageLog in Postgres
                from app.db.models.policy import Policy # Avoid circular
                from sqlalchemy import update

                # Find existing log for this policy and window
                result = await db.execute(
                    select(UsageLog).where(
                        UsageLog.policy_id == policy_id,
                        UsageLog.window_start == window_start
                    )
                )
                log_entry = result.scalar_one_or_none()

                if not log_entry:
                    log_entry = UsageLog(
                        policy_id=policy_id,
                        window_start=window_start,
                        allowed_count=0,
                        blocked_count=0
                    )
                    # We need to resolve client_id for the UsageLog.
                    # In a real system, we'd cache policy_id -> client_id.
                    # For now, we'll query the policy.
                    policy_res = await db.execute(select(Policy).where(Policy.id == policy_id))
                    policy = policy_res.scalar_one_or_none()
                    if policy:
                        log_entry.client_id = policy.client_id
                    else:
                        continue
                    db.add(log_entry)

                if status == "allowed":
                    log_entry.allowed_count += count
                else:
                    log_entry.blocked_count += count

                processed_keys.append(key)

            if cursor == 0:
                break

        await db.commit()

        # 3. Cleanup processed keys in Redis
        if processed_keys:
            await self.redis.delete(*processed_keys)
            logger.info(f"Flushed {len(processed_keys)} stats keys to DB.")
