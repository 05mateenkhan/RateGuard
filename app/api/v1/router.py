from fastapi import APIRouter
from app.api.v1.endpoints import auth, check, policies, usage

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(check.router, prefix="", tags=["Rate Limiter"])
api_router.include_router(policies.router, prefix="/policies", tags=["Policies"])
api_router.include_router(usage.router, prefix="", tags=["Analytics"])
