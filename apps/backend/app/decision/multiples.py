"""Implied valuation multiples derived from simulated scenarios.

These are presentation-layer reads: valuation (DCF equity, present value)
divided by the realized year-5 annual metric of the same scenario.  They are
implied by the user's own assumptions and are NOT market multiples.  No engine
formula is involved.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

MIN_ELIGIBLE_SCENARIOS = 30


@dataclass(frozen=True, slots=True)
class MultipleSummary:
    p25: float
    p50: float
    p75: float
    eligible_count: int
    excluded_count: int


@dataclass(frozen=True, slots=True)
class ImpliedMultiples:
    status: str  # "available" | "not_available"
    reason: str | None
    value_to_revenue: MultipleSummary | None
    value_to_ebitda: MultipleSummary | None


def _summary(valuations: np.ndarray, metric: np.ndarray) -> MultipleSummary | None:
    if metric.shape != valuations.shape:
        raise ValueError("metric vector must align with valuations")
    if not np.all(np.isfinite(metric)):
        raise ValueError("metric vector must be finite")
    eligible = (metric > 0.0) & (valuations > 0.0)
    count = int(np.sum(eligible))
    if count < MIN_ELIGIBLE_SCENARIOS:
        return None
    multiples = valuations[eligible] / metric[eligible]
    p25, p50, p75 = np.quantile(multiples, (0.25, 0.50, 0.75), method="linear")
    return MultipleSummary(
        float(p25), float(p50), float(p75), count, int(valuations.size - count)
    )


def compute_implied_multiples(
    valuations: np.ndarray,
    revenue_exit_year: np.ndarray | None,
    ebitda_exit_year: np.ndarray | None,
) -> ImpliedMultiples:
    values = np.asarray(valuations, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("valuations must be a non-empty finite one-dimensional array")
    if revenue_exit_year is None and ebitda_exit_year is None:
        return ImpliedMultiples(
            "not_available", "metrics_unavailable_for_input_mode", None, None
        )
    revenue = (
        _summary(values, np.asarray(revenue_exit_year, dtype=np.float64))
        if revenue_exit_year is not None
        else None
    )
    ebitda = (
        _summary(values, np.asarray(ebitda_exit_year, dtype=np.float64))
        if ebitda_exit_year is not None
        else None
    )
    if revenue is None and ebitda is None:
        return ImpliedMultiples(
            "not_available", "insufficient_eligible_scenarios", None, None
        )
    return ImpliedMultiples("available", None, revenue, ebitda)


def _summary_payload(summary: MultipleSummary | None) -> dict[str, object] | None:
    if summary is None:
        return None
    return {
        "p25": summary.p25,
        "p50": summary.p50,
        "p75": summary.p75,
        "eligible_count": summary.eligible_count,
        "excluded_count": summary.excluded_count,
    }


def implied_multiples_payload(result: ImpliedMultiples) -> dict[str, object]:
    return {
        "status": result.status,
        "reason": result.reason,
        "basis": "equity_dcf_over_year5_metric",
        "value_to_revenue": _summary_payload(result.value_to_revenue),
        "value_to_ebitda": _summary_payload(result.value_to_ebitda),
    }
