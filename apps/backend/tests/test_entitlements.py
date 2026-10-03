from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.rate_limit import clear_local_for_tests
from app.core.entitlements import Entitlements, PlanTier, entitlements_for, set_workspace_plan
from app.db.base import Base, get_db
from app.db.models import AuditEvent, Workspace
from app.main import app


def test_free_plan_matrix() -> None:
    free = entitlements_for("free")
    assert free == Entitlements(
        plan=PlanTier.free,
        max_startups=1,
        max_scenarios_per_run=1_000,
        white_label=False,
        full_report=False,
        target_plan_section=False,
        implied_multiples=False,
    )


def test_empresario_plan_matrix() -> None:
    empresario = entitlements_for("empresario")
    assert empresario == Entitlements(
        plan=PlanTier.empresario,
        max_startups=5,
        max_scenarios_per_run=10_000,
        white_label=False,
        full_report=True,
        target_plan_section=True,
        implied_multiples=True,
    )


def test_consultor_plan_matrix() -> None:
    consultor = entitlements_for("consultor")
    assert consultor == Entitlements(
        plan=PlanTier.consultor,
        max_startups=10,
        max_scenarios_per_run=25_000,
        white_label=True,
        full_report=True,
        target_plan_section=True,
        implied_multiples=True,
    )


def test_escritorio_plan_matrix() -> None:
    escritorio = entitlements_for("escritorio")
    assert escritorio == Entitlements(
        plan=PlanTier.escritorio,
        max_startups=None,
        max_scenarios_per_run=25_000,
        white_label=True,
        full_report=True,
        target_plan_section=True,
        implied_multiples=True,
    )
    assert escritorio.max_startups is None


def test_unknown_or_missing_plan_defaults_to_free() -> None:
    assert entitlements_for("nonsense").plan is PlanTier.free
    assert entitlements_for(None).plan is PlanTier.free


@pytest.fixture
def db_session() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_set_workspace_plan_persists_and_audits(
    db_session: sessionmaker[Session],
) -> None:
    with db_session() as db:
        workspace = Workspace(name="Audited Workspace")
        db.add(workspace)
        db.flush()
        db.commit()
        workspace_id = workspace.id

    with db_session() as db:
        set_workspace_plan(
            db, workspace_id=workspace_id, plan=PlanTier.consultor, actor_id="actor-1"
        )
        db.commit()

    with db_session() as db:
        reloaded = db.get(Workspace, workspace_id)
        assert reloaded is not None
        assert reloaded.plan == "consultor"
        event = db.scalar(
            select(AuditEvent).where(AuditEvent.action == "workspace.plan_changed")
        )
        assert event is not None
        assert event.resource_type == "workspace"
        assert event.workspace_id == workspace_id
        assert event.actor_id == "actor-1"
        assert event.metadata_redacted == {"plan": "consultor"}


@pytest.fixture
def api() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    clear_local_for_tests()
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
    with TestClient(app) as client:
        yield client, factory
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
    clear_local_for_tests()


def _signup(client: TestClient, suffix: str = "one") -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "name": f"Founder {suffix}",
            "email": f"founder-{suffix}@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_entitlements_endpoint_returns_free_defaults_for_fresh_workspace(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    _signup(client)
    response = client.get("/api/v1/workspace/entitlements")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "plan": "free",
        "max_startups": 1,
        "max_scenarios_per_run": 1_000,
        "white_label": False,
        "full_report": False,
        "target_plan_section": False,
        "implied_multiples": False,
    }


def test_entitlements_endpoint_requires_auth(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    response = client.get("/api/v1/workspace/entitlements")
    assert response.status_code == 401
