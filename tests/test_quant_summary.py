import pytest

from app.modules.quant.schemas import (
    MacdResult,
    MacdState,
    RsiState,
    TrendState,
    PriceDirection,
    VolumeAnalysisResult,
    VolumeState,
    EvidenceState,
    RiskFlag,
    TechnicalSummary,
)
from app.modules.quant.service import (
    classify_macd,
    classify_rsi,
    classify_trend,
    classify_volume,
    classify_evidence,
    collect_risk_flags,
    build_technical_summary,
)


@pytest.mark.parametrize(
    ("rsi", "expected"),
    [
        (70.0, RsiState.HIGH),
        (69.9, RsiState.RELATIVELY_STRONG),
        (55.0, RsiState.BALANCED),
        (45.0, RsiState.BALANCED),
        (44.9, RsiState.RELATIVELY_WEAK),
        (30.0, RsiState.LOW),
        (None, RsiState.INSUFFICIENT_DATA),
    ],
)
def test_classify_rsi(rsi: float | None, expected: RsiState) -> None:
    assert classify_rsi(rsi) == expected


@pytest.mark.parametrize(
    ("macd", "expected"),
    [
        (
            MacdResult(dif=1.2, dea=0.8, histogram=0.8),
            MacdState.POSITIVE,
        ),
        (
            MacdResult(dif=-1.2, dea=-0.8, histogram=-0.8),
            MacdState.NEGATIVE,
        ),
        (
            MacdResult(dif=1.2, dea=0.8, histogram=-0.2),
            MacdState.MIXED,
        ),
        (
            MacdResult(dif=0.5, dea=0.5, histogram=0.0),
            MacdState.MIXED,
        ),
        (
            None,
            MacdState.INSUFFICIENT_DATA,
        ),
    ],
)
def test_classify_macd(
    macd: MacdResult | None,
    expected: MacdState,
) -> None:
    assert classify_macd(macd) == expected


@pytest.mark.parametrize(
    ("latest_close", "ma5", "ma20", "expected"),
    [
        (110.0, 105.0, 100.0, TrendState.UPWARD),
        (90.0, 95.0, 100.0, TrendState.DOWNWARD),
        (105.0, 100.0, 102.0, TrendState.MIXED),
        (100.0, 100.0, 100.0, TrendState.MIXED),
        (None, 100.0, 95.0, TrendState.INSUFFICIENT_DATA),
        (100.0, None, 95.0, TrendState.INSUFFICIENT_DATA),
        (100.0, 95.0, None, TrendState.INSUFFICIENT_DATA),
    ],
)
def test_classify_trend(
    latest_close: float | None,
    ma5: float | None,
    ma20: float | None,
    expected: TrendState,
) -> None:
    assert classify_trend(latest_close, ma5, ma20) == expected


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
            VolumeState.LOW,
        ),
        (
            make_volume_result(1.0, PriceDirection.UP),
            TrendState.UPWARD,
            VolumeState.INCONCLUSIVE,
        ),
        (
            make_volume_result(1.2, PriceDirection.UP),
            TrendState.UPWARD,
            VolumeState.CONFIRMING,
        ),
        (
            make_volume_result(1.2, PriceDirection.DOWN),
            TrendState.DOWNWARD,
            VolumeState.CONFIRMING,
        ),
        (
            make_volume_result(1.2, PriceDirection.DOWN),
            TrendState.UPWARD,
            VolumeState.CONTRADICTING,
        ),
        (
            make_volume_result(1.2, PriceDirection.UP),
            TrendState.DOWNWARD,
            VolumeState.CONTRADICTING,
        ),
        (
            make_volume_result(1.2, PriceDirection.FLAT),
            TrendState.UPWARD,
            VolumeState.INCONCLUSIVE,
        ),
        (
            make_volume_result(1.2, PriceDirection.UP),
            TrendState.MIXED,
            VolumeState.INCONCLUSIVE,
        ),
        (
            None,
            TrendState.UPWARD,
            VolumeState.INSUFFICIENT_DATA,
        ),
    ],
)
def test_classify_volume(
    volume: VolumeAnalysisResult | None,
    trend: TrendState,
    expected: VolumeState,
) -> None:
    assert classify_volume(volume, trend) == expected


@pytest.mark.parametrize(
    ("trend", "rsi", "macd", "volume", "expected"),
    [
        (
            TrendState.UPWARD,
            RsiState.RELATIVELY_STRONG,
            MacdState.POSITIVE,
            VolumeState.CONFIRMING,
            EvidenceState.CONSISTENT_POSITIVE,
        ),
        (
            TrendState.UPWARD,
            RsiState.HIGH,
            MacdState.POSITIVE,
            VolumeState.LOW,
            EvidenceState.CONSISTENT_POSITIVE,
        ),
        (
            TrendState.DOWNWARD,
            RsiState.RELATIVELY_WEAK,
            MacdState.NEGATIVE,
            VolumeState.CONFIRMING,
            EvidenceState.CONSISTENT_NEGATIVE,
        ),
        (
            TrendState.DOWNWARD,
            RsiState.LOW,
            MacdState.NEGATIVE,
            VolumeState.INCONCLUSIVE,
            EvidenceState.CONSISTENT_NEGATIVE,
        ),
        (
            TrendState.UPWARD,
            RsiState.RELATIVELY_STRONG,
            MacdState.POSITIVE,
            VolumeState.CONTRADICTING,
            EvidenceState.MIXED,
        ),
        (
            TrendState.UPWARD,
            RsiState.RELATIVELY_WEAK,
            MacdState.NEGATIVE,
            VolumeState.CONFIRMING,
            EvidenceState.MIXED,
        ),
        (
            TrendState.INSUFFICIENT_DATA,
            RsiState.BALANCED,
            MacdState.POSITIVE,
            VolumeState.INCONCLUSIVE,
            EvidenceState.INSUFFICIENT_DATA,
        ),
        (
            TrendState.UPWARD,
            RsiState.INSUFFICIENT_DATA,
            MacdState.POSITIVE,
            VolumeState.CONFIRMING,
            EvidenceState.INSUFFICIENT_DATA,
        ),
        (
            TrendState.UPWARD,
            RsiState.RELATIVELY_STRONG,
            MacdState.INSUFFICIENT_DATA,
            VolumeState.CONFIRMING,
            EvidenceState.INSUFFICIENT_DATA,
        ),
    ],
)
def test_classify_evidence(
    trend: TrendState,
    rsi: RsiState,
    macd: MacdState,
    volume: VolumeState,
    expected: EvidenceState,
) -> None:
    assert classify_evidence(trend, rsi, macd, volume) == expected


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
            (RiskFlag.PRICE_FAR_ABOVE_MA20,),
        ),
        (
            90.0,
            100.0,
            50.0,
            (RiskFlag.PRICE_FAR_BELOW_MA20,),
        ),
        (
            115.0,
            100.0,
            75.0,
            (
                RiskFlag.RSI_HIGH,
                RiskFlag.PRICE_FAR_ABOVE_MA20,
            ),
        ),
        (None, 100.0, 50.0, (RiskFlag.INSUFFICIENT_DATA,)),
        (100.0, None, 50.0, (RiskFlag.INSUFFICIENT_DATA,)),
        (100.0, 100.0, None, (RiskFlag.INSUFFICIENT_DATA,)),
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
        ma20=100.0,
        rsi=60.0,
        macd=macd,
        volume=volume,
    )

    assert result == TechnicalSummary(
        trend=TrendState.UPWARD,
        rsi=RsiState.RELATIVELY_STRONG,
        macd=MacdState.POSITIVE,
        volume=VolumeState.CONFIRMING,
        evidence=EvidenceState.CONSISTENT_POSITIVE,
        risk_flags=(),
    )


def test_build_technical_summary_with_missing_data() -> None:
    result = build_technical_summary(
        latest_close=None,
        ma5=None,
        ma20=None,
        rsi=None,
        macd=None,
        volume=None,
    )

    assert result == TechnicalSummary(
        trend=TrendState.INSUFFICIENT_DATA,
        rsi=RsiState.INSUFFICIENT_DATA,
        macd=MacdState.INSUFFICIENT_DATA,
        volume=VolumeState.INSUFFICIENT_DATA,
        evidence=EvidenceState.INSUFFICIENT_DATA,
        risk_flags=(RiskFlag.INSUFFICIENT_DATA,),
    )
