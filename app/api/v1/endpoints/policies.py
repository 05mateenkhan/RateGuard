from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.api.deps import get_current_client, get_db
from app.db.models.client import Client
from app.db.models.policy import Policy
from app.schemas.policy import PolicyCreate, PolicyUpdate, PolicyResponse
from app.services.cache_service import PolicyCacheService
from app.db.redis import get_redis
import redis.asyncio as redis

router = APIRouter()

@router.post("/", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    payload: PolicyCreate,
    client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
    redis: redis.Redis = Depends(get_redis)
):
    # Check if a policy for this resource already exists for the client
    result = await db.execute(
        select(Policy).where(Policy.client_id == client.id, Policy.resource_key == payload.resource_key)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Policy for this resource already exists. Use PUT to update."
        )

    new_policy = Policy(
        **payload.model_dump(),
        client_id=client.id
    )

    db.add(new_policy)
    await db.commit()
    await db.refresh(new_policy)

    # Pre-warm cache
    cache_service = PolicyCacheService(redis)
    # We force a DB read by getting the policy through the service or just manually setting it
    # For simplicity, we just invalidate it, and the next /check will populate it.
    await cache_service.invalidate_policy(str(client.id), payload.resource_key)

    return new_policy

@router.get("/", response_model=list[PolicyResponse])
async def list_policies(
    client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Policy).where(Policy.client_id == client.id))
    return result.scalars().all()

@router.put("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: UUID,
    payload: PolicyUpdate,
    client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
    redis: redis.Redis = Depends(get_redis)
):
    result = await db.execute(select(Policy).where(Policy.id == policy_id, Policy.client_id == client.id))
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(policy, key, value)

    await db.commit()
    await db.refresh(policy)

    # Invalidate cache
    cache_service = PolicyCacheService(redis)
    await cache_service.invalidate_policy(str(client.id), policy.resource_key)

    return policy

@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    policy_id: UUID,
    client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
    redis: redis.Redis = Depends(get_redis)
):
    result = await db.execute(select(Policy).where(Policy.id == policy_id, Policy.client_id == client.id))
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    resource_key = policy.resource_key
    await db.delete(policy)
    await db.commit()

    # Invalidate cache
    cache_service = PolicyCacheService(redis)
    await cache_service.invalidate_policy(str(client.id), resource_key)

    return None
