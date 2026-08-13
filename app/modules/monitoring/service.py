from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.session import get_session_factory
from app.modules.monitoring.models import (
    MonitoringEventStatus,
    MonitoringServiceName,
    SystemMonitoringEvent,
)
from app.modules.monitoring.schemas import (
    MonitoringErrorRecord,
    MonitoringHealthStatus,
    MonitoringServiceMetrics,
    MonitoringTrendBucket,
    MonitoringTrendServiceBucket,
    MonitoringWindow,
    SystemMonitoringSummaryResponse,
)
from app.modules.users.models import utc_now


logger = logging.getLogger(__name__)

ERROR_MESSAGE_MAX_LENGTH = 240
ERROR_RECORD_LIMIT = 20
SENSITIVE_VALUE_PATTERN = re.compile(
    r"\b(bearer|basic)\s+[a-z0-9._~+/=-]+"
    r"|\b(api[_-]?key|token|password|secret)\s*[:=]\s*[^,\s]+"
    r"|eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MonitoringRange:
    window: MonitoringWindow
    start: datetime
    end: datetime
    step: timedelta
    bucket_count: int


def record_monitoring_event(
    *,
    service: MonitoringServiceName,
    endpoint: str,
    status: MonitoringEventStatus,
    duration_ms: int | None = None,
    http_status_code: int | None = None,
    error_type: str | None = None,
    error_message: object | None = None,
    occurred_at: datetime | None = None,
    settings: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
) -> None:
    try:
        factory = session_factory or get_session_factory(settings)
        event_time = _as_utc(occurred_at or utc_now())
        with factory() as db:
            db.add(
                SystemMonitoringEvent(
                    service=service,
                    endpoint=_safe_endpoint(endpoint),
                    status=status,
                    occurred_at=event_time,
                    duration_ms=_safe_duration(duration_ms),
                    http_status_code=http_status_code,
                    error_type=_safe_error_type(error_type),
                    error_message=sanitize_error_message(error_message),
                    created_at=event_time,
                )
            )
            db.commit()
    except Exception:
        logger.exception(
            "Failed to record system monitoring event",
            extra={
                "monitoring_service": service.value,
                "monitoring_endpoint": endpoint,
                "monitoring_status": status.value,
            },
        )


def get_system_monitoring_summary(
    db: Session,
    *,
    window: MonitoringWindow,
    now: datetime | None = None,
) -> SystemMonitoringSummaryResponse:
    range_ = _resolve_monitoring_range(window, now=now)
    window_events = list(
        db.scalars(
            select(SystemMonitoringEvent)
            .where(
                SystemMonitoringEvent.occurred_at >= range_.start,
                SystemMonitoringEvent.occurred_at <= range_.end,
            )
            .order_by(SystemMonitoringEvent.occurred_at.asc(), SystemMonitoringEvent.id.asc())
        )
    )
    all_latest = {
        service: _latest_event(db, service=service)
        for service in MonitoringServiceName
    }
    all_latest_error = {
        service: _latest_event(
            db,
            service=service,
            status=MonitoringEventStatus.FAILURE,
        )
        for service in MonitoringServiceName
    }
    backend_24h_start = range_.end - timedelta(hours=24)
    backend_24h_events = [
        event
        for event in window_events
        if event.service == MonitoringServiceName.BACKEND and _as_utc(event.occurred_at) >= backend_24h_start
    ]
    if window == "7d":
        backend_24h_events = list(
            db.scalars(
                select(SystemMonitoringEvent).where(
                    SystemMonitoringEvent.service == MonitoringServiceName.BACKEND,
                    SystemMonitoringEvent.occurred_at >= backend_24h_start,
                    SystemMonitoringEvent.occurred_at <= range_.end,
                )
            )
        )

    services = {
        service: _service_metrics(
            service=service,
            events=[event for event in window_events if event.service == service],
            latest_event=all_latest[service],
            latest_error=all_latest_error[service],
            backend_24h_events=backend_24h_events if service == MonitoringServiceName.BACKEND else None,
        )
        for service in MonitoringServiceName
    }

    return SystemMonitoringSummaryResponse(
        window=window,
        window_start=range_.start,
        window_end=range_.end,
        services=services,
        trends=_build_trend_buckets(range_, window_events),
        recent_errors=_recent_error_records(db, start=range_.start, end=range_.end),
    )


def sanitize_error_message(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = SENSITIVE_VALUE_PATTERN.sub("[REDACTED]", text)
    if len(text) > ERROR_MESSAGE_MAX_LENGTH:
        return text[: ERROR_MESSAGE_MAX_LENGTH - 3].rstrip() + "..."
    return text or None


def _service_metrics(
    *,
    service: MonitoringServiceName,
    events: list[SystemMonitoringEvent],
    latest_event: SystemMonitoringEvent | None,
    latest_error: SystemMonitoringEvent | None,
    backend_24h_events: list[SystemMonitoringEvent] | None,
) -> MonitoringServiceMetrics:
    total_calls = len(events)
    success_count = sum(1 for event in events if event.status == MonitoringEventStatus.SUCCESS)
    failure_count = total_calls - success_count
    durations = [
        event.duration_ms
        for event in events
        if event.duration_ms is not None and event.duration_ms >= 0
    ]
    status = (
        "healthy"
        if service == MonitoringServiceName.BACKEND and latest_event is None
        else _health_status(latest_event)
    )
    success_rate = round(success_count / total_calls * 100, 2) if total_calls else None
    avg_duration = round(sum(durations) / len(durations), 2) if durations else None
    metrics = MonitoringServiceMetrics(
        service=service,
        status=status,
        last_called_at=_as_utc(latest_event.occurred_at) if latest_event is not None else None,
        total_calls=total_calls,
        success_count=success_count,
        failure_count=failure_count,
        success_rate=success_rate,
        avg_response_time_ms=avg_duration,
        last_error_at=_as_utc(latest_error.occurred_at) if latest_error is not None else None,
        last_error_message=latest_error.error_message if latest_error is not None else None,
    )
    if service == MonitoringServiceName.BACKEND:
        recent_events = backend_24h_events or []
        last_exception = next(
            (
                event
                for event in sorted(
                    recent_events,
                    key=lambda item: (item.occurred_at, item.id),
                    reverse=True,
                )
                if event.status == MonitoringEventStatus.FAILURE
            ),
            latest_error,
        )
        metrics.request_count_24h = len(recent_events)
        metrics.exception_count_24h = sum(
            1 for event in recent_events if event.status == MonitoringEventStatus.FAILURE
        )
        metrics.last_exception_at = _as_utc(last_exception.occurred_at) if last_exception is not None else None
        metrics.last_exception_message = last_exception.error_message if last_exception is not None else None
    return metrics


def _build_trend_buckets(
    range_: MonitoringRange,
    events: Iterable[SystemMonitoringEvent],
) -> list[MonitoringTrendBucket]:
    buckets: dict[datetime, dict[str, int]] = {}
    for index in range(range_.bucket_count):
        bucket_start = range_.start + (range_.step * index)
        buckets[bucket_start] = {
            "pandaai_calls": 0,
            "pandaai_failures": 0,
            "ai_model_calls": 0,
            "ai_model_failures": 0,
            "newsapi_calls": 0,
            "newsapi_failures": 0,
            "backend_calls": 0,
            "backend_failures": 0,
        }

    for event in events:
        bucket_start = _bucket_start(event.occurred_at, range_)
        if bucket_start not in buckets:
            continue
        prefix = _trend_prefix(event.service)
        buckets[bucket_start][f"{prefix}_calls"] += 1
        if event.status == MonitoringEventStatus.FAILURE:
            buckets[bucket_start][f"{prefix}_failures"] += 1

    return [
        MonitoringTrendBucket(
            bucket_start=bucket_start,
            bucket_end=bucket_start + range_.step,
            services=_trend_services(counts),
            **counts,
        )
        for bucket_start, counts in buckets.items()
    ]


def _recent_error_records(
    db: Session,
    *,
    start: datetime,
    end: datetime,
) -> list[MonitoringErrorRecord]:
    events = db.scalars(
        select(SystemMonitoringEvent)
        .where(
            SystemMonitoringEvent.status == MonitoringEventStatus.FAILURE,
            SystemMonitoringEvent.occurred_at >= start,
            SystemMonitoringEvent.occurred_at <= end,
        )
        .order_by(desc(SystemMonitoringEvent.occurred_at), desc(SystemMonitoringEvent.id))
        .limit(ERROR_RECORD_LIMIT)
    )
    return [
        MonitoringErrorRecord(
            id=event.id,
            service=event.service,
            endpoint=event.endpoint,
            occurred_at=_as_utc(event.occurred_at),
            http_status_code=event.http_status_code,
            error_type=event.error_type,
            error_message=event.error_message,
        )
        for event in events
    ]


def _latest_event(
    db: Session,
    *,
    service: MonitoringServiceName,
    status: MonitoringEventStatus | None = None,
) -> SystemMonitoringEvent | None:
    statement = select(SystemMonitoringEvent).where(SystemMonitoringEvent.service == service)
    if status is not None:
        statement = statement.where(SystemMonitoringEvent.status == status)
    return db.scalar(
        statement.order_by(desc(SystemMonitoringEvent.occurred_at), desc(SystemMonitoringEvent.id)).limit(1)
    )


def _resolve_monitoring_range(
    window: MonitoringWindow,
    *,
    now: datetime | None,
) -> MonitoringRange:
    end = _as_utc(now or utc_now())
    if window == "24h":
        start = end.replace(minute=0, second=0, microsecond=0) - timedelta(hours=23)
        return MonitoringRange(window=window, start=start, end=end, step=timedelta(hours=1), bucket_count=24)

    start_date = end.date() - timedelta(days=6)
    start = datetime.combine(start_date, time.min, tzinfo=UTC)
    return MonitoringRange(window=window, start=start, end=end, step=timedelta(days=1), bucket_count=7)


def _bucket_start(occurred_at: datetime, range_: MonitoringRange) -> datetime:
    value = _as_utc(occurred_at)
    if range_.window == "24h":
        return value.replace(minute=0, second=0, microsecond=0)
    return datetime.combine(value.date(), time.min, tzinfo=UTC)


def _health_status(event: SystemMonitoringEvent | None) -> MonitoringHealthStatus:
    if event is None:
        return "no_calls"
    return "healthy" if event.status == MonitoringEventStatus.SUCCESS else "unhealthy"


def _trend_prefix(service: MonitoringServiceName) -> str:
    if service == MonitoringServiceName.PANDAAI:
        return "pandaai"
    if service == MonitoringServiceName.AI_MODEL:
        return "ai_model"
    if service == MonitoringServiceName.NEWSAPI:
        return "newsapi"
    return "backend"


def _trend_services(counts: dict[str, int]) -> dict[MonitoringServiceName, MonitoringTrendServiceBucket]:
    return {
        service: MonitoringTrendServiceBucket(
            calls=counts[f"{_trend_prefix(service)}_calls"],
            failures=counts[f"{_trend_prefix(service)}_failures"],
        )
        for service in MonitoringServiceName
    }


def _safe_endpoint(value: str) -> str:
    normalized = value.strip() or "unknown"
    return normalized[:255]


def _safe_error_type(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip()[:100] or None


def _safe_duration(value: int | None) -> int | None:
    if value is None:
        return None
    return max(0, int(value))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
