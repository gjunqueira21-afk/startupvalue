"""Rank-association drivers; results describe association, never causality."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from scipy.stats import rankdata  # type: ignore[import-untyped]


@dataclass(frozen=True, slots=True)
class DriverResult:
    name: str
    rho: float | None
    direction: str | None
    count: int
    status: str
    population: str


def _finite_vector(name: str, values: Sequence[float] | np.ndarray, count: int) -> np.ndarray:
    vector = np.asarray(values, dtype=np.float64)
    if vector.shape != (count,):
        raise ValueError(f"{name} must contain one value per valuation")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} contains a non-finite value")
    return vector


def spearman_drivers(
    realized_inputs: Mapping[str, Sequence[float] | np.ndarray],
    valuations: Sequence[float] | np.ndarray,
    *,
    population: str = "unconditional",
) -> tuple[DriverResult, ...]:
    values = np.asarray(valuations, dtype=np.float64)
    if values.ndim != 1 or values.size < 2 or not np.all(np.isfinite(values)):
        raise ValueError("valuations must contain at least two finite samples")
    valuation_constant = np.all(values == values[0])
    valuation_ranks = rankdata(values, method="average")
    results: list[DriverResult] = []
    for name, samples in realized_inputs.items():
        factor = _finite_vector(name, samples, int(values.size))
        if valuation_constant or np.all(factor == factor[0]):
            results.append(
                DriverResult(
                    name,
                    None,
                    None,
                    int(values.size),
                    "not_estimable_constant",
                    population,
                )
            )
            continue
        rho = float(np.corrcoef(rankdata(factor, method="average"), valuation_ranks)[0, 1])
        direction = "positive" if rho > 0.0 else "negative" if rho < 0.0 else "neutral"
        results.append(
            DriverResult(name, rho, direction, int(values.size), "estimated", population)
        )
    return tuple(
        sorted(
            results,
            key=lambda result: (
                result.rho is None,
                -(abs(result.rho) if result.rho is not None else 0.0),
                result.name,
            ),
        )
    )
