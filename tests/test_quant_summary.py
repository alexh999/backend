from datetime import date, timedelta
import pytest

from app.modules.quant.schemas import (
    MacdResult,
    MomentumState,
    StrengthState,
    TrendState,
    PriceDirection,
    VolumeAnalysisResult,
    ParticipationState,
    EvidenceConsistency,
    RiskFlag,
    TechnicalSummary,
    DailyBar,
)
from app.modules.quant.service import (
    classify_macd,
    classify_rsi,
    classify_trend,
    classify_volume,
    classify_evidence,
    collect_risk_flags,
    build_technical_summary,
    analyze_technical_summary,
)


@pytest.mark.parametrize(
    ("rsi", "expected"),
    [
        (70.0, StrengthState.HIGH),
        (69.9, StrengthState.RELATIVELY_STRONG),
        (55.0, StrengthState.BALANCED),
        (45.0, StrengthState.BALANCED),
        (44.9, StrengthState.RELATIVELY_WEAK),
        (30.0, StrengthState.LOW),
        (None, StrengthState.INSUFFICIENT_DATA),
    ],
)
def test_classify_rsi(rsi: float | None, expected: StrengthState) -> None:
    assert classify_rsi(rsi) == expected


@pytest.mark.parametrize(
    ("macd", "expected"),
    [
        (
            MacdResult(dif=1.2, dea=0.8, histogram=0.8),
            MomentumState.POSITIVE,
        ),
        (
            MacdResult(dif=-1.2, dea=-0.8, histogram=-0.8),
            MomentumState.NEGATIVE,
        ),
        (
            MacdResult(dif=1.2, dea=0.8, histogram=-0.2),
            MomentumState.MIXED,
        ),
        (
            MacdResult(dif=0.5, dea=0.5, histogram=0.0),
            MomentumState.MIXED,
        ),
        (
            None,
            MomentumState.INSUFFICIENT_DATA,
        ),
    ],
)
def test_classify_macd(
    macd: MacdResult | None,
    expected: MomentumState,
) -> None:
    assert classify_macd(macd) == expected


@pytest.mark.parametrize(
    (
        "latest_close",
        "ma5",
        "ma10",
        "ma20",
        "earlier_ma20",
        "expected",
    ),
    [
        (
            110.0,
            105.0,
            103.0,
            100.0,
            99.0,
            TrendState.UPWARD,
        ),
        (
            90.0,
            95.0,
            97.0,
            100.0,
            101.0,
            TrendState.DOWNWARD,
        ),
        (
            105.0,
            103.0,
            104.0,
            100.0,
            99.0,
            TrendState.MIXED,
        ),
        (
            105.0,
            104.0,
            103.0,
            100.4,
            100.0,
            TrendState.MIXED,
        ),
        (
            None,
            105.0,
            103.0,
            100.0,
            99.0,
            TrendState.INSUFFICIENT_DATA,
        ),
        (
            110.0,
            None,
            103.0,
            100.0,
            99.0,
            TrendState.INSUFFICIENT_DATA,
        ),
        (
            110.0,
            105.0,
            None,
            100.0,
            99.0,
            TrendState.INSUFFICIENT_DATA,
        ),
        (
            110.0,
            105.0,
            103.0,
            None,
            99.0,
            TrendState.INSUFFICIENT_DATA,
        ),
        (
            110.0,
            105.0,
            103.0,
            100.0,
            None,
            TrendState.INSUFFICIENT_DATA,
        ),
    ],
)
def test_classify_trend(
    latest_close: float | None,
    ma5: float | None,
    ma10: float | None,
    ma20: float | None,
    earlier_ma20: float | None,
    expected: TrendState,
) -> None:
    assert (
        classify_trend(
            latest_close,
            ma5,
            ma10,
            ma20,
            earlier_ma20,
        )
        == expected
    )


def make_volume_result(
    ratio: float,
    price_direction: PriceDirection,
) -> VolumeAnalysisResult:
    return VolumeAnalysisResult(
        latest_volume=1200,
        average_volume=1000,
        volume_ratio=ratio,
        price_direction=price_direction,
    )


@pytest.mark.parametrize(
    ("volume", "trend", "expected"),
    [
        (
            make_volume_result(0.8, PriceDirection.UP),
            TrendState.UPWARD,
            ParticipationState.LOW,
        ),
        (
            make_volume_result(1.0, PriceDirection.UP),
            TrendState.UPWARD,
            ParticipationState.INCONCLUSIVE,
        ),
        (
            make_volume_result(1.1, PriceDirection.UP),
            TrendState.UPWARD,
            ParticipationState.CONFIRMING,
        ),
        (
            make_volume_result(1.2, PriceDirection.UP),
            TrendState.UPWARD,
            ParticipationState.CONFIRMING,
        ),
        (
            make_volume_result(1.2, PriceDirection.DOWN),
            TrendState.DOWNWARD,
            ParticipationState.CONFIRMING,
        ),
        (
            make_volume_result(1.2, PriceDirection.DOWN),
            TrendState.UPWARD,
            ParticipationState.CONTRADICTING,
        ),
        (
            make_volume_result(1.2, PriceDirection.UP),
            TrendState.DOWNWARD,
            ParticipationState.CONTRADICTING,
        ),
        (
            make_volume_result(1.2, PriceDirection.FLAT),
            TrendState.UPWARD,
            ParticipationState.INCONCLUSIVE,
        ),
        (
            make_volume_result(1.2, PriceDirection.UP),
            TrendState.MIXED,
            ParticipationState.INCONCLUSIVE,
        ),
        (
            make_volume_result(0.8, PriceDirection.UP),
            TrendState.INSUFFICIENT_DATA,
            ParticipationState.INSUFFICIENT_DATA,
        ),
        (
            None,
            TrendState.UPWARD,
            ParticipationState.INSUFFICIENT_DATA,
        ),
    ],
)
def test_classify_volume(
    volume: VolumeAnalysisResult | None,
    trend: TrendState,
    expected: ParticipationState,
) -> None:
    assert classify_volume(volume, trend) == expected


@pytest.mark.parametrize(
    ("trend", "macd", "volume", "expected"),
    [
        (
            TrendState.UPWARD,
            MomentumState.POSITIVE,
            ParticipationState.CONFIRMING,
            EvidenceConsistency.HIGH,
        ),
        (
            TrendState.DOWNWARD,
            MomentumState.NEGATIVE,
            ParticipationState.CONFIRMING,
            EvidenceConsistency.HIGH,
        ),
        (
            TrendState.UPWARD,
            MomentumState.POSITIVE,
            ParticipationState.LOW,
            EvidenceConsistency.MODERATE,
        ),
        (
            TrendState.DOWNWARD,
            MomentumState.NEGATIVE,
            ParticipationState.INCONCLUSIVE,
            EvidenceConsistency.MODERATE,
        ),
        (
            TrendState.UPWARD,
            MomentumState.NEGATIVE,
            ParticipationState.CONFIRMING,
            EvidenceConsistency.DIVERGENT,
        ),
        (
            TrendState.DOWNWARD,
            MomentumState.POSITIVE,
            ParticipationState.CONFIRMING,
            EvidenceConsistency.DIVERGENT,
        ),
        (
            TrendState.UPWARD,
            MomentumState.POSITIVE,
            ParticipationState.CONTRADICTING,
            EvidenceConsistency.DIVERGENT,
        ),
        (
            TrendState.MIXED,
            MomentumState.POSITIVE,
            ParticipationState.CONFIRMING,
            EvidenceConsistency.DIVERGENT,
        ),
        (
            TrendState.INSUFFICIENT_DATA,
            MomentumState.POSITIVE,
            ParticipationState.INCONCLUSIVE,
            EvidenceConsistency.UNAVAILABLE,
        ),
        (
            TrendState.UPWARD,
            MomentumState.INSUFFICIENT_DATA,
            ParticipationState.CONFIRMING,
            EvidenceConsistency.UNAVAILABLE,
        ),
    ],
)
def test_classify_evidence(
    trend: TrendState,
    macd: MomentumState,
    volume: ParticipationState,
    expected: EvidenceConsistency,
) -> None:
    assert classify_evidence(trend, macd, volume) == expected


@pytest.mark.parametrize(
    ("latest_close", "ma20", "rsi", "expected"),
    [
        (100.0, 100.0, 50.0, ()),
        (100.0, 100.0, 70.0, (RiskFlag.RSI_HIGH,)),
        (100.0, 100.0, 30.0, (RiskFlag.RSI_LOW,)),
        (
            110.0,
            100.0,
            50.0,
            (RiskFlag.PRICE_EXTENDED,),
        ),
        (
            90.0,
            100.0,
            50.0,
            (RiskFlag.PRICE_EXTENDED,),
        ),
        (
            115.0,
            100.0,
            75.0,
            (
                RiskFlag.RSI_HIGH,
                RiskFlag.PRICE_EXTENDED,
            ),
        ),
        (None, 100.0, 50.0, (RiskFlag.DATA_INSUFFICIENT,)),
        (100.0, None, 50.0, (RiskFlag.DATA_INSUFFICIENT,)),
        (100.0, 100.0, None, (RiskFlag.DATA_INSUFFICIENT,)),
    ],
)
def test_collect_risk_flags(
    latest_close: float | None,
    ma20: float | None,
    rsi: float | None,
    expected: tuple[RiskFlag, ...],
) -> None:
    assert collect_risk_flags(latest_close, ma20, rsi) == expected


def test_build_technical_summary() -> None:
    macd = MacdResult(
        dif=1.2,
        dea=0.8,
        histogram=0.8,
    )
    volume = make_volume_result(
        ratio=1.2,
        price_direction=PriceDirection.UP,
    )

    result = build_technical_summary(
        latest_close=108.0,
        ma5=105.0,
        ma10=103.0,
        ma20=100.0,
        earlier_ma20=99.0,
        rsi=60.0,
        macd=macd,
        volume=volume,
    )

    assert result == TechnicalSummary(
        trend=TrendState.UPWARD,
        strength=StrengthState.RELATIVELY_STRONG,
        momentum=MomentumState.POSITIVE,
        participation=ParticipationState.CONFIRMING,
        consistency=EvidenceConsistency.HIGH,
        risk_flags=(),
    )


def test_build_technical_summary_with_missing_data() -> None:
    result = build_technical_summary(
        latest_close=None,
        ma5=None,
        ma10=None,
        ma20=None,
        earlier_ma20=None,
        rsi=None,
        macd=None,
        volume=None,
    )

    assert result == TechnicalSummary(
        trend=TrendState.INSUFFICIENT_DATA,
        strength=StrengthState.INSUFFICIENT_DATA,
        momentum=MomentumState.INSUFFICIENT_DATA,
        participation=ParticipationState.INSUFFICIENT_DATA,
        consistency=EvidenceConsistency.UNAVAILABLE,
        risk_flags=(RiskFlag.DATA_INSUFFICIENT,),
    )


def make_rising_daily_bars(count: int) -> list[DailyBar]:
    bars: list[DailyBar] = []

    for index in range(count):
        close = 100.0 + index
        volume = 1200 if index == count - 1 else 1000

        bars.append(
            DailyBar(
                trade_date=date(2026, 1, 1) + timedelta(days=index),
                open=close,
                high=close + 1,
                low=close - 1,
                close=close,
                previous_close=close - 1 if index > 0 else None,
                volume=volume,
            )
        )

    return bars


def test_analyze_technical_summary_from_daily_bars() -> None:
    result = analyze_technical_summary(make_rising_daily_bars(40))

    assert result == TechnicalSummary(
        trend=TrendState.UPWARD,
        strength=StrengthState.HIGH,
        momentum=MomentumState.POSITIVE,
        participation=ParticipationState.CONFIRMING,
        consistency=EvidenceConsistency.HIGH,
        risk_flags=(RiskFlag.RSI_HIGH,),
    )


def test_analyze_technical_summary_with_empty_bars() -> None:
    result = analyze_technical_summary([])

    assert result == TechnicalSummary(
        trend=TrendState.INSUFFICIENT_DATA,
        strength=StrengthState.INSUFFICIENT_DATA,
        momentum=MomentumState.INSUFFICIENT_DATA,
        participation=ParticipationState.INSUFFICIENT_DATA,
        consistency=EvidenceConsistency.UNAVAILABLE,
        risk_flags=(RiskFlag.DATA_INSUFFICIENT,),
    )
