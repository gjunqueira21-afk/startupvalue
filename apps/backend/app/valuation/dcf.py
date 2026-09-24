"""Monthly DCF using accumulated effective discount rates."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite

import numpy as np


def annual_to_monthly_effective(rate: float) -> float:
    annual = float(rate)
    if not isfinite(annual) or annual <= -1.0:
        raise ValueError("annual effective rate must be finite and greater than -1")
    return float(np.expm1(np.log1p(annual) / 12.0))


def _monthly_rate_curve(annual_wacc: float | Sequence[float], periods: int) -> np.ndarray:
    if periods < 1:
        raise ValueError("DCF requires at least one period")
    if isinstance(annual_wacc, int | float | np.floating):
        annual = np.full(periods, float(annual_wacc), dtype=np.float64)
    else:
        yearly = np.asarray(tuple(annual_wacc), dtype=np.float64)
        if yearly.ndim != 1 or yearly.size == 0:
            raise ValueError("annual_wacc must be a scalar or a non-empty yearly curve")
        required_years = (periods + 11) // 12
        if yearly.size != required_years:
            raise ValueError(f"annual_wacc curve must contain {required_years} yearly rates")
        annual = np.repeat(yearly, 12)[:periods]
    if not np.all(np.isfinite(annual)) or np.any(annual <= -1.0):
        raise ValueError("all WACC values must be finite and greater than -1")
    return np.expm1(np.log1p(annual) / 12.0)


def accumulated_discount_factors(
    annual_wacc: float | Sequence[float], periods: int
) -> np.ndarray:
    """Return DF_t = product(k=1..t)(1 + monthly_rate_k)."""

    monthly = _monthly_rate_curve(annual_wacc, periods)
    factors = np.cumprod(1.0 + monthly, dtype=np.float64)
    if not np.all(np.isfinite(factors)) or np.any(factors <= 0.0):
        raise ValueError("discount factor curve is not finite and positive")
    return factors


@dataclass(frozen=True, slots=True)
class TerminalAssumptions:
    normalized_fcff_at_horizon: float
    annual_growth: float
    annual_wacc: float


@dataclass(frozen=True, slots=True)
class DCFResult:
    pv_explicit: float
    terminal_value_at_horizon: float
    pv_terminal: float
    enterprise_value: float
    discount_factors: tuple[float, ...]


def terminal_value(assumptions: TerminalAssumptions) -> float:
    fcff = float(assumptions.normalized_fcff_at_horizon)
    growth = float(assumptions.annual_growth)
    wacc = float(assumptions.annual_wacc)
    if not all(isfinite(value) for value in (fcff, growth, wacc)):
        raise ValueError("terminal assumptions must be finite")
    if fcff <= 0.0:
        raise ValueError("normalized terminal FCFF must be positive for stable growth")
    if growth <= -1.0 or wacc <= -1.0:
        raise ValueError("terminal growth and WACC must be greater than -1")
    if growth >= wacc:
        raise ValueError("terminal growth must be lower than terminal WACC")
    monthly_growth = annual_to_monthly_effective(growth)
    monthly_wacc = annual_to_monthly_effective(wacc)
    return fcff * (1.0 + monthly_growth) / (monthly_wacc - monthly_growth)


def discounted_cash_flow(
    fcff: Sequence[float],
    annual_wacc: float | Sequence[float],
    *,
    terminal: TerminalAssumptions | None = None,
) -> DCFResult:
    cash_flows = np.asarray(tuple(fcff), dtype=np.float64)
    if cash_flows.ndim != 1 or cash_flows.size == 0:
        raise ValueError("fcff must be a non-empty one-dimensional series")
    if not np.all(np.isfinite(cash_flows)):
        raise ValueError("fcff values must be finite")
    factors = accumulated_discount_factors(annual_wacc, int(cash_flows.size))
    pv_explicit = float(np.sum(cash_flows / factors, dtype=np.float64))
    tv = terminal_value(terminal) if terminal is not None else 0.0
    pv_terminal = tv / float(factors[-1])
    enterprise_value = pv_explicit + pv_terminal
    if not all(isfinite(value) for value in (pv_explicit, tv, pv_terminal, enterprise_value)):
        raise ValueError("DCF produced a non-finite result")
    return DCFResult(
        pv_explicit,
        tv,
        pv_terminal,
        enterprise_value,
        tuple(float(value) for value in factors),
    )
