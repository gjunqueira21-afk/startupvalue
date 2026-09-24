"""Documented distribution parameterizations and inverse-CDF sampling."""

from __future__ import annotations

from dataclasses import dataclass
from math import inf, isfinite, log, sqrt
from typing import TypeAlias

import numpy as np
from scipy.special import ndtr, ndtri  # type: ignore[import-untyped]
from scipy.stats import t as student_t  # type: ignore[import-untyped]


@dataclass(frozen=True, slots=True)
class Constant:
    value: float


@dataclass(frozen=True, slots=True)
class Normal:
    loc: float
    scale: float
    lower: float = -inf
    upper: float = inf


@dataclass(frozen=True, slots=True)
class StudentT:
    loc: float
    scale: float
    df: float
    lower: float = -inf
    upper: float = inf

    @classmethod
    def from_standard_deviation(
        cls,
        *,
        loc: float,
        standard_deviation: float,
        df: float,
        lower: float = -inf,
        upper: float = inf,
    ) -> StudentT:
        if df <= 2.0:
            raise ValueError("Student-t df must exceed 2 for finite variance")
        scale = float(standard_deviation) * sqrt((df - 2.0) / df)
        return cls(loc, scale, df, lower, upper)


@dataclass(frozen=True, slots=True)
class Triangular:
    minimum: float
    mode: float
    maximum: float


@dataclass(frozen=True, slots=True)
class Uniform:
    minimum: float
    maximum: float


@dataclass(frozen=True, slots=True)
class LogNormal:
    arithmetic_mean: float
    coefficient_of_variation: float


DistributionSpec: TypeAlias = Constant | Normal | StudentT | Triangular | Uniform | LogNormal


def _validate(spec: DistributionSpec) -> None:
    values = tuple(float(getattr(spec, field)) for field in spec.__dataclass_fields__)
    if any(np.isnan(value) for value in values):
        raise ValueError("distribution parameters cannot be NaN")
    if isinstance(spec, Constant):
        if not isfinite(spec.value):
            raise ValueError("constant value must be finite")
    elif isinstance(spec, Normal | StudentT):
        if not isfinite(spec.loc) or not isfinite(spec.scale) or spec.scale <= 0.0:
            raise ValueError("location must be finite and scale must be positive")
        if spec.lower >= spec.upper:
            raise ValueError("lower support must be less than upper support")
        if isinstance(spec, StudentT) and (not isfinite(spec.df) or spec.df <= 2.0):
            raise ValueError("Student-t df must exceed 2 for finite variance")
    elif isinstance(spec, Triangular):
        if not all(isfinite(value) for value in values):
            raise ValueError("triangular parameters must be finite")
        if spec.minimum == spec.maximum:
            if spec.mode != spec.minimum:
                raise ValueError("a degenerate triangular distribution must have one value")
        elif not spec.minimum <= spec.mode <= spec.maximum:
            raise ValueError("triangular parameters require minimum <= mode <= maximum")
    elif isinstance(spec, Uniform):
        if not all(isfinite(value) for value in values) or spec.minimum >= spec.maximum:
            raise ValueError("uniform parameters require finite minimum < maximum")
    elif isinstance(spec, LogNormal):
        if not all(isfinite(value) for value in values):
            raise ValueError("lognormal parameters must be finite")
        if spec.arithmetic_mean < 0.0 or spec.coefficient_of_variation < 0.0:
            raise ValueError("lognormal mean and CoV must be non-negative")
        if spec.arithmetic_mean == 0.0 and spec.coefficient_of_variation != 0.0:
            raise ValueError("structural zero lognormal must have CoV zero")


def inverse_cdf(spec: DistributionSpec, uniforms: np.ndarray) -> np.ndarray:
    """Transform open-interval uniforms using the specification's canonical inverse CDF."""

    _validate(spec)
    u = np.asarray(uniforms, dtype=np.float64)
    if not np.all(np.isfinite(u)) or np.any((u < 0.0) | (u > 1.0)):
        raise ValueError("uniform draws must be finite and in [0, 1]")
    eps = np.nextafter(0.0, 1.0)
    safe_u = np.clip(u, eps, np.nextafter(1.0, 0.0))
    if isinstance(spec, Constant):
        return np.full(u.shape, spec.value, dtype=np.float64)
    if isinstance(spec, Normal):
        lower_cdf = 0.0 if spec.lower == -inf else float(ndtr((spec.lower - spec.loc) / spec.scale))
        upper_cdf = 1.0 if spec.upper == inf else float(ndtr((spec.upper - spec.loc) / spec.scale))
        q = lower_cdf + safe_u * (upper_cdf - lower_cdf)
        return np.asarray(spec.loc + spec.scale * ndtri(q), dtype=np.float64)
    if isinstance(spec, StudentT):
        lower_cdf = 0.0 if spec.lower == -inf else float(
            student_t.cdf((spec.lower - spec.loc) / spec.scale, spec.df)
        )
        upper_cdf = 1.0 if spec.upper == inf else float(
            student_t.cdf((spec.upper - spec.loc) / spec.scale, spec.df)
        )
        q = lower_cdf + safe_u * (upper_cdf - lower_cdf)
        return np.asarray(spec.loc + spec.scale * student_t.ppf(q, spec.df), dtype=np.float64)
    if isinstance(spec, Triangular):
        if spec.minimum == spec.maximum:
            return np.full(u.shape, spec.minimum, dtype=np.float64)
        width = spec.maximum - spec.minimum
        split = (spec.mode - spec.minimum) / width
        left = spec.minimum + np.sqrt(safe_u * width * (spec.mode - spec.minimum))
        right = spec.maximum - np.sqrt((1.0 - safe_u) * width * (spec.maximum - spec.mode))
        return np.where(safe_u < split, left, right)
    if isinstance(spec, Uniform):
        return spec.minimum + safe_u * (spec.maximum - spec.minimum)
    if spec.arithmetic_mean == 0.0 or spec.coefficient_of_variation == 0.0:
        return np.full(u.shape, spec.arithmetic_mean, dtype=np.float64)
    sigma = sqrt(log(1.0 + spec.coefficient_of_variation**2))
    mu = log(spec.arithmetic_mean) - 0.5 * sigma**2
    return np.asarray(np.exp(mu + sigma * ndtri(safe_u)), dtype=np.float64)


def sample_distribution(
    spec: DistributionSpec, rng: np.random.Generator, size: int | tuple[int, ...]
) -> np.ndarray:
    return inverse_cdf(spec, rng.random(size, dtype=np.float64))
