from collections.abc import Sequence
from math import isfinite

from app.modules.quant.service import (
    analyze_volume,
    calculate_macd,
    calculate_moving_average,
    calculate_rsi,
)
from app.modules.quant.schemas import DailyBar, PriceDirection


def calculate_trend_factor_score(
    bars: Sequence[DailyBar],
) -> float | None:
    if not bars:
        return None

    close = bars[-1].close
    ma5 = calculate_moving_average(bars, period=5)
    ma10 = calculate_moving_average(bars, period=10)
    ma20 = calculate_moving_average(bars, period=20)

    if not all(
        value is not None and isfinite(value) and value > 0
        for value in (close, ma5, ma10, ma20)
    ):
        return None

    valid_ma5 = float(ma5)
    valid_ma10 = float(ma10)
    valid_ma20 = float(ma20)

    price_deviation = _clamp(
        (close - valid_ma20) / valid_ma20,
        -0.10,
        0.10,
    )
    short_term_spread = _clamp(
        (valid_ma5 - valid_ma10) / valid_ma10,
        -0.05,
        0.05,
    )
    medium_term_spread = _clamp(
        (valid_ma10 - valid_ma20) / valid_ma20,
        -0.05,
        0.05,
    )

    score = (
        50
        + price_deviation / 0.10 * 25
        + short_term_spread / 0.05 * 12.5
        + medium_term_spread / 0.05 * 12.5
    )

    return _clamp(score, 0, 100)


def calculate_momentum_factor_score(
    bars: Sequence[DailyBar],
) -> float | None:
    if not bars:
        return None

    rsi = calculate_rsi(bars, period=14)
    macd = calculate_macd(
        bars,
        fast_period=12,
        slow_period=26,
        signal_period=9,
    )
    close = bars[-1].close

    if (
        rsi is None
        or not isfinite(rsi)
        or rsi < 0
        or rsi > 100
        or macd is None
        or not isfinite(macd.dif)
        or not isfinite(macd.dea)
        or not isfinite(macd.histogram)
        or not isfinite(close)
        or close <= 0
    ):
        return None

    if rsi <= 30:
        rsi_score = 10 + rsi / 30 * 20
    elif rsi <= 50:
        rsi_score = 30 + (rsi - 30)
    elif rsi <= 65:
        rsi_score = 50 + (rsi - 50) / 15 * 35
    elif rsi <= 70:
        rsi_score = 85 - (rsi - 65) / 5 * 10
    else:
        rsi_score = 75 - (rsi - 70) / 30 * 45

    normalized_gap = _clamp(
        (macd.dif - macd.dea) / close,
        -0.02,
        0.02,
    )
    normalized_histogram = _clamp(
        macd.histogram / close,
        -0.02,
        0.02,
    )

    macd_score = 50 + normalized_gap / 0.02 * 25 + normalized_histogram / 0.02 * 25

    return _clamp(
        rsi_score * 0.45 + macd_score * 0.55,
        0,
        100,
    )


def calculate_volume_factor_score(
    bars: Sequence[DailyBar],
) -> float | None:
    volume = analyze_volume(bars, baseline_period=5)

    if volume is None or not isfinite(volume.volume_ratio) or volume.volume_ratio < 0:
        return None

    normalized_ratio = _clamp(volume.volume_ratio, 0, 2)

    if volume.price_direction == PriceDirection.UP:
        score = 50 + normalized_ratio / 2 * 50
    elif volume.price_direction == PriceDirection.FLAT:
        score = _clamp(
            45 + abs(normalized_ratio - 1) * 5,
            40,
            55,
        )
    else:
        score = 50 - normalized_ratio / 2 * 50

    return _clamp(score, 0, 100)


SUPPORTED_FACTOR_IDS = ("trend", "momentum", "volume")


def calculate_factor_score(
    factor_id: str,
    bars: Sequence[DailyBar],
) -> float | None:
    normalized_factor_id = factor_id.strip().lower()

    if normalized_factor_id == "trend":
        return calculate_trend_factor_score(bars)

    if normalized_factor_id == "momentum":
        return calculate_momentum_factor_score(bars)

    if normalized_factor_id == "volume":
        return calculate_volume_factor_score(bars)

    raise ValueError(f"unsupported factor id: {factor_id}")


def _clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(minimum, min(maximum, value))
