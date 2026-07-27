from datetime import date

import pytest
from pydantic import ValidationError

from app.modules.quant.schemas import DailyBar, PriceAdjustment


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