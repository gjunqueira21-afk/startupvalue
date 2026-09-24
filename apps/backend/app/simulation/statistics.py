"""Descriptive statistics over the complete, unfiltered scenario population."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class DistributionSummary:
    count: int
    minimum: float
    maximum: float
    mean: float
    median: float
    p5: float
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    p95: float
    variance_population: float
    standard_deviation_population: float
    non_positive_probability: float
    zero_probability: float


@dataclass(frozen=True, slots=True)
class Histogram:
    kind: str
    counts: tuple[int, ...]
    edges: tuple[float, ...]
    atom_value: float | None = None


def _values(samples: Sequence[float] | np.ndarray) -> np.ndarray:
    values = np.asarray(samples, dtype=np.float64)
    if values.ndim != 1 or values.size == 0:
        raise ValueError("samples must be a non-empty one-dimensional array")
    if not np.all(np.isfinite(values)):
        raise ValueError("all samples must be finite")
    return values


def summarize(samples: Sequence[float] | np.ndarray) -> DistributionSummary:
    values = _values(samples)
    p5, p10, p25, p50, p75, p90, p95 = np.quantile(
        values, (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95), method="linear"
    )
    return DistributionSummary(
        int(values.size),
        float(np.min(values)),
        float(np.max(values)),
        float(np.mean(values)),
        float(p50),
        float(p5),
        float(p10),
        float(p25),
        float(p50),
        float(p75),
        float(p90),
        float(p95),
        float(np.var(values, ddof=0)),
        float(np.std(values, ddof=0)),
        float(np.mean(values <= 0.0)),
        float(np.mean(values == 0.0)),
    )


def histogram(samples: Sequence[float] | np.ndarray, bins: int = 30) -> Histogram:
    values = _values(samples)
    if bins < 1:
        raise ValueError("bins must be positive")
    if np.all(values == values[0]):
        return Histogram("atom", (int(values.size),), (), float(values[0]))
    counts, edges = np.histogram(values, bins=bins)
    return Histogram(
        "continuous",
        tuple(int(value) for value in counts),
        tuple(float(value) for value in edges),
    )
