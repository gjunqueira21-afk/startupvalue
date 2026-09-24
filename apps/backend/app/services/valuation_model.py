"""Evaluate one canonical input set: scenario paths, valuation parameters and tornado.

Random streams (all derived from the simulation seed, see METHODOLOGY §14):
- the operating engine draws factor paths and failure months from ``PCG64(seed)``;
- each *uncertain* valuation parameter draws from its own stream
  ``PCG64(SeedSequence([seed, stream]))``, so enabling one range never changes
  the operating draws or the draws of another parameter.
A range given as a constant distribution is a fixed assumption, not a driver.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import inf

import numpy as np

from app.api.schemas import CanonicalValuationInputs, DistributionInput
from app.simulation.distributions import (
    Constant,
    DistributionSpec,
    LogNormal,
    Normal,
    StudentT,
    Triangular,
    Uniform,
    inverse_cdf,
)
from app.simulation.monte_carlo import (
    SimpleCashFlowSimulationInput,
    StructuredCashFlowSimulationInput,
    simulate_simple_cash_flows,
    simulate_structured_cash_flows,
)
from app.valuation.scenario_dcf import (
    ExitMultipleTerminal,
    GordonTerminal,
    Parameter,
    scenario_enterprise_values,
)

PARAMETER_STREAMS = {"annual_wacc": 1, "terminal_growth": 2, "exit_multiple": 3}
TORNADO_METHOD_VERSION = "tornado-v1"
# Minimum distance kept between WACC and perpetuity growth when swinging either.
RATE_GAP = 0.005


def distribution_spec(value: DistributionInput) -> DistributionSpec:
    lower = value.lower if value.lower is not None else -inf
    upper = value.upper if value.upper is not None else inf
    if value.kind == "constant":
        assert value.value is not None
        return Constant(value.value)
    if value.kind == "normal":
        assert value.standard_deviation is not None
        return Normal(value.mean, value.standard_deviation, lower, upper)
    if value.kind == "student_t":
        assert value.standard_deviation is not None and value.degrees_of_freedom is not None
        return StudentT.from_standard_deviation(
            loc=value.mean,
            standard_deviation=value.standard_deviation,
            df=value.degrees_of_freedom,
            lower=lower,
            upper=upper,
        )
    if value.kind == "triangular":
        assert value.minimum is not None and value.mode is not None and value.maximum is not None
        return Triangular(value.minimum, value.mode, value.maximum)
    if value.kind == "uniform":
        assert value.minimum is not None and value.maximum is not None
        return Uniform(value.minimum, value.maximum)
    assert value.coefficient_of_variation is not None
    return LogNormal(value.mean, value.coefficient_of_variation)


@dataclass(frozen=True, slots=True)
class ScenarioPaths:
    realized_cash_flows: np.ndarray
    failure_months: np.ndarray
    realized_inputs: dict[str, np.ndarray]
    revenue_year5: np.ndarray | None
    ebitda_year5: np.ndarray | None


def _operating_outcomes(
    revenue: np.ndarray, opex: np.ndarray, margins: np.ndarray
) -> dict[str, np.ndarray]:
    """Year-5 business metrics on the operating path, before any absorbing failure."""
    revenue_y1 = np.sum(revenue[:, :12], axis=1)
    revenue_y5 = np.sum(revenue[:, -12:], axis=1)
    opex_y5 = np.sum(opex[:, -12:], axis=1)
    outcomes = {"revenue_year5_operating": revenue_y5, "opex_year5_operating": opex_y5}
    # Ratios are only published when defined for every scenario; no substitute values.
    if np.all(revenue_y5 > 0.0):
        gross_profit_y5 = np.sum(revenue[:, -12:] * margins[:, -12:], axis=1)
        outcomes["ebitda_margin_year5_operating"] = (gross_profit_y5 - opex_y5) / revenue_y5
        if np.all(revenue_y1 > 0.0):
            outcomes["revenue_cagr_operating"] = (revenue_y5 / revenue_y1) ** 0.25 - 1.0
    return outcomes


def simulate_paths(
    inputs: CanonicalValuationInputs, *, seed: int, scenarios: int, p_failure: float
) -> ScenarioPaths:
    if inputs.monthly_fcff is not None:
        assert inputs.uncertainty is not None
        simple = simulate_simple_cash_flows(
            SimpleCashFlowSimulationInput(
                base_cash_flows=tuple(inputs.monthly_fcff),
                factor=distribution_spec(inputs.uncertainty),
                scenarios=scenarios,
                seed=seed,
                p_failure_horizon=p_failure,
                liquidation_value=inputs.liquidation_value,
            )
        )
        return ScenarioPaths(
            simple.realized_cash_flows,
            simple.failure_months,
            {
                "scenario_factor_mean": np.mean(simple.factor_paths, axis=1),
                "failure_state": (simple.failure_months > 0).astype(np.float64),
            },
            None,
            None,
        )
    assert inputs.monthly_revenue is not None
    assert inputs.monthly_opex is not None
    assert inputs.monthly_capex is not None
    assert inputs.gross_margin is not None
    assert inputs.revenue_uncertainty is not None
    assert inputs.cost_uncertainty is not None
    structured = simulate_structured_cash_flows(
        StructuredCashFlowSimulationInput(
            base_monthly_revenue=tuple(inputs.monthly_revenue),
            base_monthly_opex=tuple(inputs.monthly_opex),
            base_monthly_capex=tuple(inputs.monthly_capex),
            gross_margin=inputs.gross_margin,
            revenue_factor=distribution_spec(inputs.revenue_uncertainty),
            cost_factor=distribution_spec(inputs.cost_uncertainty),
            margin_uncertainty_pp=inputs.margin_uncertainty_pp,
            serial_correlation=inputs.serial_correlation,
            persistent_weight=inputs.persistent_weight,
            scenarios=scenarios,
            seed=seed,
            p_failure_horizon=p_failure,
            liquidation_value=inputs.liquidation_value,
        )
    )
    margins = structured.factor_paths[:, :, 2]
    realized_revenue_y5 = structured.realized_revenue[:, -12:]
    return ScenarioPaths(
        structured.realized_cash_flows,
        structured.failure_months,
        {
            "revenue_factor_mean": np.mean(structured.factor_paths[:, :, 0], axis=1),
            "cost_factor_mean": np.mean(structured.factor_paths[:, :, 1], axis=1),
            "gross_margin_mean": np.mean(margins, axis=1),
            "failure_state": (structured.failure_months > 0).astype(np.float64),
            **_operating_outcomes(
                structured.counterfactual_revenue, structured.counterfactual_opex, margins
            ),
        },
        np.sum(realized_revenue_y5, axis=1),
        np.sum(
            realized_revenue_y5 * margins[:, -12:] - structured.realized_opex[:, -12:], axis=1
        ),
    )


@dataclass(frozen=True, slots=True)
class ValuationParameters:
    annual_wacc: Parameter
    terminal_growth: Parameter | None
    exit_multiple: Parameter | None

    def drivers(self) -> dict[str, np.ndarray]:
        """Sampled parameters are primitive drivers; fixed ones are not."""
        values = {
            "annual_wacc": self.annual_wacc,
            "terminal_growth": self.terminal_growth,
            "exit_multiple": self.exit_multiple,
        }
        return {name: value for name, value in values.items() if isinstance(value, np.ndarray)}


def _uncertain(value: DistributionInput | None) -> bool:
    return value is not None and value.kind != "constant"


def _sample(
    name: str, base: float, value: DistributionInput | None, seed: int, scenarios: int
) -> Parameter:
    if value is None or not _uncertain(value):
        return base
    stream = np.random.Generator(
        np.random.PCG64(np.random.SeedSequence([seed, PARAMETER_STREAMS[name]]))
    )
    return inverse_cdf(distribution_spec(value), stream.random(scenarios, dtype=np.float64))


def sample_parameters(
    inputs: CanonicalValuationInputs, *, seed: int, scenarios: int
) -> ValuationParameters:
    growth: Parameter | None = None
    if inputs.terminal_method == "gordon" and inputs.terminal_growth is not None:
        growth = _sample(
            "terminal_growth",
            inputs.terminal_growth,
            inputs.terminal_growth_uncertainty,
            seed,
            scenarios,
        )
    multiple: Parameter | None = None
    if inputs.terminal_method == "exit_multiple":
        assert inputs.exit_multiple is not None
        multiple = _sample(
            "exit_multiple", inputs.exit_multiple, inputs.exit_multiple_uncertainty, seed, scenarios
        )
    return ValuationParameters(
        _sample("annual_wacc", inputs.annual_wacc, inputs.wacc_uncertainty, seed, scenarios),
        growth,
        multiple,
    )


def equity_values(
    inputs: CanonicalValuationInputs, paths: ScenarioPaths, parameters: ValuationParameters
) -> np.ndarray:
    terminal: GordonTerminal | ExitMultipleTerminal | None = None
    if parameters.terminal_growth is not None:
        terminal = GordonTerminal(parameters.terminal_growth)
    elif parameters.exit_multiple is not None:
        metric = paths.revenue_year5 if inputs.exit_metric == "revenue" else paths.ebitda_year5
        assert metric is not None
        terminal = ExitMultipleTerminal(parameters.exit_multiple, metric)
    enterprise = scenario_enterprise_values(
        paths.realized_cash_flows,
        paths.failure_months,
        annual_wacc=parameters.annual_wacc,
        terminal=terminal,
    )
    return enterprise + inputs.excess_cash - inputs.debt


def _p50(values: np.ndarray) -> float:
    return float(np.quantile(values, 0.5, method="linear"))


def _levels(
    name: str,
    base: float,
    value: DistributionInput | None,
    delta: float,
    *,
    relative: bool = False,
) -> tuple[float, float, str]:
    if value is not None and _uncertain(value):
        low, high = inverse_cdf(distribution_spec(value), np.array([0.1, 0.9]))
        return float(low), float(high), "distribution_p10_p90"
    swing = base * delta if relative else delta
    return base - swing, base + swing, "base_plus_minus_delta"


def build_tornado(
    inputs: CanonicalValuationInputs,
    *,
    seed: int,
    scenarios: int,
    paths: ScenarioPaths,
    parameters: ValuationParameters,
    base_value: float,
) -> dict[str, object]:
    """One-at-a-time swings on common random numbers; each bar re-values the same draws."""
    settings = inputs.tornado
    items: list[dict[str, object]] = []

    def item(
        parameter: str,
        base_level: float,
        levels: tuple[float, float, str],
        clamped_levels: tuple[float, float],
        values: tuple[float, float],
    ) -> None:
        low, high, source = levels
        items.append(
            {
                "parameter": parameter,
                "base_level": base_level,
                "low_level": clamped_levels[0],
                "high_level": clamped_levels[1],
                "value_at_low": values[0],
                "value_at_high": values[1],
                "swing": abs(values[1] - values[0]),
                "level_source": source,
                "clamped": clamped_levels != (low, high),
            }
        )

    def revalue(**changes: float) -> float:
        return _p50(equity_values(inputs, paths, replace(parameters, **changes)))

    growth_max = (
        float(np.max(parameters.terminal_growth))
        if parameters.terminal_growth is not None
        else -1.0 + RATE_GAP
    )
    wacc = _levels("annual_wacc", inputs.annual_wacc, inputs.wacc_uncertainty, settings.wacc_delta)
    wacc_clamped = (max(wacc[0], growth_max + RATE_GAP), max(wacc[1], growth_max + RATE_GAP))
    item(
        "annual_wacc",
        inputs.annual_wacc,
        wacc,
        wacc_clamped,
        (revalue(annual_wacc=wacc_clamped[0]), revalue(annual_wacc=wacc_clamped[1])),
    )

    if parameters.terminal_growth is not None:
        assert inputs.terminal_growth is not None
        wacc_min = float(np.min(parameters.annual_wacc))
        growth = _levels(
            "terminal_growth",
            inputs.terminal_growth,
            inputs.terminal_growth_uncertainty,
            settings.terminal_growth_delta,
        )
        cap = wacc_min - RATE_GAP
        growth_clamped = (min(growth[0], cap), min(growth[1], cap))
        item(
            "terminal_growth",
            inputs.terminal_growth,
            growth,
            growth_clamped,
            (
                revalue(terminal_growth=growth_clamped[0]),
                revalue(terminal_growth=growth_clamped[1]),
            ),
        )

    if parameters.exit_multiple is not None:
        assert inputs.exit_multiple is not None
        multiple = _levels(
            "exit_multiple",
            inputs.exit_multiple,
            inputs.exit_multiple_uncertainty,
            settings.exit_multiple_relative_delta,
            relative=True,
        )
        multiple_clamped = (max(multiple[0], 0.0), multiple[1])
        item(
            "exit_multiple",
            inputs.exit_multiple,
            multiple,
            multiple_clamped,
            (
                revalue(exit_multiple=multiple_clamped[0]),
                revalue(exit_multiple=multiple_clamped[1]),
            ),
        )

    base_failure = inputs.failure_probability_horizon
    failure = (
        base_failure - settings.failure_probability_delta,
        base_failure + settings.failure_probability_delta,
        "base_plus_minus_delta",
    )
    failure_clamped = (min(max(failure[0], 0.0), 1.0), min(max(failure[1], 0.0), 1.0))

    def failure_value(level: float) -> float:
        # Same seed: factor paths are identical; only the failure draw changes.
        swung = (
            paths
            if level == base_failure
            else simulate_paths(inputs, seed=seed, scenarios=scenarios, p_failure=level)
        )
        return _p50(equity_values(inputs, swung, parameters))

    item(
        "failure_probability",
        base_failure,
        failure,
        failure_clamped,
        (failure_value(failure_clamped[0]), failure_value(failure_clamped[1])),
    )
    items.sort(key=lambda entry: (-float(entry["swing"]), str(entry["parameter"])))  # type: ignore[arg-type]
    return {
        "method": "one_at_a_time_common_random_numbers",
        "method_version": TORNADO_METHOD_VERSION,
        "statistic": "p50",
        "base_value": base_value,
        "items": items,
    }
