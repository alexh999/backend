from fastapi import APIRouter, Depends, Path

from app.modules.market.schemas import MarketStockDetailResponse
from app.modules.market.service import MarketStockService, get_market_stock_service

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/stocks/{symbol}/detail", response_model=MarketStockDetailResponse)
def read_market_stock_detail(
    symbol: str = Path(..., min_length=1, max_length=16),
    service: MarketStockService = Depends(get_market_stock_service),
) -> MarketStockDetailResponse:
    return service.get_stock_detail(symbol)
