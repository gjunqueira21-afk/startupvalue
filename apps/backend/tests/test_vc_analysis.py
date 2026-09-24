from __future__ import annotations

import pytest

from app.services.vc_analysis import analyze_vc_profile


def profile(
    *, cadence: str = "annual", year_five: float = 1_200_000, investment: float = 1_000_000
) -> dict[str, object]:
    return {
        "revenue": {"cadence": cadence, "years": [0, 100_000, 300_000, 700_000, year_five]},
        "valuation_assumptions": {
            "vcTargetReturn": 30,
            "exitMultiple": 8,
            "investmentHorizonYears": 5,
            "investmentAmount": investment,
            "targetOwnership": 20,
        },
        "metrics": {"cash": 400_000, "debt": 100_000},
    }


def test_vc_profile_golden_year_five_revenue_multiple() -> None:
    result = analyze_vc_profile(profile())
    assert result["status"] == "available"
    assert result["exit_metric"] == "revenue_last_12_months"
    assert result["exit_multiple_basis"] == "enterprise_value_to_annual_revenue"
    assert result["annual_exit_revenue"] == 1_200_000
    assert result["exit_enterprise_value"] == 9_600_000
    assert result["exit_equity_value"] == 9_600_000
    assert result["present_exit_equity"] == pytest.approx(2_585_559.1136918818)
    assert result["post_money"] == pytest.approx(2_585_559.1136918818)
    assert result["pre_money"] == pytest.approx(1_585_559.1136918818)
    assert result["required_ownership_today"] == pytest.approx(0.386763541667)
    assert result["target_ownership_meets_return"] is False
    assert result["current_cash_not_applied_to_exit"] == 400_000
    assert result["current_debt_not_applied_to_exit"] == 100_000


def test_monthly_cadence_annualizes_year_five_average() -> None:
    result = analyze_vc_profile(profile(cadence="monthly", year_five=100_000))
    assert result["annual_exit_revenue"] == 1_200_000
    assert result["exit_enterprise_value"] == 9_600_000


def test_round_infeasible_keeps_exit_math_visible() -> None:
    result = analyze_vc_profile(profile(investment=3_000_000))
    assert result["status"] == "infeasible"
    assert result["reason_code"] == "investment_exceeds_vc_post_money"
    assert result["post_money"] == pytest.approx(2_585_559.1136918818)
    assert result["pre_money"] < 0
    assert result["required_ownership_today"] > 1


def test_zero_investment_does_not_invent_round_ownership() -> None:
    result = analyze_vc_profile(profile(investment=0))
    assert result["status"] == "available"
    assert result["post_money"] is None
    assert result["pre_money"] is None
    assert result["required_ownership_today"] is None


@pytest.mark.parametrize(
    ("change", "reason_code"),
    [
        ({"revenue": {"cadence": "annual", "years": [1, 2]}}, "revenue_projection_missing"),
        ({"revenue": {"cadence": "annual", "years": [0, 1, 2, 3, 0]}}, "exit_revenue_non_positive"),
        (
            {
                "valuation_assumptions": {
                    "investmentHorizonYears": 7,
                    "exitMultiple": 8,
                    "vcTargetReturn": 30,
                    "investmentAmount": 1,
                    "targetOwnership": 20,
                }
            },
            "exit_year_unsupported",
        ),
    ],
)
def test_unavailable_inputs_are_explicit(change: dict[str, object], reason_code: str) -> None:
    candidate = profile()
    candidate.update(change)
    result = analyze_vc_profile(candidate)
    assert result["status"] == "unavailable"
    assert result["reason_code"] == reason_code
