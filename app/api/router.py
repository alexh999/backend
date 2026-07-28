from fastapi import APIRouter

from app.api.health import router as health_router
from app.modules.ai.router import router as ai_router
from app.modules.quant.router import router as quant_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(ai_router)
api_router.include_router(quant_router)