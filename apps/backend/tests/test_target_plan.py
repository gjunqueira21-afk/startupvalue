import numpy as np
import pytest

from app.decision.target_plan import MIN_HIT_SAMPLE, build_target_plan


def _factors(n_hit: int, n_miss: int) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    valuations = np.concatenate([np.full(n_hit, 200.0), np.full(n_miss, 50.0)])
    factors = {
        "revenue_cagr_operating": np.concatenate(
            [np.full(n_hit, 0.30), np.full(n_miss, 0.10)]
        ),
        "ebitda_margin_year5_operating": np.concatenate(
            [np.full(n_hit, 0.25), np.full(n_miss, 0.12)]
        ),
    }
    return valuations, factors


def test_available_plan_reports_hit_medians_and_trajectory():
    valuations, factors = _factors(60, 40)
    plan = build_target_plan(valuations, 100.0, factors, base_year_revenue=1_000_000.0)
    assert plan.status == "available"
    assert plan.hit_count == 60
    assert plan.required_revenue_cagr == pytest.approx(0.30)
    assert plan.hit_ebitda_margin == pytest.approx(0.25)
    assert plan.miss_revenue_cagr == pytest.approx(0.10)
    assert plan.miss_ebitda_margin == pytest.approx(0.12)
    assert [point.year for point in plan.trajectory] == [1, 2, 3, 4, 5]
    assert plan.trajectory[0].revenue == pytest.approx(1_000_000.0)
    assert plan.trajectory[4].revenue == pytest.approx(1_000_000.0 * 1.30**4)


def test_insufficient_hits_below_threshold():
    valuations, factors = _factors(MIN_HIT_SAMPLE - 1, 100)
    plan = build_target_plan(valuations, 100.0, factors, base_year_revenue=1_000_000.0)
    assert plan.status == "insufficient_hits"
    assert plan.required_revenue_cagr is None
    assert plan.trajectory == ()


def test_missing_cagr_factor_means_not_available_for_inputs():
    valuations = np.full(200, 200.0)
    plan = build_target_plan(valuations, 100.0, {}, base_year_revenue=1_000_000.0)
    assert plan.status == "not_available_for_inputs"


def test_no_base_revenue_yields_empty_trajectory_without_nan():
    valuations, factors = _factors(60, 40)
    plan = build_target_plan(valuations, 100.0, factors, base_year_revenue=None)
    assert plan.status == "available"
    assert plan.trajectory == ()
    assert plan.required_revenue_cagr == pytest.approx(0.30)


def test_margin_factor_optional():
    valuations, factors = _factors(60, 40)
    del factors["ebitda_margin_year5_operating"]
    plan = build_target_plan(valuations, 100.0, factors, base_year_revenue=1.0)
    assert plan.status == "available"
    assert plan.hit_ebitda_margin is None
