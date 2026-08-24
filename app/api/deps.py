from fastapi import Header, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.db.models.client import Client
from app.db.redis import get_redis
import redis.asyncio as redis
import hashlib

async def get_current_client(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
    redis: redis.Redis = Depends(get_redis)
) -> Client:
    # Hash the provided key
    hashed_key = hashlib.sha256(x_api_key.encode()).hexdigest()

    # 1. Check Redis Cache
    cache_key = f"auth:{hashed_key}"
    client_id = await redis.get(cache_key)

    if client_id:
        # We have the ID, fetch the client object from DB
        # (Optimization: we could just return the ID if that's all we need)
        from uuid import UUID
        result = await db.execute(select(Client).where(Client.id == UUID(client_id)))
        client = result.scalar_one_or_none()
        if client:
            return client

    # 2. Cache miss: Query Postgres
    result = await db.execute(select(Client).where(Client.api_key_hash == hashed_key))
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )

    # 3. Update Cache
    await redis.setex(cache_key, 3600, str(client.id))

    return client
