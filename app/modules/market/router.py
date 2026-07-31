from fastapi import APIRouter, Depends, Path

from app.modules.market.schemas import (
    MarketIndexOverviewResponse,
    MarketStockDetailResponse,
    MarketStockListItemResponse,
)
from app.modules.market.service import MarketStockService, get_market_stock_service

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/indexes/overview", response_model=MarketIndexOverviewResponse)
def read_market_index_overview(
    service: MarketStockService = Depends(get_market_stock_service),
) -> MarketIndexOverviewResponse:
    return service.get_market_index_overview()


@router.get("/stocks", response_model=list[MarketStockListItemResponse])
def list_market_stocks(
    service: MarketStockService = Depends(get_market_stock_service),
) -> list[MarketStockListItemResponse]:
    return service.list_stocks()


@router.get("/stocks/{symbol}/detail", response_model=MarketStockDetailResponse)
def read_market_stock_detail(
    symbol: str = Path(..., min_length=1, max_length=16),
    service: MarketStockService = Depends(get_market_stock_service),
) -> MarketStockDetailResponse:
    return service.get_stock_detail(symbol)
