from datetime import date, timedelta

import pytest

from app.core.errors import ApplicationError
from app.modules.quant.schemas import (
    DailyBar,
    RiskFlag,
    TechnicalSummary,
    TrendState,
)
from app.modules.quant.service import analyze_symbol_technical_summary


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
