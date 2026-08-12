from typing import Annotated
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.integrations.siliconflow.client import SiliconFlowClient
from app.modules.activity.service import UserActivityEvent, record_user_activity
from app.modules.ai.schemas import AIChatRequest, AIChatResponse
from app.modules.ai.service import AIService
from app.modules.auth.dependencies import get_optional_current_regular_user
from app.modules.market.service import MarketStockService, get_market_stock_service
from app.modules.users.models import User

router = APIRouter(prefix="/ai", tags=["ai"])
logger = logging.getLogger(__name__)


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
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_current_regular_user)],
) -> AIChatResponse:
    reply = await service.chat(request)
    _record_ai_chat_activity(db, current_user)
    return AIChatResponse(reply=reply)


def _record_ai_chat_activity(db: Session, user: User | None) -> None:
    try:
        record_user_activity(db, user=user, event=UserActivityEvent.AI_CHAT)
    except Exception:
        logger.exception(
            "Failed to record AI chat user activity",
            extra={"user_id": user.id if user is not None else None},
        )
