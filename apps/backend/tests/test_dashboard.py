from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes.dashboard import read_dashboard
from app.db.base import Base
from app.db.models import (
    Report,
    Role,
    Scenario,
    ScenarioRevision,
    Simulation,
    SimulationResult,
    SimulationStatus,
    Startup,
    User,
    Workspace,
)
from app.services.auth import CurrentActor


def _actor(workspace_id: str, user_id: str) -> CurrentActor:
    return CurrentActor(
        user_id=user_id,
        workspace_id=workspace_id,
        role=Role.owner,
        name="Founder",
        email="founder@example.com",
        session_id="session",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )


def _seed_analysis(db: Session, suffix: str) -> tuple[str, str, str]:
    workspace = Workspace(name=f"Workspace {suffix}")
    user = User(name=f"Founder {suffix}", email=f"{suffix}@example.com", password_hash="hash")
    db.add_all([workspace, user])
    db.flush()
    startup = Startup(workspace_id=workspace.id, name=f"Startup {suffix}", currency="BRL")
    db.add(startup)
    db.flush()
    scenario = Scenario(workspace_id=workspace.id, startup_id=startup.id, name="Base")
    db.add(scenario)
    db.flush()
    revision = ScenarioRevision(
        workspace_id=workspace.id,
        scenario_id=scenario.id,
        revision_no=1,
        canonical_inputs={},
        input_hash=suffix,
        created_by=user.id,
    )
    db.add(revision)
    db.flush()
    simulation = Simulation(
        workspace_id=workspace.id,
        scenario_revision_id=revision.id,
        model_version="3.0.0",
        tax_version="1.0.0",
        seed=471829,
        simulation_count=1000,
        status=SimulationStatus.succeeded,
        idempotency_key=suffix,
    )
    db.add(simulation)
    db.flush()
    result = SimulationResult(
        workspace_id=workspace.id,
        simulation_id=simulation.id,
        schema_version="1",
        summary={"percentiles": {"p25": 5_000_000, "p50": 8_000_000, "p75": 12_000_000}},
        result_hash=suffix,
        samples_object_key="",
        samples_hash="",
    )
    db.add(result)
    db.flush()
    db.add(
        Report(
            workspace_id=workspace.id,
            simulation_result_id=result.id,
            template_version="1",
            status="ready",
        )
    )
    db.commit()
    return workspace.id, user.id, simulation.id


def test_dashboard_uses_persisted_result_and_isolates_workspaces() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            first_workspace, first_user, first_simulation = _seed_analysis(db, "first")
            second_workspace, second_user, second_simulation = _seed_analysis(db, "second")
            first = read_dashboard(db, _actor(first_workspace, first_user))
            second = read_dashboard(db, _actor(second_workspace, second_user))
            assert (first.company_count, first.scenario_count, first.simulation_count) == (1, 1, 1)
            assert (first.scenario_runs, first.report_count) == (1000, 1)
            assert [row.simulation_id for row in first.recent_analyses] == [first_simulation]
            assert first.recent_analyses[0].p50 == 8_000_000
            assert [row.simulation_id for row in second.recent_analyses] == [second_simulation]
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
