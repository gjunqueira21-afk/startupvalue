"""Deterministic VC Method analysis of the wizard's saved startup profile.

The wizard supplies five annual revenue figures (or five average monthly
figures), but no forecast exit balance sheet. Current cash and debt are
reported for transparency and never silently projected to the exit date.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

from app.valuation.venture_capital import value_vc_exit


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if isfinite(number) else None


def _section(profile: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = profile.get(name)
    return value if isinstance(value, Mapping) else {}


def _unavailable(code: str, reason: str) -> dict[str, Any]:
    return {"status": "unavailable", "reason_code": code, "reason": reason}


def analyze_vc_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Value an explicit year-five revenue exit from a persisted wizard profile.

    Output is JSON serializable and independent of DCF/Monte Carlo values.
    ``status`` is ``available``, ``unavailable`` or ``infeasible``. An
    infeasible round still reports the economically meaningful exit values.
    Percentages in the profile are divided by 100; output rates are decimal.
    """
    revenue = _section(profile, "revenue")
    assumptions = _section(profile, "valuation_assumptions")
    metrics = _section(profile, "metrics")
    years = revenue.get("years")
    cadence = revenue.get("cadence")
    if (
        cadence not in ("annual", "monthly")
        or not isinstance(years, list | tuple)
        or len(years) != 5
    ):
        return _unavailable(
            "revenue_projection_missing", "Five years of revenue and its cadence are required."
        )
    yearly = [_number(value) for value in years]
    if any(value is None or value < 0 for value in yearly):
        return _unavailable(
            "revenue_projection_invalid", "Revenue years must be finite and non-negative."
        )
    multiple = _number(assumptions.get("exitMultiple"))
    target_return_percent = _number(assumptions.get("vcTargetReturn"))
    horizon = _number(assumptions.get("investmentHorizonYears"))
    if (
        multiple is None
        or multiple <= 0
        or target_return_percent is None
        or target_return_percent < 0
    ):
        return _unavailable(
            "vc_assumptions_invalid",
            "A positive exit multiple and non-negative annual target return are required.",
        )
    if horizon != 5:
        return _unavailable(
            "exit_year_unsupported", "The saved revenue projection supports only a year-five exit."
        )
    investment = _number(assumptions.get("investmentAmount"))
    ownership_percent = _number(assumptions.get("targetOwnership"))
    if (
        investment is None
        or investment < 0
        or ownership_percent is None
        or not 0 <= ownership_percent < 100
    ):
        return _unavailable(
            "round_assumptions_invalid",
            "Investment and target ownership must be finite and within their allowed ranges.",
        )
    year_five = yearly[4]
    assert year_five is not None
    annual_exit_revenue = year_five * (12 if cadence == "monthly" else 1)
    if not isfinite(annual_exit_revenue) or not isfinite(annual_exit_revenue * multiple):
        return _unavailable(
            "vc_calculation_invalid", "Exit revenue or value exceeds numeric limits."
        )
    if annual_exit_revenue <= 0:
        return _unavailable(
            "exit_revenue_non_positive",
            "Year-five exit revenue must be positive for a revenue multiple.",
        )

    # No exit balance-sheet projection is present in wizard_schema_version 1.
    # Zero is a declared convention, not a use of today's cash/debt balances.
    current_cash = _number(metrics.get("cash"))
    current_debt = _number(metrics.get("debt"))
    reason_code: str | None
    reason: str | None
    try:
        valuation = value_vc_exit(
            [annual_exit_revenue / 12] * 12,
            exit_multiple=multiple,
            target_return_annual=target_return_percent / 100,
            horizon_years=5,
            excess_cash_exit=0,
            debt_exit=0,
            investment=investment if investment > 0 else None,
        )
    except (ValueError, OverflowError, ZeroDivisionError) as exc:
        if "round is infeasible" not in str(exc):
            return _unavailable("vc_calculation_invalid", str(exc))
        valuation = value_vc_exit(
            [annual_exit_revenue / 12] * 12,
            exit_multiple=multiple,
            target_return_annual=target_return_percent / 100,
            horizon_years=5,
        )
        status = "infeasible"
        reason_code = "investment_exceeds_vc_post_money"
        reason = (
            "Investment exceeds the present value of exit equity; "
            "no non-negative pre-money meets the target return."
        )
    else:
        status = "available"
        reason_code = None
        reason = None

    if (
        not isfinite(valuation.present_exit_equity)
        or valuation.present_exit_equity <= 0
    ):
        return _unavailable(
            "vc_calculation_invalid", "Present exit equity is not finite and positive."
        )

    round_result = valuation.round
    required_ownership = round_result.ownership_today if round_result else (
        investment / valuation.present_exit_equity if investment > 0 else None
    )
    target_ownership = ownership_percent / 100
    return {
        "status": status,
        "reason_code": reason_code,
        "reason": reason,
        "method": "venture_capital",
        "exit_metric": "revenue_last_12_months",
        "exit_multiple_basis": "enterprise_value_to_annual_revenue",
        "exit_year": 5,
        "revenue_cadence": cadence,
        "annual_exit_revenue": valuation.annual_exit_metric,
        "exit_multiple": multiple,
        "target_return_annual": target_return_percent / 100,
        "exit_enterprise_value": valuation.exit_enterprise_value,
        "exit_equity_value": valuation.exit_equity_value,
        "present_exit_equity": valuation.present_exit_equity,
        "exit_balance_sheet_policy": "zero_exit_cash_and_debt_unless_forecast_available",
        "current_cash_not_applied_to_exit": current_cash,
        "current_debt_not_applied_to_exit": current_debt,
        "investment": investment,
        "post_money": round_result.post_money if round_result else (
            valuation.present_exit_equity if investment > 0 else None
        ),
        "pre_money": round_result.pre_money if round_result else (
            valuation.present_exit_equity - investment if investment > 0 else None
        ),
        "required_ownership_today": required_ownership,
        "required_ownership_at_exit": required_ownership,
        "future_ownership_retention": 1.0,
        "target_ownership": target_ownership,
        "target_ownership_meets_return": (
            target_ownership >= required_ownership if required_ownership is not None else None
        ),
    }
