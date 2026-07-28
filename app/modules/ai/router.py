from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.integrations.siliconflow.client import SiliconFlowClient
from app.modules.ai.schemas import AIChatRequest, AIChatResponse
from app.modules.ai.service import AIService

router = APIRouter(prefix="/ai", tags=["ai"])


def get_ai_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AIService:
    return AIService(SiliconFlowClient.from_settings(settings))


@router.post("/chat", response_model=AIChatResponse)
async def chat(
    request: AIChatRequest,
    service: Annotated[AIService, Depends(get_ai_service)],
) -> AIChatResponse:
    reply = await service.chat(request)
    return AIChatResponse(reply=reply)
