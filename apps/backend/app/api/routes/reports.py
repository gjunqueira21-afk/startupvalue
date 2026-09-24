"""Authenticated, workspace-scoped PDF download from saved simulation results."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from app.api.dependencies import Actor, Database
from app.db.models import (
    Scenario,
    ScenarioRevision,
    Simulation,
    SimulationResult,
    SimulationSamples,
    SimulationStatus,
    Startup,
)
from app.decision.targets import analyze_target
from app.insights.engine import InsightReport, build_insight, condition_variables
from app.reports import build_report_pdf
from app.reports.from_result import report_from_result
from app.services.audit import record_event
from app.services.simulation import (
    driver_ranking_payload,
    load_sample_vectors,
    rank_snapshot_drivers,
    with_uncertainty,
)

router = APIRouter(prefix="/api/v1", tags=["reports"])


@router.get("/simulations/{simulation_id}/report.pdf")
def download_simulation_report(
    simulation_id: str,
    db: Database,
    actor: Actor,
    target: Annotated[float | None, Query(allow_inf_nan=False)] = None,
) -> Response:
    row = db.execute(
        select(Simulation, SimulationResult, ScenarioRevision, Scenario, Startup)
        .join(SimulationResult, SimulationResult.simulation_id == Simulation.id)
        .join(ScenarioRevision, ScenarioRevision.id == Simulation.scenario_revision_id)
        .join(Scenario, Scenario.id == ScenarioRevision.scenario_id)
        .join(Startup, Startup.id == Scenario.startup_id)
        .where(
            Simulation.id == simulation_id,
            Simulation.workspace_id == actor.workspace_id,
            SimulationResult.workspace_id == actor.workspace_id,
            ScenarioRevision.workspace_id == actor.workspace_id,
            Scenario.workspace_id == actor.workspace_id,
            Startup.workspace_id == actor.workspace_id,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "simulation_not_found")
    simulation, result, revision, scenario, startup = row
    if simulation.status != SimulationStatus.succeeded:
        raise HTTPException(status.HTTP_409_CONFLICT, "simulation_not_complete")

    snapshot = db.scalar(
        select(SimulationSamples).where(
            SimulationSamples.workspace_id == actor.workspace_id,
            SimulationSamples.simulation_result_id == result.id,
        )
    )
    persisted = result.summary.get("drivers")
    ranking: dict[str, Any] | None = persisted if isinstance(persisted, dict) else None
    target_analysis = None
    insight: InsightReport | None = None
    if snapshot is None and target is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "simulation_samples_unavailable")
    if snapshot is not None:
        try:
            valuations, factors = load_sample_vectors(
                snapshot, result=result, simulation=simulation
            )
            if ranking is None:
                ranking = driver_ranking_payload(rank_snapshot_drivers(factors, valuations))
            if target is not None:
                target_analysis = analyze_target(
                    valuations, target, condition_variables(factors)
                )
            # Same deterministic engine as GET /insight, so PDF and dashboard read alike.
            insight = build_insight(
                summary=with_uncertainty(result.summary),
                valuations=valuations,
                factors=factors,
                currency=startup.currency,
                target=target,
            )
        except RuntimeError as exc:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, "simulation_samples_integrity_error"
            ) from exc

    data = report_from_result(
        simulation=simulation,
        result=result,
        revision=revision,
        scenario=scenario,
        startup=startup,
        drivers=ranking,
        target=target_analysis,
        insight=insight,
    )
    pdf = build_report_pdf(data)
    record_event(
        db,
        action="report.download",
        resource_type="simulation_result",
        workspace_id=actor.workspace_id,
        actor_id=actor.user_id,
        resource_id=result.id,
        metadata={"simulation_id": simulation.id, "result_hash": result.result_hash},
    )
    db.commit()
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="startupvalue-{simulation.id}.pdf"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
