from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import ApplicationError
from app.db.base import Base
from app.main import create_app
from app.modules.paper_trading.dependencies import get_paper_trading_service
from app.modules.paper_trading.models import (
    PaperAccount,
    PaperExecution,
    PaperOrder,
    PaperPosition,
)
from app.modules.paper_trading.quote_provider import (
    PaperTradingQuote,
    PaperTradingQuoteProvider,
)
from app.modules.paper_trading.schemas import PaperOrderCreateRequest
from app.modules.paper_trading.service import PaperTradingService

TEST_MODEL = "deepseek-ai/DeepSeek-V4-Flash"


class MutableQuoteProvider(PaperTradingQuoteProvider):
    def __init__(self) -> None:
        timestamp = datetime(2026, 8, 3, 9, 30, tzinfo=timezone.utc)
        self.quotes = {
            "00700.HK": PaperTradingQuote(
                symbol="00700.HK",
                name="Tencent Holdings",
                price=Decimal("380.00"),
                currency="HKD",
                timestamp=timestamp,
            ),
            "AAPL": PaperTradingQuote(
                symbol="AAPL",
                name="Apple Inc.",
                price=Decimal("215.20"),
                currency="USD",
                timestamp=timestamp,
            ),
        }

    def get_quote(self, symbol: str) -> PaperTradingQuote:
        normalized = symbol.strip().upper()
        if normalized == "00700":
            normalized = "00700.HK"
        quote = self.quotes.get(normalized)
        if quote is None:
            raise ApplicationError(
                f"Unknown paper trading symbol: {normalized}.",
                status_code=404,
            )
        return quote


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'paper_trading_test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        cors_origins="",
        siliconflow_model=TEST_MODEL,
        paper_trading_demo_account_key="demo",
        paper_trading_initial_cash=Decimal("200000"),
        paper_trading_currency="HKD",
        paper_trading_quote_provider="mock",
    )


@pytest.fixture
def quote_provider() -> MutableQuoteProvider:
    return MutableQuoteProvider()


def make_service(
    session_factory,
    settings: Settings,
    quote_provider: MutableQuoteProvider,
) -> tuple[PaperTradingService, Session]:
    db = session_factory()
    return PaperTradingService(db, quote_provider, settings), db


def place_order(
    service: PaperTradingService,
    *,
    symbol: str = "00700.HK",
    side: str = "buy",
    quantity: int = 100,
):
    return service.place_order(
        PaperOrderCreateRequest(symbol=symbol, side=side, quantity=quantity)
    )


def test_demo_account_is_created_once_and_reused(
    session_factory,
    settings: Settings,
    quote_provider: MutableQuoteProvider,
) -> None:
    service, db = make_service(session_factory, settings, quote_provider)

    first = service.get_portfolio()
    second = service.get_portfolio()

    assert first.account.id == second.account.id
    assert db.scalar(select(func.count()).select_from(PaperAccount)) == 1
    db.close()


def test_empty_portfolio_returns_initial_cash_and_zero_positions(
    session_factory,
    settings: Settings,
    quote_provider: MutableQuoteProvider,
) -> None:
    service, db = make_service(session_factory, settings, quote_provider)

    portfolio = service.get_portfolio()

    assert portfolio.account.account_key == "demo"
    assert portfolio.account.currency == "HKD"
    assert portfolio.summary.initial_cash == Decimal("200000.00")
    assert portfolio.summary.available_cash == Decimal("200000.00")
    assert portfolio.summary.market_value == Decimal("0.00")
    assert portfolio.summary.total_assets == Decimal("200000.00")
    assert portfolio.summary.total_profit_loss == Decimal("0.00")
    assert portfolio.summary.total_profit_loss_percent == Decimal("0.00")
    assert portfolio.summary.position_ratio == Decimal("0.00")
    assert portfolio.positions == []
    db.close()


def test_portfolio_route_returns_empty_portfolio(
    session_factory,
    settings: Settings,
    quote_provider: MutableQuoteProvider,
) -> None:
    app = create_app(settings)

    def override_service():
        db = session_factory()
        try:
            yield PaperTradingService(db, quote_provider, settings)
        finally:
            db.close()

    app.dependency_overrides[get_paper_trading_service] = override_service

    with TestClient(app) as client:
        response = client.get("/api/v1/paper-trading/portfolio")

    assert response.status_code == 200
    payload = response.json()
    assert payload["account"]["account_key"] == "demo"
    assert payload["summary"]["initial_cash"] == 200000.0
    assert payload["positions"] == []


def test_successful_buy_persists_order_execution_and_position(
    session_factory,
    settings: Settings,
    quote_provider: MutableQuoteProvider,
) -> None:
    service, db = make_service(session_factory, settings, quote_provider)

    response = place_order(service, quantity=100)

    assert response.order.status == "filled"
    assert response.execution.price == Decimal("380.0000")
    assert response.summary.available_cash == Decimal("162000.00")
    position = db.scalar(select(PaperPosition).where(PaperPosition.symbol == "00700.HK"))
    assert position is not None
    assert position.quantity == 100
    assert position.average_cost == Decimal("380.0000")
    assert len(db.scalars(select(PaperOrder)).all()) == 1
    assert len(db.scalars(select(PaperExecution)).all()) == 1
    db.close()


def test_insufficient_cash_rejects_and_rolls_back(
    session_factory,
    settings: Settings,
    quote_provider: MutableQuoteProvider,
) -> None:
    service, db = make_service(session_factory, settings, quote_provider)
    before = service.count_records()

    with pytest.raises(ApplicationError) as exc_info:
        place_order(service, quantity=1000)

    assert exc_info.value.status_code == 409
    assert service.count_records() == before
    assert len(db.scalars(select(PaperPosition)).all()) == 0
    db.close()


def test_repeated_buys_update_weighted_average_cost(
    session_factory,
    settings: Settings,
    quote_provider: MutableQuoteProvider,
) -> None:
    service, db = make_service(session_factory, settings, quote_provider)
    place_order(service, quantity=100)
    quote_provider.quotes["00700.HK"] = PaperTradingQuote(
        symbol="00700.HK",
        name="Tencent Holdings",
        price=Decimal("400.00"),
        currency="HKD",
        timestamp=datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc),
    )

    place_order(service, quantity=100)

    position = db.scalar(select(PaperPosition).where(PaperPosition.symbol == "00700.HK"))
    assert position is not None
    assert position.quantity == 200
    assert position.average_cost == Decimal("390.0000")
    db.close()


def test_successful_partial_sell_preserves_average_cost(
    session_factory,
    settings: Settings,
    quote_provider: MutableQuoteProvider,
) -> None:
    service, db = make_service(session_factory, settings, quote_provider)
    place_order(service, quantity=100)

    response = place_order(service, side="sell", quantity=40)

    assert response.order.side == "sell"
    assert response.summary.available_cash == Decimal("177200.00")
    position = db.scalar(select(PaperPosition).where(PaperPosition.symbol == "00700.HK"))
    assert position is not None
    assert position.quantity == 60
    assert position.average_cost == Decimal("380.0000")
    db.close()


def test_insufficient_holdings_rejects_and_rolls_back(
    session_factory,
    settings: Settings,
    quote_provider: MutableQuoteProvider,
) -> None:
    service, db = make_service(session_factory, settings, quote_provider)
    place_order(service, quantity=50)
    before = service.count_records()

    with pytest.raises(ApplicationError) as exc_info:
        place_order(service, side="sell", quantity=51)

    assert exc_info.value.status_code == 409
    assert service.count_records() == before
    position = db.scalar(select(PaperPosition).where(PaperPosition.symbol == "00700.HK"))
    assert position is not None
    assert position.quantity == 50
    db.close()


def test_full_sell_removes_position(
    session_factory,
    settings: Settings,
    quote_provider: MutableQuoteProvider,
) -> None:
    service, db = make_service(session_factory, settings, quote_provider)
    place_order(service, quantity=25)

    place_order(service, side="sell", quantity=25)

    assert service.get_portfolio().positions == []
    assert db.scalar(select(PaperPosition).where(PaperPosition.symbol == "00700.HK")) is None
    db.close()


def test_short_selling_is_rejected(
    session_factory,
    settings: Settings,
    quote_provider: MutableQuoteProvider,
) -> None:
    service, db = make_service(session_factory, settings, quote_provider)
    before = service.count_records()

    with pytest.raises(ApplicationError) as exc_info:
        place_order(service, side="sell", quantity=1)

    assert exc_info.value.status_code == 404
    assert service.count_records() == before
    db.close()


def test_unknown_symbol_is_rejected(
    session_factory,
    settings: Settings,
    quote_provider: MutableQuoteProvider,
) -> None:
    service, db = make_service(session_factory, settings, quote_provider)

    with pytest.raises(ApplicationError) as exc_info:
        place_order(service, symbol="UNKNOWN", quantity=1)

    assert exc_info.value.status_code == 404
    assert len(db.scalars(select(PaperOrder)).all()) == 0
    db.close()


def test_currency_mismatch_is_rejected(
    session_factory,
    settings: Settings,
    quote_provider: MutableQuoteProvider,
) -> None:
    service, db = make_service(session_factory, settings, quote_provider)

    with pytest.raises(ApplicationError) as exc_info:
        place_order(service, symbol="AAPL", quantity=1)

    assert exc_info.value.status_code == 422
    assert len(db.scalars(select(PaperOrder)).all()) == 0
    db.close()


def test_portfolio_totals_and_percentages_are_correct(
    session_factory,
    settings: Settings,
    quote_provider: MutableQuoteProvider,
) -> None:
    service, db = make_service(session_factory, settings, quote_provider)
    place_order(service, quantity=100)
    quote_provider.quotes["00700.HK"] = PaperTradingQuote(
        symbol="00700.HK",
        name="Tencent Holdings",
        price=Decimal("400.00"),
        currency="HKD",
        timestamp=datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc),
    )

    portfolio = service.get_portfolio()

    assert portfolio.summary.available_cash == Decimal("162000.00")
    assert portfolio.summary.market_value == Decimal("40000.00")
    assert portfolio.summary.total_assets == Decimal("202000.00")
    assert portfolio.summary.total_profit_loss == Decimal("2000.00")
    assert portfolio.summary.total_profit_loss_percent == Decimal("1.00")
    assert portfolio.summary.position_ratio == Decimal("19.80")
    assert portfolio.positions[0].unrealized_profit_loss == Decimal("2000.00")
    assert portfolio.positions[0].unrealized_profit_loss_percent == Decimal("5.26")
    db.close()


def test_orders_are_returned_newest_first(
    session_factory,
    settings: Settings,
    quote_provider: MutableQuoteProvider,
) -> None:
    service, db = make_service(session_factory, settings, quote_provider)
    buy = place_order(service, quantity=10)
    sell = place_order(service, side="sell", quantity=5)

    orders = service.list_orders()

    assert [order.id for order in orders] == [sell.order.id, buy.order.id]
    assert service.list_orders(side="buy")[0].side == "buy"
    assert service.list_orders(status="filled")[0].status == "filled"
    db.close()


def test_malformed_symbol_is_rejected(
    session_factory,
    settings: Settings,
    quote_provider: MutableQuoteProvider,
) -> None:
    service, db = make_service(session_factory, settings, quote_provider)

    with pytest.raises(ApplicationError) as exc_info:
        place_order(service, symbol="bad symbol", quantity=1)

    assert exc_info.value.status_code == 422
    db.close()
