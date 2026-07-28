from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PriceAdjustment(StrEnum):
    NONE = "none"
    FORWARD = "forward"
    BACKWARD = "backward"


class DailyBar(BaseModel):
    model_config = ConfigDict(frozen=True)

    trade_date: date
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    previous_close: float | None = Field(default=None, gt=0)
    volume: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_price_range(self) -> "DailyBar":
        if self.low > self.high:
            raise ValueError("low must not be greater than high")

        if not self.low <= self.open <= self.high:
            raise ValueError("open must be between low and high")

        if not self.low <= self.close <= self.high:
            raise ValueError("close must be between low and high")

        return self


class MacdResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    dif: float
    dea: float
    histogram: float


class PriceDirection(StrEnum):
    UP = "up"
    FLAT = "flat"
    DOWN = "down"


class VolumeAnalysisResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    latest_volume: int = Field(ge=0)
    average_volume: float = Field(gt=0)
    volume_ratio: float = Field(ge=0)
    price_direction: PriceDirection