from __future__ import annotations

import numpy as np
import pytest

from app.insights.tails import tail_shifts


def _case(n: int = 5000) -> tuple[dict[str, np.ndarray], np.ndarray]:
    rng = np.random.default_rng(21)
    revenue = rng.lognormal(0.0, 0.3, n)
    failed = (rng.random(n) < 0.2).astype(float)
    noise = rng.normal(0.0, 1.0, n)
    valuation = np.where(failed == 1.0, -1.0, 10.0 * revenue)
    return {"revenue_factor_mean": revenue, "failure_state": failed, "noise": noise}, valuation


def test_upside_tail_shows_higher_revenue_and_fewer_failures() -> None:
    drivers, valuation = _case()
    upside, _ = tail_shifts(drivers, valuation, order=list(drivers))
    by_name = {item.name: item for item in upside}
    revenue = by_name["revenue_factor_mean"]
    assert revenue.direction == "higher"
    assert revenue.kind == "continuous"
    assert revenue.group_value > revenue.overall_value
    failure = by_name["failure_state"]
    assert failure.kind == "binary"
    assert failure.direction == "lower"
    assert failure.group_value == 0.0
    assert failure.overall_value == pytest.approx(np.mean(drivers["failure_state"]))
    assert revenue.group_share == pytest.approx(0.1, abs=0.002)


def test_downside_tail_concentrates_failures() -> None:
    drivers, valuation = _case()
    _, downside = tail_shifts(drivers, valuation, order=list(drivers))
    assert downside[0].name == "revenue_factor_mean" or downside[0].name == "failure_state"
    failure = next(item for item in downside if item.name == "failure_state")
    assert failure.direction == "higher"
    assert failure.group_value == 1.0
    # Ties at P10 (every failed scenario has the same value) are kept whole and reported.
    assert failure.group_size == int(np.sum(valuation <= np.quantile(valuation, 0.1)))


def test_immaterial_shifts_are_not_reported() -> None:
    drivers, valuation = _case()
    upside, downside = tail_shifts(drivers, valuation, order=list(drivers))
    assert all(item.name != "noise" for item in (*upside, *downside))


def test_respects_contribution_order_and_limit() -> None:
    drivers, valuation = _case()
    upside, _ = tail_shifts(
        drivers, valuation, order=["failure_state", "revenue_factor_mean"], limit=1
    )
    assert [item.name for item in upside] == ["failure_state"]


def test_constant_valuation_has_no_tails() -> None:
    assert tail_shifts({"x": np.arange(5.0)}, np.ones(5), order=["x"]) == ([], [])
