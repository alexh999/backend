from fastapi import APIRouter

from app.modules.quant.schemas import DailyBar, TechnicalSummary
from app.modules.quant.service import analyze_technical_summary

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
