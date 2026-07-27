from collections.abc import Sequence

from app.modules.quant.schemas import DailyBar


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