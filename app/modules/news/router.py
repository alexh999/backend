from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.modules.news.schemas import NewsListResponse
from app.modules.news.service import NewsService, get_news_service

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=NewsListResponse)
def list_news(
    category: Annotated[str, Query(min_length=1, max_length=32)] = "markets",
    query: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    service: Annotated[NewsService, Depends(get_news_service)] = None,
) -> NewsListResponse:
    return service.list_news(category=category, query=query, limit=limit)


@router.get("/stocks/{symbol}", response_model=NewsListResponse)
def list_stock_news(
    symbol: str = Path(..., min_length=1, max_length=16),
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
    service: Annotated[NewsService, Depends(get_news_service)] = None,
) -> NewsListResponse:
    return service.list_symbol_news(symbol=symbol, limit=limit)
