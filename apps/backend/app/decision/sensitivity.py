"""Driver ranking by standardized rank regression (see METHODOLOGY §10).

For each primitive stochastic driver we publish the Spearman rho and the
standardized rank regression coefficient (SRRC) from a joint least-squares fit
of valuation ranks on all driver ranks. ``contribution`` is SRRC² normalised
over estimable drivers: with independent drivers it approximates each driver's
share of the explained rank variance; ``r_squared`` states how much of that
variance the monotone-additive fit explains at all. Results describe
association inside the model, never causality.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.stats import rankdata  # type: ignore[import-untyped]

DRIVER_METHOD_VERSION = "drivers-v1"
LOW_FIT_R_SQUARED = 0.6
CORRELATED_DRIVERS_RHO = 0.5

Direction = Literal["positive", "negative", "neutral"]


@dataclass(frozen=True, slots=True)
class RankedDriver:
    name: str
    rho: float | None
    srrc: float | None
    contribution: float | None
    direction: Direction | None
    count: int
    status: str


@dataclass(frozen=True, slots=True)
class DriverRanking:
    method: str
    method_version: str
    scenario_count: int
    r_squared: float | None
    drivers: tuple[RankedDriver, ...]
    warnings: tuple[str, ...]


def _standardized_ranks(values: np.ndarray) -> np.ndarray:
    ranks = np.asarray(rankdata(values, method="average"), dtype=np.float64)
    centered = ranks - ranks.mean()
    return np.asarray(centered / np.sqrt(np.mean(centered**2)), dtype=np.float64)


def _direction(value: float) -> Direction:
    return "positive" if value > 0.0 else "negative" if value < 0.0 else "neutral"


def rank_drivers(
    drivers: Mapping[str, Sequence[float] | np.ndarray],
    valuations: Sequence[float] | np.ndarray,
) -> DriverRanking:
    values = np.asarray(valuations, dtype=np.float64)
    if values.ndim != 1 or values.size < 2 or not np.all(np.isfinite(values)):
        raise ValueError("valuations must contain at least two finite samples")
    count = int(values.size)
    vectors: dict[str, np.ndarray] = {}
    for name, samples in drivers.items():
        vector = np.asarray(samples, dtype=np.float64)
        if vector.shape != (count,):
            raise ValueError(f"{name} must contain one value per valuation")
        if not np.all(np.isfinite(vector)):
            raise ValueError(f"{name} contains a non-finite value")
        vectors[name] = vector

    def constant(name: str) -> RankedDriver:
        return RankedDriver(name, None, None, None, None, count, "not_estimable_constant")

    if np.all(values == values[0]):
        return DriverRanking(
            "spearman+srrc",
            DRIVER_METHOD_VERSION,
            count,
            None,
            tuple(constant(name) for name in sorted(vectors)),
            ("valuation_constant",),
        )

    estimable = [name for name, vector in vectors.items() if not np.all(vector == vector[0])]
    constants = sorted(name for name in vectors if name not in estimable)
    warnings: list[str] = []
    ranked: list[RankedDriver] = []
    r_squared: float | None = None
    if estimable:
        y = _standardized_ranks(values)
        design = np.column_stack([_standardized_ranks(vectors[name]) for name in estimable])
        rho = design.T @ y / count
        coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
        residual = y - design @ coefficients
        r_squared = float(max(0.0, 1.0 - np.mean(residual**2)))
        squared = coefficients**2
        total = float(np.sum(squared))
        for index, name in enumerate(estimable):
            srrc = float(coefficients[index])
            ranked.append(
                RankedDriver(
                    name,
                    float(rho[index]),
                    srrc,
                    float(squared[index] / total) if total > 0.0 else 0.0,
                    _direction(srrc),
                    count,
                    "estimated",
                )
            )
        if len(estimable) > 1:
            inter = np.abs(np.corrcoef(design, rowvar=False))
            np.fill_diagonal(inter, 0.0)
            if float(np.max(inter)) > CORRELATED_DRIVERS_RHO:
                warnings.append("correlated_drivers")
        if r_squared < LOW_FIT_R_SQUARED:
            warnings.append("low_rank_linear_fit")
    ranked.sort(key=lambda item: (-(item.contribution or 0.0), -abs(item.rho or 0.0), item.name))
    return DriverRanking(
        "spearman+srrc",
        DRIVER_METHOD_VERSION,
        count,
        r_squared,
        tuple(ranked) + tuple(constant(name) for name in constants),
        tuple(warnings),
    )
