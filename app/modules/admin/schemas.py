from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.admin.models import AdminAuditAction
from app.modules.users.schemas import UserResponse


class UserStatistics(BaseModel):
    total: int = Field(ge=0)
    active: int = Field(ge=0)
    disabled: int = Field(ge=0)
    admins: int = Field(ge=0)
    regular_users: int = Field(ge=0)


class AdminOverviewResponse(BaseModel):
    users: UserStatistics


class AdminUserListResponse(BaseModel):
    items: list[UserResponse]
    total: int = Field(ge=0)
    total_pages: int = Field(ge=1)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class AdminUserStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool


class AdminAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int
    actor_username: str
    action: AdminAuditAction
    target_user_id: int
    target_username: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")


class AdminAuditLogListResponse(BaseModel):
    items: list[AdminAuditLogResponse]
    total: int = Field(ge=0)
    total_pages: int = Field(ge=1)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
