from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.users.models import UserRole, UserStatus


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: UserRole
    status: UserStatus
    created_at: datetime
    updated_at: datetime


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
