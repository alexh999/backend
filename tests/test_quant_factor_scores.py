from datetime import date, timedelta
import pytest

from app.modules.quant.factor_scores import (
    calculate_momentum_factor_score,
    calculate_trend_factor_score,
    calculate_volume_factor_score,
    calculate_factor_score,
)
from app.modules.quant.schemas import DailyBar


def _make_bars(
    closes: list[float],
) -> list[DailyBar]:
    return [
        DailyBar(
            trade_date=date(2026, 1, 1) + timedelta(days=index),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1000,
        )
        for index, close in enumerate(closes)
    ]


def test_trend_factor_scores_upward_prices_above_neutral() -> None:
    bars = _make_bars(
        [100.0 + index for index in range(35)],
    )

    result = calculate_trend_factor_score(bars)

    assert result is not None
    assert result > 50
    assert result <= 100


def test_trend_factor_scores_downward_prices_below_neutral() -> None:
    bars = _make_bars(
        [140.0 - index for index in range(35)],
    )

    result = calculate_trend_factor_score(bars)

    assert result is not None
    assert result < 50
    assert result >= 0


def test_trend_factor_returns_neutral_for_flat_prices() -> None:
    result = calculate_trend_factor_score(
        _make_bars([100.0] * 35),
    )

    assert result == 50


def test_trend_factor_returns_none_for_insufficient_history() -> None:
    result = calculate_trend_factor_score(
        _make_bars([100.0] * 19),
    )

    assert result is None


def test_momentum_factor_scores_upward_prices_above_neutral() -> None:
    result = calculate_momentum_factor_score(
        _make_bars(
            [
                100.0 + index * 0.3 - (1.0 if index % 3 == 0 else 0.0)
                for index in range(40)
            ]
        ),
    )

    assert result is not None
    assert result > 50
    assert result <= 100


def test_momentum_factor_scores_downward_prices_below_neutral() -> None:
    result = calculate_momentum_factor_score(
        _make_bars([150.0 - index for index in range(40)]),
    )

    assert result is not None
    assert result < 50
    assert result >= 0


def test_momentum_factor_returns_none_for_insufficient_history() -> None:
    result = calculate_momentum_factor_score(
        _make_bars([100.0 + index for index in range(33)]),
    )

    assert result is None


def test_volume_factor_rewards_high_volume_price_increase() -> None:
    bars = _make_bars([100.0] * 5 + [102.0])
    bars[-1] = bars[-1].model_copy(update={"volume": 2000})

    result = calculate_volume_factor_score(bars)

    assert result == 100


def test_volume_factor_penalizes_high_volume_price_decrease() -> None:
    bars = _make_bars([100.0] * 5 + [98.0])
    bars[-1] = bars[-1].model_copy(update={"volume": 2000})

    result = calculate_volume_factor_score(bars)

    assert result == 0


def test_volume_factor_keeps_flat_price_neutral() -> None:
    result = calculate_volume_factor_score(
        _make_bars([100.0] * 6),
    )

    assert result == 45


def test_volume_factor_returns_none_for_insufficient_history() -> None:
    result = calculate_volume_factor_score(
        _make_bars([100.0] * 5),
    )

    assert result is None


def test_factor_score_dispatches_supported_factor_ids() -> None:
    bars = _make_bars(
        [100.0 + index * 0.3 - (1.0 if index % 3 == 0 else 0.0) for index in range(40)]
    )

    assert calculate_factor_score(" trend ", bars) == (
        calculate_trend_factor_score(bars)
    )
    assert calculate_factor_score("MOMENTUM", bars) == (
        calculate_momentum_factor_score(bars)
    )
    assert calculate_factor_score("volume", bars) == (
        calculate_volume_factor_score(bars)
    )


def test_factor_score_rejects_unsupported_factor_id() -> None:
    with pytest.raises(ValueError, match="unsupported factor id"):
        calculate_factor_score(
            "quality",
            _make_bars([100.0] * 40),
        )
