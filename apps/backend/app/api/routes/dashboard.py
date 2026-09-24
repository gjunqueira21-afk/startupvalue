from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.api.dependencies import Actor, Database
from app.db.models import (
    Report,
    Scenario,
    ScenarioRevision,
    Simulation,
    SimulationResult,
    SimulationStatus,
    Startup,
)

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


class DashboardAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    simulation_id: str
    startup_id: str
    startup_name: str
    currency: str
    scenario_name: str
    status: str
    seed: int
    simulation_count: int
    model_version: str
    created_at: datetime
    p25: float | None
    p50: float | None
    p75: float | None


class DashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_count: int
    scenario_count: int
    simulation_count: int
    scenario_runs: int
    report_count: int
    recent_analyses: list[DashboardAnalysis]


@router.get("/dashboard", response_model=DashboardResponse)
def read_dashboard(db: Database, actor: Actor) -> DashboardResponse:
    workspace_id = actor.workspace_id
    active_startups = select(Startup.id).where(
        Startup.workspace_id == workspace_id,
        Startup.archived_at.is_(None),
    )
    active_scenarios = select(Scenario.id).where(
        Scenario.workspace_id == workspace_id,
        Scenario.archived_at.is_(None),
        Scenario.startup_id.in_(active_startups),
    )
    company_count = db.scalar(
        select(func.count()).select_from(Startup).where(Startup.id.in_(active_startups))
    ) or 0
    scenario_count = db.scalar(
        select(func.count()).select_from(Scenario).where(Scenario.id.in_(active_scenarios))
    ) or 0
    simulations = (
        select(Simulation.id, Simulation.simulation_count, Simulation.status)
        .join(
            ScenarioRevision,
            (ScenarioRevision.id == Simulation.scenario_revision_id)
            & (ScenarioRevision.workspace_id == workspace_id),
        )
        .where(
            Simulation.workspace_id == workspace_id,
            ScenarioRevision.scenario_id.in_(active_scenarios),
        )
        .subquery()
    )
    simulation_count = db.scalar(select(func.count()).select_from(simulations)) or 0
    scenario_runs = db.scalar(
        select(func.coalesce(func.sum(simulations.c.simulation_count), 0))
        .where(simulations.c.status == SimulationStatus.succeeded)
    ) or 0
    report_count = db.scalar(select(func.count()).select_from(Report).where(
        Report.workspace_id == workspace_id,
    )) or 0

    rows = db.execute(
        select(Simulation, SimulationResult, Scenario, Startup)
        .join(
            ScenarioRevision,
            (ScenarioRevision.id == Simulation.scenario_revision_id)
            & (ScenarioRevision.workspace_id == workspace_id),
        )
        .join(
            Scenario,
            (Scenario.id == ScenarioRevision.scenario_id)
            & (Scenario.workspace_id == workspace_id)
            & Scenario.archived_at.is_(None),
        )
        .join(
            Startup,
            (Startup.id == Scenario.startup_id)
            & (Startup.workspace_id == workspace_id)
            & Startup.archived_at.is_(None),
        )
        .outerjoin(
            SimulationResult,
            (SimulationResult.simulation_id == Simulation.id)
            & (SimulationResult.workspace_id == workspace_id),
        )
        .where(Simulation.workspace_id == workspace_id)
        .order_by(Simulation.created_at.desc(), Simulation.id.desc())
        .limit(20)
    ).all()
    recent_analyses = []
    for simulation, result, scenario, startup in rows:
        percentiles = result.summary.get("percentiles", {}) if result else {}
        recent_analyses.append(
            DashboardAnalysis(
                simulation_id=simulation.id,
                startup_id=startup.id,
                startup_name=startup.name,
                currency=startup.currency,
                scenario_name=scenario.name,
                status=simulation.status.value,
                seed=simulation.seed,
                simulation_count=simulation.simulation_count,
                model_version=simulation.model_version,
                created_at=simulation.created_at,
                p25=percentiles.get("p25"),
                p50=percentiles.get("p50"),
                p75=percentiles.get("p75"),
            )
        )
    return DashboardResponse(
        company_count=company_count,
        scenario_count=scenario_count,
        simulation_count=simulation_count,
        scenario_runs=scenario_runs,
        report_count=report_count,
        recent_analyses=recent_analyses,
    )
