import logging

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.activity.service import UserActivityEvent, record_user_activity
from app.modules.auth.dependencies import get_optional_current_regular_user
from app.modules.market.service import (
    MarketStockService,
    get_market_stock_service,
)
from app.modules.quant.market_data import MarketServiceDataProvider
from app.modules.quant.schemas import (
    DailyBar,
    QuantStockAnalysis,
    TechnicalSummary,
)
from app.modules.quant.service import (
    analyze_symbol_stock,
    analyze_symbol_technical_summary,
    analyze_technical_summary,
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/quant",
    tags=["quant"],
)


@router.post(
    "/technical-summary",
    response_model=TechnicalSummary,
)
def get_technical_summary(
    bars: list[DailyBar],
) -> TechnicalSummary:
    return analyze_technical_summary(bars)


@router.get(
    "/stocks/{symbol}/technical-summary",
    response_model=TechnicalSummary,
)
def get_symbol_technical_summary(
    symbol: str = Path(..., min_length=1, max_length=16),
    limit: int = Query(default=60, ge=1, le=500),
    market_service: MarketStockService = Depends(get_market_stock_service),
) -> TechnicalSummary:
    market_data = MarketServiceDataProvider(market_service)

    return analyze_symbol_technical_summary(
        symbol=symbol,
        market_data=market_data,
        limit=limit,
    )


@router.get(
    "/stocks/{symbol}/analysis",
    response_model=QuantStockAnalysis,
)
def get_symbol_analysis(
    symbol: str = Path(..., min_length=1, max_length=16),
    limit: int = Query(default=60, ge=1, le=500),
    market_service: MarketStockService = Depends(get_market_stock_service),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_regular_user),
) -> QuantStockAnalysis:
    market_data = MarketServiceDataProvider(market_service)

    result = analyze_symbol_stock(
        symbol=symbol,
        market_data=market_data,
        limit=limit,
    )
    _record_quant_analysis_activity(db, current_user)
    return result


def _record_quant_analysis_activity(db: Session, user: User | None) -> None:
    try:
        record_user_activity(db, user=user, event=UserActivityEvent.QUANT_ANALYSIS)
    except Exception:
        logger.exception(
            "Failed to record quant analysis user activity",
            extra={"user_id": user.id if user is not None else None},
        )
