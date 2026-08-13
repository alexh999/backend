from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.admin.models import AdminAuditAction
from app.modules.activity.schemas import UserActivitySummaryResponse
from app.modules.forum.models import ForumContentStatus
from app.modules.forum.schemas import ForumPostResponse
from app.modules.monitoring.schemas import SystemMonitoringSummaryResponse
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


SAFE_AUDIT_METADATA_KEYS = {
    "previous_status",
    "new_status",
    "previous_role",
    "new_role",
    "content_type",
    "content_id",
    "previous_moderation_status",
    "new_moderation_status",
    "reason",
}


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

    @field_validator("metadata", mode="before")
    @classmethod
    def filter_safe_metadata(cls, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        return {key: value[key] for key in SAFE_AUDIT_METADATA_KEYS if key in value}


class AdminAuditLogListResponse(BaseModel):
    items: list[AdminAuditLogResponse]
    total: int = Field(ge=0)
    total_pages: int = Field(ge=1)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class AdminUserActivitySummaryResponse(UserActivitySummaryResponse):
    pass


class AdminSystemMonitoringResponse(SystemMonitoringSummaryResponse):
    pass


class AdminContentModerationListResponse(BaseModel):
    items: list[ForumPostResponse]
    total: int = Field(ge=0)
    total_pages: int = Field(ge=1)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class AdminContentModerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ForumContentStatus
    reason: str | None = Field(default=None, max_length=255)
