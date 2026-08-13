from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.modules.users.models import utc_now


class MonitoringServiceName(StrEnum):
    PANDAAI = "pandaai"
    AI_MODEL = "ai_model"
    NEWSAPI = "newsapi"
    BACKEND = "backend"


class MonitoringEventStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class SystemMonitoringEvent(Base):
    __tablename__ = "system_monitoring_events"
    __table_args__ = (
        Index(
            "ix_system_monitoring_events_service_occurred_at",
            "service",
            "occurred_at",
        ),
        Index(
            "ix_system_monitoring_events_status_occurred_at",
            "status",
            "occurred_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service: Mapped[MonitoringServiceName] = mapped_column(
        Enum(
            MonitoringServiceName,
            name="monitoring_service_name",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
            create_constraint=True,
        ),
        index=True,
        nullable=False,
    )
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[MonitoringEventStatus] = mapped_column(
        Enum(
            MonitoringEventStatus,
            name="monitoring_event_status",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
            create_constraint=True,
        ),
        index=True,
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
