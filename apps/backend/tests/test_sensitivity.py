from __future__ import annotations

import numpy as np
import pytest

from app.decision.sensitivity import DRIVER_METHOD_VERSION, rank_drivers


def _independent(n: int = 5000, seed: int = 7) -> tuple[dict[str, np.ndarray], np.ndarray]:
    rng = np.random.default_rng(seed)
    strong = rng.lognormal(0.0, 0.3, n)
    weak = rng.normal(1.0, 0.1, n)
    cost = rng.lognormal(0.0, 0.2, n)
    valuation = 10.0 * strong + 2.0 * weak - 4.0 * cost + rng.normal(0.0, 0.2, n)
    return {"weak": weak, "cost": cost, "strong": strong}, valuation


def test_ranks_independent_drivers_by_share_of_explained_rank_variance() -> None:
    drivers, valuation = _independent()
    ranking = rank_drivers(drivers, valuation)
    assert ranking.method == "spearman+srrc"
    assert ranking.method_version == DRIVER_METHOD_VERSION
    assert [item.name for item in ranking.drivers] == ["strong", "cost", "weak"]
    shares = [item.contribution for item in ranking.drivers]
    assert all(share is not None and share > 0 for share in shares)
    assert sum(share for share in shares if share is not None) == pytest.approx(1.0)
    assert ranking.r_squared is not None and ranking.r_squared > 0.9
    assert ranking.warnings == ()


def test_direction_follows_the_sign_of_the_standardized_rank_coefficient() -> None:
    drivers, valuation = _independent()
    by_name = {item.name: item for item in rank_drivers(drivers, valuation).drivers}
    assert by_name["strong"].direction == "positive"
    assert by_name["strong"].srrc is not None and by_name["strong"].srrc > 0
    assert by_name["cost"].direction == "negative"
    assert by_name["cost"].rho is not None and by_name["cost"].rho < 0


def test_constant_driver_is_reported_without_invented_coefficients() -> None:
    drivers, valuation = _independent()
    drivers["fixed_wacc"] = np.full(valuation.size, 0.25)
    ranking = rank_drivers(drivers, valuation)
    fixed = next(item for item in ranking.drivers if item.name == "fixed_wacc")
    assert fixed.status == "not_estimable_constant"
    assert fixed.rho is None and fixed.srrc is None and fixed.contribution is None
    assert ranking.drivers[-1].name == "fixed_wacc"
    estimated = [item.contribution for item in ranking.drivers if item.contribution is not None]
    assert sum(estimated) == pytest.approx(1.0)


def test_constant_valuation_makes_every_driver_not_estimable() -> None:
    ranking = rank_drivers({"x": [1.0, 2.0, 3.0]}, [5.0, 5.0, 5.0])
    assert ranking.r_squared is None
    assert ranking.drivers[0].status == "not_estimable_constant"
    assert "valuation_constant" in ranking.warnings


def test_duplicated_information_is_flagged_instead_of_double_counted() -> None:
    drivers, valuation = _independent()
    drivers["strong_copy"] = drivers["strong"] * 3.0 + 1.0
    ranking = rank_drivers(drivers, valuation)
    assert "correlated_drivers" in ranking.warnings


def test_non_monotone_relationship_is_flagged_as_low_fit() -> None:
    rng = np.random.default_rng(3)
    x = rng.normal(0.0, 1.0, 4000)
    ranking = rank_drivers({"x": x}, x**2)
    assert ranking.r_squared is not None and ranking.r_squared < 0.1
    assert "low_rank_linear_fit" in ranking.warnings


def test_binary_driver_is_supported() -> None:
    rng = np.random.default_rng(11)
    failed = (rng.random(3000) < 0.3).astype(float)
    growth = rng.lognormal(0.0, 0.2, 3000)
    valuation = np.where(failed == 1.0, -1.0, 10.0 * growth)
    by_name = {
        item.name: item
        for item in rank_drivers({"failure_state": failed, "growth": growth}, valuation).drivers
    }
    assert by_name["failure_state"].direction == "negative"
    assert by_name["failure_state"].status == "estimated"


def test_ranking_is_permutation_invariant() -> None:
    drivers, valuation = _independent(n=500)
    order = np.random.default_rng(1).permutation(valuation.size)
    original = rank_drivers(drivers, valuation)
    shuffled = rank_drivers({k: v[order] for k, v in drivers.items()}, valuation[order])
    assert [d.name for d in shuffled.drivers] == [d.name for d in original.drivers]
    for left, right in zip(original.drivers, shuffled.drivers, strict=True):
        assert left.srrc == pytest.approx(right.srrc, abs=1e-12)
        assert left.rho == pytest.approx(right.rho, abs=1e-12)
    assert shuffled.r_squared == pytest.approx(original.r_squared, abs=1e-12)


def test_rejects_misaligned_or_non_finite_vectors() -> None:
    with pytest.raises(ValueError):
        rank_drivers({"x": [1.0, 2.0]}, [1.0, 2.0, 3.0])
    with pytest.raises(ValueError):
        rank_drivers({"x": [1.0, float("inf"), 3.0]}, [1.0, 2.0, 3.0])
