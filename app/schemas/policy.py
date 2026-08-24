from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional
from datetime import datetime

class PolicyBase(BaseModel):
    name: str = Field(..., example="Login Endpoint Limit")
    resource_key: str = Field(..., example="login")
    algorithm: str = Field(..., example="fixed_window") # fixed_window, sliding_log, token_bucket, sliding_counter
    limit_count: int = Field(..., gt=0, example=100)
    window_seconds: int = Field(..., gt=0, example=60)
    burst_capacity: Optional[int] = Field(None, gt=0, example=120)

class PolicyCreate(PolicyBase):
    pass

class PolicyUpdate(BaseModel):
    name: Optional[str] = None
    resource_key: Optional[str] = None
    algorithm: Optional[str] = None
    limit_count: Optional[int] = None
    window_seconds: Optional[int] = None
    burst_capacity: Optional[int] = None

class PolicyResponse(PolicyBase):
    id: UUID
    client_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
