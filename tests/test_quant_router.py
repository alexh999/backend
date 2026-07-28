from datetime import date, timedelta

from app.modules.quant.router import get_technical_summary
from app.modules.quant.schemas import (
    DailyBar,
    EvidenceConsistency,
    MomentumState,
    ParticipationState,
    StrengthState,
    TrendState,
)


def make_bars() -> list[DailyBar]:
    bars = []

    for index in range(40):
        close = 100 + index

        bars.append(
            DailyBar(
                trade_date=date(2026, 1, 1) + timedelta(days=index),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1200 if index == 39 else 1000,
            )
        )

    return bars


def test_technical_summary_route_returns_analysis_result() -> None:
    result = get_technical_summary(make_bars())

    assert isinstance(result, dict) or result.__class__.__name__ == "TechnicalSummary"
    assert result.trend == TrendState.UPWARD
    assert result.momentum == MomentumState.POSITIVE
    assert result.strength == StrengthState.HIGH
    assert result.participation == ParticipationState.CONFIRMING
    assert result.consistency == EvidenceConsistency.HIGH
