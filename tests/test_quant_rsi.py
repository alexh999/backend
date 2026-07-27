from datetime import date, timedelta

import pytest

from app.modules.quant.schemas import DailyBar
from app.modules.quant.service import calculate_rsi


def bars_from_closes(closes: list[float]) -> list[DailyBar]:
    start_date = date(2026, 7, 1)

    return [
        DailyBar(
            trade_date=start_date + timedelta(days=index),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1000,
        )
        for index, close in enumerate(closes)
    ]


def test_rsi_returns_none_when_data_is_insufficient() -> None:
    bars = bars_from_closes([10, 11, 12])

    result = calculate_rsi(bars, period=3)

    assert result is None


def test_rsi_returns_100_when_all_prices_rise() -> None:
    bars = bars_from_closes([10, 11, 12, 13])

    result = calculate_rsi(bars, period=3)

    assert result == 100.0


def test_rsi_returns_zero_when_all_prices_fall() -> None:
    bars = bars_from_closes([13, 12, 11, 10])

    result = calculate_rsi(bars, period=3)

    assert result == 0.0


def test_rsi_returns_50_when_prices_do_not_change() -> None:
    bars = bars_from_closes([10, 10, 10, 10])

    result = calculate_rsi(bars, period=3)

    assert result == 50.0


def test_rsi_calculates_mixed_price_changes() -> None:
    bars = bars_from_closes([10, 12, 11, 13])

    result = calculate_rsi(bars, period=3)

    assert result == pytest.approx(80.0)


def test_rsi_rejects_zero_period() -> None:
    with pytest.raises(
        ValueError,
        match="period must be greater than zero",
    ):
        calculate_rsi([], period=0)