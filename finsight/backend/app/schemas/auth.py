from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    image_url: Optional[str] = None
    provider: str
    provider_sub: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AuthStatusResponse(BaseModel):
    is_authenticated: bool
    user: Optional[UserResponse] = None
