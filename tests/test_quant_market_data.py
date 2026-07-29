from datetime import date, timedelta

import pytest

from app.modules.quant.schemas import DailyBar, TechnicalSummary
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