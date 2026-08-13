from __future__ import annotations

import time

from fastapi import FastAPI, Request

from app.core.config import Settings
from app.modules.monitoring.models import MonitoringEventStatus, MonitoringServiceName
from app.modules.monitoring.service import record_monitoring_event, sanitize_error_message


def add_monitoring_middleware(app: FastAPI, settings: Settings) -> None:
    @app.middleware("http")
    async def system_monitoring_middleware(request: Request, call_next):
        start = time.perf_counter()
        endpoint = f"{request.method} {request.url.path}"
        try:
            response = await call_next(request)
        except Exception as exc:
            record_monitoring_event(
                service=MonitoringServiceName.BACKEND,
                endpoint=endpoint,
                status=MonitoringEventStatus.FAILURE,
                duration_ms=_duration_ms(start),
                error_type=type(exc).__name__,
                error_message=sanitize_error_message(exc),
                settings=settings,
            )
            raise

        status_code = response.status_code
        is_failure = status_code >= 500
        record_monitoring_event(
            service=MonitoringServiceName.BACKEND,
            endpoint=endpoint,
            status=MonitoringEventStatus.FAILURE if is_failure else MonitoringEventStatus.SUCCESS,
            duration_ms=_duration_ms(start),
            http_status_code=status_code,
            error_type=f"HTTP_{status_code}" if is_failure else None,
            error_message=f"Backend request returned HTTP {status_code}." if is_failure else None,
            settings=settings,
        )
        return response


def _duration_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)
