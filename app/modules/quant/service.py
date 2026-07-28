from collections.abc import Sequence

from app.modules.quant.schemas import (
    DailyBar,
    MacdResult,
    PriceDirection,
    VolumeAnalysisResult,
)

def calculate_moving_average(
    bars: Sequence[DailyBar],
    period: int,
) -> float | None:
    if period <= 0:
        raise ValueError("period must be greater than zero")

    if len(bars) < period:
        return None

    recent_bars = bars[-period:]
    total_close = sum(bar.close for bar in recent_bars)

    return total_close / period


def calculate_rsi(
    bars: Sequence[DailyBar],
    period: int = 14,
) -> float | None:
    if period <= 0:
        raise ValueError("period must be greater than zero")

    if len(bars) < period + 1:
        return None

    total_gain = 0.0
    total_loss = 0.0
    start_index = len(bars) - period

    for index in range(start_index, len(bars)):
        change = bars[index].close - bars[index - 1].close

        if change > 0:
            total_gain += change
        elif change < 0:
            total_loss += -change

    if total_gain == 0 and total_loss == 0:
        return 50.0

    if total_loss == 0:
        return 100.0

    if total_gain == 0:
        return 0.0

    average_gain = total_gain / period
    average_loss = total_loss / period
    relative_strength = average_gain / average_loss

    return 100 - (100 / (1 + relative_strength))
def calculate_macd(
    bars: Sequence[DailyBar],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> MacdResult | None:
    if fast_period <= 0 or slow_period <= 0 or signal_period <= 0:
        raise ValueError("MACD periods must be greater than zero")

    if fast_period >= slow_period:
        raise ValueError("fast period must be less than slow period")

    minimum_bar_count = slow_period + signal_period - 1

    if len(bars) < minimum_bar_count:
        return None

    fast_alpha = 2 / (fast_period + 1)
    slow_alpha = 2 / (slow_period + 1)
    signal_alpha = 2 / (signal_period + 1)

    fast_ema = bars[0].close
    slow_ema = bars[0].close
    dif = fast_ema - slow_ema
    dea = dif

    for bar in bars[1:]:
        close = bar.close

        fast_ema = close * fast_alpha + fast_ema * (1 - fast_alpha)
        slow_ema = close * slow_alpha + slow_ema * (1 - slow_alpha)

        dif = fast_ema - slow_ema
        dea = dif * signal_alpha + dea * (1 - signal_alpha)

    return MacdResult(
        dif=dif,
        dea=dea,
        histogram=2 * (dif - dea),
    )
def analyze_volume(
    bars: Sequence[DailyBar],
    baseline_period: int = 5,
) -> VolumeAnalysisResult | None:
    if baseline_period <= 0:
        raise ValueError("baseline period must be greater than zero")

    if len(bars) < baseline_period + 1:
        return None

    latest_bar = bars[-1]
    previous_bar = bars[-2]
    baseline_bars = bars[-baseline_period - 1 : -1]

    average_volume = (
        sum(bar.volume for bar in baseline_bars) / baseline_period
    )

    if average_volume <= 0:
        return None

    if latest_bar.close > previous_bar.close:
        price_direction = PriceDirection.UP
    elif latest_bar.close < previous_bar.close:
        price_direction = PriceDirection.DOWN
    else:
        price_direction = PriceDirection.FLAT

    return VolumeAnalysisResult(
        latest_volume=latest_bar.volume,
        average_volume=average_volume,
        volume_ratio=latest_bar.volume / average_volume,
        price_direction=price_direction,
    )