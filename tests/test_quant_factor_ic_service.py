from datetime import date, timedelta
import threading

import pytest

from app.core.errors import ApplicationError
from app.modules.quant.factor_ic_service import analyze_real_factor_ic
from app.modules.quant.schemas import (
    DailyBar,
    FactorIcAnalysisRequest,
    QuantMarket,
)


class StubMarketDataProvider:
    def __init__(
        self,
        bars_by_symbol: dict[str, tuple[DailyBar, ...]],
    ) -> None:
        self.bars_by_symbol = bars_by_symbol
        self.calls: list[tuple[str, int]] = []

    def get_daily_bars(
        self,
        symbol: str,
        limit: int,
    ) -> tuple[DailyBar, ...]:
        self.calls.append((symbol, limit))
        return self.bars_by_symbol.get(symbol, ())


def _make_bars(
    start_price: float,
    daily_change: float,
    count: int = 45,
) -> tuple[DailyBar, ...]:
    bars = []

    for index in range(count):
        close = start_price + daily_change * index

        bars.append(
            DailyBar(
                trade_date=date(2026, 1, 1) + timedelta(days=index),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1000 + index * 10,
            )
        )

    return tuple(bars)


def test_analyzes_three_factors_from_market_data() -> None:
    market_data = StubMarketDataProvider(
        {
            "AAPL": _make_bars(100.0, 1.0),
            "MSFT": _make_bars(200.0, 0.5),
            "NVDA": _make_bars(150.0, -0.25),
        }
    )
    request = FactorIcAnalysisRequest(
        market=QuantMarket.UNITED_STATES,
        symbols=("AAPL", "MSFT", "NVDA"),
    )

    response = analyze_real_factor_ic(request, market_data)

    assert response.market == QuantMarket.UNITED_STATES
    assert response.symbols == ("AAPL", "MSFT", "NVDA")
    assert response.successful_symbols == ("AAPL", "MSFT", "NVDA")
    assert response.failed_stocks == ()
    assert sorted(market_data.calls) == [
        ("AAPL", 120),
        ("MSFT", 120),
        ("NVDA", 120),
    ]
    assert tuple(
        result.factor_id
        for result in response.factor_results
    ) == ("trend", "momentum", "volume")
    assert all(result.periods for result in response.factor_results)


def test_rejects_symbols_from_another_market() -> None:
    market_data = StubMarketDataProvider({})
    request = FactorIcAnalysisRequest(
        market=QuantMarket.UNITED_STATES,
        symbols=("AAPL", "MSFT", "0700.HK"),
    )

    with pytest.raises(ApplicationError) as error:
        analyze_real_factor_ic(request, market_data)

    assert error.value.status_code == 422
    assert "0700.HK" in error.value.message
    assert market_data.calls == []


def test_skips_symbol_without_market_data_and_reports_insufficient_sample() -> None:
    market_data = StubMarketDataProvider(
        {
            "AAPL": _make_bars(100.0, 1.0),
            "MSFT": (),
            "NVDA": _make_bars(150.0, 0.5),
        }
    )
    request = FactorIcAnalysisRequest(
        market=QuantMarket.UNITED_STATES,
        symbols=("AAPL", "MSFT", "NVDA"),
    )

    response = analyze_real_factor_ic(request, market_data)

    assert response.successful_symbols == ("AAPL", "NVDA")
    assert response.factor_results == ()
    assert len(response.failed_stocks) == 1
    assert response.failed_stocks[0].symbol == "MSFT"
    assert response.failed_stocks[0].reason == "market_data_not_found"


def test_continues_analysis_when_one_stock_request_fails() -> None:
    class PartiallyFailingMarketDataProvider(StubMarketDataProvider):
        def get_daily_bars(
            self,
            symbol: str,
            limit: int,
        ) -> tuple[DailyBar, ...]:
            if symbol == "TSLA":
                raise ApplicationError("Provider rate limited.", status_code=502)
            return super().get_daily_bars(symbol, limit)

    market_data = PartiallyFailingMarketDataProvider(
        {
            "AAPL": _make_bars(100.0, 1.0),
            "MSFT": _make_bars(200.0, 0.5),
            "NVDA": _make_bars(150.0, -0.25),
        }
    )
    request = FactorIcAnalysisRequest(
        market=QuantMarket.UNITED_STATES,
        symbols=("AAPL", "MSFT", "NVDA", "TSLA"),
    )

    response = analyze_real_factor_ic(request, market_data)

    assert response.successful_symbols == ("AAPL", "MSFT", "NVDA")
    assert len(response.factor_results) == 3
    assert response.failed_stocks[0].symbol == "TSLA"
    assert response.failed_stocks[0].reason == "market_data_unavailable"


def test_analyzes_twelve_stock_batch_when_some_market_requests_fail() -> None:
    symbols = tuple(f"STOCK{index}" for index in range(12))

    class LargePoolMarketDataProvider(StubMarketDataProvider):
        def get_daily_bars(
            self,
            symbol: str,
            limit: int,
        ) -> tuple[DailyBar, ...]:
            if symbol in {"STOCK2", "STOCK9"}:
                raise ApplicationError("Provider request failed.", status_code=502)
            return super().get_daily_bars(symbol, limit)

    market_data = LargePoolMarketDataProvider(
        {
            symbol: _make_bars(100.0 + index, 0.1 * (index + 1))
            for index, symbol in enumerate(symbols)
            if symbol not in {"STOCK2", "STOCK9"}
        }
    )
    request = FactorIcAnalysisRequest(
        market=QuantMarket.UNITED_STATES,
        symbols=symbols,
    )

    response = analyze_real_factor_ic(request, market_data)

    assert len(response.successful_symbols) == 10
    assert tuple(failure.symbol for failure in response.failed_stocks) == (
        "STOCK2",
        "STOCK9",
    )
    assert len(response.factor_results) == 3


def test_loads_market_data_concurrently() -> None:
    barrier = threading.Barrier(3)

    class ConcurrentMarketDataProvider(StubMarketDataProvider):
        def get_daily_bars(
            self,
            symbol: str,
            limit: int,
        ) -> tuple[DailyBar, ...]:
            barrier.wait(timeout=5)
            return super().get_daily_bars(symbol, limit)

    market_data = ConcurrentMarketDataProvider(
        {
            "AAPL": _make_bars(100.0, 1.0),
            "MSFT": _make_bars(200.0, 0.5),
            "NVDA": _make_bars(150.0, -0.25),
        }
    )
    request = FactorIcAnalysisRequest(
        market=QuantMarket.UNITED_STATES,
        symbols=("AAPL", "MSFT", "NVDA"),
    )

    response = analyze_real_factor_ic(request, market_data)

    assert response.symbols == ("AAPL", "MSFT", "NVDA")
    assert len(market_data.calls) == 3
