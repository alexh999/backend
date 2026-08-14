from fastapi import APIRouter, Depends, Path, Query

from app.modules.market.service import (
    MarketStockService,
    get_market_stock_service,
)
from app.modules.quant.factor_ic_service import analyze_real_factor_ic
from app.modules.quant.market_data import MarketServiceDataProvider
from app.modules.quant.schemas import (
    DailyBar,
    FactorIcAnalysisRequest,
    FactorIcAnalysisResponse,
    QuantStockAnalysis,
    TechnicalSummary,
)
from app.modules.quant.service import (
    analyze_symbol_stock,
    analyze_symbol_technical_summary,
    analyze_technical_summary,
)

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
) -> QuantStockAnalysis:
    market_data = MarketServiceDataProvider(market_service)

    return analyze_symbol_stock(
        symbol=symbol,
        market_data=market_data,
        limit=limit,
    )


@router.post(
    "/factor-ic-analysis",
    response_model=FactorIcAnalysisResponse,
)
def get_factor_ic_analysis(
    request: FactorIcAnalysisRequest,
    market_service: MarketStockService = Depends(get_market_stock_service),
) -> FactorIcAnalysisResponse:
    market_data = MarketServiceDataProvider(market_service)

    return analyze_real_factor_ic(
        request=request,
        market_data=market_data,
    )
