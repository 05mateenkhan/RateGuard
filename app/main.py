from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
import logging
from app.api.v1.router import api_router
from app.db.session import engine, AsyncSessionLocal
from app.db.base import Base
from app.db.redis import redis_client
from app.services.stats_service import StatsService

logger = logging.getLogger(__name__)

async def stats_flusher_task():
    """
    Background task that periodically flushes Redis stats to PostgreSQL.
    """
    stats_service = StatsService(redis_client)
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await stats_service.flush_stats_to_db(db)
        except Exception as e:
            logger.error(f"Error flushing stats: {e}")

        # Flush every 5 minutes
        await asyncio.sleep(300)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables (for dev purposes)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Start the background flusher
    flusher_task = asyncio.create_task(stats_flusher_task())

    yield
    # Shutdown: Cancel flusher and close Redis
    flusher_task.cancel()
    try:
        await flusher_task
    except asyncio.CancelledError:
        pass
    await redis_client.close()

app = FastAPI(
    title="RateGuard API",
    description="Rate Limiter as a Service",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(api_router, prefix="/v1")

@app.get("/health")
async def health_check():
    return {"status": "ok"}
