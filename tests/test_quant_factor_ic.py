import pytest
from datetime import date

from app.modules.quant.factor_ic import (
    FactorIcCrossSection,
    calculate_average_ranks,
    calculate_factor_ic_period,
    calculate_pearson_correlation,
    FactorIcReliability,
    calculate_factor_ic,
)


def test_pearson_correlation_returns_one_for_same_direction() -> None:
    result = calculate_pearson_correlation(
        [1.0, 2.0, 3.0, 4.0],
        [0.01, 0.04, 0.09, 0.16],
    )

    assert result == pytest.approx(0.984374, abs=0.000001)


def test_pearson_correlation_returns_negative_one_for_opposite_order() -> None:
    result = calculate_pearson_correlation(
        [1.0, 2.0, 3.0],
        [3.0, 2.0, 1.0],
    )

    assert result == pytest.approx(-1.0)


def test_pearson_correlation_returns_none_for_constant_values() -> None:
    result = calculate_pearson_correlation(
        [1.0, 1.0, 1.0],
        [2.0, 3.0, 4.0],
    )

    assert result is None


def test_pearson_correlation_rejects_different_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        calculate_pearson_correlation(
            [1.0, 2.0],
            [1.0],
        )


def test_average_ranks_use_average_position_for_ties() -> None:
    result = calculate_average_ranks(
        [30.0, 10.0, 20.0, 20.0],
    )

    assert result == [4.0, 1.0, 2.5, 2.5]


def test_factor_ic_period_calculates_ic_and_rank_ic() -> None:
    result = calculate_factor_ic_period(
        FactorIcCrossSection(
            date=date(2026, 8, 1),
            factor_values_by_stock={
                "A": 1.0,
                "B": 2.0,
                "C": 3.0,
                "D": 4.0,
            },
            forward_returns_by_stock={
                "A": 0.01,
                "B": 0.04,
                "C": 0.09,
                "D": 0.16,
            },
        )
    )

    assert result.date == date(2026, 8, 1)
    assert result.sample_size == 4
    assert result.information_coefficient == pytest.approx(
        0.984374,
        abs=0.000001,
    )
    assert result.rank_information_coefficient == pytest.approx(1.0)


def test_factor_ic_period_uses_only_matching_finite_values() -> None:
    result = calculate_factor_ic_period(
        FactorIcCrossSection(
            date=date(2026, 8, 1),
            factor_values_by_stock={
                "A": 1.0,
                "B": 2.0,
                "C": float("nan"),
                "D": 4.0,
            },
            forward_returns_by_stock={
                "A": 0.01,
                "C": 0.03,
                "D": 0.04,
            },
        ),
        minimum_sample_size=2,
    )

    assert result.sample_size == 2
    assert result.information_coefficient == pytest.approx(1.0)
    assert result.rank_information_coefficient == pytest.approx(1.0)


def test_factor_ic_period_returns_unavailable_when_samples_are_insufficient() -> None:
    result = calculate_factor_ic_period(
        FactorIcCrossSection(
            date=date(2026, 8, 1),
            factor_values_by_stock={"A": 1.0, "B": 2.0},
            forward_returns_by_stock={"A": 0.01, "B": 0.02},
        ),
        minimum_sample_size=3,
    )

    assert result.sample_size == 2
    assert result.information_coefficient is None
    assert result.rank_information_coefficient is None


def test_factor_ic_calculates_multi_period_summary() -> None:
    cross_sections = [
        FactorIcCrossSection(
            date=date(2026, 8, 3),
            factor_values_by_stock={"A": 1.0, "B": 2.0, "C": 3.0},
            forward_returns_by_stock={"A": 0.01, "B": 0.02, "C": 0.03},
        ),
        FactorIcCrossSection(
            date=date(2026, 8, 1),
            factor_values_by_stock={"A": 1.0, "B": 2.0, "C": 3.0},
            forward_returns_by_stock={"A": 0.01, "B": 0.02, "C": 0.03},
        ),
        FactorIcCrossSection(
            date=date(2026, 8, 2),
            factor_values_by_stock={"A": 1.0, "B": 2.0, "C": 3.0},
            forward_returns_by_stock={"A": 0.03, "B": 0.02, "C": 0.01},
        ),
    ]

    result = calculate_factor_ic(
        factor_id=" trend ",
        cross_sections=cross_sections,
    )

    assert result.factor_id == "trend"
    assert [period.date for period in result.periods] == [
        date(2026, 8, 1),
        date(2026, 8, 2),
        date(2026, 8, 3),
    ]
    assert len(result.available_periods) == 3
    assert result.average_information_coefficient == pytest.approx(1 / 3)
    assert result.average_rank_information_coefficient == pytest.approx(1 / 3)
    assert result.positive_information_coefficient_rate == pytest.approx(2 / 3)
    assert result.positive_rank_information_coefficient_rate == pytest.approx(2 / 3)
    assert result.ic_information_ratio == pytest.approx(0.288675, abs=0.000001)
    assert result.rank_ic_information_ratio == pytest.approx(
        0.288675,
        abs=0.000001,
    )
    assert result.average_sample_size == 3
    assert result.reliability == FactorIcReliability.INSUFFICIENT


def test_factor_ic_rejects_duplicate_cross_section_dates() -> None:
    section = FactorIcCrossSection(
        date=date(2026, 8, 1),
        factor_values_by_stock={"A": 1.0, "B": 2.0, "C": 3.0},
        forward_returns_by_stock={"A": 0.01, "B": 0.02, "C": 0.03},
    )

    with pytest.raises(ValueError, match="must not be duplicated"):
        calculate_factor_ic(
            factor_id="trend",
            cross_sections=[section, section],
        )


def test_factor_ic_rejects_blank_factor_id() -> None:
    with pytest.raises(ValueError, match="cannot be blank"):
        calculate_factor_ic(
            factor_id="   ",
            cross_sections=[],
        )
