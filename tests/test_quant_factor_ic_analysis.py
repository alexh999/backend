from datetime import date, timedelta

import pytest

from app.modules.quant.factor_ic_analysis import (
    build_factor_ic_cross_sections,
    calculate_factor_ic_analysis,
)
from app.modules.quant.schemas import DailyBar


def _make_bars(
    start_price: float,
    daily_change: float,
    count: int = 40,
) -> list[DailyBar]:
    bars: list[DailyBar] = []

    for index in range(count):
        close = start_price + daily_change * index

        bars.append(
            DailyBar(
                trade_date=date(2026, 1, 1) + timedelta(days=index),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1000 + index,
            )
        )

    return bars


def test_builds_cross_section_from_multiple_stocks() -> None:
    bars_by_stock = {
        "AAA": _make_bars(100.0, 1.0),
        "BBB": _make_bars(80.0, 0.5),
        "CCC": _make_bars(120.0, -0.5),
    }

    sections = build_factor_ic_cross_sections(
        factor_id="trend",
        bars_by_stock=bars_by_stock,
    )

    assert len(sections) == 1

    section = sections[0]

    assert section.date == date(2026, 2, 4)
    assert set(section.factor_values_by_stock) == {
        "AAA",
        "BBB",
        "CCC",
    }
    assert set(section.forward_returns_by_stock) == {
        "AAA",
        "BBB",
        "CCC",
    }
    assert section.forward_returns_by_stock["AAA"] == pytest.approx(139.0 / 135.0 - 1)


def test_factor_score_does_not_use_future_bars() -> None:
    original_bars = _make_bars(100.0, 0.5)
    changed_future_bars = list(original_bars)

    for index in range(35, 40):
        future_price = 200.0 + index * 5

        changed_future_bars[index] = changed_future_bars[index].model_copy(
            update={
                "open": future_price,
                "high": future_price,
                "low": future_price,
                "close": future_price,
            }
        )

    original_section = build_factor_ic_cross_sections(
        factor_id="trend",
        bars_by_stock={"AAA": original_bars},
    )[0]
    changed_section = build_factor_ic_cross_sections(
        factor_id="trend",
        bars_by_stock={"AAA": changed_future_bars},
    )[0]

    assert original_section.date == changed_section.date
    assert original_section.factor_values_by_stock["AAA"] == pytest.approx(
        changed_section.factor_values_by_stock["AAA"]
    )
    assert original_section.forward_returns_by_stock["AAA"] != pytest.approx(
        changed_section.forward_returns_by_stock["AAA"]
    )


def test_uses_next_open_and_holding_period_close_for_forward_return() -> None:
    bars = _make_bars(100.0, 0.0)

    bars[35] = bars[35].model_copy(
        update={
            "open": 110.0,
            "high": 110.0,
            "low": 110.0,
            "close": 110.0,
        }
    )
    bars[39] = bars[39].model_copy(
        update={
            "open": 121.0,
            "high": 121.0,
            "low": 121.0,
            "close": 121.0,
        }
    )

    section = build_factor_ic_cross_sections(
        factor_id="volume",
        bars_by_stock={"AAA": bars},
        holding_period=5,
    )[0]

    assert section.forward_returns_by_stock["AAA"] == pytest.approx(0.1)


def test_rejects_invalid_analysis_parameters() -> None:
    with pytest.raises(ValueError, match="unsupported factor id"):
        build_factor_ic_cross_sections(
            factor_id="quality",
            bars_by_stock={},
        )

    with pytest.raises(ValueError, match="holding period"):
        build_factor_ic_cross_sections(
            factor_id="trend",
            bars_by_stock={},
            holding_period=0,
        )

    with pytest.raises(ValueError, match="minimum lookback"):
        build_factor_ic_cross_sections(
            factor_id="trend",
            bars_by_stock={},
            minimum_lookback=34,
        )


def test_calculates_complete_factor_ic_analysis() -> None:
    result = calculate_factor_ic_analysis(
        factor_id="trend",
        bars_by_stock={
            "AAA": _make_bars(100.0, 1.0),
            "BBB": _make_bars(80.0, 0.5),
            "CCC": _make_bars(120.0, -0.5),
        },
    )

    assert result.factor_id == "trend"
    assert len(result.periods) == 1
    assert len(result.available_periods) == 1
    assert result.periods[0].sample_size == 3
    assert result.average_information_coefficient is not None
    assert result.average_rank_information_coefficient is not None
