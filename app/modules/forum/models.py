from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.users.models import User, utc_now


class ForumContentStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    HIDDEN = "HIDDEN"


class ForumPost(Base):
    __tablename__ = "forum_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    topic_label: Mapped[str] = mapped_column(String(32), default="Discussion", nullable=False)
    status: Mapped[ForumContentStatus] = mapped_column(
        Enum(
            ForumContentStatus,
            name="forum_content_status",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
            create_constraint=True,
        ),
        default=ForumContentStatus.PENDING,
        server_default=ForumContentStatus.PENDING.value,
        index=True,
        nullable=False,
    )
    moderation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    moderated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    author: Mapped[User] = relationship(foreign_keys=[author_user_id])
    moderator: Mapped[User | None] = relationship(foreign_keys=[moderated_by_user_id])
