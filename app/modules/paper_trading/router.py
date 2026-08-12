import logging
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.activity.service import UserActivityEvent, record_user_activity
from app.modules.auth.dependencies import get_optional_current_regular_user
from app.modules.paper_trading.dependencies import get_paper_trading_service
from app.modules.paper_trading.schemas import (
    PaperOrderCreateRequest,
    PaperOrderCreateResponse,
    PaperOrderResponse,
    PaperPortfolioResponse,
    PaperPositionResponse,
)
from app.modules.paper_trading.service import PaperTradingService
from app.modules.users.models import User


router = APIRouter(prefix="/paper-trading", tags=["paper-trading"])
logger = logging.getLogger(__name__)


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
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_regular_user),
) -> PaperOrderCreateResponse:
    """Create an immediate-fill market order.

    Phase 1 has no open orders to cancel because every accepted market order is
    filled synchronously.
    """
    response = service.place_order(request)
    _record_paper_order_activity(db, current_user)
    return response


def _record_paper_order_activity(db: Session, user: User | None) -> None:
    try:
        record_user_activity(db, user=user, event=UserActivityEvent.PAPER_ORDER)
    except Exception:
        logger.exception(
            "Failed to record paper trading user activity",
            extra={"user_id": user.id if user is not None else None},
        )
