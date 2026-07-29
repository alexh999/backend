from collections.abc import Sequence
from math import isfinite

from app.modules.quant.schemas import (
    DailyBar,
    MacdResult,
    MomentumState,
    PriceDirection,
    StrengthState,
    VolumeAnalysisResult,
    TrendState,
    ParticipationState,
    EvidenceConsistency,
    RiskFlag,
    TechnicalSummary,
)
from app.modules.quant.market_data import (
    MarketDataProvider,
    normalize_daily_bars,
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


def classify_rsi(rsi: float | None) -> StrengthState:
    if rsi is None:
        return StrengthState.INSUFFICIENT_DATA

    if rsi >= 70:
        return StrengthState.HIGH

    if rsi > 55:
        return StrengthState.RELATIVELY_STRONG

    if rsi >= 45:
        return StrengthState.BALANCED

    if rsi > 30:
        return StrengthState.RELATIVELY_WEAK

    return StrengthState.LOW


def classify_macd(macd: MacdResult | None) -> MomentumState:
    if macd is None:
        return MomentumState.INSUFFICIENT_DATA

    if macd.dif > macd.dea and macd.histogram > 0:
        return MomentumState.POSITIVE

    if macd.dif < macd.dea and macd.histogram < 0:
        return MomentumState.NEGATIVE

    return MomentumState.MIXED


def classify_trend(
    latest_close: float | None,
    ma5: float | None,
    ma10: float | None,
    ma20: float | None,
    earlier_ma20: float | None,
) -> TrendState:
    if (
        latest_close is None
        or ma5 is None
        or ma10 is None
        or ma20 is None
        or earlier_ma20 is None
    ):
        return TrendState.INSUFFICIENT_DATA

    if not all(
        isfinite(value)
        for value in (
            latest_close,
            ma5,
            ma10,
            ma20,
            earlier_ma20,
        )
    ):
        return TrendState.INSUFFICIENT_DATA

    if latest_close <= 0 or ma20 <= 0 or earlier_ma20 <= 0:
        return TrendState.INSUFFICIENT_DATA

    ma20_slope = (ma20 - earlier_ma20) / earlier_ma20
    slope_threshold = 0.005

    if latest_close >= ma20 and ma5 >= ma10 and ma20_slope >= slope_threshold:
        return TrendState.UPWARD

    if latest_close <= ma20 and ma5 <= ma10 and ma20_slope <= -slope_threshold:
        return TrendState.DOWNWARD

    return TrendState.MIXED


def classify_volume(
    volume: VolumeAnalysisResult | None,
    trend: TrendState,
) -> ParticipationState:
    if volume is None or trend == TrendState.INSUFFICIENT_DATA:
        return ParticipationState.INSUFFICIENT_DATA

    if not isfinite(volume.volume_ratio) or volume.volume_ratio < 0:
        return ParticipationState.INSUFFICIENT_DATA

    if volume.volume_ratio < 0.9:
        return ParticipationState.LOW

    if (
        volume.volume_ratio < 1.1
        or volume.price_direction == PriceDirection.FLAT
        or trend == TrendState.MIXED
    ):
        return ParticipationState.INCONCLUSIVE

    confirms_upward_trend = (
        trend == TrendState.UPWARD and volume.price_direction == PriceDirection.UP
    )
    confirms_downward_trend = (
        trend == TrendState.DOWNWARD and volume.price_direction == PriceDirection.DOWN
    )

    if confirms_upward_trend or confirms_downward_trend:
        return ParticipationState.CONFIRMING

    return ParticipationState.CONTRADICTING


def classify_evidence(
    trend: TrendState,
    macd: MomentumState,
    volume: ParticipationState,
) -> EvidenceConsistency:
    if trend == TrendState.INSUFFICIENT_DATA or macd == MomentumState.INSUFFICIENT_DATA:
        return EvidenceConsistency.UNAVAILABLE

    direction_conflicts = (
        trend == TrendState.UPWARD and macd == MomentumState.NEGATIVE
    ) or (trend == TrendState.DOWNWARD and macd == MomentumState.POSITIVE)

    if direction_conflicts or volume == ParticipationState.CONTRADICTING:
        return EvidenceConsistency.DIVERGENT

    direction_aligns = (
        trend == TrendState.UPWARD and macd == MomentumState.POSITIVE
    ) or (trend == TrendState.DOWNWARD and macd == MomentumState.NEGATIVE)

    if direction_aligns and volume == ParticipationState.CONFIRMING:
        return EvidenceConsistency.HIGH

    if direction_aligns:
        return EvidenceConsistency.MODERATE

    return EvidenceConsistency.DIVERGENT


def collect_risk_flags(
    latest_close: float | None,
    ma20: float | None,
    rsi: float | None,
) -> tuple[RiskFlag, ...]:
    risk_flags: list[RiskFlag] = []

    if rsi is None or not isfinite(rsi) or rsi < 0 or rsi > 100:
        risk_flags.append(RiskFlag.DATA_INSUFFICIENT)
    elif rsi >= 70:
        risk_flags.append(RiskFlag.RSI_HIGH)
    elif rsi <= 30:
        risk_flags.append(RiskFlag.RSI_LOW)

    price_data_invalid = (
        latest_close is None
        or ma20 is None
        or not isfinite(latest_close)
        or not isfinite(ma20)
        or latest_close <= 0
        or ma20 <= 0
    )

    if price_data_invalid:
        if RiskFlag.DATA_INSUFFICIENT not in risk_flags:
            risk_flags.append(RiskFlag.DATA_INSUFFICIENT)

        return tuple(risk_flags)

    price_deviation = abs(latest_close - ma20) / ma20

    if price_deviation >= 0.1:
        risk_flags.append(RiskFlag.PRICE_EXTENDED)

    return tuple(risk_flags)


def build_technical_summary(
    latest_close: float | None,
    ma5: float | None,
    ma10: float | None,
    ma20: float | None,
    earlier_ma20: float | None,
    rsi: float | None,
    macd: MacdResult | None,
    volume: VolumeAnalysisResult | None,
) -> TechnicalSummary:
    trend_state = classify_trend(
        latest_close,
        ma5,
        ma10,
        ma20,
        earlier_ma20,
    )
    rsi_state = classify_rsi(rsi)
    macd_state = classify_macd(macd)
    volume_state = classify_volume(volume, trend_state)

    evidence_state = classify_evidence(
        trend=trend_state,
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
        momentum=macd_state,
        strength=rsi_state,
        participation=volume_state,
        consistency=evidence_state,
        risk_flags=risk_flags,
    )


def analyze_technical_summary(
    bars: Sequence[DailyBar],
) -> TechnicalSummary:
    slope_lookback = 5
    latest_close = bars[-1].close if bars else None

    ma5 = calculate_moving_average(bars, period=5)
    ma10 = calculate_moving_average(bars, period=10)
    ma20 = calculate_moving_average(bars, period=20)

    earlier_bars = bars[:-slope_lookback]
    earlier_ma20 = calculate_moving_average(
        earlier_bars,
        period=20,
    )

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
        ma10=ma10,
        ma20=ma20,
        earlier_ma20=earlier_ma20,
        rsi=rsi,
        macd=macd,
        volume=volume,
    )


def analyze_symbol_technical_summary(
    symbol: str,
    market_data: MarketDataProvider,
    limit: int = 60,
) -> TechnicalSummary:
    normalized_symbol = symbol.strip().upper()

    if not normalized_symbol:
        raise ValueError("symbol must not be blank")

    if limit <= 0:
        raise ValueError("limit must be greater than zero")

    bars = market_data.get_daily_bars(
        symbol=normalized_symbol,
        limit=limit,
    )
    normalized_bars = normalize_daily_bars(bars)

    return analyze_technical_summary(normalized_bars)
