from __future__ import annotations

import hashlib
import json
import uuid
import zlib
from math import inf

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import CanonicalValuationInputs, DistributionInput, SimulationRunRequest
from app.core.config import get_settings
from app.db.models import (
    Scenario,
    ScenarioRevision,
    Simulation,
    SimulationResult,
    SimulationSamples,
    SimulationStatus,
    Startup,
)
from app.services.vc_analysis import analyze_vc_profile
from app.simulation.distributions import (
    Constant,
    DistributionSpec,
    LogNormal,
    Normal,
    StudentT,
    Triangular,
    Uniform,
)
from app.simulation.monte_carlo import (
    SimpleCashFlowSimulationInput,
    StructuredCashFlowSimulationInput,
    simulate_simple_cash_flows,
    simulate_structured_cash_flows,
)
from app.simulation.statistics import DistributionSummary, summarize
from app.valuation.dcf import TerminalAssumptions, accumulated_discount_factors, terminal_value


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


def _summary_payload(
    summary: DistributionSummary, failure_probability: float, equity_values: np.ndarray
) -> dict[str, object]:
    uncertainty_ratio = (
        (summary.p75 - summary.p25) / abs(summary.p50) if abs(summary.p50) >= 1.0 else None
    )
    if summary.minimum == summary.maximum:
        histogram_edges = [summary.minimum - 0.5, summary.maximum + 0.5]
        histogram_counts = [int(equity_values.size)]
    else:
        counts, edges = np.histogram(equity_values, bins=40)
        histogram_edges = edges.tolist()
        histogram_counts = counts.tolist()
    return {
        "basis": "DCF equity value (signed)",
        "percentiles": {
            "p5": summary.p5,
            "p10": summary.p10,
            "p25": summary.p25,
            "p50": summary.p50,
            "p75": summary.p75,
            "p90": summary.p90,
            "p95": summary.p95,
        },
        "minimum": summary.minimum,
        "maximum": summary.maximum,
        "mean": summary.mean,
        "standard_deviation": summary.standard_deviation_population,
        "failure_probability": failure_probability,
        "uncertainty_label": "NOT AVAILABLE",
        "uncertainty_ratio": uncertainty_ratio,
        "breakeven_probabilities": {},
        "breakeven_month_percentiles": {},
        "non_positive_probability": summary.non_positive_probability,
        "histogram": {"edges": histogram_edges, "counts": histogram_counts},
    }


def _snapshot_payload(
    valuations: np.ndarray, realized_inputs: dict[str, np.ndarray],
) -> tuple[list[str], bytes, str]:
    """Encode aligned float64 scenario vectors without exposing them in the API."""
    factor_names = ["valuation", *realized_inputs]
    columns = (valuations, *realized_inputs.values())
    if any(value.shape != valuations.shape or not np.all(np.isfinite(value)) for value in columns):
        raise ValueError("decision vectors must be finite and aligned with valuations")
    matrix = np.ascontiguousarray(np.column_stack(columns), dtype="<f8")
    raw = matrix.tobytes(order="C")
    manifest = json.dumps(
        {"format_version": "aligned-f64-le-zlib-v1", "factor_names": factor_names,
         "scenario_count": int(matrix.shape[0])},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return factor_names, zlib.compress(raw, level=6), hashlib.sha256(manifest + raw).hexdigest()


def load_sample_vectors(
    snapshot: SimulationSamples, *, result: SimulationResult, simulation: Simulation
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Verify and read stored vectors; never rerun or resample the model."""
    names = snapshot.factor_names
    if (
        snapshot.format_version != "aligned-f64-le-zlib-v1"
        or not isinstance(names, list)
        or names[:1] != ["valuation"]
        or len(names) != len(set(names))
        or not 1 <= len(names) <= 16
        or snapshot.scenario_count != simulation.simulation_count
        or snapshot.workspace_id != result.workspace_id
        or snapshot.simulation_result_id != result.id
    ):
        raise RuntimeError("simulation sample manifest is invalid")
    expected_bytes = snapshot.scenario_count * len(names) * 8
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(snapshot.payload, expected_bytes + 1)
    except zlib.error as exc:
        raise RuntimeError("simulation sample payload is invalid") from exc
    manifest = json.dumps(
        {"format_version": snapshot.format_version, "factor_names": names,
         "scenario_count": snapshot.scenario_count},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if (
        len(raw) != expected_bytes
        or not decoder.eof
        or decoder.unused_data
        or hashlib.sha256(manifest + raw).hexdigest() != snapshot.payload_hash
    ):
        raise RuntimeError("simulation sample payload failed integrity check")
    matrix = np.frombuffer(raw, dtype="<f8").reshape(snapshot.scenario_count, len(names))
    if not np.all(np.isfinite(matrix)):
        raise RuntimeError("simulation sample payload contains non-finite values")
    valuations = matrix[:, 0]
    valuation_digest = hashlib.sha256(np.ascontiguousarray(valuations).tobytes()).hexdigest()
    if valuation_digest != result.samples_hash:
        raise RuntimeError("simulation valuation samples failed integrity check")
    return valuations, {name: matrix[:, index] for index, name in enumerate(names[1:], 1)}


def _vc_profile_summary(db: Session, *, workspace_id: str, revision_id: str) -> dict[str, object]:
    startup = db.scalar(
        select(Startup)
        .join(Scenario, Scenario.startup_id == Startup.id)
        .join(ScenarioRevision, ScenarioRevision.scenario_id == Scenario.id)
        .where(
            ScenarioRevision.id == revision_id,
            ScenarioRevision.workspace_id == workspace_id,
            Scenario.workspace_id == workspace_id,
            Startup.workspace_id == workspace_id,
        )
    )
    if startup is None:
        return {
            "status": "unavailable",
            "reason_code": "startup_profile_unavailable",
            "reason": "No startup profile was found for this scenario revision.",
        }
    return analyze_vc_profile(startup.profile)


def execute_synchronously(
    db: Session,
    *,
    workspace_id: str,
    revision_id: str,
    canonical_inputs: dict[str, object],
    request: SimulationRunRequest,
) -> tuple[Simulation, SimulationResult]:
    existing = None
    if request.idempotency_key is not None:
        existing = db.scalar(
            select(Simulation).where(
                Simulation.workspace_id == workspace_id,
                Simulation.idempotency_key == request.idempotency_key,
            )
        )
    if existing is not None:
        result = db.scalar(
            select(SimulationResult).where(
                SimulationResult.workspace_id == workspace_id,
                SimulationResult.simulation_id == existing.id,
            )
        )
        if result is None:
            raise RuntimeError("idempotent simulation exists without a result")
        return existing, result

    settings = get_settings()
    simulation = Simulation(
        workspace_id=workspace_id,
        scenario_revision_id=revision_id,
        model_version=settings.model_version,
        tax_version=settings.tax_version,
        seed=request.seed,
        simulation_count=request.simulation_count,
        status=SimulationStatus.running,
        idempotency_key=request.idempotency_key or str(uuid.uuid4()),
    )
    db.add(simulation)
    db.flush()

    inputs = CanonicalValuationInputs.model_validate(canonical_inputs)
    if inputs.monthly_fcff is not None:
        assert inputs.uncertainty is not None
        simulated_legacy = simulate_simple_cash_flows(
            SimpleCashFlowSimulationInput(
                base_cash_flows=tuple(inputs.monthly_fcff),
                factor=distribution_spec(inputs.uncertainty),
                scenarios=request.simulation_count,
                seed=request.seed,
                p_failure_horizon=inputs.failure_probability_horizon,
                liquidation_value=inputs.liquidation_value,
            )
        )
        realized_cash_flows = simulated_legacy.realized_cash_flows
        failure_months = simulated_legacy.failure_months
        realized_inputs = {
            "scenario_factor_mean": np.mean(simulated_legacy.factor_paths, axis=1),
            "failure_state": (failure_months > 0).astype(np.float64),
        }
    else:
        assert inputs.monthly_revenue is not None
        assert inputs.monthly_opex is not None
        assert inputs.monthly_capex is not None
        assert inputs.gross_margin is not None
        assert inputs.revenue_uncertainty is not None
        assert inputs.cost_uncertainty is not None
        simulated_structured = simulate_structured_cash_flows(
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
                scenarios=request.simulation_count,
                seed=request.seed,
                p_failure_horizon=inputs.failure_probability_horizon,
                liquidation_value=inputs.liquidation_value,
            )
        )
        realized_cash_flows = simulated_structured.realized_cash_flows
        failure_months = simulated_structured.failure_months
        realized_inputs = {
            "revenue_year5": np.sum(simulated_structured.realized_revenue[:, -12:], axis=1),
            "opex_year5": np.sum(simulated_structured.realized_opex[:, -12:], axis=1),
            "modeled_gross_margin_year5": np.mean(
                simulated_structured.factor_paths[:, -12:, 2], axis=1
            ),
            "revenue_factor_mean": np.mean(simulated_structured.factor_paths[:, :, 0], axis=1),
            "cost_factor_mean": np.mean(simulated_structured.factor_paths[:, :, 1], axis=1),
            "failure_state": (failure_months > 0).astype(np.float64),
        }
    discount_factors = accumulated_discount_factors(
        inputs.annual_wacc, realized_cash_flows.shape[1]
    )
    enterprise_values = np.asarray(
        np.sum(
            realized_cash_flows / discount_factors[None, :],
            axis=1,
            dtype=np.float64,
        ),
        dtype=np.float64,
    )
    if inputs.terminal_growth is not None:
        unit_terminal = terminal_value(
            TerminalAssumptions(1.0, inputs.terminal_growth, inputs.annual_wacc)
        )
        eligible = failure_months == 0
        terminal_fcff = np.maximum(np.mean(realized_cash_flows[:, -12:], axis=1), 0.0)
        enterprise_values += eligible * terminal_fcff * unit_terminal / discount_factors[-1]
    equity_values = enterprise_values + inputs.excess_cash - inputs.debt
    distribution = summarize(equity_values)
    observed_failure = float(np.mean(failure_months > 0))
    summary = _summary_payload(distribution, observed_failure, equity_values)
    summary["vc_method"] = _vc_profile_summary(
        db, workspace_id=workspace_id, revision_id=revision_id
    )

    names, sample_payload, payload_hash = _snapshot_payload(equity_values, realized_inputs)

    samples_hash = hashlib.sha256(equity_values.astype("<f8", copy=False).tobytes()).hexdigest()
    result_material = {
        "simulation_id": simulation.id,
        "schema_version": "1.1.0",
        "summary": summary,
        "samples_hash": samples_hash,
        "samples_payload_hash": payload_hash,
    }
    result_hash = hashlib.sha256(
        json.dumps(result_material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    snapshot_id = str(uuid.uuid4())
    result = SimulationResult(
        workspace_id=workspace_id,
        simulation_id=simulation.id,
        schema_version="1.1.0",
        summary=summary,
        result_hash=result_hash,
        samples_object_key=f"db-private://simulation_samples/{snapshot_id}",
        samples_hash=samples_hash,
    )
    simulation.status = SimulationStatus.succeeded
    db.add(result)
    db.flush()
    db.add(
        SimulationSamples(
            id=snapshot_id,
            workspace_id=workspace_id,
            simulation_result_id=result.id,
            format_version="aligned-f64-le-zlib-v1",
            factor_names=names,
            scenario_count=request.simulation_count,
            payload=sample_payload,
            payload_hash=payload_hash,
        )
    )
    db.flush()
    return simulation, result
