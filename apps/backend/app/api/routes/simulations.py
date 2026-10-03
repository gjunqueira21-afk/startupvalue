from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.dependencies import Actor, Database
from app.api.schemas import (
    ConditionalStatisticsResponse,
    DecisionResponse,
    DriverRankingSummary,
    DriverResponse,
    InsightResponse,
    SimulationCreateRequest,
    SimulationResponse,
    SimulationRunRequest,
    SimulationSummary,
    TargetComparisonResponse,
    TargetPlanResponse,
    TargetResponse,
    TornadoItemResponse,
    TornadoResponse,
    TornadoSummary,
    YearTargetResponse,
)
from app.db.models import (
    Role,
    Scenario,
    ScenarioRevision,
    Simulation,
    SimulationResult,
    SimulationSamples,
    Startup,
)
from app.decision.catalog import describe
from app.decision.target_plan import base_year_revenue_from_inputs, build_target_plan
from app.decision.targets import analyze_target
from app.insights.engine import build_insight
from app.repositories.resources import get_revision, get_simulation
from app.services.audit import record_event
from app.services.simulation import (
    driver_ranking_payload,
    execute_synchronously,
    load_sample_vectors,
    rank_snapshot_drivers,
    with_uncertainty,
)

router = APIRouter(prefix="/api/v1", tags=["simulations"])


def _identity(db: Database, simulation: Simulation) -> tuple[str | None, str | None, str]:
    """Company, scenario and currency of the revision this simulation ran on."""
    row = db.execute(
        select(Startup.name, Scenario.name, Startup.currency)
        .join(Scenario, Scenario.startup_id == Startup.id)
        .join(ScenarioRevision, ScenarioRevision.scenario_id == Scenario.id)
        .where(
            ScenarioRevision.id == simulation.scenario_revision_id,
            ScenarioRevision.workspace_id == simulation.workspace_id,
            Scenario.workspace_id == simulation.workspace_id,
            Startup.workspace_id == simulation.workspace_id,
        )
    ).one_or_none()
    return (row[0], row[1], row[2]) if row else (None, None, "BRL")


def _response(
    db: Database, simulation: Simulation, result: SimulationResult | None
) -> SimulationResponse:
    company_name, scenario_name, currency = _identity(db, simulation)
    return SimulationResponse(
        company_name=company_name,
        scenario_name=scenario_name,
        currency=currency,
        simulation_id=simulation.id,
        scenario_revision_id=simulation.scenario_revision_id,
        model_version=simulation.model_version,
        tax_version=simulation.tax_version,
        seed=simulation.seed,
        simulation_count=simulation.simulation_count,
        status=simulation.status.value,
        summary=SimulationSummary.model_validate(with_uncertainty(result.summary))
        if result
        else None,
        result_hash=result.result_hash if result else None,
        created_at=simulation.created_at,
    )


@router.post(
    "/scenario-revisions/{revision_id}/simulations",
    response_model=SimulationResponse,
    status_code=status.HTTP_201_CREATED,
)
def run_simulation(
    revision_id: str, payload: SimulationRunRequest, db: Database, actor: Actor
) -> SimulationResponse:
    return _run(revision_id, payload, db, actor)


@router.post(
    "/simulations",
    response_model=SimulationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_simulation(
    payload: SimulationCreateRequest, db: Database, actor: Actor
) -> SimulationResponse:
    request = SimulationRunRequest.model_validate(
        payload.model_dump(exclude={"scenario_revision_id"})
    )
    return _run(payload.scenario_revision_id, request, db, actor)


def _run(
    revision_id: str, payload: SimulationRunRequest, db: Database, actor: Actor
) -> SimulationResponse:
    if actor.role not in {Role.owner, Role.admin, Role.analyst}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "action_not_allowed")
    revision = get_revision(db, revision_id=revision_id, workspace_id=actor.workspace_id)
    if revision is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "scenario_revision_not_found")
    try:
        simulation, result = execute_synchronously(
            db,
            workspace_id=actor.workspace_id,
            revision_id=revision.id,
            canonical_inputs=revision.canonical_inputs,
            request=payload,
        )
    except (ValueError, RuntimeError) as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    record_event(
        db,
        action="simulation.succeeded",
        resource_type="simulation",
        workspace_id=actor.workspace_id,
        actor_id=actor.user_id,
        resource_id=simulation.id,
        metadata={
            "model_version": simulation.model_version,
            "seed": simulation.seed,
            "simulation_count": simulation.simulation_count,
        },
    )
    db.commit()
    db.refresh(simulation)
    db.refresh(result)
    return _response(db, simulation, result)


@router.get("/simulations/{simulation_id}", response_model=SimulationResponse)
def read_simulation(simulation_id: str, db: Database, actor: Actor) -> SimulationResponse:
    simulation = get_simulation(
        db, simulation_id=simulation_id, workspace_id=actor.workspace_id
    )
    if simulation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "simulation_not_found")
    result = db.scalar(
        select(SimulationResult).where(
            SimulationResult.workspace_id == actor.workspace_id,
            SimulationResult.simulation_id == simulation.id,
        )
    )
    return _response(db, simulation, result)


def _decision_source(
    simulation_id: str, db: Database, actor: Actor
) -> tuple[Simulation, SimulationResult, SimulationSamples]:
    simulation = get_simulation(db, simulation_id=simulation_id, workspace_id=actor.workspace_id)
    if simulation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "simulation_not_found")
    result = db.scalar(
        select(SimulationResult).where(
            SimulationResult.workspace_id == actor.workspace_id,
            SimulationResult.simulation_id == simulation.id,
        )
    )
    if result is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "simulation_result_unavailable")
    snapshot = db.scalar(
        select(SimulationSamples).where(
            SimulationSamples.workspace_id == actor.workspace_id,
            SimulationSamples.simulation_result_id == result.id,
        )
    )
    if snapshot is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "simulation_samples_unavailable")
    return simulation, result, snapshot


@router.get("/simulations/{simulation_id}/decision", response_model=DecisionResponse)
def read_decision(simulation_id: str, db: Database, actor: Actor) -> DecisionResponse:
    simulation, result, snapshot = _decision_source(simulation_id, db, actor)
    try:
        # Verify the snapshot even when the ranking is persisted: a tampered payload must fail.
        valuations, factors = load_sample_vectors(snapshot, result=result, simulation=simulation)
    except RuntimeError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "simulation_samples_integrity_error"
        ) from exc
    persisted = result.summary.get("drivers")
    ranking = DriverRankingSummary.model_validate(
        persisted
        if isinstance(persisted, dict)
        else driver_ranking_payload(rank_snapshot_drivers(factors, valuations))
    )
    stored_tornado = result.summary.get("sensitivity")
    tornado = (
        TornadoSummary.model_validate(stored_tornado) if isinstance(stored_tornado, dict) else None
    )
    return DecisionResponse(
        simulation_id=simulation.id,
        result_hash=result.result_hash,
        basis=str(result.summary["basis"]),
        scenario_count=simulation.simulation_count,
        method_version=ranking.method_version,
        r_squared=ranking.r_squared,
        warnings=ranking.warnings,
        drivers=[
            DriverResponse(
                **item.model_dump(),
                label=describe(item.name).label,
                unit=describe(item.name).unit,
                count=ranking.scenario_count,
            )
            for item in ranking.items
        ],
        tornado=TornadoResponse(
            **tornado.model_dump(exclude={"items"}),
            items=[
                TornadoItemResponse(
                    **item.model_dump(),
                    label=describe(item.parameter).label,
                    unit=describe(item.parameter).unit,
                )
                for item in tornado.items
            ],
        )
        if tornado is not None
        else None,
    )


@router.get("/simulations/{simulation_id}/insight", response_model=InsightResponse)
def read_insight(
    simulation_id: str,
    db: Database,
    actor: Actor,
    target: Annotated[float | None, Query(allow_inf_nan=False)] = None,
) -> InsightResponse:
    """Executive interpretation of the saved result; reads vectors, never resamples."""
    simulation, result, snapshot = _decision_source(simulation_id, db, actor)
    try:
        valuations, factors = load_sample_vectors(snapshot, result=result, simulation=simulation)
    except RuntimeError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "simulation_samples_integrity_error"
        ) from exc
    _, _, currency = _identity(db, simulation)
    report = build_insight(
        summary=with_uncertainty(result.summary),
        valuations=valuations,
        factors=factors,
        currency=currency,
        target=target,
    )
    return InsightResponse.model_validate(
        {"simulation_id": simulation.id, "result_hash": result.result_hash, **asdict(report)}
    )


@router.get("/simulations/{simulation_id}/target", response_model=TargetResponse)
def read_target(
    simulation_id: str,
    db: Database,
    actor: Actor,
    value: Annotated[float, Query(allow_inf_nan=False)],
) -> TargetResponse:
    simulation, result, snapshot = _decision_source(simulation_id, db, actor)
    try:
        valuations, factors = load_sample_vectors(snapshot, result=result, simulation=simulation)
        target = analyze_target(valuations, value, factors)
    except RuntimeError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "simulation_samples_integrity_error"
        ) from exc
    revision = get_revision(
        db, revision_id=simulation.scenario_revision_id, workspace_id=actor.workspace_id
    )
    base_year_revenue = base_year_revenue_from_inputs(
        revision.canonical_inputs if revision else None
    )
    plan = build_target_plan(valuations, value, factors, base_year_revenue)
    return TargetResponse(
        simulation_id=simulation.id,
        result_hash=result.result_hash,
        basis=str(result.summary["basis"]),
        target=target.target,
        scenario_count=target.scenario_count,
        hit_count=target.hit_count,
        miss_count=target.miss_count,
        probability=target.probability,
        wilson95_low=target.wilson95_low,
        wilson95_high=target.wilson95_high,
        comparisons=[
            TargetComparisonResponse(
                name=item.name,
                label=describe(item.name).label,
                unit=describe(item.name).unit,
                role=describe(item.name).role,
                hit=ConditionalStatisticsResponse(
                    count=item.hit.count,
                    p25=item.hit.p25,
                    p50=item.hit.p50,
                    p75=item.hit.p75,
                    reason=item.hit.reason,
                ),
                miss=ConditionalStatisticsResponse(
                    count=item.miss.count,
                    p25=item.miss.p25,
                    p50=item.miss.p50,
                    p75=item.miss.p75,
                    reason=item.miss.reason,
                ),
                median_difference_hit_minus_miss=item.median_difference_hit_minus_miss,
                status=item.status,
            )
            for item in target.comparisons
        ],
        plan=TargetPlanResponse(
            status=plan.status,
            hit_count=plan.hit_count,
            required_revenue_cagr=plan.required_revenue_cagr,
            hit_ebitda_margin=plan.hit_ebitda_margin,
            miss_revenue_cagr=plan.miss_revenue_cagr,
            miss_ebitda_margin=plan.miss_ebitda_margin,
            trajectory=[
                YearTargetResponse(year=item.year, revenue=item.revenue)
                for item in plan.trajectory
            ],
        ),
    )
