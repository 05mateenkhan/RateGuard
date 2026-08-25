from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import get_current_client
from app.db.session import get_db
from app.db.models.client import Client
from app.db.models.usage import UsageLog
from pydantic import BaseModel
from datetime import datetime
from typing import List

class UsageStat(BaseModel):
    window_start: datetime
    allowed_count: int
    blocked_count: int

router = APIRouter()

@router.get("/usage", response_model=List[UsageStat])
async def get_usage_stats(
    client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db)
):
    # Fetch usage logs for this client
    result = await db.execute(
        select(UsageLog).where(UsageLog.client_id == client.id).order_by(UsageLog.window_start.desc())
    )
    return result.scalars().all()
