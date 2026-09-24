"""Vectorized DCF over simulated scenarios with per-scenario valuation parameters.

WACC, terminal growth and exit multiple may be scalars (fixed assumption) or one
value per scenario (sampled assumption). The scalar path is the reference DCF of
``app.valuation.dcf`` operation for operation, so fixed-parameter results are
bitwise stable across model versions.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .dcf import TerminalAssumptions, accumulated_discount_factors, terminal_value

Parameter = float | np.ndarray


@dataclass(frozen=True, slots=True)
class GordonTerminal:
    """Perpetuity on the normalized FCFF (mean of the last 12 realized months)."""

    growth: Parameter


@dataclass(frozen=True, slots=True)
class ExitMultipleTerminal:
    """Exit value = multiple x annual metric of months 49-60 (revenue or EBITDA)."""

    multiple: Parameter
    metric_year5: np.ndarray


def _per_scenario(name: str, value: Parameter, count: int) -> np.ndarray:
    vector = np.asarray(value, dtype=np.float64)
    if vector.ndim == 0:
        vector = np.full(count, float(vector), dtype=np.float64)
    if vector.shape != (count,) or not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must be a finite scalar or one value per scenario")
    return vector


def _monthly(annual: np.ndarray) -> np.ndarray:
    return np.asarray(np.expm1(np.log1p(annual) / 12.0), dtype=np.float64)


def scenario_enterprise_values(
    realized_cash_flows: np.ndarray,
    failure_months: np.ndarray,
    *,
    annual_wacc: Parameter,
    terminal: GordonTerminal | ExitMultipleTerminal | None,
) -> np.ndarray:
    flows = np.asarray(realized_cash_flows, dtype=np.float64)
    failures = np.asarray(failure_months)
    if flows.ndim != 2 or failures.shape != (flows.shape[0],):
        raise ValueError("cash flows must be [scenario, month] with one failure month each")
    count, periods = flows.shape
    eligible = failures == 0

    scalar_path = np.ndim(annual_wacc) == 0 and (
        not isinstance(terminal, GordonTerminal) or np.ndim(terminal.growth) == 0
    )
    if scalar_path:
        factors = accumulated_discount_factors(float(annual_wacc), periods)
        values = np.asarray(
            np.sum(flows / factors[None, :], axis=1, dtype=np.float64), dtype=np.float64
        )
        last_factor: np.ndarray | float = float(factors[-1])
    else:
        wacc = _per_scenario("annual_wacc", annual_wacc, count)
        if np.any(wacc <= -1.0):
            raise ValueError("all WACC values must be greater than -1")
        growth_rate = 1.0 + _monthly(wacc)
        matrix = np.cumprod(
            np.broadcast_to(growth_rate[:, None], (count, periods)), axis=1, dtype=np.float64
        )
        values = np.asarray(np.sum(flows / matrix, axis=1, dtype=np.float64), dtype=np.float64)
        last_factor = matrix[:, -1]

    if isinstance(terminal, GordonTerminal):
        normalized = np.maximum(np.mean(flows[:, -12:], axis=1), 0.0)
        if scalar_path:
            unit = terminal_value(
                TerminalAssumptions(1.0, float(terminal.growth), float(annual_wacc))
            )
            values += eligible * normalized * unit / last_factor
        else:
            growth = _per_scenario("terminal growth", terminal.growth, count)
            wacc = _per_scenario("annual_wacc", annual_wacc, count)
            if np.any(growth >= wacc) or np.any(growth <= -1.0):
                raise ValueError("terminal growth must be lower than WACC in every scenario")
            monthly_growth = _monthly(growth)
            unit_vector = (1.0 + monthly_growth) / (_monthly(wacc) - monthly_growth)
            values += eligible * normalized * unit_vector / last_factor
    elif isinstance(terminal, ExitMultipleTerminal):
        multiple = _per_scenario("exit multiple", terminal.multiple, count)
        metric = _per_scenario("exit metric", terminal.metric_year5, count)
        if np.any(multiple < 0.0):
            raise ValueError("exit multiple must be non-negative")
        # A negative exit metric has no meaningful multiple; it contributes no exit value.
        values += eligible * multiple * np.maximum(metric, 0.0) / last_factor
    if not np.all(np.isfinite(values)):
        raise ValueError("scenario DCF produced a non-finite value")
    return values
