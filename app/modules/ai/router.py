from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.integrations.siliconflow.client import SiliconFlowClient
from app.modules.ai.schemas import AIChatRequest, AIChatResponse
from app.modules.ai.service import AIService
from app.modules.market.service import MarketStockService, get_market_stock_service

router = APIRouter(prefix="/ai", tags=["ai"])


def get_ai_service(
    settings: Annotated[Settings, Depends(get_settings)],
    market_service: Annotated[MarketStockService, Depends(get_market_stock_service)],
) -> AIService:
    return AIService(
        SiliconFlowClient.from_settings(settings),
        market_service=market_service,
    )


@router.post("/chat", response_model=AIChatResponse)
async def chat(
    request: AIChatRequest,
    service: Annotated[AIService, Depends(get_ai_service)],
) -> AIChatResponse:
    reply = await service.chat(request)
    return AIChatResponse(reply=reply)
