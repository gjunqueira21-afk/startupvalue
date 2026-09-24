from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Scenario, ScenarioRevision, Simulation, Startup


def get_startup(db: Session, *, startup_id: str, workspace_id: str) -> Startup | None:
    return db.scalar(
        select(Startup).where(
            Startup.id == startup_id,
            Startup.workspace_id == workspace_id,
            Startup.archived_at.is_(None),
        )
    )


def get_scenario(db: Session, *, scenario_id: str, workspace_id: str) -> Scenario | None:
    return db.scalar(
        select(Scenario).where(
            Scenario.id == scenario_id,
            Scenario.workspace_id == workspace_id,
            Scenario.archived_at.is_(None),
        )
    )


def get_revision(
    db: Session, *, revision_id: str, workspace_id: str
) -> ScenarioRevision | None:
    return db.scalar(
        select(ScenarioRevision).where(
            ScenarioRevision.id == revision_id,
            ScenarioRevision.workspace_id == workspace_id,
        )
    )


def get_simulation(
    db: Session, *, simulation_id: str, workspace_id: str
) -> Simulation | None:
    return db.scalar(
        select(Simulation).where(
            Simulation.id == simulation_id,
            Simulation.workspace_id == workspace_id,
        )
    )
