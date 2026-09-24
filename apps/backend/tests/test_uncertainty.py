from __future__ import annotations

import pytest

from app.decision.uncertainty import UNCERTAINTY_RULE_VERSION, assess_uncertainty


def _assess(
    p50: float,
    *,
    iqr_ratio: float,
    non_positive: float = 0.0,
    spread80_ratio: float | None = None,
) -> object:
    half = iqr_ratio * abs(p50) / 2.0
    wide = (spread80_ratio if spread80_ratio is not None else iqr_ratio * 2.0) * abs(p50) / 2.0
    return assess_uncertainty(
        p10=p50 - wide,
        p25=p50 - half,
        p50=p50,
        p75=p50 + half,
        p90=p50 + wide,
        non_positive_probability=non_positive,
    )


@pytest.mark.parametrize(
    ("ratio", "label"),
    [
        (0.0, "LOW"),
        (0.39, "LOW"),
        (0.40, "MODERATE"),
        (0.79, "MODERATE"),
        (0.80, "HIGH"),
        (0.82, "HIGH"),
        (1.49, "HIGH"),
        (1.50, "VERY HIGH"),
        (3.66, "VERY HIGH"),
    ],
)
def test_label_follows_published_iqr_ratio_bands(ratio: float, label: str) -> None:
    result = _assess(8_400_000.0, iqr_ratio=ratio)
    assert result.label == label
    assert result.reason == "iqr_ratio"
    assert result.iqr_ratio == pytest.approx(ratio)
    assert result.rule_version == UNCERTAINTY_RULE_VERSION


def test_reports_absolute_and_relative_spreads() -> None:
    result = assess_uncertainty(
        p10=4.3e6, p25=6.1e6, p50=8.4e6, p75=11.7e6, p90=15.2e6, non_positive_probability=0.0
    )
    assert result.iqr == pytest.approx(5.6e6)
    assert result.iqr_ratio == pytest.approx(5.6 / 8.4)
    assert result.spread80 == pytest.approx(10.9e6)
    assert result.spread80_ratio == pytest.approx(10.9 / 8.4)
    assert result.label == "MODERATE"


def test_non_positive_median_is_very_high_without_a_misleading_ratio() -> None:
    result = assess_uncertainty(
        p10=-3e6, p25=-1e6, p50=-0.2e6, p75=2e6, p90=5e6, non_positive_probability=0.55
    )
    assert result.label == "VERY HIGH"
    assert result.reason == "median_not_positive"
    assert result.iqr_ratio is None
    assert result.spread80_ratio is None
    assert result.iqr == pytest.approx(3e6)


def test_immaterial_positive_median_is_treated_as_not_positive() -> None:
    result = assess_uncertainty(
        p10=-1.0, p25=0.0, p50=0.4, p75=2.0, p90=5.0, non_positive_probability=0.3
    )
    assert result.label == "VERY HIGH"
    assert result.reason == "median_not_positive"
    assert result.iqr_ratio is None


def test_material_mass_of_worthless_outcomes_overrides_a_narrow_core_range() -> None:
    result = _assess(1_000_000.0, iqr_ratio=0.3, non_positive=0.25)
    assert result.label == "VERY HIGH"
    assert result.reason == "material_non_positive_mass"
    assert result.iqr_ratio == pytest.approx(0.3)


def test_degenerate_positive_distribution_is_low() -> None:
    result = assess_uncertainty(
        p10=5.0, p25=5.0, p50=5.0, p75=5.0, p90=5.0, non_positive_probability=0.0
    )
    assert result.label == "LOW"
    assert result.iqr == 0.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"p10": 3.0, "p25": 2.0, "p50": 4.0, "p75": 5.0, "p90": 6.0, "non_positive_probability": 0},
        {"p10": 1.0, "p25": 2.0, "p50": 4.0, "p75": 5.0, "p90": 6.0, "non_positive_probability": 2},
        {
            "p10": 1.0,
            "p25": 2.0,
            "p50": float("nan"),
            "p75": 5.0,
            "p90": 6.0,
            "non_positive_probability": 0,
        },
    ],
)
def test_rejects_unordered_or_invalid_inputs(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        assess_uncertainty(**kwargs)
