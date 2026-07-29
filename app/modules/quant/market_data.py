from collections.abc import Sequence
from typing import Protocol

from app.modules.market.service import MarketStockService
from app.modules.quant.schemas import DailyBar


class MarketDataProvider(Protocol):
    def get_daily_bars(
        self,
        symbol: str,
        limit: int,
    ) -> Sequence[DailyBar]:
        ...


class MarketServiceDataProvider:
    def __init__(self, market_service: MarketStockService) -> None:
        self._market_service = market_service

    def get_daily_bars(
        self,
        symbol: str,
        limit: int,
    ) -> Sequence[DailyBar]:
        market_bars = self._market_service.get_daily_bars(
            symbol=symbol,
            limit=limit,
        )

        return tuple(
            DailyBar(
                trade_date=bar.trade_date,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                previous_close=bar.previous_close,
                volume=int(bar.volume or 0),
            )
            for bar in market_bars
        )


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