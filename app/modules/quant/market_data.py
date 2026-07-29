from collections.abc import Sequence
from typing import Protocol

from app.modules.quant.schemas import DailyBar


class MarketDataProvider(Protocol):
    def get_daily_bars(
        self,
        symbol: str,
        limit: int,
    ) -> Sequence[DailyBar]:
        ...


def normalize_daily_bars(
    bars: Sequence[DailyBar],
) -> tuple[DailyBar, ...]:
    sorted_bars = tuple(
        sorted(
            bars,
            key=lambda bar: bar.trade_date,
        )
    )

    trade_dates = [bar.trade_date for bar in sorted_bars]

    if len(trade_dates) != len(set(trade_dates)):
        raise ValueError("daily bars must not contain duplicate trade dates")

    return sorted_bars
