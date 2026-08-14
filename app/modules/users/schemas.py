from datetime import datetime

from pydantic import BaseModel, ConfigDict

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
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str
