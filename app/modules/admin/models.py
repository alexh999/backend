from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Enum, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.modules.users.models import USERNAME_MAX_LENGTH, utc_now


class AdminAuditAction(StrEnum):
    ADMIN_CREATED = "ADMIN_CREATED"
    USER_DISABLED = "USER_DISABLED"
    USER_ENABLED = "USER_ENABLED"
    FORUM_POST_APPROVED = "FORUM_POST_APPROVED"
    FORUM_POST_REJECTED = "FORUM_POST_REJECTED"
    FORUM_POST_HIDDEN = "FORUM_POST_HIDDEN"
    FORUM_POST_RESTORED = "FORUM_POST_RESTORED"


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    actor_username: Mapped[str] = mapped_column(String(USERNAME_MAX_LENGTH), nullable=False, index=True)
    action: Mapped[AdminAuditAction] = mapped_column(
        Enum(
            AdminAuditAction,
            name="admin_audit_action",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
            create_constraint=True,
        ),
        nullable=False,
        index=True,
    )
    target_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    target_username: Mapped[str] = mapped_column(String(USERNAME_MAX_LENGTH), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )
