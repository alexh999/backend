from datetime import date

import pytest

from app.modules.quant.schemas import DailyBar
from app.modules.quant.service import calculate_moving_average


def make_bar(close: float) -> DailyBar:
    return DailyBar(
        trade_date=date(2026, 7, 1),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
    )


def test_moving_average_uses_latest_five_closing_prices() -> None:
    bars = [
        make_bar(1),
        make_bar(10),
        make_bar(11),
        make_bar(12),
        make_bar(13),
        make_bar(14),
    ]

    result = calculate_moving_average(bars, period=5)

    assert result == pytest.approx(12.0)


def test_moving_average_returns_none_when_data_is_insufficient() -> None:
    bars = [make_bar(10), make_bar(11)]

    result = calculate_moving_average(bars, period=5)

    assert result is None


def test_moving_average_rejects_zero_period() -> None:
    with pytest.raises(
        ValueError,
        match="period must be greater than zero",
    ):
        calculate_moving_average([], period=0)


def test_moving_average_does_not_modify_original_bars() -> None:
    bars = [make_bar(10), make_bar(11), make_bar(12)]
    original_bars = list(bars)

    calculate_moving_average(bars, period=2)

    assert bars == original_bars