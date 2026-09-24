from __future__ import annotations

import numpy as np
import pytest

from app.simulation.distributions import (
    LogNormal,
    Normal,
    StudentT,
    Triangular,
    Uniform,
    sample_distribution,
)
from app.simulation.monte_carlo import (
    SimpleCashFlowSimulationInput,
    apply_absorbing_failure,
    simulate_simple_cash_flows,
)
from app.simulation.random_engine import pcg64
from app.simulation.statistics import histogram, summarize


def test_percentile_convention_golden_case_preserves_zero() -> None:
    result = summarize([0, 10, 20, 30, 40])
    assert (result.p5, result.p10, result.p25, result.p50) == (2, 4, 10, 20)
    assert (result.p75, result.p90, result.p95) == (30, 36, 38)
    assert result.zero_probability == 0.2


def test_documented_distribution_moments() -> None:
    count = 80_000
    triangular = sample_distribution(Triangular(50, 100, 150), pcg64(10), count)
    uniform = sample_distribution(Uniform(50, 150), pcg64(11), count)
    lognormal = sample_distribution(LogNormal(100, 0.25), pcg64(12), count)
    student = sample_distribution(
        StudentT.from_standard_deviation(loc=0, standard_deviation=1, df=5),
        pcg64(13),
        count,
    )
    assert np.mean(triangular) == pytest.approx(100, abs=0.3)
    assert np.mean(uniform) == pytest.approx(100, abs=0.35)
    assert np.mean(lognormal) == pytest.approx(100, abs=0.3)
    assert np.std(lognormal) / np.mean(lognormal) == pytest.approx(0.25, abs=0.006)
    assert np.var(student) == pytest.approx(1.0, abs=0.05)


def test_truncated_normal_does_not_create_boundary_atoms() -> None:
    samples = sample_distribution(Normal(0, 1, 0, 2), pcg64(15), 50_000)
    assert np.all((samples > 0) & (samples < 2))
    assert not np.any(samples == 0)
    assert not np.any(samples == 2)


def test_simple_simulation_is_seed_reproducible_and_persistent() -> None:
    inputs = SimpleCashFlowSimulationInput(
        base_cash_flows=(10.0, 20.0, 30.0),
        factor=LogNormal(1.0, 0.25),
        scenarios=2_000,
        seed=471829,
        p_failure_horizon=0.3,
    )
    first = simulate_simple_cash_flows(inputs)
    second = simulate_simple_cash_flows(inputs)
    np.testing.assert_array_equal(first.factor_paths, second.factor_paths)
    np.testing.assert_array_equal(first.failure_months, second.failure_months)
    np.testing.assert_array_equal(first.realized_cash_flows, second.realized_cash_flows)
    np.testing.assert_array_equal(first.factor_paths[:, 0], first.factor_paths[:, 2])
    assert first.factor_paths.flags.writeable is False


def test_failure_is_absorbing_but_preserves_prior_history_and_recovery() -> None:
    counterfactual = np.array([[10.0, 20.0, 30.0], [10.0, 20.0, 30.0]])
    realized = apply_absorbing_failure(counterfactual, np.array([2, 0]), liquidation_value=7)
    np.testing.assert_array_equal(realized[0], [10, 7, 0])
    np.testing.assert_array_equal(realized[1], counterfactual[1])


def test_failure_probability_extremes_are_preserved() -> None:
    base = dict(base_cash_flows=(1.0, 2.0), factor=Uniform(1.0, 1.1), scenarios=20, seed=2)
    no_failure = simulate_simple_cash_flows(
        SimpleCashFlowSimulationInput(**base, p_failure_horizon=0)
    )
    all_failure = simulate_simple_cash_flows(
        SimpleCashFlowSimulationInput(**base, p_failure_horizon=1)
    )
    assert np.all(no_failure.failure_months == 0)
    assert np.all(all_failure.failure_months == 1)
    assert set(all_failure.states) == {"failure"}


def test_histogram_counts_all_scenarios_and_constant_is_atom() -> None:
    result = histogram([-1, 0, 1, 2], bins=2)
    assert sum(result.counts) == 4
    atom = histogram([7, 7, 7])
    assert atom.kind == "atom"
    assert atom.counts == (3,)
    assert atom.atom_value == 7
