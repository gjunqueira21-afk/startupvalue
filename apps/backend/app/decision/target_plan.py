"""Reverse engineering of a valuation target from already-simulated scenarios.

Answers "what has to happen for the company to be worth X at the horizon":
the median revenue CAGR and year-5 EBITDA margin among scenarios that reach
the target, contrasted with scenarios that miss it, plus a reference
revenue trajectory built from that CAGR.  Associations, not causes; derived
reads, no re-simulation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

import numpy as np

MIN_HIT_SAMPLE = 50

CAGR_FACTOR = "revenue_cagr_operating"
MARGIN_FACTOR = "ebitda_margin_year5_operating"


@dataclass(frozen=True, slots=True)
class YearTarget:
    year: int
    revenue: float


@dataclass(frozen=True, slots=True)
class TargetPlan:
    status: str  # "available" | "insufficient_hits" | "not_available_for_inputs"
    hit_count: int
    required_revenue_cagr: float | None
    hit_ebitda_margin: float | None
    miss_revenue_cagr: float | None
    miss_ebitda_margin: float | None
    trajectory: tuple[YearTarget, ...]


def _median(values: np.ndarray) -> float | None:
    return float(np.median(values)) if values.size else None


def base_year_revenue_from_inputs(canonical_inputs: dict[str, Any] | None) -> float | None:
    """Sum of the first 12 months of ``monthly_revenue``, or None when unavailable."""
    monthly_revenue = (canonical_inputs or {}).get("monthly_revenue")
    if not isinstance(monthly_revenue, list) or not monthly_revenue:
        return None
    return float(sum(monthly_revenue[:12]))


def build_target_plan(
    valuations: np.ndarray,
    target: float,
    factors: Mapping[str, np.ndarray],
    base_year_revenue: float | None,
    horizon_years: int = 5,
) -> TargetPlan:
    values = np.asarray(valuations, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("valuations must be a non-empty finite one-dimensional array")
    if not isfinite(float(target)):
        raise ValueError("target must be finite")
    hit_mask = values >= float(target)
    hit_count = int(np.sum(hit_mask))
    if CAGR_FACTOR not in factors:
        return TargetPlan("not_available_for_inputs", hit_count, None, None, None, None, ())
    if hit_count < MIN_HIT_SAMPLE:
        return TargetPlan("insufficient_hits", hit_count, None, None, None, None, ())
    cagr = np.asarray(factors[CAGR_FACTOR], dtype=np.float64)
    if cagr.shape != values.shape or not np.all(np.isfinite(cagr)):
        raise ValueError(f"{CAGR_FACTOR} must provide one finite value per valuation")
    required_cagr = _median(cagr[hit_mask])
    miss_cagr = _median(cagr[~hit_mask])
    hit_margin = miss_margin = None
    if MARGIN_FACTOR in factors:
        margin = np.asarray(factors[MARGIN_FACTOR], dtype=np.float64)
        if margin.shape != values.shape or not np.all(np.isfinite(margin)):
            raise ValueError(
                f"{MARGIN_FACTOR} must provide one finite value per valuation"
            )
        hit_margin = _median(margin[hit_mask])
        miss_margin = _median(margin[~hit_mask])
    trajectory: tuple[YearTarget, ...] = ()
    if (
        base_year_revenue is not None
        and isfinite(base_year_revenue)
        and base_year_revenue > 0.0
        and required_cagr is not None
    ):
        trajectory = tuple(
            YearTarget(year, base_year_revenue * (1.0 + required_cagr) ** (year - 1))
            for year in range(1, horizon_years + 1)
        )
    return TargetPlan(
        "available", hit_count, required_cagr, hit_margin, miss_cagr, miss_margin, trajectory
    )
