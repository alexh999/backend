from collections.abc import Mapping, Sequence
from math import isfinite

from app.modules.quant.factor_ic import (
    FactorIcCrossSection,
    FactorIcResult,
    calculate_factor_ic,
)
from app.modules.quant.factor_scores import (
    SUPPORTED_FACTOR_IDS,
    calculate_factor_score,
)
from app.modules.quant.market_data import normalize_daily_bars
from app.modules.quant.schemas import DailyBar
from datetime import date


def build_factor_ic_cross_sections(
    factor_id: str,
    bars_by_stock: Mapping[str, Sequence[DailyBar]],
    holding_period: int = 5,
    minimum_lookback: int = 35,
) -> tuple[FactorIcCrossSection, ...]:
    normalized_factor_id = factor_id.strip().lower()

    if normalized_factor_id not in SUPPORTED_FACTOR_IDS:
        raise ValueError(f"unsupported factor id: {factor_id}")

    if holding_period <= 0:
        raise ValueError("holding period must be greater than zero")

    if minimum_lookback < 35:
        raise ValueError("minimum lookback cannot be smaller than 35")

    sections_by_date: dict[
        date,
        tuple[dict[str, float], dict[str, float]],
    ] = {}

    for raw_symbol, raw_bars in bars_by_stock.items():
        symbol = raw_symbol.strip().upper()

        if not symbol:
            continue

        bars = normalize_daily_bars(raw_bars)
        signal_index = minimum_lookback - 1

        while signal_index < len(bars):
            entry_index = signal_index + 1
            exit_index = entry_index + holding_period - 1

            if exit_index >= len(bars):
                break

            entry_bar = bars[entry_index]
            exit_bar = bars[exit_index]

            if (
                not isfinite(entry_bar.open)
                or entry_bar.open <= 0
                or not isfinite(exit_bar.close)
                or exit_bar.close <= 0
            ):
                signal_index += 1
                continue

            historical_bars = bars[: signal_index + 1]
            factor_score = calculate_factor_score(
                normalized_factor_id,
                historical_bars,
            )

            if factor_score is None or not isfinite(factor_score):
                signal_index += 1
                continue

            forward_return = exit_bar.close / entry_bar.open - 1

            if not isfinite(forward_return):
                signal_index += 1
                continue

            signal_date = bars[signal_index].trade_date
            factor_values, forward_returns = sections_by_date.setdefault(
                signal_date,
                ({}, {}),
            )

            factor_values[symbol] = factor_score
            forward_returns[symbol] = forward_return
            signal_index += 1

    return tuple(
        FactorIcCrossSection(
            date=signal_date,
            factor_values_by_stock=dict(sections_by_date[signal_date][0]),
            forward_returns_by_stock=dict(sections_by_date[signal_date][1]),
        )
        for signal_date in sorted(sections_by_date)
    )


def calculate_factor_ic_analysis(
    factor_id: str,
    bars_by_stock: Mapping[str, Sequence[DailyBar]],
    holding_period: int = 5,
    minimum_lookback: int = 35,
    minimum_sample_size: int = 3,
) -> FactorIcResult:
    cross_sections = build_factor_ic_cross_sections(
        factor_id=factor_id,
        bars_by_stock=bars_by_stock,
        holding_period=holding_period,
        minimum_lookback=minimum_lookback,
    )

    return calculate_factor_ic(
        factor_id=factor_id,
        cross_sections=cross_sections,
        minimum_sample_size=minimum_sample_size,
    )
