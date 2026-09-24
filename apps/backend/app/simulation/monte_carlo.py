"""Simple-mode persistent-factor cash-flow simulation with absorbing failure."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite

import numpy as np

from .distributions import Constant, DistributionSpec, Normal
from .random_engine import PersistentProcess, factor_paths, pcg64


def sample_failure_months(
    rng: np.random.Generator, scenarios: int, horizon: int, p_failure_horizon: float
) -> np.ndarray:
    probability = float(p_failure_horizon)
    if scenarios < 1 or horizon < 1:
        raise ValueError("scenarios and horizon must be positive")
    if not isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError("failure probability must be in [0, 1]")
    if probability == 0.0:
        return np.zeros(scenarios, dtype=np.int64)
    if probability == 1.0:
        return np.ones(scenarios, dtype=np.int64)
    hazard = 1.0 - (1.0 - probability) ** (1.0 / horizon)
    sampled = rng.geometric(hazard, size=scenarios).astype(np.int64, copy=False)
    sampled[sampled > horizon] = 0
    return sampled


def apply_absorbing_failure(
    counterfactual_cash_flows: np.ndarray,
    failure_months: np.ndarray,
    liquidation_value: float | Sequence[float] = 0.0,
) -> np.ndarray:
    """Keep history, put recovery in the failure month, then zero future flows."""

    cash_flows = np.asarray(counterfactual_cash_flows, dtype=np.float64)
    failures = np.asarray(failure_months, dtype=np.int64)
    if cash_flows.ndim != 2 or failures.shape != (cash_flows.shape[0],):
        raise ValueError("cash flows must be [scenario, month] and failures one per scenario")
    if not np.all(np.isfinite(cash_flows)):
        raise ValueError("counterfactual cash flows must be finite")
    if np.any((failures < 0) | (failures > cash_flows.shape[1])):
        raise ValueError("failure month must be zero or within the horizon")
    recovery = np.asarray(liquidation_value, dtype=np.float64)
    if recovery.ndim == 0:
        recovery = np.full(cash_flows.shape[0], float(recovery), dtype=np.float64)
    if recovery.shape != (cash_flows.shape[0],) or not np.all(np.isfinite(recovery)):
        raise ValueError("liquidation value must be finite and scalar or one per scenario")
    realized = cash_flows.copy()
    for scenario, failure_month in enumerate(failures):
        if failure_month:
            index = int(failure_month) - 1
            realized[scenario, index:] = 0.0
            realized[scenario, index] = recovery[scenario]
    return realized


@dataclass(frozen=True, slots=True)
class SimpleCashFlowSimulationInput:
    base_cash_flows: tuple[float, ...]
    factor: DistributionSpec
    scenarios: int
    seed: int
    p_failure_horizon: float = 0.0
    liquidation_value: float = 0.0


@dataclass(frozen=True, slots=True)
class SimpleCashFlowSimulationResult:
    seed: int
    scenario_count: int
    factor_paths: np.ndarray
    counterfactual_cash_flows: np.ndarray
    realized_cash_flows: np.ndarray
    failure_months: np.ndarray
    states: tuple[str, ...]


def _readonly(array: np.ndarray) -> np.ndarray:
    array.setflags(write=False)
    return array


def simulate_simple_cash_flows(
    inputs: SimpleCashFlowSimulationInput,
) -> SimpleCashFlowSimulationResult:
    base = np.asarray(inputs.base_cash_flows, dtype=np.float64)
    if base.ndim != 1 or base.size == 0 or not np.all(np.isfinite(base)):
        raise ValueError("base cash flows must be a finite, non-empty monthly series")
    if inputs.scenarios < 1:
        raise ValueError("scenario count must be positive")
    rng = pcg64(inputs.seed)
    factors = factor_paths(
        rng,
        (inputs.factor,),
        scenarios=inputs.scenarios,
        months=int(base.size),
        process=PersistentProcess(rho=0.0, persistent_weight=1.0),
    )[:, :, 0]
    counterfactual = factors * base[None, :]
    failures = sample_failure_months(
        rng, inputs.scenarios, int(base.size), inputs.p_failure_horizon
    )
    realized = apply_absorbing_failure(counterfactual, failures, inputs.liquidation_value)
    states = tuple("failure" if month else "operating" for month in failures)
    return SimpleCashFlowSimulationResult(
        inputs.seed,
        inputs.scenarios,
        _readonly(factors),
        _readonly(counterfactual),
        _readonly(realized),
        _readonly(failures),
        states,
    )


@dataclass(frozen=True, slots=True)
class StructuredCashFlowSimulationInput:
    base_monthly_revenue: tuple[float, ...]
    base_monthly_opex: tuple[float, ...]
    base_monthly_capex: tuple[float, ...]
    gross_margin: float
    revenue_factor: DistributionSpec
    cost_factor: DistributionSpec
    margin_uncertainty_pp: float
    serial_correlation: float
    persistent_weight: float
    scenarios: int
    seed: int
    p_failure_horizon: float = 0.0
    liquidation_value: float = 0.0


@dataclass(frozen=True, slots=True)
class StructuredCashFlowSimulationResult:
    seed: int
    scenario_count: int
    factor_paths: np.ndarray
    counterfactual_cash_flows: np.ndarray
    realized_cash_flows: np.ndarray
    realized_revenue: np.ndarray
    realized_opex: np.ndarray
    counterfactual_revenue: np.ndarray
    counterfactual_opex: np.ndarray
    failure_months: np.ndarray
    states: tuple[str, ...]


def simulate_structured_cash_flows(
    inputs: StructuredCashFlowSimulationInput,
) -> StructuredCashFlowSimulationResult:
    """Revenue, opex and margin paths share a reproducible three-factor process."""
    revenue = np.asarray(inputs.base_monthly_revenue, dtype=np.float64)
    opex = np.asarray(inputs.base_monthly_opex, dtype=np.float64)
    capex = np.asarray(inputs.base_monthly_capex, dtype=np.float64)
    for name, values in (("revenue", revenue), ("opex", opex), ("capex", capex)):
        if values.shape != (60,) or not np.all(np.isfinite(values)) or np.any(values < 0):
            raise ValueError(f"{name} must contain 60 finite, non-negative monthly values")
    if not isfinite(inputs.gross_margin) or not 0 <= inputs.gross_margin <= 1:
        raise ValueError("gross margin must be in [0, 1]")
    if not isfinite(inputs.margin_uncertainty_pp) or not 0 <= inputs.margin_uncertainty_pp <= 1:
        raise ValueError("margin uncertainty in percentage points must be in [0, 1]")
    if inputs.scenarios < 1:
        raise ValueError("scenario count must be positive")
    margin_spec: DistributionSpec = (
        Constant(inputs.gross_margin)
        if inputs.margin_uncertainty_pp == 0.0
        else Normal(inputs.gross_margin, inputs.margin_uncertainty_pp, 0.0, 1.0)
    )
    rng = pcg64(inputs.seed)
    factors = factor_paths(
        rng,
        (inputs.revenue_factor, inputs.cost_factor, margin_spec),
        scenarios=inputs.scenarios,
        months=60,
        process=PersistentProcess(
            rho=inputs.serial_correlation,
            persistent_weight=inputs.persistent_weight,
        ),
    )
    revenue_factor = factors[:, :, 0]
    cost_factor = factors[:, :, 1]
    margins = factors[:, :, 2]
    if (
        not np.all(np.isfinite(factors))
        or np.any(revenue_factor < 0)
        or np.any(cost_factor < 0)
        or np.any((margins < 0) | (margins > 1))
    ):
        raise ValueError("structured factor paths must keep revenue, cost and margin valid")
    counterfactual_revenue = revenue_factor * revenue[None, :]
    counterfactual_opex = cost_factor * opex[None, :]
    counterfactual_cash_flows = (
        counterfactual_revenue * margins - counterfactual_opex - capex[None, :]
    )
    failures = sample_failure_months(rng, inputs.scenarios, 60, inputs.p_failure_horizon)
    realized_cash_flows = apply_absorbing_failure(
        counterfactual_cash_flows, failures, inputs.liquidation_value
    )
    month_numbers = np.arange(1, 61, dtype=np.int64)[None, :]
    operating = (failures[:, None] == 0) | (month_numbers < failures[:, None])
    realized_revenue = np.where(operating, counterfactual_revenue, 0.0)
    realized_opex = np.where(operating, counterfactual_opex, 0.0)
    states = tuple("failure" if month else "operating" for month in failures)
    return StructuredCashFlowSimulationResult(
        inputs.seed,
        inputs.scenarios,
        _readonly(factors),
        _readonly(counterfactual_cash_flows),
        _readonly(realized_cash_flows),
        _readonly(realized_revenue),
        _readonly(realized_opex),
        _readonly(counterfactual_revenue),
        _readonly(counterfactual_opex),
        _readonly(failures),
        states,
    )
