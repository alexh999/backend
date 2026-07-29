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