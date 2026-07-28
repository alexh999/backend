from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict


class PandaAIBaseRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    def first_non_null(self, *names: str) -> Any:
        for name in names:
            value = getattr(self, name, None)
            if value is not None:
                return value
            extra = self.model_extra or {}
            if extra.get(name) is not None:
                return extra[name]
        return None


class PandaAIUsDetailRecord(PandaAIBaseRecord):
    symbol: str
    name: str | None = None
    local_name: str | None = None
    exchange_name: str | None = None
    listed_date: str | None = None
    website: str | None = None
    business_sector: str | None = None
    economic_sector: str | None = None
    industry_group: str | None = None
    office_country: str | None = None
    status: int | None = None


class PandaAIUsDailyRecord(PandaAIBaseRecord):
    symbol: str
    date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    amount: float | None = None
    name: str | None = None


class PandaAIMktFinMetricRecord(PandaAIBaseRecord):
    symbol: str
    date: str | None = None
    market_cap: float | None = None
    curr_market_cap: float | None = None
    market_value: float | None = None
    curr_market_value: float | None = None
    total_market_value: float | None = None
    curr_total_market_value: float | None = None
    pe_ttm: float | None = None
    curr_pe_ttm: float | None = None
    price_to_eps_ttm: float | None = None
    curr_price_to_eps_ttm: float | None = None
    dividend_yield: float | None = None
    curr_dividend_yield: float | None = None
    dividend_yield_ttm: float | None = None
    curr_dividend_yield_ttm: float | None = None
    dps_issue_ttm: float | None = None
    curr_dps_issue_ttm: float | None = None
    curr_price_to_dps_issue_ttm: float | None = None


class PandaAICompanyProfile(BaseModel):
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


class PandaAIDailyBar(BaseModel):
    symbol: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    amount: float | None = None


class PandaAIValuationSnapshot(BaseModel):
    symbol: str
    as_of_date: date | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None
    dividend_yield: float | None = None
