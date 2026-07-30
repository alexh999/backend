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


class TrendState(StrEnum):
    UPWARD = "upward"
    DOWNWARD = "downward"
    MIXED = "mixed"
    INSUFFICIENT_DATA = "insufficient_data"


class StrengthState(StrEnum):
    HIGH = "high"
    RELATIVELY_STRONG = "relatively_strong"
    BALANCED = "balanced"
    RELATIVELY_WEAK = "relatively_weak"
    LOW = "low"
    INSUFFICIENT_DATA = "insufficient_data"


class MomentumState(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    INSUFFICIENT_DATA = "insufficient_data"


class ParticipationState(StrEnum):
    LOW = "low"
    INCONCLUSIVE = "inconclusive"
    CONFIRMING = "confirming"
    CONTRADICTING = "contradicting"
    INSUFFICIENT_DATA = "insufficient_data"


class EvidenceConsistency(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    DIVERGENT = "divergent"
    UNAVAILABLE = "unavailable"


class RiskFlag(StrEnum):
    RSI_HIGH = "rsi_high"
    RSI_LOW = "rsi_low"
    PRICE_EXTENDED = "price_extended"
    DATA_INSUFFICIENT = "data_insufficient"


class TechnicalSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    trend: TrendState
    momentum: MomentumState
    strength: StrengthState
    participation: ParticipationState
    consistency: EvidenceConsistency
    risk_flags: tuple[RiskFlag, ...] = ()


class QuantStockAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    bars: tuple[DailyBar, ...]
    latest_bar: DailyBar
    ma5: float | None = None
    ma10: float | None = None
    ma20: float | None = None
    macd: MacdResult | None = None
    rsi14: float | None = None
    volume: VolumeAnalysisResult | None = None
    technical_summary: TechnicalSummary
