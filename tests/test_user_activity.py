from __future__ import annotations

from collections.abc import Generator, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.errors import ApplicationError
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.integrations.siliconflow.client import SiliconFlowChatResult, SiliconFlowMessage
from app.main import create_app
from app.modules.activity.models import UserDailyActivity
from app.modules.activity.service import (
    UserActivityEvent,
    get_user_activity_summary,
    record_user_activity,
)
from app.modules.ai.router import get_ai_service
from app.modules.ai.service import AIService
from app.modules.market.schemas import MarketDailyBarData, MarketStockSnapshotData
from app.modules.market.service import get_market_stock_service
from app.modules.paper_trading.quote_provider import (
    PaperTradingQuote,
    PaperTradingQuoteProvider,
    get_paper_trading_quote_provider,
)
from app.modules.paper_trading.models import (
    PaperAccount,
    PaperAccountResetEvent,
    PaperExecution,
    PaperOrder,
    PaperPosition,
)
from app.modules.paper_trading.service import PaperTradingService
from app.modules.users.models import User, UserRole, UserStatus
from app.modules.users.service import create_user


TEST_PASSWORD = "test-only-password"
TEST_MODEL = "deepseek-ai/DeepSeek-V4-Flash"


class FakeAIIntegration:
    def __init__(self, *, reply: str = "ok") -> None:
        self.reply = reply
        self.calls = 0

    async def chat(
        self,
        messages: Sequence[SiliconFlowMessage],
    ) -> SiliconFlowChatResult:
        self.calls += 1
        return SiliconFlowChatResult(text=self.reply)


class StubMarketService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def get_daily_bars(
        self,
        symbol: str,
        limit: int,
    ) -> list[MarketDailyBarData]:
        self.calls.append((symbol, limit))
        return [
            MarketDailyBarData(
                ticker=symbol,
                trade_date=date(2026, 1, 1) + timedelta(days=index),
                open=100.0 + index,
                high=101.0 + index,
                low=99.0 + index,
                close=100.0 + index,
                previous_close=99.0 + index,
                volume=10_000 + index,
            )
            for index in range(limit)
        ]

    def get_stock_snapshot(self, symbol: str) -> MarketStockSnapshotData:
        self.calls.append((symbol, 1))
        return MarketStockSnapshotData(
            ticker=symbol,
            company_name="Example Corp.",
            exchange_label="NASDAQ",
            latest_trading_date=date(2026, 8, 12),
            latest_close=210.5,
            previous_close=208.0,
            change_value=2.5,
            change_percent=1.2,
            open=208.5,
            high=212.0,
            low=207.8,
            volume=12_000_000,
            amount=2_500_000_000,
            market_cap=3_000_000_000_000,
            pe_ratio=30.5,
            valuation_date=date(2026, 8, 12),
        )


class StaticQuoteProvider(PaperTradingQuoteProvider):
    def get_quote(self, symbol: str) -> PaperTradingQuote:
        normalized = symbol.strip().upper()
        if normalized == "00700":
            normalized = "00700.HK"
        if normalized != "00700.HK":
            raise ApplicationError(f"Unknown paper trading symbol: {normalized}.", status_code=404)
        return PaperTradingQuote(
            symbol="00700.HK",
            name="Tencent Holdings",
            price=Decimal("380.00"),
            currency="HKD",
            timestamp=datetime(2026, 8, 3, 9, 30, tzinfo=UTC),
        )


@pytest.fixture
def activity_context(tmp_path) -> Generator[tuple[TestClient, sessionmaker[Session], Settings], None, None]:
    database_url = f"sqlite:///{tmp_path / 'activity_test.db'}"
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
        paper_trading_demo_account_key="demo",
        paper_trading_initial_cash=Decimal("200000"),
        paper_trading_currency="HKD",
        paper_trading_quote_provider="mock",
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
    app.dependency_overrides[get_paper_trading_quote_provider] = StaticQuoteProvider
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
    created_at: datetime | None = None,
) -> User:
    with session_factory() as db:
        user = create_user(
            db,
            username=username,
            password=TEST_PASSWORD,
            role=role,
            status=status,
        )
        if created_at is not None:
            user.created_at = created_at
            user.updated_at = created_at
            db.commit()
            db.refresh(user)
        return user


def _authorization(user: User, settings: Settings, *, expires_delta: timedelta | None = None) -> dict[str, str]:
    token = create_access_token(user.id, settings, expires_delta=expires_delta)
    return {"Authorization": f"Bearer {token}"}


def _activity_rows(session_factory: sessionmaker[Session]) -> list[UserDailyActivity]:
    with session_factory() as db:
        return list(db.scalars(select(UserDailyActivity).order_by(UserDailyActivity.id)).all())


def _without_tz(value: datetime) -> datetime:
    return value.replace(tzinfo=None)


def test_record_user_activity_upserts_same_user_same_day(activity_context) -> None:
    _, session_factory, _ = activity_context
    user = _create_user(session_factory, username="active-user")
    first = datetime(2026, 8, 12, 1, 2, 3, tzinfo=UTC)
    second = datetime(2026, 8, 12, 8, 9, 10, tzinfo=UTC)

    with session_factory() as db:
        db_user = db.get(User, user.id)
        record_user_activity(db, user=db_user, event=UserActivityEvent.AI_CHAT, occurred_at=first)
    with session_factory() as db:
        db_user = db.get(User, user.id)
        record_user_activity(db, user=db_user, event=UserActivityEvent.QUANT_ANALYSIS, occurred_at=second)

    rows = _activity_rows(session_factory)
    assert len(rows) == 1
    assert rows[0].user_id == user.id
    assert rows[0].activity_date == date(2026, 8, 12)
    assert rows[0].first_seen_at == _without_tz(first)
    assert rows[0].last_seen_at == _without_tz(second)
    assert rows[0].event_count == 2


def test_record_user_activity_separates_users_and_dates(activity_context) -> None:
    _, session_factory, _ = activity_context
    first_user = _create_user(session_factory, username="first-user")
    second_user = _create_user(session_factory, username="second-user")

    with session_factory() as db:
        record_user_activity(
            db,
            user=db.get(User, first_user.id),
            event=UserActivityEvent.AI_CHAT,
            occurred_at=datetime(2026, 8, 11, 23, 59, tzinfo=UTC),
        )
    with session_factory() as db:
        record_user_activity(
            db,
            user=db.get(User, first_user.id),
            event=UserActivityEvent.AI_CHAT,
            occurred_at=datetime(2026, 8, 12, 0, 1, tzinfo=UTC),
        )
    with session_factory() as db:
        record_user_activity(
            db,
            user=db.get(User, second_user.id),
            event=UserActivityEvent.PAPER_ORDER,
            occurred_at=datetime(2026, 8, 12, 3, 0, tzinfo=UTC),
        )

    rows = _activity_rows(session_factory)
    assert len(rows) == 3
    assert {(row.user_id, row.activity_date) for row in rows} == {
        (first_user.id, date(2026, 8, 11)),
        (first_user.id, date(2026, 8, 12)),
        (second_user.id, date(2026, 8, 12)),
    }


def test_record_user_activity_skips_admins(activity_context) -> None:
    _, session_factory, _ = activity_context
    admin = _create_user(session_factory, username="admin-user", role=UserRole.ADMIN)

    with session_factory() as db:
        record_user_activity(
            db,
            user=db.get(User, admin.id),
            event=UserActivityEvent.AI_CHAT,
            occurred_at=datetime(2026, 8, 12, tzinfo=UTC),
        )

    assert _activity_rows(session_factory) == []


def test_user_activity_summary_counts_dau_mau_and_new_users(activity_context) -> None:
    _, session_factory, _ = activity_context
    as_of = date(2026, 8, 12)
    user_today = _create_user(
        session_factory,
        username="today-user",
        created_at=datetime(2026, 8, 12, 4, 0, tzinfo=UTC),
    )
    user_window_edge = _create_user(
        session_factory,
        username="window-edge",
        created_at=datetime(2026, 8, 11, 4, 0, tzinfo=UTC),
    )
    user_too_old = _create_user(
        session_factory,
        username="old-user",
        created_at=datetime(2026, 7, 1, 4, 0, tzinfo=UTC),
    )
    _create_user(
        session_factory,
        username="admin-created-today",
        role=UserRole.ADMIN,
        created_at=datetime(2026, 8, 12, 5, 0, tzinfo=UTC),
    )

    with session_factory() as db:
        record_user_activity(
            db,
            user=db.get(User, user_today.id),
            event=UserActivityEvent.AI_CHAT,
            occurred_at=datetime(2026, 8, 12, 12, 0, tzinfo=UTC),
        )
    with session_factory() as db:
        record_user_activity(
            db,
            user=db.get(User, user_window_edge.id),
            event=UserActivityEvent.AI_CHAT,
            occurred_at=datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
        )
    with session_factory() as db:
        record_user_activity(
            db,
            user=db.get(User, user_too_old.id),
            event=UserActivityEvent.AI_CHAT,
            occurred_at=datetime(2026, 7, 13, 12, 0, tzinfo=UTC),
        )

    with session_factory() as db:
        summary = get_user_activity_summary(
            db,
            as_of_date=as_of,
            start_date=date(2026, 8, 10),
            end_date=date(2026, 8, 12),
        )

    assert summary.dau == 1
    assert summary.mau == 2
    assert [(item.date, item.count) for item in summary.daily_dau] == [
        (date(2026, 8, 10), 0),
        (date(2026, 8, 11), 0),
        (date(2026, 8, 12), 1),
    ]
    assert [(item.date, item.count) for item in summary.daily_new_users] == [
        (date(2026, 8, 10), 0),
        (date(2026, 8, 11), 1),
        (date(2026, 8, 12), 1),
    ]


def test_admin_user_activity_summary_permissions_and_validation(activity_context) -> None:
    client, session_factory, settings = activity_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    regular_user = _create_user(session_factory, username="regular-user")
    disabled_admin = _create_user(
        session_factory,
        username="disabled-admin",
        role=UserRole.ADMIN,
        status=UserStatus.DISABLED,
    )

    assert client.get("/api/v1/admin/user-activity-summary").status_code == 401
    assert client.get(
        "/api/v1/admin/user-activity-summary",
        headers=_authorization(regular_user, settings),
    ).status_code == 403
    assert client.get(
        "/api/v1/admin/user-activity-summary",
        headers=_authorization(disabled_admin, settings),
    ).status_code == 401

    headers = _authorization(admin, settings)
    invalid_order = client.get(
        "/api/v1/admin/user-activity-summary",
        params={"start_date": "2026-08-12", "end_date": "2026-08-10"},
        headers=headers,
    )
    too_large = client.get(
        "/api/v1/admin/user-activity-summary",
        params={"start_date": "2025-01-01", "end_date": "2026-08-12"},
        headers=headers,
    )

    assert invalid_order.status_code == 422
    assert too_large.status_code == 422


def test_admin_user_activity_summary_returns_zero_filled_payload(activity_context) -> None:
    client, session_factory, settings = activity_context
    admin = _create_user(session_factory, username="admin", role=UserRole.ADMIN)
    user = _create_user(
        session_factory,
        username="regular-user",
        created_at=datetime(2026, 8, 11, 9, 0, tzinfo=UTC),
    )
    with session_factory() as db:
        record_user_activity(
            db,
            user=db.get(User, user.id),
            event=UserActivityEvent.QUANT_ANALYSIS,
            occurred_at=datetime(2026, 8, 12, 10, 0, tzinfo=UTC),
        )

    response = client.get(
        "/api/v1/admin/user-activity-summary",
        params={
            "as_of_date": "2026-08-12",
            "start_date": "2026-08-10",
            "end_date": "2026-08-12",
        },
        headers=_authorization(admin, settings),
    )

    assert response.status_code == 200
    assert response.json() == {
        "as_of_date": "2026-08-12",
        "start_date": "2026-08-10",
        "end_date": "2026-08-12",
        "dau": 1,
        "mau": 1,
        "daily_dau": [
            {"date": "2026-08-10", "count": 0},
            {"date": "2026-08-11", "count": 0},
            {"date": "2026-08-12", "count": 1},
        ],
        "daily_new_users": [
            {"date": "2026-08-10", "count": 0},
            {"date": "2026-08-11", "count": 1},
            {"date": "2026-08-12", "count": 0},
        ],
    }


def test_ai_chat_records_one_activity_for_authenticated_regular_user(activity_context) -> None:
    client, session_factory, settings = activity_context
    user = _create_user(session_factory, username="regular-user")
    integration = FakeAIIntegration(reply="answered")
    market_service = StubMarketService()
    client.app.dependency_overrides[get_ai_service] = lambda: AIService(
        integration,
        market_service=market_service,
    )

    response = client.post(
        "/api/v1/ai/chat",
        json={"message": "Tell me about AAPL", "history": []},
        headers=_authorization(user, settings),
    )

    assert response.status_code == 200
    assert integration.calls == 1
    assert market_service.calls == [("AAPL", 1)]
    rows = _activity_rows(session_factory)
    assert len(rows) == 1
    assert rows[0].user_id == user.id
    assert rows[0].event_count == 1


def test_anonymous_and_admin_ai_chat_do_not_record_activity(activity_context) -> None:
    client, session_factory, settings = activity_context
    admin = _create_user(session_factory, username="admin-user", role=UserRole.ADMIN)
    client.app.dependency_overrides[get_ai_service] = lambda: AIService(FakeAIIntegration())

    anonymous = client.post("/api/v1/ai/chat", json={"message": "Hello"})
    admin_response = client.post(
        "/api/v1/ai/chat",
        json={"message": "Hello again"},
        headers=_authorization(admin, settings),
    )

    assert anonymous.status_code == 200
    assert admin_response.status_code == 200
    assert _activity_rows(session_factory) == []


def test_invalid_or_expired_token_is_rejected_and_not_recorded(activity_context) -> None:
    client, session_factory, settings = activity_context
    user = _create_user(session_factory, username="regular-user")
    client.app.dependency_overrides[get_ai_service] = lambda: AIService(FakeAIIntegration())

    invalid = client.post(
        "/api/v1/ai/chat",
        json={"message": "Hello"},
        headers={"Authorization": "Bearer not-a-token"},
    )
    expired = client.post(
        "/api/v1/ai/chat",
        json={"message": "Hello"},
        headers=_authorization(user, settings, expires_delta=timedelta(seconds=-1)),
    )

    assert invalid.status_code == 401
    assert expired.status_code == 401
    assert _activity_rows(session_factory) == []


def test_quant_analysis_records_activity_but_technical_summary_does_not(activity_context) -> None:
    client, session_factory, settings = activity_context
    user = _create_user(session_factory, username="regular-user")
    market_service = StubMarketService()
    client.app.dependency_overrides[get_market_stock_service] = lambda: market_service
    headers = _authorization(user, settings)

    technical = client.get(
        "/api/v1/quant/stocks/aapl/technical-summary",
        params={"limit": 40},
        headers=headers,
    )
    assert technical.status_code == 200
    assert _activity_rows(session_factory) == []

    analysis = client.get(
        "/api/v1/quant/stocks/aapl/analysis",
        params={"limit": 40},
        headers=headers,
    )

    assert analysis.status_code == 200
    rows = _activity_rows(session_factory)
    assert len(rows) == 1
    assert rows[0].user_id == user.id
    assert rows[0].event_count == 1


def test_paper_order_records_activity_but_read_only_requests_do_not(activity_context) -> None:
    client, session_factory, settings = activity_context
    user = _create_user(session_factory, username="regular-user")
    headers = _authorization(user, settings)

    portfolio = client.get("/api/v1/paper-trading/portfolio", headers=headers)
    orders = client.get("/api/v1/paper-trading/orders", headers=headers)
    assert portfolio.status_code == 200
    assert orders.status_code == 200
    assert _activity_rows(session_factory) == []

    order = client.post(
        "/api/v1/paper-trading/orders",
        json={"symbol": "00700.HK", "side": "buy", "quantity": 1},
        headers=headers,
    )

    assert order.status_code == 200
    rows = _activity_rows(session_factory)
    assert len(rows) == 1
    assert rows[0].user_id == user.id
    assert rows[0].event_count == 1


def test_authenticated_paper_buy_persists_records_after_auth_autobegin(activity_context) -> None:
    client, session_factory, settings = activity_context
    user = _create_user(session_factory, username="regular-user")

    response = client.post(
        "/api/v1/paper-trading/orders",
        json={"symbol": "00700.HK", "side": "buy", "quantity": 2},
        headers=_authorization(user, settings),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["order"]["status"] == "filled"
    assert payload["execution"]["price"] == 380.0
    assert payload["summary"]["available_cash"] == 199240.0

    with session_factory() as db:
        account = db.scalar(select(PaperAccount))
        assert account is not None
        assert account.available_cash == Decimal("199240.0000")
        position = db.scalar(select(PaperPosition).where(PaperPosition.symbol == "00700.HK"))
        assert position is not None
        assert position.quantity == 2
        assert db.scalar(select(func.count(PaperOrder.id))) == 1
        assert db.scalar(select(func.count(PaperExecution.id))) == 1
        assert db.scalar(select(func.count(UserDailyActivity.id))) == 1


def test_authenticated_paper_sell_has_no_nested_transaction_error(activity_context) -> None:
    client, session_factory, settings = activity_context
    user = _create_user(session_factory, username="regular-user")
    headers = _authorization(user, settings)

    buy = client.post(
        "/api/v1/paper-trading/orders",
        json={"symbol": "00700.HK", "side": "buy", "quantity": 3},
        headers=headers,
    )
    sell = client.post(
        "/api/v1/paper-trading/orders",
        json={"symbol": "00700.HK", "side": "sell", "quantity": 1},
        headers=headers,
    )

    assert buy.status_code == 200
    assert sell.status_code == 200
    with session_factory() as db:
        position = db.scalar(select(PaperPosition).where(PaperPosition.symbol == "00700.HK"))
        assert position is not None
        assert position.quantity == 2
        assert db.scalar(select(func.count(PaperOrder.id))) == 2
        assert db.scalar(select(func.count(PaperExecution.id))) == 2
        activity = db.scalar(select(UserDailyActivity).where(UserDailyActivity.user_id == user.id))
        assert activity is not None
        assert activity.event_count == 2


def test_admin_token_paper_order_does_not_record_user_activity(activity_context) -> None:
    client, session_factory, settings = activity_context
    admin = _create_user(session_factory, username="admin-user", role=UserRole.ADMIN)

    response = client.post(
        "/api/v1/paper-trading/orders",
        json={"symbol": "00700.HK", "side": "buy", "quantity": 1},
        headers=_authorization(admin, settings),
    )

    assert response.status_code == 200
    with session_factory() as db:
        assert db.scalar(select(func.count(PaperOrder.id))) == 1
        assert db.scalar(select(func.count(UserDailyActivity.id))) == 0


def test_activity_recording_failure_does_not_rollback_successful_paper_order(
    activity_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.modules.paper_trading.router as paper_router

    client, session_factory, settings = activity_context
    user = _create_user(session_factory, username="regular-user")

    def fail_activity_recording(*args, **kwargs) -> None:
        raise RuntimeError("activity write failed")

    monkeypatch.setattr(paper_router, "record_user_activity", fail_activity_recording)

    response = client.post(
        "/api/v1/paper-trading/orders",
        json={"symbol": "00700.HK", "side": "buy", "quantity": 1},
        headers=_authorization(user, settings),
    )

    assert response.status_code == 200
    with session_factory() as db:
        account = db.scalar(select(PaperAccount))
        assert account is not None
        assert account.available_cash == Decimal("199620.0000")
        assert db.scalar(select(func.count(PaperPosition.id))) == 1
        assert db.scalar(select(func.count(PaperOrder.id))) == 1
        assert db.scalar(select(func.count(PaperExecution.id))) == 1
        assert db.scalar(select(func.count(UserDailyActivity.id))) == 0


def test_failed_paper_order_does_not_record_activity(activity_context) -> None:
    client, session_factory, settings = activity_context
    user = _create_user(session_factory, username="regular-user")

    response = client.post(
        "/api/v1/paper-trading/orders",
        json={"symbol": "UNKNOWN", "side": "buy", "quantity": 1},
        headers=_authorization(user, settings),
    )

    assert response.status_code == 404
    assert _activity_rows(session_factory) == []


def test_failed_paper_buy_rolls_back_account_created_in_request(activity_context) -> None:
    client, session_factory, settings = activity_context
    user = _create_user(session_factory, username="regular-user")

    response = client.post(
        "/api/v1/paper-trading/orders",
        json={"symbol": "00700.HK", "side": "buy", "quantity": 1000},
        headers=_authorization(user, settings),
    )

    assert response.status_code == 409
    with session_factory() as db:
        assert db.scalar(select(func.count(PaperAccount.id))) == 0
        assert db.scalar(select(func.count(PaperPosition.id))) == 0
        assert db.scalar(select(func.count(PaperOrder.id))) == 0
        assert db.scalar(select(func.count(PaperExecution.id))) == 0
        assert db.scalar(select(func.count(UserDailyActivity.id))) == 0


def test_paper_reset_requires_regular_user_and_clears_owned_account(activity_context) -> None:
    client, session_factory, settings = activity_context
    user = _create_user(session_factory, username="regular-user")
    admin = _create_user(session_factory, username="admin-user", role=UserRole.ADMIN)
    user_headers = _authorization(user, settings)

    buy = client.post(
        "/api/v1/paper-trading/orders",
        json={"symbol": "00700.HK", "side": "buy", "quantity": 3},
        headers=user_headers,
    )
    reset_missing = client.post("/api/v1/paper-trading/reset")
    reset_admin = client.post(
        "/api/v1/paper-trading/reset",
        headers=_authorization(admin, settings),
    )
    reset = client.post("/api/v1/paper-trading/reset", headers=user_headers)

    assert buy.status_code == 200
    assert reset_missing.status_code == 401
    assert reset_admin.status_code == 403
    assert reset.status_code == 200
    payload = reset.json()
    assert payload["account"]["account_key"] == f"user:{user.id}"
    assert payload["summary"]["initial_cash"] == 200000.0
    assert payload["summary"]["available_cash"] == 200000.0
    assert payload["summary"]["market_value"] == 0.0
    assert payload["summary"]["total_profit_loss"] == 0.0
    assert payload["positions"] == []

    with session_factory() as db:
        account = db.scalar(select(PaperAccount).where(PaperAccount.user_id == user.id))
        assert account is not None
        assert account.account_key == f"user:{user.id}"
        assert account.available_cash == Decimal("200000.0000")
        assert db.scalar(select(func.count(PaperPosition.id))) == 0
        assert db.scalar(select(func.count(PaperOrder.id))) == 0
        assert db.scalar(select(func.count(PaperExecution.id))) == 0
        reset_event = db.scalar(select(PaperAccountResetEvent))
        assert reset_event is not None
        assert reset_event.user_id == user.id
        assert reset_event.result == "success"


def test_paper_reset_is_user_scoped_and_repeatable(activity_context) -> None:
    client, session_factory, settings = activity_context
    first_user = _create_user(session_factory, username="first-user")
    second_user = _create_user(session_factory, username="second-user")
    first_headers = _authorization(first_user, settings)
    second_headers = _authorization(second_user, settings)

    assert client.post(
        "/api/v1/paper-trading/orders",
        json={"symbol": "00700.HK", "side": "buy", "quantity": 5},
        headers=first_headers,
    ).status_code == 200
    assert client.post(
        "/api/v1/paper-trading/orders",
        json={"symbol": "00700.HK", "side": "buy", "quantity": 2},
        headers=second_headers,
    ).status_code == 200

    first_reset = client.post("/api/v1/paper-trading/reset", headers=first_headers)
    repeated_reset = client.post("/api/v1/paper-trading/reset", headers=first_headers)

    assert first_reset.status_code == 200
    assert repeated_reset.status_code == 200
    with session_factory() as db:
        first_account = db.scalar(select(PaperAccount).where(PaperAccount.user_id == first_user.id))
        second_account = db.scalar(select(PaperAccount).where(PaperAccount.user_id == second_user.id))
        assert first_account is not None
        assert second_account is not None
        assert first_account.available_cash == Decimal("200000.0000")
        assert second_account.available_cash == Decimal("199240.0000")
        assert db.scalar(select(func.count(PaperAccount.id))) == 2
        assert db.scalar(select(func.count(PaperOrder.id))) == 1
        assert db.scalar(select(func.count(PaperAccountResetEvent.id))) == 2


def test_paper_reset_failure_rolls_back_all_business_changes(
    activity_context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session_factory, settings = activity_context
    user = _create_user(session_factory, username="rollback-user")
    headers = _authorization(user, settings)

    assert client.post(
        "/api/v1/paper-trading/orders",
        json={"symbol": "00700.HK", "side": "buy", "quantity": 3},
        headers=headers,
    ).status_code == 200

    with session_factory() as db:
        account = db.scalar(select(PaperAccount).where(PaperAccount.user_id == user.id))
        assert account is not None
        original_cash = account.available_cash
        original_counts = (
            db.scalar(select(func.count(PaperPosition.id))),
            db.scalar(select(func.count(PaperOrder.id))),
            db.scalar(select(func.count(PaperExecution.id))),
        )
        service = PaperTradingService(
            db,
            StaticQuoteProvider(),
            settings,
            user_id=user.id,
        )

        def fail_response_build(_account: PaperAccount):
            raise RuntimeError("reset response build failed")

        monkeypatch.setattr(service, "_build_portfolio", fail_response_build)
        with pytest.raises(RuntimeError, match="reset response build failed"):
            service.reset_account()

    with session_factory() as db:
        account = db.scalar(select(PaperAccount).where(PaperAccount.user_id == user.id))
        assert account is not None
        assert account.available_cash == original_cash
        assert (
            db.scalar(select(func.count(PaperPosition.id))),
            db.scalar(select(func.count(PaperOrder.id))),
            db.scalar(select(func.count(PaperExecution.id))),
        ) == original_counts
        events = list(db.scalars(select(PaperAccountResetEvent)))
        assert len(events) == 1
        assert events[0].user_id == user.id
        assert events[0].result == "failure"
