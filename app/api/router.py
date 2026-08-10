from fastapi import APIRouter

from app.api.health import router as health_router
from app.modules.admin.router import router as admin_router
from app.modules.ai.router import router as ai_router
from app.modules.auth.router import router as auth_router
from app.modules.market.router import router as market_router
from app.modules.quant.router import router as quant_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(admin_router)
api_router.include_router(auth_router)
api_router.include_router(ai_router)
api_router.include_router(market_router)
api_router.include_router(quant_router)
