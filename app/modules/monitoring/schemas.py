from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.monitoring.models import MonitoringServiceName


MonitoringWindow = Literal["24h", "7d"]
MonitoringHealthStatus = Literal["healthy", "unhealthy", "no_calls"]


class MonitoringServiceMetrics(BaseModel):
    service: MonitoringServiceName
    status: MonitoringHealthStatus
    last_called_at: datetime | None = None
    total_calls: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    success_rate: float | None = None
    avg_response_time_ms: float | None = None
    last_error_at: datetime | None = None
    last_error_message: str | None = None
    request_count_24h: int | None = None
    exception_count_24h: int | None = None
    last_exception_at: datetime | None = None
    last_exception_message: str | None = None


class MonitoringTrendServiceBucket(BaseModel):
    calls: int = Field(ge=0)
    failures: int = Field(ge=0)


class MonitoringTrendBucket(BaseModel):
    bucket_start: datetime
    bucket_end: datetime
    services: dict[MonitoringServiceName, MonitoringTrendServiceBucket]
    pandaai_calls: int = Field(ge=0)
    pandaai_failures: int = Field(ge=0)
    ai_model_calls: int = Field(ge=0)
    ai_model_failures: int = Field(ge=0)
    newsapi_calls: int = Field(ge=0)
    newsapi_failures: int = Field(ge=0)
    backend_calls: int = Field(ge=0)
    backend_failures: int = Field(ge=0)


class MonitoringErrorRecord(BaseModel):
    id: int
    service: MonitoringServiceName
    endpoint: str
    occurred_at: datetime
    http_status_code: int | None = None
    error_type: str | None = None
    error_message: str | None = None


class SystemMonitoringSummaryResponse(BaseModel):
    window: MonitoringWindow
    window_start: datetime
    window_end: datetime
    services: dict[MonitoringServiceName, MonitoringServiceMetrics]
    trends: list[MonitoringTrendBucket]
    recent_errors: list[MonitoringErrorRecord]
