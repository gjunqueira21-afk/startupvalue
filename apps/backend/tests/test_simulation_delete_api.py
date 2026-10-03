"""DELETE /api/v1/simulations/{simulation_id}: delete an analysis and its
persisted artifacts, while leaving the Scenario/Revision/Startup intact.

Reuses the SQLite + CSRF fixture pattern from test_report_api.py /
test_branding_api.py.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.security import hash_password
from app.db.base import Base, get_db
from app.db.models import (
    AuditEvent,
    Report,
    Role,
    Scenario,
    ScenarioRevision,
    Simulation,
    SimulationResult,
    SimulationSamples,
    Startup,
    User,
    WorkspaceMembership,
)
from app.main import app

PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def clients() -> Iterator[tuple[TestClient, TestClient, sessionmaker[Session]]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as owner, TestClient(app) as other:
        yield owner, other, factory
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _signup(client: TestClient, email: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/signup",
        json={"name": "Founder", "email": email, "password": PASSWORD},
    )
    assert response.status_code == 201, response.text
    csrf = client.get("/api/v1/auth/csrf")
    assert csrf.status_code == 200, csrf.text
    client.headers.update({"X-CSRF-Token": csrf.json()["csrf_token"]})
    return response.json()  # type: ignore[no-any-return]


def _login(client: TestClient, email: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    csrf = client.get("/api/v1/auth/csrf")
    assert csrf.status_code == 200, csrf.text
    client.headers.update({"X-CSRF-Token": csrf.json()["csrf_token"]})
    return response.json()  # type: ignore[no-any-return]


def _add_member(
    factory: sessionmaker[Session], *, workspace_id: str, email: str, role: Role
) -> None:
    with factory() as db:
        user = User(name="Member", email=email, password_hash=hash_password(PASSWORD))
        db.add(user)
        db.flush()
        db.add(WorkspaceMembership(workspace_id=workspace_id, user_id=user.id, role=role))
        db.commit()


def _simulate(owner: TestClient, *, suffix: str = "") -> dict[str, object]:
    startup = owner.post(
        "/api/v1/startups",
        json={"name": f"Árvore Analytics{suffix}", "currency": "BRL"},
    )
    assert startup.status_code == 201, startup.text
    scenario = owner.post(
        f"/api/v1/startups/{startup.json()['id']}/scenarios",
        json={"name": "Base Case", "mode": "professional"},
    )
    assert scenario.status_code == 201, scenario.text
    revision = owner.post(
        f"/api/v1/scenarios/{scenario.json()['id']}/revisions",
        json={
            "inputs": {
                "monthly_fcff": [100000.0] * 12,
                "annual_wacc": 0.2,
                "terminal_growth": 0.03,
                "excess_cash": 250000,
                "debt": 100000,
                "uncertainty": {
                    "kind": "lognormal",
                    "mean": 1.0,
                    "coefficient_of_variation": 0.2,
                },
                "failure_probability_horizon": 0.1,
                "liquidation_value": 0,
            }
        },
    )
    assert revision.status_code == 201, revision.text
    simulation = owner.post(
        "/api/v1/simulations",
        json={
            "scenario_revision_id": revision.json()["id"],
            "seed": 471829,
            "simulation_count": 1000,
            "idempotency_key": f"delete-test-run{suffix}",
        },
    )
    assert simulation.status_code == 201, simulation.text
    return simulation.json()  # type: ignore[no-any-return]


def _insert_report_row(factory: sessionmaker[Session], *, result_id: str, workspace_id: str) -> str:
    with factory() as db:
        report = Report(
            workspace_id=workspace_id,
            simulation_result_id=result_id,
            template_version="v1",
            status="ready",
            object_key="reports/test.pdf",
            checksum="deadbeef",
        )
        db.add(report)
        db.commit()
        return report.id


def test_owner_deletes_own_simulation_and_its_artifacts(
    clients: tuple[TestClient, TestClient, sessionmaker[Session]],
) -> None:
    owner, _, factory = clients
    session = _signup(owner, "owner-delete@example.com")
    workspace_id = str(session["workspace_id"])
    saved = _simulate(owner)
    simulation_id = str(saved["simulation_id"])

    with factory() as db:
        result = db.scalar(
            select(SimulationResult).where(SimulationResult.simulation_id == simulation_id)
        )
        assert result is not None
        result_id = result.id
        samples = db.scalar(
            select(SimulationSamples).where(SimulationSamples.simulation_result_id == result_id)
        )
        assert samples is not None

    report_id = _insert_report_row(factory, result_id=result_id, workspace_id=workspace_id)

    response = owner.delete(f"/api/v1/simulations/{simulation_id}")
    assert response.status_code == 204, response.text
    assert response.content == b""

    follow_up = owner.get(f"/api/v1/simulations/{simulation_id}")
    assert follow_up.status_code == 404, follow_up.text
    assert follow_up.json()["detail"] == "simulation_not_found"

    with factory() as db:
        assert db.get(Simulation, simulation_id) is None
        assert db.get(SimulationResult, result_id) is None
        assert (
            db.scalar(
                select(SimulationSamples).where(
                    SimulationSamples.simulation_result_id == result_id
                )
            )
            is None
        )
        assert db.get(Report, report_id) is None

        events = (
            db.execute(
                select(AuditEvent).where(
                    AuditEvent.workspace_id == workspace_id,
                    AuditEvent.action == "simulation.deleted",
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 1
        assert events[0].resource_id == simulation_id


def test_delete_leaves_scenario_revision_and_startup_intact(
    clients: tuple[TestClient, TestClient, sessionmaker[Session]],
) -> None:
    owner, _, factory = clients
    _signup(owner, "owner-keep@example.com")
    saved = _simulate(owner)
    simulation_id = str(saved["simulation_id"])
    revision_id = str(saved["scenario_revision_id"])

    with factory() as db:
        revision = db.get(ScenarioRevision, revision_id)
        assert revision is not None
        scenario = db.get(Scenario, revision.scenario_id)
        assert scenario is not None
        startup = db.get(Startup, scenario.startup_id)
        assert startup is not None

    response = owner.delete(f"/api/v1/simulations/{simulation_id}")
    assert response.status_code == 204, response.text

    with factory() as db:
        assert db.get(ScenarioRevision, revision_id) is not None
        assert db.get(Scenario, revision.scenario_id) is not None  # type: ignore[union-attr]
        assert db.get(Startup, scenario.startup_id) is not None  # type: ignore[union-attr]


def test_analyst_role_cannot_delete_simulation(
    clients: tuple[TestClient, TestClient, sessionmaker[Session]],
) -> None:
    owner, analyst, factory = clients
    session = _signup(owner, "owner-for-analyst@example.com")
    workspace_id = str(session["workspace_id"])
    saved = _simulate(owner)
    simulation_id = str(saved["simulation_id"])

    _add_member(
        factory, workspace_id=workspace_id, email="analyst-member@example.com", role=Role.analyst
    )
    _login(analyst, "analyst-member@example.com")

    response = analyst.delete(f"/api/v1/simulations/{simulation_id}")
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "action_not_allowed"

    # Nothing was deleted.
    still_there = owner.get(f"/api/v1/simulations/{simulation_id}")
    assert still_there.status_code == 200, still_there.text


def test_cross_tenant_delete_returns_404_and_leaves_other_workspace_untouched(
    clients: tuple[TestClient, TestClient, sessionmaker[Session]],
) -> None:
    owner_a, owner_b, factory = clients
    _signup(owner_a, "tenant-a@example.com")
    session_b = _signup(owner_b, "tenant-b@example.com")
    workspace_b = str(session_b["workspace_id"])

    saved_b = _simulate(owner_b, suffix="-b")
    simulation_b_id = str(saved_b["simulation_id"])

    with factory() as db:
        result_b = db.scalar(
            select(SimulationResult).where(SimulationResult.simulation_id == simulation_b_id)
        )
        assert result_b is not None
        result_b_id = result_b.id

    response = owner_a.delete(f"/api/v1/simulations/{simulation_b_id}")
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "simulation_not_found"

    with factory() as db:
        assert db.get(Simulation, simulation_b_id) is not None
        assert db.get(SimulationResult, result_b_id) is not None
        assert (
            db.scalar(
                select(SimulationSamples).where(
                    SimulationSamples.simulation_result_id == result_b_id
                )
            )
            is not None
        )

        events = (
            db.execute(
                select(AuditEvent).where(AuditEvent.workspace_id == workspace_b)
            )
            .scalars()
            .all()
        )
        assert not any(event.action == "simulation.deleted" for event in events)


def test_unknown_simulation_id_returns_404(
    clients: tuple[TestClient, TestClient, sessionmaker[Session]],
) -> None:
    owner, _, _ = clients
    _signup(owner, "owner-unknown@example.com")

    response = owner.delete("/api/v1/simulations/does-not-exist")
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "simulation_not_found"
