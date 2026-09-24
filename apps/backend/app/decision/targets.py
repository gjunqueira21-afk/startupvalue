"""Target probability and hit-versus-miss conditional distribution analysis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite, sqrt

import numpy as np


@dataclass(frozen=True, slots=True)
class ConditionalStatistics:
    count: int
    p25: float | None
    p50: float | None
    p75: float | None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class TargetVariableComparison:
    name: str
    hit: ConditionalStatistics
    miss: ConditionalStatistics
    median_difference_hit_minus_miss: float | None
    status: str


@dataclass(frozen=True, slots=True)
class TargetAnalysis:
    target: float
    scenario_count: int
    hit_count: int
    miss_count: int
    probability: float
    wilson95_low: float
    wilson95_high: float
    comparisons: tuple[TargetVariableComparison, ...]


def wilson_interval(
    successes: int, total: int, z: float = 1.959963984540054
) -> tuple[float, float]:
    if total <= 0 or not 0 <= successes <= total:
        raise ValueError("Wilson interval requires 0 <= successes <= positive total")
    probability = successes / total
    denominator = 1.0 + z**2 / total
    center = (probability + z**2 / (2.0 * total)) / denominator
    half = (
        z
        * sqrt(probability * (1.0 - probability) / total + z**2 / (4.0 * total**2))
        / denominator
    )
    low = 0.0 if successes == 0 else max(0.0, center - half)
    high = 1.0 if successes == total else min(1.0, center + half)
    return low, high


def _conditional(values: np.ndarray) -> ConditionalStatistics:
    if values.size == 0:
        return ConditionalStatistics(0, None, None, None, "empty_subset")
    p25, p50, p75 = np.quantile(values, (0.25, 0.50, 0.75), method="linear")
    return ConditionalStatistics(int(values.size), float(p25), float(p50), float(p75))


def analyze_target(
    valuations: Sequence[float] | np.ndarray,
    target: float,
    realized_inputs: Mapping[str, Sequence[float] | np.ndarray] | None = None,
) -> TargetAnalysis:
    values = np.asarray(valuations, dtype=np.float64)
    target_value = float(target)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("valuations must be a non-empty finite one-dimensional array")
    if not isfinite(target_value):
        raise ValueError("target must be finite")
    hit_mask = values >= target_value
    hits = int(np.sum(hit_mask))
    total = int(values.size)
    interval = wilson_interval(hits, total)
    comparisons: list[TargetVariableComparison] = []
    for name, samples in (realized_inputs or {}).items():
        factor = np.asarray(samples, dtype=np.float64)
        if factor.shape != values.shape or not np.all(np.isfinite(factor)):
            raise ValueError(f"{name} must provide one finite value per valuation")
        hit_stats = _conditional(factor[hit_mask])
        miss_stats = _conditional(factor[~hit_mask])
        if np.all(factor == factor[0]):
            delta = None
            status = "not_estimable_constant"
        elif hit_stats.p50 is None or miss_stats.p50 is None:
            delta = None
            status = "not_estimable_empty_subset"
        else:
            delta = hit_stats.p50 - miss_stats.p50
            status = "estimated_association"
        comparisons.append(TargetVariableComparison(name, hit_stats, miss_stats, delta, status))
    return TargetAnalysis(
        target_value,
        total,
        hits,
        total - hits,
        hits / total,
        interval[0],
        interval[1],
        tuple(comparisons),
    )
