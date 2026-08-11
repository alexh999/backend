from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


PaperOrderSide = Literal["buy", "sell"]
PaperOrderStatus = Literal["filled", "rejected"]


class _DecimalJsonMixin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("*", when_used="json")
    def serialize_decimal(self, value: object) -> object:
        if isinstance(value, Decimal):
            return float(value)
        return value


class PaperAccountResponse(_DecimalJsonMixin):
    id: int
    account_key: str
    currency: str
    initial_cash: Decimal
    available_cash: Decimal


class PaperPortfolioSummaryResponse(_DecimalJsonMixin):
    initial_cash: Decimal
    available_cash: Decimal
    market_value: Decimal
    total_assets: Decimal
    total_profit_loss: Decimal
    total_profit_loss_percent: Decimal
    position_ratio: Decimal


class PaperPositionResponse(_DecimalJsonMixin):
    symbol: str
    name: str | None = None
    currency: str
    quantity: int
    average_cost: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_profit_loss: Decimal
    unrealized_profit_loss_percent: Decimal


class PaperPortfolioResponse(BaseModel):
    account: PaperAccountResponse
    summary: PaperPortfolioSummaryResponse
    positions: list[PaperPositionResponse]


class PaperOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    side: PaperOrderSide
    order_type: Literal["market"]
    quantity: int
    status: PaperOrderStatus
    submitted_at: datetime
    filled_at: datetime | None = None
    rejection_reason: str | None = None


class PaperExecutionResponse(_DecimalJsonMixin):
    id: int
    order_id: int
    symbol: str
    side: PaperOrderSide
    quantity: int
    price: Decimal
    executed_at: datetime


class PaperOrderCreateRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    side: PaperOrderSide
    quantity: int = Field(gt=0)


class PaperOrderCreateResponse(BaseModel):
    order: PaperOrderResponse
    execution: PaperExecutionResponse
    summary: PaperPortfolioSummaryResponse
