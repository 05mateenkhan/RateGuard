import redis.asyncio as redis
from app.core.config import settings
import os
# Initialize Redis pool
REDIS_URL = os.getenv("REDIS_URL",
                      "redis://localhost:6379")
redis_client = redis.from_url(REDIS_URL)

async def get_redis():
    return redis_client
