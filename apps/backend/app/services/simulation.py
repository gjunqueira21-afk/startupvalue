from __future__ import annotations

import hashlib
import json
import uuid
import zlib
from collections.abc import Mapping
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import CanonicalValuationInputs, SimulationRunRequest
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
from app.decision.catalog import split_by_role
from app.decision.sensitivity import DriverRanking, rank_drivers
from app.decision.uncertainty import assess_uncertainty
from app.services.valuation_model import (
    build_tornado,
    sample_parameters,
    simulate_paths,
)
from app.services.valuation_model import equity_values as model_equity_values
from app.services.vc_analysis import analyze_vc_profile
from app.simulation.statistics import DistributionSummary, summarize

RESULT_SCHEMA_VERSION = "1.3.0"


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


def uncertainty_payload(summary: Mapping[str, Any]) -> dict[str, object]:
    """Classify dispersion from persisted summary fields; never touches samples."""
    percentiles = summary["percentiles"]
    assessment = assess_uncertainty(
        p10=float(percentiles["p10"]),
        p25=float(percentiles["p25"]),
        p50=float(percentiles["p50"]),
        p75=float(percentiles["p75"]),
        p90=float(percentiles["p90"]),
        non_positive_probability=float(summary["non_positive_probability"]),
    )
    return {
        "label": assessment.label,
        "reason": assessment.reason,
        "rule_version": assessment.rule_version,
        "iqr": assessment.iqr,
        "iqr_ratio": assessment.iqr_ratio,
        "spread80": assessment.spread80,
        "spread80_ratio": assessment.spread80_ratio,
        "non_positive_probability": assessment.non_positive_probability,
    }


def with_uncertainty(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Results persisted before schema 1.2 lack the classification; derive it on read."""
    enriched = dict(summary)
    if not isinstance(enriched.get("uncertainty"), dict):
        enriched["uncertainty"] = uncertainty_payload(enriched)
        enriched["uncertainty_label"] = enriched["uncertainty"]["label"]
    return enriched


def driver_ranking_payload(ranking: DriverRanking) -> dict[str, object]:
    return {
        "method": ranking.method,
        "method_version": ranking.method_version,
        "scenario_count": ranking.scenario_count,
        "r_squared": ranking.r_squared,
        "warnings": list(ranking.warnings),
        "items": [
            {
                "name": item.name,
                "rho": item.rho,
                "srrc": item.srrc,
                "contribution": item.contribution,
                "direction": item.direction,
                "status": item.status,
            }
            for item in ranking.drivers
        ],
    }


def rank_snapshot_drivers(
    factors: Mapping[str, np.ndarray], valuations: np.ndarray
) -> DriverRanking:
    drivers, _ = split_by_role(factors)
    return rank_drivers(drivers, valuations)


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
    paths = simulate_paths(
        inputs,
        seed=request.seed,
        scenarios=request.simulation_count,
        p_failure=inputs.failure_probability_horizon,
    )
    parameters = sample_parameters(
        inputs, seed=request.seed, scenarios=request.simulation_count
    )
    equity_values = model_equity_values(inputs, paths, parameters)
    failure_months = paths.failure_months
    realized_inputs = {**paths.realized_inputs, **parameters.drivers()}
    distribution = summarize(equity_values)
    observed_failure = float(np.mean(failure_months > 0))
    summary = _summary_payload(distribution, observed_failure, equity_values)
    summary = with_uncertainty(summary)
    summary["drivers"] = driver_ranking_payload(
        rank_snapshot_drivers(realized_inputs, equity_values)
    )
    summary["sensitivity"] = build_tornado(
        inputs,
        seed=request.seed,
        scenarios=request.simulation_count,
        paths=paths,
        parameters=parameters,
        base_value=distribution.p50,
    )
    summary["vc_method"] = _vc_profile_summary(
        db, workspace_id=workspace_id, revision_id=revision_id
    )

    names, sample_payload, payload_hash = _snapshot_payload(equity_values, realized_inputs)

    samples_hash = hashlib.sha256(equity_values.astype("<f8", copy=False).tobytes()).hexdigest()
    result_material = {
        "simulation_id": simulation.id,
        "schema_version": RESULT_SCHEMA_VERSION,
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
        schema_version=RESULT_SCHEMA_VERSION,
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
