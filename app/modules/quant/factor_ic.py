from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from math import isfinite, sqrt
from enum import StrEnum


@dataclass(frozen=True)
class FactorIcCrossSection:
    date: date
    factor_values_by_stock: dict[str, float]
    forward_returns_by_stock: dict[str, float]


@dataclass(frozen=True)
class FactorIcPeriodResult:
    date: date
    sample_size: int
    information_coefficient: float | None
    rank_information_coefficient: float | None


def calculate_pearson_correlation(
    left: Sequence[float],
    right: Sequence[float],
) -> float | None:
    if len(left) != len(right):
        raise ValueError("correlation inputs must have the same length")

    if len(left) < 2:
        return None

    if not all(isfinite(value) for value in (*left, *right)):
        raise ValueError("correlation inputs must contain only finite values")

    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)

    covariance = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left, right, strict=True)
    )
    left_variance = sum((value - left_mean) ** 2 for value in left)
    right_variance = sum((value - right_mean) ** 2 for value in right)

    denominator = sqrt(left_variance * right_variance)

    if denominator <= 1e-12:
        return None

    return max(-1.0, min(1.0, covariance / denominator))


def calculate_average_ranks(values: Sequence[float]) -> list[float]:
    if not all(isfinite(value) for value in values):
        raise ValueError("rank inputs must contain only finite values")

    indexed_values = sorted(
        enumerate(values),
        key=lambda item: item[1],
    )
    ranks = [0.0] * len(values)
    start = 0

    while start < len(indexed_values):
        end = start

        while (
            end + 1 < len(indexed_values)
            and indexed_values[end + 1][1] == indexed_values[start][1]
        ):
            end += 1

        average_rank = (start + end) / 2 + 1

        for index in range(start, end + 1):
            original_index = indexed_values[index][0]
            ranks[original_index] = average_rank

        start = end + 1

    return ranks


def calculate_factor_ic_period(
    cross_section: FactorIcCrossSection,
    minimum_sample_size: int = 3,
) -> FactorIcPeriodResult:
    if minimum_sample_size < 2:
        raise ValueError("minimum sample size cannot be smaller than two")

    factor_values: list[float] = []
    forward_returns: list[float] = []

    for symbol, factor_value in cross_section.factor_values_by_stock.items():
        forward_return = cross_section.forward_returns_by_stock.get(symbol)

        if (
            forward_return is None
            or not isfinite(factor_value)
            or not isfinite(forward_return)
        ):
            continue

        factor_values.append(factor_value)
        forward_returns.append(forward_return)

    if len(factor_values) < minimum_sample_size:
        return FactorIcPeriodResult(
            date=cross_section.date,
            sample_size=len(factor_values),
            information_coefficient=None,
            rank_information_coefficient=None,
        )

    information_coefficient = calculate_pearson_correlation(
        factor_values,
        forward_returns,
    )
    rank_information_coefficient = calculate_pearson_correlation(
        calculate_average_ranks(factor_values),
        calculate_average_ranks(forward_returns),
    )

    return FactorIcPeriodResult(
        date=cross_section.date,
        sample_size=len(factor_values),
        information_coefficient=information_coefficient,
        rank_information_coefficient=rank_information_coefficient,
    )


class FactorIcReliability(StrEnum):
    INSUFFICIENT = "insufficient"
    LIMITED = "limited"
    ADEQUATE = "adequate"


@dataclass(frozen=True)
class FactorIcResult:
    factor_id: str
    periods: tuple[FactorIcPeriodResult, ...]

    @property
    def available_periods(self) -> tuple[FactorIcPeriodResult, ...]:
        return tuple(
            period
            for period in self.periods
            if period.information_coefficient is not None
            and period.rank_information_coefficient is not None
        )

    @property
    def average_information_coefficient(self) -> float | None:
        return _average(
            [
                period.information_coefficient
                for period in self.available_periods
                if period.information_coefficient is not None
            ]
        )

    @property
    def average_rank_information_coefficient(self) -> float | None:
        return _average(
            [
                period.rank_information_coefficient
                for period in self.available_periods
                if period.rank_information_coefficient is not None
            ]
        )

    @property
    def positive_information_coefficient_rate(self) -> float | None:
        return _positive_rate(
            [
                period.information_coefficient
                for period in self.available_periods
                if period.information_coefficient is not None
            ]
        )

    @property
    def positive_rank_information_coefficient_rate(self) -> float | None:
        return _positive_rate(
            [
                period.rank_information_coefficient
                for period in self.available_periods
                if period.rank_information_coefficient is not None
            ]
        )

    @property
    def ic_information_ratio(self) -> float | None:
        return _information_ratio(
            [
                period.information_coefficient
                for period in self.available_periods
                if period.information_coefficient is not None
            ]
        )

    @property
    def rank_ic_information_ratio(self) -> float | None:
        return _information_ratio(
            [
                period.rank_information_coefficient
                for period in self.available_periods
                if period.rank_information_coefficient is not None
            ]
        )

    @property
    def average_sample_size(self) -> float:
        periods = self.available_periods

        if not periods:
            return 0.0

        return sum(period.sample_size for period in periods) / len(periods)

    @property
    def reliability(self) -> FactorIcReliability:
        period_count = len(self.available_periods)

        if period_count < 5 or self.average_sample_size < 5:
            return FactorIcReliability.INSUFFICIENT

        if period_count < 20 or self.average_sample_size < 20:
            return FactorIcReliability.LIMITED

        return FactorIcReliability.ADEQUATE


def calculate_factor_ic(
    factor_id: str,
    cross_sections: Sequence[FactorIcCrossSection],
    minimum_sample_size: int = 3,
) -> FactorIcResult:
    normalized_factor_id = factor_id.strip()

    if not normalized_factor_id:
        raise ValueError("factor id cannot be blank")

    observed_dates: set[date] = set()
    periods: list[FactorIcPeriodResult] = []

    for cross_section in cross_sections:
        if cross_section.date in observed_dates:
            raise ValueError("cross-section dates must not be duplicated")

        observed_dates.add(cross_section.date)
        periods.append(
            calculate_factor_ic_period(
                cross_section,
                minimum_sample_size=minimum_sample_size,
            )
        )

    periods.sort(key=lambda period: period.date)

    return FactorIcResult(
        factor_id=normalized_factor_id,
        periods=tuple(periods),
    )


def _average(values: Sequence[float]) -> float | None:
    if not values:
        return None

    return sum(values) / len(values)


def _positive_rate(values: Sequence[float]) -> float | None:
    if not values:
        return None

    return sum(value > 0 for value in values) / len(values)


def _information_ratio(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None

    mean = sum(values) / len(values)
    sample_variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)

    if sample_variance <= 1e-12:
        return None

    return mean / sqrt(sample_variance)
