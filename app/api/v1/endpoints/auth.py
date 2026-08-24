from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.models.client import Client
from app.schemas.auth import SignupRequest, SignupResponse
from app.core.security import generate_api_key

router = APIRouter()

@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, db: AsyncSession = Depends(get_db)):
    # Check if email already exists
    from sqlalchemy import select
    result = await db.execute(select(Client).where(Client.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Generate API key
    plaintext_key, hashed_key = generate_api_key()

    # Create client
    new_client = Client(
        name=payload.name,
        email=payload.email,
        api_key_hash=hashed_key
    )

    db.add(new_client)
    await db.commit()
    await db.refresh(new_client)

    return SignupResponse(
        client_id=new_client.id,
        api_key=plaintext_key
    )
