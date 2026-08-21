from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.errors import ApplicationError
from app.main import create_app
from app.modules.market.schemas import MarketDailyBarData
from app.modules.market.service import get_market_stock_service
from app.modules.quant.market_data import MarketServiceDataProvider
from app.modules.quant.schemas import (
    DailyBar,
    RiskFlag,
    TechnicalSummary,
    TrendState,
)
from app.modules.quant.service import (
    analyze_symbol_stock,
    analyze_symbol_technical_summary,
)


class StubMarketData:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def get_daily_bars(
        self,
        symbol: str,
        limit: int,
    ) -> list[DailyBar]:
        self.calls.append((symbol, limit))

        return [
            DailyBar(
                trade_date=date(2026, 1, 1) + timedelta(days=index),
                open=100 + index,
                high=100 + index,
                low=100 + index,
                close=100 + index,
                volume=1000,
            )
            for index in range(limit)
        ]


def test_analyze_symbol_uses_market_data_once() -> None:
    market_data = StubMarketData()

    result = analyze_symbol_technical_summary(
        symbol=" aapl ",
        market_data=market_data,
        limit=40,
    )

    assert isinstance(result, TechnicalSummary)
    assert market_data.calls == [("AAPL", 40)]


def test_analyze_symbol_rejects_blank_symbol() -> None:
    market_data = StubMarketData()

    with pytest.raises(ValueError, match="symbol must not be blank"):
        analyze_symbol_technical_summary(
            symbol="   ",
            market_data=market_data,
        )

    assert market_data.calls == []


def test_analyze_symbol_rejects_invalid_limit() -> None:
    market_data = StubMarketData()

    with pytest.raises(ValueError, match="limit must be greater than zero"):
        analyze_symbol_technical_summary(
            symbol="AAPL",
            market_data=market_data,
            limit=0,
        )

    assert market_data.calls == []


def test_normalize_daily_bars_sorts_newest_first_data() -> None:
    market_data = StubMarketData()
    original_get_daily_bars = market_data.get_daily_bars

    def get_reversed_bars(
        symbol: str,
        limit: int,
    ) -> list[DailyBar]:
        return list(reversed(original_get_daily_bars(symbol, limit)))

    market_data.get_daily_bars = get_reversed_bars

    result = analyze_symbol_technical_summary(
        symbol="AAPL",
        market_data=market_data,
        limit=40,
    )

    assert isinstance(result, TechnicalSummary)
    assert result.trend == TrendState.UPWARD
    assert market_data.calls == [("AAPL", 40)]


def test_normalize_daily_bars_rejects_duplicate_dates() -> None:
    market_data = StubMarketData()

    def get_duplicate_bars(
        symbol: str,
        limit: int,
    ) -> list[DailyBar]:
        bars = market_data.get_daily_bars(symbol, limit)
        return [*bars, bars[-1]]

    with pytest.raises(
        ValueError,
        match="daily bars must not contain duplicate trade dates",
    ):
        analyze_symbol_technical_summary(
            symbol="AAPL",
            market_data=type(
                "DuplicateMarketData",
                (),
                {"get_daily_bars": staticmethod(get_duplicate_bars)},
            )(),
            limit=40,
        )


def test_analyze_symbol_rejects_empty_market_data() -> None:
    class EmptyMarketData:
        def get_daily_bars(
            self,
            symbol: str,
            limit: int,
        ) -> list[DailyBar]:
            return []

    with pytest.raises(ApplicationError) as error:
        analyze_symbol_technical_summary(
            symbol="AAPL",
            market_data=EmptyMarketData(),
        )

    assert error.value.status_code == 404
    assert error.value.message == "No market data is available for this symbol."


def test_analyze_symbol_returns_insufficient_state_for_short_history() -> None:
    market_data = StubMarketData()

    result = analyze_symbol_technical_summary(
        symbol="AAPL",
        market_data=market_data,
        limit=10,
    )

    assert result.trend == TrendState.INSUFFICIENT_DATA
    assert RiskFlag.DATA_INSUFFICIENT in result.risk_flags
    assert market_data.calls == [("AAPL", 10)]


def test_market_service_provider_maps_daily_bars() -> None:
    class StubMarketService:
        def get_daily_bars(
            self,
            symbol: str,
            limit: int,
        ) -> list[MarketDailyBarData]:
            assert symbol == "AAPL"
            assert limit == 1
            return [
                MarketDailyBarData(
                    ticker="AAPL",
                    trade_date=date(2026, 7, 29),
                    open=210.0,
                    high=215.0,
                    low=208.0,
                    close=214.0,
                    previous_close=209.0,
                    volume=12_345.0,
                )
            ]

    provider = MarketServiceDataProvider(StubMarketService())
    bars = provider.get_daily_bars("AAPL", 1)

    assert len(bars) == 1
    assert bars[0].trade_date == date(2026, 7, 29)
    assert bars[0].previous_close == 209.0
    assert bars[0].volume == 12_345


def test_symbol_technical_summary_endpoint_uses_market_service() -> None:
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

    market_service = StubMarketService()
    app = create_app()
    app.dependency_overrides[get_market_stock_service] = lambda: market_service
    client = TestClient(app)

    response = client.get(
        "/api/v1/quant/stocks/aapl/technical-summary",
        params={"limit": 40},
    )

    assert response.status_code == 200
    assert market_service.calls == [("AAPL", 40)]
    assert response.json()["trend"] == "upward"


def test_analyze_symbol_stock_builds_complete_payload_once() -> None:
    market_data = StubMarketData()

    result = analyze_symbol_stock(
        symbol=" aapl ",
        market_data=market_data,
        limit=40,
    )

    assert result.symbol == "AAPL"
    assert len(result.bars) == 40
    assert result.latest_bar == result.bars[-1]
    assert result.ma5 is not None
    assert result.ma10 is not None
    assert result.ma20 is not None
    assert result.macd is not None
    assert result.rsi14 is not None
    assert result.volume is not None
    assert result.technical_summary.trend == TrendState.UPWARD
    assert market_data.calls == [("AAPL", 40)]


def test_symbol_analysis_endpoint_returns_complete_payload() -> None:
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

    market_service = StubMarketService()
    app = create_app()
    app.dependency_overrides[get_market_stock_service] = lambda: market_service
    client = TestClient(app)

    response = client.get(
        "/api/v1/quant/stocks/aapl/analysis",
        params={"limit": 40},
    )

    assert response.status_code == 200
    assert market_service.calls == [("AAPL", 40)]

    payload = response.json()
    assert payload["symbol"] == "AAPL"
    assert len(payload["bars"]) == 40
    assert payload["latest_bar"] == payload["bars"][-1]
    assert payload["ma5"] is not None
    assert payload["macd"] is not None
    assert payload["rsi14"] is not None
    assert payload["volume"] is not None
    assert payload["technical_summary"]["trend"] == "upward"

def test_factor_ic_analysis_endpoint_returns_complete_payload() -> None:
    class StubMarketService:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int]] = []

        def get_daily_bars(
            self,
            symbol: str,
            limit: int,
        ) -> list[MarketDailyBarData]:
            self.calls.append((symbol, limit))

            price_offset = {
                "AAPL": 0.8,
                "MSFT": 0.4,
                "NVDA": -0.2,
            }[symbol]

            return [
                MarketDailyBarData(
                    ticker=symbol,
                    trade_date=date(2026, 1, 1) + timedelta(days=index),
                    open=100.0 + price_offset * index,
                    high=101.0 + price_offset * index,
                    low=99.0 + price_offset * index,
                    close=100.0 + price_offset * index,
                    previous_close=(
                        None
                        if index == 0
                        else 100.0 + price_offset * (index - 1)
                    ),
                    volume=10_000 + index * 10,
                )
                for index in range(limit)
            ]

    market_service = StubMarketService()
    app = create_app()
    app.dependency_overrides[get_market_stock_service] = lambda: market_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/quant/factor-ic-analysis",
        json={
            "market": "united_states",
            "symbols": ["AAPL", "MSFT", "NVDA"],
            "history_limit": 45,
            "holding_period": 5,
            "minimum_lookback": 35,
            "minimum_sample_size": 3,
        },
    )

    assert response.status_code == 200
    assert market_service.calls == [
        ("AAPL", 45),
        ("MSFT", 45),
        ("NVDA", 45),
    ]

    payload = response.json()

    assert payload["market"] == "united_states"
    assert payload["symbols"] == ["AAPL", "MSFT", "NVDA"]
    assert payload["successful_symbols"] == ["AAPL", "MSFT", "NVDA"]
    assert payload["failed_stocks"] == []
    assert payload["history_limit"] == 45
    assert [
        result["factor_id"]
        for result in payload["factor_results"]
    ] == ["trend", "momentum", "volume"]
    assert all(
        result["periods"]
        for result in payload["factor_results"]
    )

def test_factor_ic_analysis_endpoint_rejects_mixed_markets() -> None:
    class UnexpectedMarketService:
        def get_daily_bars(
            self,
            symbol: str,
            limit: int,
        ) -> list[MarketDailyBarData]:
            raise AssertionError("Invalid symbols should be rejected first")

    app = create_app()
    app.dependency_overrides[get_market_stock_service] = (
        lambda: UnexpectedMarketService()
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/quant/factor-ic-analysis",
        json={
            "market": "united_states",
            "symbols": ["AAPL", "MSFT", "0700.HK"],
        },
    )

    assert response.status_code == 422
    assert "0700.HK" in response.json()["detail"]
