from pydantic import BaseModel, EmailStr
from uuid import UUID

class SignupRequest(BaseModel):
    name: str
    email: EmailStr

class SignupResponse(BaseModel):
    client_id: UUID
    api_key: str
