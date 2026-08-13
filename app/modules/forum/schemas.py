from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.forum.models import ForumContentStatus


class ForumPostCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    topic_label: str = Field(default="Discussion", min_length=1, max_length=32)


class ForumPostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_user_id: int
    author_username: str
    content: str
    topic_label: str
    status: ForumContentStatus
    moderation_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class ForumPostListResponse(BaseModel):
    items: list[ForumPostResponse]
