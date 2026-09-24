from __future__ import annotations

import numpy as np
import pytest

from app.valuation.dcf import TerminalAssumptions, accumulated_discount_factors, terminal_value
from app.valuation.scenario_dcf import (
    ExitMultipleTerminal,
    GordonTerminal,
    scenario_enterprise_values,
)


def _paths() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(5)
    flows = rng.normal(50.0, 30.0, (400, 60))
    failures = np.where(rng.random(400) < 0.2, rng.integers(1, 61, 400), 0)
    for scenario, month in enumerate(failures):
        if month:
            flows[scenario, month - 1 :] = 0.0
    return flows, failures


def test_scalar_gordon_matches_the_reference_dcf_bit_for_bit() -> None:
    flows, failures = _paths()
    factors = accumulated_discount_factors(0.22, 60)
    expected = np.sum(flows / factors[None, :], axis=1, dtype=np.float64)
    unit = terminal_value(TerminalAssumptions(1.0, 0.03, 0.22))
    normalized = np.maximum(np.mean(flows[:, -12:], axis=1), 0.0)
    expected += (failures == 0) * normalized * unit / factors[-1]

    actual = scenario_enterprise_values(
        flows, failures, annual_wacc=0.22, terminal=GordonTerminal(0.03)
    )
    np.testing.assert_array_equal(actual, expected)


def test_per_scenario_rates_equal_to_the_scalar_give_the_same_values() -> None:
    flows, failures = _paths()
    scalar = scenario_enterprise_values(
        flows, failures, annual_wacc=0.22, terminal=GordonTerminal(0.03)
    )
    vector = scenario_enterprise_values(
        flows,
        failures,
        annual_wacc=np.full(400, 0.22),
        terminal=GordonTerminal(np.full(400, 0.03)),
    )
    np.testing.assert_allclose(vector, scalar, rtol=1e-12, atol=1e-9)


def test_each_scenario_is_discounted_at_its_own_wacc() -> None:
    flows = np.full((2, 60), 10.0)
    values = scenario_enterprise_values(
        flows, np.zeros(2, dtype=np.int64), annual_wacc=np.array([0.1, 0.4]), terminal=None
    )
    for index, rate in enumerate((0.1, 0.4)):
        expected = np.sum(10.0 / accumulated_discount_factors(rate, 60))
        assert values[index] == pytest.approx(expected, rel=1e-12)
    assert values[0] > values[1]


def test_no_terminal_value_discounts_explicit_flows_only() -> None:
    flows, failures = _paths()
    factors = accumulated_discount_factors(0.3, 60)
    np.testing.assert_array_equal(
        scenario_enterprise_values(flows, failures, annual_wacc=0.3, terminal=None),
        np.sum(flows / factors[None, :], axis=1, dtype=np.float64),
    )


def test_exit_multiple_values_the_year_five_metric_and_excludes_failed_or_negative() -> None:
    flows = np.zeros((3, 60))
    failures = np.array([0, 12, 0])
    metric = np.array([1_000.0, 1_000.0, -500.0])
    values = scenario_enterprise_values(
        flows,
        failures,
        annual_wacc=0.25,
        terminal=ExitMultipleTerminal(multiple=np.array([4.0, 4.0, 4.0]), metric_year5=metric),
    )
    discount = accumulated_discount_factors(0.25, 60)[-1]
    assert values[0] == pytest.approx(4_000.0 / discount, rel=1e-12)
    assert values[1] == 0.0
    assert values[2] == 0.0


def test_growth_not_below_wacc_in_any_scenario_is_rejected() -> None:
    flows, failures = _paths()
    growth = np.full(400, 0.03)
    growth[7] = 0.25
    with pytest.raises(ValueError, match="terminal growth"):
        scenario_enterprise_values(
            flows, failures, annual_wacc=0.22, terminal=GordonTerminal(growth)
        )


def test_rejects_misaligned_parameters() -> None:
    flows, failures = _paths()
    with pytest.raises(ValueError):
        scenario_enterprise_values(
            flows, failures, annual_wacc=np.full(3, 0.2), terminal=None
        )
    with pytest.raises(ValueError):
        scenario_enterprise_values(
            flows,
            failures,
            annual_wacc=0.2,
            terminal=ExitMultipleTerminal(multiple=5.0, metric_year5=np.ones(3)),
        )
