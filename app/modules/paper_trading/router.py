from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.modules.paper_trading.dependencies import get_paper_trading_service
from app.modules.paper_trading.schemas import (
    PaperOrderCreateRequest,
    PaperOrderCreateResponse,
    PaperOrderResponse,
    PaperPortfolioResponse,
    PaperPositionResponse,
)
from app.modules.paper_trading.service import PaperTradingService


router = APIRouter(prefix="/paper-trading", tags=["paper-trading"])


@router.get("/portfolio", response_model=PaperPortfolioResponse)
def read_paper_trading_portfolio(
    service: PaperTradingService = Depends(get_paper_trading_service),
) -> PaperPortfolioResponse:
    return service.get_portfolio()


@router.get("/positions", response_model=list[PaperPositionResponse])
def list_paper_trading_positions(
    service: PaperTradingService = Depends(get_paper_trading_service),
) -> list[PaperPositionResponse]:
    return service.list_positions()


@router.get("/orders", response_model=list[PaperOrderResponse])
def list_paper_trading_orders(
    side: Literal["buy", "sell"] | None = Query(default=None),
    status: Literal["filled", "rejected"] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    service: PaperTradingService = Depends(get_paper_trading_service),
) -> list[PaperOrderResponse]:
    return service.list_orders(side=side, status=status, limit=limit)


@router.post("/orders", response_model=PaperOrderCreateResponse)
def create_paper_trading_order(
    request: PaperOrderCreateRequest,
    service: PaperTradingService = Depends(get_paper_trading_service),
) -> PaperOrderCreateResponse:
    """Create an immediate-fill market order.

    Phase 1 has no open orders to cancel because every accepted market order is
    filled synchronously.
    """
    return service.place_order(request)
