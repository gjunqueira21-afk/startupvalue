from __future__ import annotations

import numpy as np
import pytest

from app.decision.drivers import spearman_drivers
from app.decision.targets import analyze_target, wilson_interval


def test_spearman_ranks_ties_and_nulls_constant_inputs() -> None:
    drivers = spearman_drivers(
        {"positive": [1, 2, 2, 4], "constant": [7, 7, 7, 7]},
        [10, 20, 20, 40],
    )
    assert drivers[0].name == "positive"
    assert drivers[0].rho == pytest.approx(1.0)
    constant = next(item for item in drivers if item.name == "constant")
    assert constant.rho is None
    assert constant.status == "not_estimable_constant"


def test_target_uses_all_scenarios_and_equality_is_a_hit() -> None:
    result = analyze_target(
        [-1, 0, 0, 10],
        0,
        {"revenue": [1, 2, 3, 8], "fixed": [4, 4, 4, 4]},
    )
    assert result.hit_count == 3
    assert result.miss_count == 1
    assert result.probability == 0.75
    revenue = result.comparisons[0]
    assert revenue.hit.p50 == 3
    assert revenue.miss.p50 == 1
    assert revenue.median_difference_hit_minus_miss == 2
    assert result.comparisons[1].status == "not_estimable_constant"


def test_target_empty_group_and_wilson_boundary() -> None:
    result = analyze_target([1, 2, 3], 10, {"x": [3, 2, 1]})
    assert result.hit_count == 0
    assert result.comparisons[0].hit.reason == "empty_subset"
    assert result.comparisons[0].median_difference_hit_minus_miss is None
    low, high = wilson_interval(0, 100)
    assert low == 0
    assert high > 0


def test_decision_statistics_are_permutation_invariant() -> None:
    valuation = np.array([2, 5, 1, 8, 4], dtype=float)
    factor = np.array([9, 7, 10, 1, 8], dtype=float)
    permutation = np.array([4, 2, 0, 3, 1])
    original_driver = spearman_drivers({"x": factor}, valuation)[0]
    shuffled_driver = spearman_drivers(
        {"x": factor[permutation]}, valuation[permutation]
    )[0]
    assert shuffled_driver.rho == original_driver.rho
    original_target = analyze_target(valuation, 4, {"x": factor})
    shuffled_target = analyze_target(
        valuation[permutation], 4, {"x": factor[permutation]}
    )
    assert shuffled_target == original_target
