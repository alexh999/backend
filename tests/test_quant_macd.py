from datetime import date, timedelta

import pytest

from app.modules.quant.schemas import DailyBar
from app.modules.quant.service import calculate_macd


def bars_from_closes(closes: list[float]) -> list[DailyBar]:
    start_date = date(2026, 1, 1)

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


def test_macd_returns_none_when_data_is_insufficient() -> None:
    bars = bars_from_closes([10.0] * 33)

    result = calculate_macd(bars)

    assert result is None


def test_macd_returns_zero_for_unchanged_prices() -> None:
    bars = bars_from_closes([10.0] * 34)

    result = calculate_macd(bars)

    assert result is not None
    assert result.dif == pytest.approx(0.0)
    assert result.dea == pytest.approx(0.0)
    assert result.histogram == pytest.approx(0.0)


def test_macd_is_positive_for_continuously_rising_prices() -> None:
    bars = bars_from_closes([10.0 + index for index in range(40)])

    result = calculate_macd(bars)

    assert result is not None
    assert result.dif > 0
    assert result.dea > 0


def test_macd_histogram_uses_project_formula() -> None:
    closes = [
        10 + index * 0.5 + (0.2 if index % 2 == 0 else -0.1)
        for index in range(40)
    ]
    bars = bars_from_closes(closes)

    result = calculate_macd(bars)

    assert result is not None
    assert result.histogram == pytest.approx(
        2 * (result.dif - result.dea),
    )


def test_macd_rejects_non_positive_period() -> None:
    with pytest.raises(
        ValueError,
        match="MACD periods must be greater than zero",
    ):
        calculate_macd([], fast_period=0)


def test_macd_rejects_fast_period_not_less_than_slow_period() -> None:
    with pytest.raises(
        ValueError,
        match="fast period must be less than slow period",
    ):
        calculate_macd([], fast_period=26, slow_period=26)