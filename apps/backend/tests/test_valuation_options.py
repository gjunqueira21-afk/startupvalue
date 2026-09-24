from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.api.schemas import CanonicalValuationInputs


def _structured(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "monthly_revenue": [100.0] * 60,
        "monthly_opex": [20.0] * 60,
        "monthly_capex": [10.0] * 60,
        "gross_margin": 0.5,
        "revenue_uncertainty": {"kind": "constant", "value": 1.0},
        "cost_uncertainty": {"kind": "constant", "value": 1.0},
        "annual_wacc": 0.25,
        "terminal_growth": 0.04,
    }
    return {**base, **overrides}


def _triangular(minimum: float, mode: float, maximum: float) -> dict[str, Any]:
    return {"kind": "triangular", "minimum": minimum, "mode": mode, "maximum": maximum}


def test_defaults_keep_the_fixed_gordon_model() -> None:
    parsed = CanonicalValuationInputs.model_validate(_structured())
    assert parsed.terminal_method == "gordon"
    assert parsed.wacc_uncertainty is None
    assert parsed.tornado.wacc_delta == pytest.approx(0.03)
    assert parsed.tornado.terminal_growth_delta == pytest.approx(0.01)
    assert parsed.tornado.exit_multiple_relative_delta == pytest.approx(0.25)
    assert parsed.tornado.failure_probability_delta == pytest.approx(0.10)


def test_accepts_wacc_and_growth_ranges_whose_supports_never_cross() -> None:
    parsed = CanonicalValuationInputs.model_validate(
        _structured(
            wacc_uncertainty=_triangular(0.20, 0.25, 0.32),
            terminal_growth_uncertainty=_triangular(0.02, 0.04, 0.06),
        )
    )
    assert parsed.wacc_uncertainty is not None


@pytest.mark.parametrize(
    "overrides",
    [
        # WACC range reaches below the fixed perpetuity growth.
        {"wacc_uncertainty": _triangular(0.03, 0.25, 0.32)},
        # Growth range reaches above the lowest possible WACC.
        {
            "wacc_uncertainty": _triangular(0.20, 0.25, 0.32),
            "terminal_growth_uncertainty": _triangular(0.02, 0.04, 0.21),
        },
        # Unbounded WACC support cannot guarantee WACC > g.
        {"wacc_uncertainty": {"kind": "normal", "mean": 0.25, "standard_deviation": 0.03}},
        # Unbounded growth support.
        {
            "terminal_growth_uncertainty": {
                "kind": "normal",
                "mean": 0.04,
                "standard_deviation": 0.01,
            }
        },
        # Base WACC outside its own range.
        {"wacc_uncertainty": _triangular(0.26, 0.28, 0.32)},
        # Growth range without a perpetuity.
        {"terminal_growth": None, "terminal_growth_uncertainty": _triangular(0.02, 0.04, 0.06)},
    ],
)
def test_rejects_rate_ranges_that_could_break_the_perpetuity(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        CanonicalValuationInputs.model_validate(_structured(**overrides))


def test_exit_multiple_method_requires_multiple_and_metric_and_no_perpetuity() -> None:
    valid = _structured(
        terminal_method="exit_multiple",
        terminal_growth=None,
        exit_multiple=6.0,
        exit_metric="revenue",
        exit_multiple_uncertainty=_triangular(4.0, 6.0, 9.0),
    )
    assert CanonicalValuationInputs.model_validate(valid).exit_metric == "revenue"
    for broken in (
        {**valid, "exit_multiple": None},
        {**valid, "exit_metric": None},
        {**valid, "terminal_growth": 0.04},
        {
            **valid,
            "exit_multiple_uncertainty": {"kind": "uniform", "minimum": -1.0, "maximum": 3.0},
        },
    ):
        with pytest.raises(ValidationError):
            CanonicalValuationInputs.model_validate(broken)


def test_exit_multiple_fields_are_rejected_under_the_gordon_method() -> None:
    with pytest.raises(ValidationError):
        CanonicalValuationInputs.model_validate(_structured(exit_multiple=6.0))


def test_exit_multiple_requires_the_structured_model() -> None:
    with pytest.raises(ValidationError):
        CanonicalValuationInputs.model_validate(
            {
                "monthly_fcff": [10.0] * 12,
                "uncertainty": {"kind": "constant", "value": 1.0},
                "annual_wacc": 0.2,
                "terminal_method": "exit_multiple",
                "exit_multiple": 5.0,
                "exit_metric": "revenue",
            }
        )
