from datetime import date

from pydantic import BaseModel


class YahooFinanceDailyBar(BaseModel):
    symbol: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    amount: float | None = None