from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.v1.router import api_router
from app.db.session import engine
from app.db.base import Base
from app.db.redis import redis_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables (for dev purposes)
    # In prod, we would use Alembic migrations.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield
    # Shutdown: Close Redis connection
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
