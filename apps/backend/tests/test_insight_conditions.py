from __future__ import annotations

import numpy as np
import pytest

from app.insights.conditions import cliffs_delta, target_conditions


def _case(n: int = 6000) -> tuple[dict[str, np.ndarray], np.ndarray]:
    rng = np.random.default_rng(8)
    revenue = rng.lognormal(15.0, 0.3, n)
    wacc = rng.triangular(0.18, 0.25, 0.35, n)
    failed = (rng.random(n) < 0.15).astype(float)
    noise = rng.normal(0.0, 1.0, n)
    valuation = np.where(failed == 1.0, 0.0, revenue * (0.45 - wacc) * 5.0)
    variables = {
        "revenue_year5_operating": revenue,
        "annual_wacc": wacc,
        "failure_state": failed,
        "noise": noise,
    }
    return variables, valuation


def test_cliffs_delta_counts_pairwise_dominance_with_ties() -> None:
    assert cliffs_delta(np.array([3.0, 4.0]), np.array([1.0, 2.0, 3.0])) == pytest.approx(5 / 6)
    assert cliffs_delta(np.array([1.0]), np.array([2.0])) == -1.0


def test_revenue_threshold_is_the_lower_quartile_of_successful_scenarios() -> None:
    variables, valuation = _case()
    target = float(np.quantile(valuation, 0.75))
    result = target_conditions(variables, valuation, target)
    assert result.sample_note == "ok"
    revenue = next(c for c in result.conditions if c.name == "revenue_year5_operating")
    hits = valuation >= target
    assert revenue.direction == "higher"
    assert revenue.cliffs_delta > 0.33
    expected = np.quantile(variables["revenue_year5_operating"][hits], 0.25)
    assert revenue.threshold == pytest.approx(expected)
    assert revenue.threshold_coverage == pytest.approx(0.75, abs=0.01)
    assert revenue.hit_rate_beyond_threshold is not None
    assert revenue.hit_rate_beyond_threshold > result.base_rate


def test_inverse_relationship_uses_the_upper_quartile_as_a_ceiling() -> None:
    variables, valuation = _case()
    result = target_conditions(variables, valuation, float(np.quantile(valuation, 0.75)))
    wacc = next(c for c in result.conditions if c.name == "annual_wacc")
    hits = valuation >= float(np.quantile(valuation, 0.75))
    assert wacc.direction == "lower"
    assert wacc.threshold == pytest.approx(np.quantile(variables["annual_wacc"][hits], 0.75))
    assert wacc.hit_rate_beyond_threshold is not None
    assert wacc.hit_rate_beyond_threshold > result.base_rate


def test_binary_condition_reports_rates_without_threshold() -> None:
    variables, valuation = _case()
    result = target_conditions(variables, valuation, float(np.quantile(valuation, 0.75)))
    failure = next(c for c in result.conditions if c.name == "failure_state")
    assert failure.kind == "binary"
    assert failure.hit_value == 0.0
    assert failure.miss_value > 0.15
    assert failure.direction == "lower"
    assert failure.threshold is None


def test_conditions_are_ranked_by_effect_and_weak_ones_have_no_threshold() -> None:
    variables, valuation = _case()
    result = target_conditions(variables, valuation, float(np.quantile(valuation, 0.75)))
    effects = [abs(c.cliffs_delta) for c in result.conditions]
    assert effects == sorted(effects, reverse=True)
    noise = next(c for c in result.conditions if c.name == "noise")
    assert noise.threshold is None


def test_empty_group_has_no_conditions() -> None:
    variables, valuation = _case()
    result = target_conditions(variables, valuation, float(valuation.max()) + 1.0)
    assert result.sample_note == "empty_group"
    assert result.hit_count == 0
    assert result.conditions == ()


def test_tiny_groups_do_not_get_thresholds() -> None:
    variables, valuation = _case()
    target = float(np.sort(valuation)[-5])
    result = target_conditions(variables, valuation, target)
    assert result.sample_note == "insufficient"
    assert all(c.threshold is None for c in result.conditions)


def test_constant_variables_are_skipped() -> None:
    variables, valuation = _case()
    variables["fixed"] = np.full(valuation.size, 3.0)
    result = target_conditions(variables, valuation, float(np.median(valuation)))
    assert all(c.name != "fixed" for c in result.conditions)
