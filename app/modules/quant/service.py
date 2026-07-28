from collections.abc import Sequence

from app.modules.quant.schemas import (
    DailyBar,
    MacdResult,
    MacdState,
    PriceDirection,
    RsiState,
    VolumeAnalysisResult,
    TrendState,
    VolumeState,
    EvidenceState,
    RiskFlag,
    TechnicalSummary,
)


def calculate_moving_average(
    bars: Sequence[DailyBar],
    period: int,
) -> float | None:
    if period <= 0:
        raise ValueError("period must be greater than zero")

    if len(bars) < period:
        return None

    recent_bars = bars[-period:]
    total_close = sum(bar.close for bar in recent_bars)

    return total_close / period


def calculate_rsi(
    bars: Sequence[DailyBar],
    period: int = 14,
) -> float | None:
    if period <= 0:
        raise ValueError("period must be greater than zero")

    if len(bars) < period + 1:
        return None

    total_gain = 0.0
    total_loss = 0.0
    start_index = len(bars) - period

    for index in range(start_index, len(bars)):
        change = bars[index].close - bars[index - 1].close

        if change > 0:
            total_gain += change
        elif change < 0:
            total_loss += -change

    if total_gain == 0 and total_loss == 0:
        return 50.0

    if total_loss == 0:
        return 100.0

    if total_gain == 0:
        return 0.0

    average_gain = total_gain / period
    average_loss = total_loss / period
    relative_strength = average_gain / average_loss

    return 100 - (100 / (1 + relative_strength))


def calculate_macd(
    bars: Sequence[DailyBar],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> MacdResult | None:
    if fast_period <= 0 or slow_period <= 0 or signal_period <= 0:
        raise ValueError("MACD periods must be greater than zero")

    if fast_period >= slow_period:
        raise ValueError("fast period must be less than slow period")

    minimum_bar_count = slow_period + signal_period - 1

    if len(bars) < minimum_bar_count:
        return None

    fast_alpha = 2 / (fast_period + 1)
    slow_alpha = 2 / (slow_period + 1)
    signal_alpha = 2 / (signal_period + 1)

    fast_ema = bars[0].close
    slow_ema = bars[0].close
    dif = fast_ema - slow_ema
    dea = dif

    for bar in bars[1:]:
        close = bar.close

        fast_ema = close * fast_alpha + fast_ema * (1 - fast_alpha)
        slow_ema = close * slow_alpha + slow_ema * (1 - slow_alpha)

        dif = fast_ema - slow_ema
        dea = dif * signal_alpha + dea * (1 - signal_alpha)

    return MacdResult(
        dif=dif,
        dea=dea,
        histogram=2 * (dif - dea),
    )


def analyze_volume(
    bars: Sequence[DailyBar],
    baseline_period: int = 5,
) -> VolumeAnalysisResult | None:
    if baseline_period <= 0:
        raise ValueError("baseline period must be greater than zero")

    if len(bars) < baseline_period + 1:
        return None

    latest_bar = bars[-1]
    previous_bar = bars[-2]
    baseline_bars = bars[-baseline_period - 1 : -1]

    average_volume = sum(bar.volume for bar in baseline_bars) / baseline_period

    if average_volume <= 0:
        return None

    if latest_bar.close > previous_bar.close:
        price_direction = PriceDirection.UP
    elif latest_bar.close < previous_bar.close:
        price_direction = PriceDirection.DOWN
    else:
        price_direction = PriceDirection.FLAT

    return VolumeAnalysisResult(
        latest_volume=latest_bar.volume,
        average_volume=average_volume,
        volume_ratio=latest_bar.volume / average_volume,
        price_direction=price_direction,
    )


def classify_rsi(rsi: float | None) -> RsiState:
    if rsi is None:
        return RsiState.INSUFFICIENT_DATA

    if rsi >= 70:
        return RsiState.HIGH

    if rsi > 55:
        return RsiState.RELATIVELY_STRONG

    if rsi >= 45:
        return RsiState.BALANCED

    if rsi > 30:
        return RsiState.RELATIVELY_WEAK

    return RsiState.LOW


def classify_macd(macd: MacdResult | None) -> MacdState:
    if macd is None:
        return MacdState.INSUFFICIENT_DATA

    if macd.dif > macd.dea and macd.histogram > 0:
        return MacdState.POSITIVE

    if macd.dif < macd.dea and macd.histogram < 0:
        return MacdState.NEGATIVE

    return MacdState.MIXED


def classify_trend(
    latest_close: float | None,
    ma5: float | None,
    ma20: float | None,
) -> TrendState:
    if latest_close is None or ma5 is None or ma20 is None:
        return TrendState.INSUFFICIENT_DATA

    if latest_close > ma5 > ma20:
        return TrendState.UPWARD

    if latest_close < ma5 < ma20:
        return TrendState.DOWNWARD

    return TrendState.MIXED


def classify_volume(
    volume: VolumeAnalysisResult | None,
    trend: TrendState,
) -> VolumeState:
    if volume is None:
        return VolumeState.INSUFFICIENT_DATA

    if volume.volume_ratio < 0.9:
        return VolumeState.LOW

    if volume.volume_ratio <= 1.1:
        return VolumeState.INCONCLUSIVE

    if trend == TrendState.UPWARD:
        if volume.price_direction == PriceDirection.UP:
            return VolumeState.CONFIRMING
        if volume.price_direction == PriceDirection.DOWN:
            return VolumeState.CONTRADICTING

    if trend == TrendState.DOWNWARD:
        if volume.price_direction == PriceDirection.DOWN:
            return VolumeState.CONFIRMING
        if volume.price_direction == PriceDirection.UP:
            return VolumeState.CONTRADICTING

    return VolumeState.INCONCLUSIVE


def classify_evidence(
    trend: TrendState,
    rsi: RsiState,
    macd: MacdState,
    volume: VolumeState,
) -> EvidenceState:
    if (
        trend == TrendState.INSUFFICIENT_DATA
        or rsi == RsiState.INSUFFICIENT_DATA
        or macd == MacdState.INSUFFICIENT_DATA
    ):
        return EvidenceState.INSUFFICIENT_DATA

    if volume == VolumeState.CONTRADICTING:
        return EvidenceState.MIXED

    positive_rsi_states = {
        RsiState.HIGH,
        RsiState.RELATIVELY_STRONG,
    }
    negative_rsi_states = {
        RsiState.LOW,
        RsiState.RELATIVELY_WEAK,
    }

    if (
        trend == TrendState.UPWARD
        and rsi in positive_rsi_states
        and macd == MacdState.POSITIVE
    ):
        return EvidenceState.CONSISTENT_POSITIVE

    if (
        trend == TrendState.DOWNWARD
        and rsi in negative_rsi_states
        and macd == MacdState.NEGATIVE
    ):
        return EvidenceState.CONSISTENT_NEGATIVE

    return EvidenceState.MIXED


def collect_risk_flags(
    latest_close: float | None,
    ma20: float | None,
    rsi: float | None,
) -> tuple[RiskFlag, ...]:
    if latest_close is None or ma20 is None or rsi is None:
        return (RiskFlag.INSUFFICIENT_DATA,)

    risk_flags: list[RiskFlag] = []

    if rsi >= 70:
        risk_flags.append(RiskFlag.RSI_HIGH)
    elif rsi <= 30:
        risk_flags.append(RiskFlag.RSI_LOW)

    price_deviation = (latest_close - ma20) / ma20

    if price_deviation >= 0.1:
        risk_flags.append(RiskFlag.PRICE_FAR_ABOVE_MA20)
    elif price_deviation <= -0.1:
        risk_flags.append(RiskFlag.PRICE_FAR_BELOW_MA20)

    return tuple(risk_flags)


def build_technical_summary(
    latest_close: float | None,
    ma5: float | None,
    ma20: float | None,
    rsi: float | None,
    macd: MacdResult | None,
    volume: VolumeAnalysisResult | None,
) -> TechnicalSummary:
    trend_state = classify_trend(latest_close, ma5, ma20)
    rsi_state = classify_rsi(rsi)
    macd_state = classify_macd(macd)
    volume_state = classify_volume(volume, trend_state)

    evidence_state = classify_evidence(
        trend=trend_state,
        rsi=rsi_state,
        macd=macd_state,
        volume=volume_state,
    )

    risk_flags = collect_risk_flags(
        latest_close=latest_close,
        ma20=ma20,
        rsi=rsi,
    )

    return TechnicalSummary(
        trend=trend_state,
        rsi=rsi_state,
        macd=macd_state,
        volume=volume_state,
        evidence=evidence_state,
        risk_flags=risk_flags,
    )


def analyze_technical_summary(
    bars: Sequence[DailyBar],
) -> TechnicalSummary:
    latest_close = bars[-1].close if bars else None

    ma5 = calculate_moving_average(bars, period=5)
    ma20 = calculate_moving_average(bars, period=20)
    rsi = calculate_rsi(bars, period=14)
    macd = calculate_macd(
        bars,
        fast_period=12,
        slow_period=26,
        signal_period=9,
    )
    volume = analyze_volume(bars, baseline_period=5)

    return build_technical_summary(
        latest_close=latest_close,
        ma5=ma5,
        ma20=ma20,
        rsi=rsi,
        macd=macd,
        volume=volume,
    )
