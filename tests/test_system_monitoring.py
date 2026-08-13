from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.integrations.newsapi.client import NewsApiClient, NewsApiIntegrationError
from app.integrations.pandaai.client import PandaAIClient, PandaAIIntegrationError
from app.integrations.siliconflow.client import SiliconFlowClient, SiliconFlowMessage
from app.main import create_app
from app.modules.monitoring.models import (
    MonitoringEventStatus,
    MonitoringServiceName,
    SystemMonitoringEvent,
)
from app.modules.monitoring.service import (
    get_system_monitoring_summary,
    record_monitoring_event,
)
from app.modules.paper_trading.quote_provider import MockPaperTradingQuoteProvider
from app.modules.users.models import User, UserRole, UserStatus
from app.modules.users.service import create_user


TEST_PASSWORD = "test-only-password"
TEST_MODEL = "deepseek-ai/DeepSeek-V4-Flash"


@pytest.fixture
def monitoring_context(tmp_path) -> Generator[tuple[TestClient, sessionmaker[Session], Settings], None, None]:
    database_url = f"sqlite:///{tmp_path / 'monitoring_test.db'}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    settings = Settings(
        cors_origins="",
        database_url=database_url,
        jwt_secret=SecretStr("test-only-jwt-secret-that-is-not-used-in-production"),
        siliconflow_model=TEST_MODEL,
    )
    app = create_app(settings)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            yield client, session_factory, settings
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _create_user(
    session_factory: sessionmaker[Session],
    *,
    username: str,
    role: UserRole = UserRole.USER,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    with session_factory() as db:
        return create_user(
            db,
            username=username,
            password=TEST_PASSWORD,
            role=role,
            status=status,
        )


def _authorization(user: User, settings: Settings) -> dict[str, str]:
    token = create_access_token(user.id, settings)
    return {"Authorization": f"Bearer {token}"}


def _events(session_factory: sessionmaker[Session]) -> list[SystemMonitoringEvent]:
    with session_factory() as db:
        return list(db.scalars(select(SystemMonitoringEvent).order_by(SystemMonitoringEvent.id)))


def test_monitoring_summary_reports_no_calls_for_never_called_services(monitoring_context) -> None:
    _, session_factory, _ = monitoring_context

    with session_factory() as db:
        summary = get_system_monitoring_summary(
            db,
            window="24h",
            now=datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
        )

    assert summary.services[MonitoringServiceName.PANDAAI].status == "no_calls"
    assert summary.services[MonitoringServiceName.AI_MODEL].status == "no_calls"
    assert summary.services[MonitoringServiceName.BACKEND].status == "healthy"
    assert summary.trends[0].pandaai_calls == 0
    assert len(summary.trends) == 24
    assert summary.recent_errors == []


def test_record_monitoring_event_summarizes_success_failure_and_sanitizes(
    monitoring_context,
) -> None:
    _, session_factory, _ = monitoring_context
    now = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)

    record_monitoring_event(
        service=MonitoringServiceName.PANDAAI,
        endpoint="/multi/getStockDaily",
        status=MonitoringEventStatus.SUCCESS,
        duration_ms=120,
        http_status_code=200,
        occurred_at=now - timedelta(minutes=10),
        session_factory=session_factory,
    )
    record_monitoring_event(
        service=MonitoringServiceName.PANDAAI,
        endpoint="/multi/getStockDaily",
        status=MonitoringEventStatus.FAILURE,
        duration_ms=240,
        http_status_code=403,
        error_type="PandaAIIntegrationError",
        error_message="permission denied token=secret-value Bearer abc.def.ghi",
        occurred_at=now - timedelta(minutes=5),
        session_factory=session_factory,
    )

    with session_factory() as db:
        summary = get_system_monitoring_summary(db, window="24h", now=now)

    pandaai = summary.services[MonitoringServiceName.PANDAAI]
    assert pandaai.status == "unhealthy"
    assert pandaai.total_calls == 2
    assert pandaai.success_count == 1
    assert pandaai.failure_count == 1
    assert pandaai.success_rate == 50
    assert pandaai.avg_response_time_ms == 180
    assert pandaai.last_error_message == "permission denied [REDACTED] [REDACTED]"
    assert "secret-value" not in summary.model_dump_json()


def test_monitoring_trends_respect_window_and_recent_errors_are_descending(
    monitoring_context,
) -> None:
    _, session_factory, _ = monitoring_context
    now = datetime(2026, 8, 12, 15, 0, tzinfo=UTC)
    older = now - timedelta(days=8)
    first_error = now - timedelta(hours=3)
    second_error = now - timedelta(hours=1)

    record_monitoring_event(
        service=MonitoringServiceName.AI_MODEL,
        endpoint="/chat/completions",
        status=MonitoringEventStatus.FAILURE,
        error_type="HTTP_500",
        error_message="first",
        occurred_at=first_error,
        session_factory=session_factory,
    )
    record_monitoring_event(
        service=MonitoringServiceName.BACKEND,
        endpoint="GET /api/v1/probe",
        status=MonitoringEventStatus.FAILURE,
        http_status_code=500,
        error_type="RuntimeError",
        error_message="second",
        occurred_at=second_error,
        session_factory=session_factory,
    )
    record_monitoring_event(
        service=MonitoringServiceName.PANDAAI,
        endpoint="/old",
        status=MonitoringEventStatus.FAILURE,
        occurred_at=older,
        session_factory=session_factory,
    )

    with session_factory() as db:
        summary = get_system_monitoring_summary(db, window="7d", now=now)

    assert [item.error_message for item in summary.recent_errors] == ["second", "first"]
    assert all(item.error_message != "/old" for item in summary.recent_errors)
    today_bucket = summary.trends[-1]
    assert today_bucket.ai_model_failures == 1
    assert today_bucket.backend_failures == 1
    assert today_bucket.pandaai_failures == 0
    assert today_bucket.services[MonitoringServiceName.AI_MODEL].failures == 1
    assert today_bucket.services[MonitoringServiceName.NEWSAPI].calls == 0


def test_admin_system_monitoring_requires_active_admin(monitoring_context) -> None:
    client, session_factory, settings = monitoring_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    regular = _create_user(session_factory, username="regular")
    disabled_admin = _create_user(
        session_factory,
        username="disabled-admin",
        role=UserRole.ADMIN,
        status=UserStatus.DISABLED,
    )

    assert client.get("/api/v1/admin/system-monitoring").status_code == 401
    assert client.get(
        "/api/v1/admin/system-monitoring",
        headers=_authorization(regular, settings),
    ).status_code == 403
    assert client.get(
        "/api/v1/admin/system-monitoring",
        headers=_authorization(disabled_admin, settings),
    ).status_code == 401

    response = client.get(
        "/api/v1/admin/system-monitoring?window=24h",
        headers=_authorization(admin, settings),
    )
    invalid = client.get(
        "/api/v1/admin/system-monitoring?window=30d",
        headers=_authorization(admin, settings),
    )

    assert response.status_code == 200
    assert response.json()["window"] == "24h"
    assert invalid.status_code == 422


def test_backend_middleware_records_requests_and_unhandled_exceptions(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'backend_monitoring_test.db'}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    settings = Settings(
        cors_origins="",
        database_url=database_url,
        jwt_secret=SecretStr("test-only-jwt-secret-that-is-not-used-in-production"),
        siliconflow_model=TEST_MODEL,
    )
    app = create_app(settings)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("backend exploded token=secret")

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            ok = client.get("/api/v1/health")
            failed = client.get("/boom")

        assert ok.status_code == 200
        assert failed.status_code == 500
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        events = _events(session_factory)
        assert [event.status for event in events] == [
            MonitoringEventStatus.SUCCESS,
            MonitoringEventStatus.FAILURE,
        ]
        assert events[1].service == MonitoringServiceName.BACKEND
        assert events[1].endpoint == "GET /boom"
        assert "secret" not in (events[1].error_message or "")
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_pandaai_success_and_failure_calls_are_recorded(monitoring_context) -> None:
    _, session_factory, settings = monitoring_context
    settings.pandaai_username = "user"
    settings.pandaai_password = "password"
    settings.pandaai_max_retries = 1
    client = PandaAIClient(settings)
    client._token = "cached-token"
    client._token_expires_at = time.time() + 3600

    def success_post(*args, **kwargs):
        return 200, {"Content-Type": "application/json"}, json.dumps({"code": "200", "data": [{"ok": True}]}).encode()

    client._post_with_httpx = success_post
    assert client._post_data("/multi/getStockDaily", {"symbol": ["AAPL"]}) == [{"ok": True}]

    def failed_post(*args, **kwargs):
        return 200, {"Content-Type": "application/json"}, json.dumps({"code": "403", "message": "API permission denied"}).encode()

    client._post_with_httpx = failed_post
    with pytest.raises(PandaAIIntegrationError):
        client._post_data("/multi/getStockDaily", {"symbol": ["AAPL"]})

    events = _events(session_factory)
    assert [event.service for event in events] == [
        MonitoringServiceName.PANDAAI,
        MonitoringServiceName.PANDAAI,
    ]
    assert [event.status for event in events] == [
        MonitoringEventStatus.SUCCESS,
        MonitoringEventStatus.FAILURE,
    ]
    assert events[0].endpoint == "/multi/getStockDaily"
    assert events[1].error_type == "PandaAIIntegrationError"


def test_pandaai_token_failure_before_data_request_is_not_recorded(monitoring_context) -> None:
    _, session_factory, settings = monitoring_context
    settings.pandaai_username = ""
    settings.pandaai_password = ""
    settings.pandaai_max_retries = 1
    client = PandaAIClient(settings)

    with pytest.raises(PandaAIIntegrationError):
        client._post_data("/multi/getStockDaily", {"symbol": ["AAPL"]})

    assert _events(session_factory) == []


def test_pandaai_failure_then_mock_fallback_records_only_real_external_request(
    monitoring_context,
) -> None:
    _, session_factory, settings = monitoring_context
    settings.pandaai_username = "user"
    settings.pandaai_password = "password"
    settings.pandaai_max_retries = 1
    client = PandaAIClient(settings)
    client._token = "cached-token"
    client._token_expires_at = time.time() + 3600
    post_count = 0

    def failed_post(*args, **kwargs):
        nonlocal post_count
        post_count += 1
        return (
            200,
            {"Content-Type": "application/json"},
            json.dumps({"code": "403", "message": "API permission denied"}).encode(),
        )

    client._post_with_httpx = failed_post
    with pytest.raises(PandaAIIntegrationError):
        client._post_data("/multi/getStockDaily", {"symbol": ["AAPL"]})

    fallback_quote = MockPaperTradingQuoteProvider().get_quote("AAPL")

    events = _events(session_factory)
    assert post_count == 1
    assert fallback_quote.symbol == "AAPL"
    assert len(events) == 1
    assert events[0].service == MonitoringServiceName.PANDAAI
    assert events[0].status == MonitoringEventStatus.FAILURE


def test_pure_mock_data_does_not_record_pandaai_monitoring(monitoring_context) -> None:
    _, session_factory, _ = monitoring_context

    quote = MockPaperTradingQuoteProvider().get_quote("600519.SH")

    assert quote.symbol == "600519.SH"
    assert _events(session_factory) == []


def test_newsapi_success_and_failure_calls_are_recorded(
    monitoring_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, session_factory, settings = monitoring_context
    settings.newsapi_api_key = SecretStr("test-news-key")

    class FakeResponse:
        def __init__(self, *, status_code: int, payload: dict[str, object]) -> None:
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "boom token=secret",
                    request=httpx.Request("GET", "https://newsapi.org/v2/everything"),
                    response=httpx.Response(self.status_code),
                )

        def json(self) -> dict[str, object]:
            return self._payload

    class FakeClient:
        calls = 0

        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, *args, **kwargs) -> FakeResponse:
            FakeClient.calls += 1
            if FakeClient.calls == 1:
                return FakeResponse(
                    status_code=200,
                    payload={
                        "status": "ok",
                        "articles": [
                            {
                                "title": "Markets rally",
                                "url": "https://example.com/markets",
                                "source": {"name": "Example"},
                                "publishedAt": "2026-08-12T01:00:00Z",
                            }
                        ],
                    },
                )
            return FakeResponse(status_code=429, payload={})

    monkeypatch.setattr(httpx, "Client", FakeClient)
    client = NewsApiClient(settings)

    articles = client.search(query="markets", page_size=1)
    with pytest.raises(NewsApiIntegrationError):
        client.search(query="markets", page_size=1)

    events = _events(session_factory)
    assert articles[0].title == "Markets rally"
    assert FakeClient.calls == 2
    assert [event.service for event in events] == [
        MonitoringServiceName.NEWSAPI,
        MonitoringServiceName.NEWSAPI,
    ]
    assert [event.status for event in events] == [
        MonitoringEventStatus.SUCCESS,
        MonitoringEventStatus.FAILURE,
    ]
    assert events[0].endpoint == "/everything"
    assert events[1].http_status_code == 429
    assert "secret" not in (events[1].error_message or "")


def test_newsapi_missing_key_before_request_is_not_recorded(monitoring_context) -> None:
    _, session_factory, settings = monitoring_context
    settings.newsapi_api_key = None
    client = NewsApiClient(settings)

    with pytest.raises(NewsApiIntegrationError):
        client.search(query="markets")

    assert _events(session_factory) == []


def test_newsapi_failure_then_mock_fallback_records_only_real_external_request(
    monitoring_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, session_factory, settings = monitoring_context
    settings.newsapi_api_key = SecretStr("test-news-key")

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, *args, **kwargs):
            return httpx.Response(
                200,
                json={"status": "error", "code": "rateLimited", "message": "quota exceeded"},
                request=httpx.Request("GET", "https://newsapi.org/v2/everything"),
            )

    monkeypatch.setattr(httpx, "Client", FakeClient)
    client = NewsApiClient(settings)

    with pytest.raises(NewsApiIntegrationError):
        client.search(query="markets", page_size=1)

    fallback_articles = [
        {
            "title": "Mock market update",
            "source_name": "Local mock",
        }
    ]
    events = _events(session_factory)
    assert fallback_articles[0]["title"] == "Mock market update"
    assert len(events) == 1
    assert events[0].service == MonitoringServiceName.NEWSAPI
    assert events[0].status == MonitoringEventStatus.FAILURE
    assert events[0].error_type == "rateLimited"


def test_pandaai_retry_records_each_real_external_request_once(monitoring_context) -> None:
    _, session_factory, settings = monitoring_context
    settings.pandaai_username = "user"
    settings.pandaai_password = "password"
    settings.pandaai_max_retries = 1
    client = PandaAIClient(settings)
    client._token = "cached-token"
    client._token_expires_at = time.time() + 3600
    data_requests = 0

    def unauthorized_post(*args, **kwargs):
        nonlocal data_requests
        data_requests += 1
        return 401, {"Content-Type": "application/json"}, b"{}"

    client._post_with_httpx = unauthorized_post

    def refresh_fails(*, force_refresh: bool) -> str:
        if force_refresh:
            raise PandaAIIntegrationError("refresh failed")
        return "cached-token"

    client._ensure_token = refresh_fails

    with pytest.raises(PandaAIIntegrationError):
        client._post_data("/multi/getStockDaily", {"symbol": ["AAPL"]})

    events = _events(session_factory)
    assert data_requests == 1
    assert len(events) == 1
    assert events[0].status == MonitoringEventStatus.FAILURE
    assert events[0].http_status_code == 401


def test_pandaai_monitoring_failure_does_not_break_successful_call(
    monitoring_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, settings = monitoring_context
    import app.modules.monitoring.service as monitoring_service

    def fail_session_factory(*args, **kwargs):
        raise RuntimeError("monitoring database unavailable")

    monkeypatch.setattr(monitoring_service, "get_session_factory", fail_session_factory)
    settings.pandaai_username = "user"
    settings.pandaai_password = "password"
    client = PandaAIClient(settings)
    client._token = "cached-token"
    client._token_expires_at = time.time() + 3600
    client._post_with_httpx = lambda *args, **kwargs: (
        200,
        {"Content-Type": "application/json"},
        json.dumps({"code": "200", "data": [{"ok": True}]}).encode(),
    )

    assert client._post_data("/multi/getStockDaily", {"symbol": ["AAPL"]}) == [{"ok": True}]


def test_siliconflow_success_and_failure_calls_are_recorded(monitoring_context) -> None:
    _, session_factory, settings = monitoring_context

    def success_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "ok",
                "model": TEST_MODEL,
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            },
        )

    success_client = SiliconFlowClient(
        api_key="test-api-key",
        base_url="https://api.siliconflow.com/v1",
        model=TEST_MODEL,
        timeout_seconds=1,
        max_tokens=32,
        transport=httpx.MockTransport(success_handler),
        settings=settings,
    )
    result = asyncio.run(success_client.chat([SiliconFlowMessage(role="user", content="Hello")]))
    assert result.text == "ok"

    def failure_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "provider unavailable"})

    failure_client = SiliconFlowClient(
        api_key="test-api-key",
        base_url="https://api.siliconflow.com/v1",
        model=TEST_MODEL,
        timeout_seconds=1,
        max_tokens=32,
        transport=httpx.MockTransport(failure_handler),
        settings=settings,
    )
    with pytest.raises(Exception):
        asyncio.run(failure_client.chat([SiliconFlowMessage(role="user", content="Hello")]))

    events = _events(session_factory)
    ai_events = [event for event in events if event.service == MonitoringServiceName.AI_MODEL]
    assert [event.status for event in ai_events] == [
        MonitoringEventStatus.SUCCESS,
        MonitoringEventStatus.FAILURE,
    ]
    assert ai_events[0].endpoint == "/chat/completions"
    assert ai_events[1].http_status_code == 503


def test_siliconflow_configuration_failure_before_request_is_not_recorded(monitoring_context) -> None:
    _, session_factory, settings = monitoring_context
    client = SiliconFlowClient(
        api_key=None,
        base_url="https://api.siliconflow.com/v1",
        model=TEST_MODEL,
        timeout_seconds=1,
        max_tokens=32,
        settings=settings,
    )

    with pytest.raises(Exception):
        asyncio.run(client.chat([SiliconFlowMessage(role="user", content="Hello")]))

    assert _events(session_factory) == []
