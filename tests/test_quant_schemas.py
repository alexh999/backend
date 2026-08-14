from datetime import date

import pytest
from pydantic import ValidationError

from app.modules.quant.schemas import (
    DailyBar,
    FactorIcAnalysisRequest,
    PriceAdjustment,
    QuantMarket,
)


def test_daily_bar_accepts_valid_market_data() -> None:
    bar = DailyBar(
        trade_date="2026-07-22",
        open=1488.00,
        high=1512.50,
        low=1476.20,
        close=1505.00,
        previous_close=1482.00,
        volume=3_258_400,
    )

    assert bar.trade_date == date(2026, 7, 22)
    assert bar.close == 1505.00
    assert bar.volume == 3_258_400


def test_daily_bar_rejects_negative_volume() -> None:
    with pytest.raises(ValidationError):
        DailyBar(
            trade_date="2026-07-22",
            open=10.00,
            high=11.00,
            low=9.00,
            close=10.50,
            volume=-1,
        )


def test_daily_bar_rejects_low_above_high() -> None:
    with pytest.raises(ValidationError):
        DailyBar(
            trade_date="2026-07-22",
            open=10.00,
            high=9.00,
            low=11.00,
            close=10.50,
            volume=1000,
        )


def test_daily_bar_rejects_close_outside_price_range() -> None:
    with pytest.raises(ValidationError):
        DailyBar(
            trade_date="2026-07-22",
            open=10.00,
            high=11.00,
            low=9.00,
            close=12.00,
            volume=1000,
        )


def test_price_adjustment_values_are_stable() -> None:
    assert PriceAdjustment.NONE.value == "none"
    assert PriceAdjustment.FORWARD.value == "forward"
    assert PriceAdjustment.BACKWARD.value == "backward"


def test_factor_ic_analysis_request_normalizes_symbols() -> None:
    request = FactorIcAnalysisRequest(
        market=QuantMarket.UNITED_STATES,
        symbols=(" aapl ", "MSFT", "nvda"),
    )

    assert request.symbols == ("AAPL", "MSFT", "NVDA")
    assert request.history_limit == 120
    assert request.holding_period == 5
    assert request.minimum_lookback == 35
    assert request.minimum_sample_size == 3


def test_factor_ic_analysis_request_rejects_duplicate_symbols() -> None:
    with pytest.raises(ValidationError, match="must not be duplicated"):
        FactorIcAnalysisRequest(
            market=QuantMarket.UNITED_STATES,
            symbols=("AAPL", " aapl ", "MSFT"),
        )


def test_factor_ic_analysis_request_rejects_too_few_symbols() -> None:
    with pytest.raises(ValidationError):
        FactorIcAnalysisRequest(
            market=QuantMarket.UNITED_STATES,
            symbols=("AAPL", "MSFT"),
        )


def test_factor_ic_analysis_request_rejects_sample_size_above_stock_count() -> None:
    with pytest.raises(ValidationError, match="cannot exceed"):
        FactorIcAnalysisRequest(
            market=QuantMarket.UNITED_STATES,
            symbols=("AAPL", "MSFT", "NVDA"),
            minimum_sample_size=4,
        )


def test_factor_ic_analysis_request_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        FactorIcAnalysisRequest.model_validate(
            {
                "market": "united_states",
                "symbols": ["AAPL", "MSFT", "NVDA"],
                "unknown": True,
            }
        )
