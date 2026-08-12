from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class DailyMetric(BaseModel):
    date: date
    count: int = Field(ge=0)


class UserActivitySummaryResponse(BaseModel):
    as_of_date: date
    start_date: date
    end_date: date
    dau: int = Field(ge=0)
    mau: int = Field(ge=0)
    daily_dau: list[DailyMetric]
    daily_new_users: list[DailyMetric]
