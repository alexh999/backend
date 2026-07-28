from datetime import date, timedelta

import pytest

from app.modules.quant.schemas import DailyBar, PriceDirection
from app.modules.quant.service import analyze_volume


def build_bars(
    closes: list[float],
    volumes: list[int],
) -> list[DailyBar]:
    start_date = date(2026, 7, 1)

    return [
        DailyBar(
            trade_date=start_date + timedelta(days=index),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=volumes[index],
        )
        for index, close in enumerate(closes)
    ]


def test_volume_returns_none_when_data_is_insufficient() -> None:
    bars = build_bars(
        closes=[10, 10, 10, 10, 10],
        volumes=[100, 100, 100, 100, 100],
    )

    assert analyze_volume(bars) is None


def test_volume_calculates_baseline_average_and_ratio() -> None:
    bars = build_bars(
        closes=[10, 10, 10, 10, 10, 11],
        volumes=[100, 200, 300, 400, 500, 600],
    )

    result = analyze_volume(bars)

    assert result is not None
    assert result.latest_volume == 600
    assert result.average_volume == pytest.approx(300)
    assert result.volume_ratio == pytest.approx(2)


@pytest.mark.parametrize(
    ("closes", "expected_direction"),
    [
        ([10, 10, 10, 10, 10, 11], PriceDirection.UP),
        ([10, 10, 10, 10, 11, 10], PriceDirection.DOWN),
        ([10, 10, 10, 10, 10, 10], PriceDirection.FLAT),
    ],
)
def test_volume_classifies_latest_price_direction(
    closes: list[float],
    expected_direction: PriceDirection,
) -> None:
    bars = build_bars(
        closes=closes,
        volumes=[100, 100, 100, 100, 100, 100],
    )

    result = analyze_volume(bars)

    assert result is not None
    assert result.price_direction is expected_direction


def test_latest_volume_is_not_included_in_baseline_average() -> None:
    bars = build_bars(
        closes=[10, 10, 10, 10, 10, 11],
        volumes=[100, 100, 100, 100, 100, 1000],
    )

    result = analyze_volume(bars)

    assert result is not None
    assert result.average_volume == pytest.approx(100)
    assert result.volume_ratio == pytest.approx(10)


def test_volume_rejects_non_positive_baseline_period() -> None:
    with pytest.raises(
        ValueError,
        match="baseline period must be greater than zero",
    ):
        analyze_volume([], baseline_period=0)


def test_volume_returns_none_when_baseline_average_is_zero() -> None:
    bars = build_bars(
        closes=[10, 10, 10, 10, 10, 11],
        volumes=[0, 0, 0, 0, 0, 200],
    )

    assert analyze_volume(bars) is None