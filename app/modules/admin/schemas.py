from pydantic import BaseModel, ConfigDict, Field

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
