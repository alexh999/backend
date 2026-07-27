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