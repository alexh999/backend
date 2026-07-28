from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class MarketStockStatData(BaseModel):
    label: str
    value: str


class MarketChartPoint(BaseModel):
    date: date
    close: float


class MarketChartCandleData(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float


class MarketChartRangeData(BaseModel):
    range: str
    line_points: list[MarketChartPoint]
    candle_points: list[MarketChartCandleData]


class MarketCompanyProfileData(BaseModel):
    symbol: str
    company_name: str
    local_name: str | None = None
    exchange_label: str | None = None
    listed_date: date | None = None
    website: str | None = None
    business_sector: str | None = None
    economic_sector: str | None = None
    industry_group: str | None = None
    office_country: str | None = None
    status: int | None = None


class MarketStockDetailResponse(BaseModel):
    id: str
    ticker: str
    company_name: str
    exchange_label: str | None = None
    price_text: str
    latest_close: float
    latest_trading_date: date
    change_value: float
    change_percent: float
    change_label: str
    default_chart_range: str
    available_chart_ranges: list[str]
    chart_ranges: list[MarketChartRangeData]
    stats: list[MarketStockStatData]
    profile: MarketCompanyProfileData
    news_articles: list[dict[str, object]] = Field(default_factory=list)
