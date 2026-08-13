from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.auth.dependencies import get_optional_current_regular_user
from app.modules.paper_trading.quote_provider import (
    PaperTradingQuoteProvider,
    get_paper_trading_quote_provider,
)
from app.modules.paper_trading.service import PaperTradingService
from app.modules.users.models import User


def get_demo_account_key(settings: Settings = Depends(get_settings)) -> str:
    # Development-only account resolution. Replace this dependency with a
    # current-user backed account resolver once authentication exists.
    return settings.paper_trading_demo_account_key


def get_paper_trading_service(
    db: Session = Depends(get_db),
    quote_provider: PaperTradingQuoteProvider = Depends(get_paper_trading_quote_provider),
    settings: Settings = Depends(get_settings),
    current_user: User | None = Depends(get_optional_current_regular_user),
) -> PaperTradingService:
    return PaperTradingService(
        db,
        quote_provider,
        settings,
        user_id=current_user.id if current_user is not None else None,
    )
