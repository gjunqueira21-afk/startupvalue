"""Canonical PCG64 random stream and persistent Gaussian-copula factors."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import sqrt

import numpy as np
from scipy.special import ndtr  # type: ignore[import-untyped]

from .distributions import DistributionSpec, inverse_cdf


def pcg64(seed: int) -> np.random.Generator:
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    return np.random.Generator(np.random.PCG64(seed))


@dataclass(frozen=True, slots=True)
class PersistentProcess:
    rho: float = 0.0
    persistent_weight: float = 1.0
    correlation: tuple[tuple[float, ...], ...] | None = None


def _cholesky(correlation: tuple[tuple[float, ...], ...] | None, factors: int) -> np.ndarray:
    if correlation is None:
        return np.eye(factors, dtype=np.float64)
    matrix = np.asarray(correlation, dtype=np.float64)
    if matrix.shape != (factors, factors):
        raise ValueError("correlation matrix shape must match factor count")
    if not np.all(np.isfinite(matrix)) or not np.allclose(matrix, matrix.T, atol=1e-12):
        raise ValueError("correlation matrix must be finite and symmetric")
    if not np.allclose(np.diag(matrix), 1.0, atol=1e-12):
        raise ValueError("correlation matrix diagonal must equal one")
    try:
        return np.linalg.cholesky(matrix)
    except np.linalg.LinAlgError as exc:
        raise ValueError("correlation matrix must be positive definite") from exc


def latent_factor_paths(
    rng: np.random.Generator,
    *,
    scenarios: int,
    months: int,
    factors: int,
    process: PersistentProcess,
) -> np.ndarray:
    """Generate stationary latent normals in a frozen call order: A, E1, epsilon."""

    if scenarios < 1 or months < 1 or factors < 1:
        raise ValueError("scenarios, months, and factors must be positive")
    rho = float(process.rho)
    weight = float(process.persistent_weight)
    if not -1.0 < rho < 1.0:
        raise ValueError("rho must be strictly between -1 and 1")
    if not 0.0 <= weight <= 1.0:
        raise ValueError("persistent_weight must be in [0, 1]")
    chol = _cholesky(process.correlation, factors)
    persistent = rng.standard_normal((scenarios, factors)) @ chol.T
    residual = np.empty((scenarios, months, factors), dtype=np.float64)
    residual[:, 0, :] = rng.standard_normal((scenarios, factors)) @ chol.T
    innovations = rng.standard_normal((scenarios, max(months - 1, 0), factors))
    innovation_scale = sqrt(1.0 - rho**2)
    for month in range(1, months):
        epsilon = innovations[:, month - 1, :] @ chol.T
        residual[:, month, :] = rho * residual[:, month - 1, :] + innovation_scale * epsilon
    return np.asarray(
        sqrt(weight) * persistent[:, None, :] + sqrt(1.0 - weight) * residual,
        dtype=np.float64,
    )


def factor_paths(
    rng: np.random.Generator,
    specs: Sequence[DistributionSpec],
    *,
    scenarios: int,
    months: int,
    process: PersistentProcess,
) -> np.ndarray:
    specs_tuple = tuple(specs)
    latent = latent_factor_paths(
        rng,
        scenarios=scenarios,
        months=months,
        factors=len(specs_tuple),
        process=process,
    )
    uniforms = ndtr(latent)
    transformed = np.empty_like(latent)
    for factor, spec in enumerate(specs_tuple):
        transformed[:, :, factor] = inverse_cdf(spec, uniforms[:, :, factor])
    return transformed
