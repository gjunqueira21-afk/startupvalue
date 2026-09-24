from __future__ import annotations

import math

import pytest

from app.valuation.bridges import bridge_enterprise_to_equity
from app.valuation.dcf import TerminalAssumptions, discounted_cash_flow
from app.valuation.dilution import round_for_target_ownership
from app.valuation.fcff import calculate_fcff
from app.valuation.venture_capital import value_vc_exit


def test_fcff_golden_reconciliation() -> None:
    result = calculate_fcff(
        revenue=200.0,
        cogs=50.0,
        operating_expenses=50.0,
        depreciation_amortization=10.0,
        cash_operating_taxes=18.0,
        capex=20.0,
        delta_nwc=5.0,
    )
    assert result.ebitda == 100.0
    assert result.ebit == 90.0
    assert result.fcff == 57.0


def test_dcf_accumulates_each_years_rate() -> None:
    result = discounted_cash_flow([0.0] * 23 + [100.0], [0.20, 0.10])
    assert result.enterprise_value == pytest.approx(100.0 / (1.2 * 1.1), abs=1e-10)


def test_dcf_terminal_golden_case() -> None:
    result = discounted_cash_flow(
        [100.0] * 60,
        0.12,
        terminal=TerminalAssumptions(100.0, 0.03, 0.12),
    )
    assert result.enterprise_value == pytest.approx(12658.806629718902, abs=1e-6)


@pytest.mark.parametrize("growth", [0.12, 0.13])
def test_dcf_rejects_non_convergent_terminal(growth: float) -> None:
    with pytest.raises(ValueError, match="lower"):
        discounted_cash_flow(
            [100.0] * 60,
            0.12,
            terminal=TerminalAssumptions(100.0, growth, 0.12),
        )


def test_dcf_monotonic_properties_for_non_negative_flows() -> None:
    base = discounted_cash_flow([100.0] * 60, 0.12).enterprise_value
    higher_flow = discounted_cash_flow([101.0] * 60, 0.12).enterprise_value
    higher_wacc = discounted_cash_flow([100.0] * 60, 0.20).enterprise_value
    assert higher_flow > base
    assert higher_wacc < base


def test_enterprise_to_equity_preserves_signed_and_limited_views() -> None:
    result = bridge_enterprise_to_equity(10_000_000, excess_cash=2_000_000, debt=3_000_000)
    assert result.equity_signed == 9_000_000
    assert result.equity_limited_liability == 9_000_000
    negative = bridge_enterprise_to_equity(1, debt=2)
    assert negative.equity_signed == -1
    assert negative.equity_limited_liability == 0


def test_vc_method_uses_annual_exit_metric_and_gross_discount_factor() -> None:
    result = value_vc_exit(
        [100_000.0] * 12,
        exit_multiple=8.0,
        target_return_annual=0.30,
        horizon_years=5.0,
        investment=1_000_000.0,
    )
    assert result.exit_enterprise_value == 9_600_000.0
    assert result.present_exit_equity == pytest.approx(2_585_559.1136918818)
    assert result.round is not None
    assert result.round.ownership_at_exit == pytest.approx(0.386763541667)
    assert result.round.pre_money == pytest.approx(1_585_559.1136918818)


def test_vc_zero_target_return_is_finite() -> None:
    result = value_vc_exit(
        [100_000.0] * 12,
        exit_multiple=8,
        target_return_annual=0,
        horizon_years=5,
    )
    assert result.present_exit_equity == 9_600_000


def test_primary_round_target_ownership_golden_case() -> None:
    result = round_for_target_ownership(5_000_000, 0.15)
    assert result.investment == pytest.approx(882_352.94117647)
    assert result.post_money == pytest.approx(5_882_352.94117647)
    assert math.isclose(result.investor_ownership, 0.15)
