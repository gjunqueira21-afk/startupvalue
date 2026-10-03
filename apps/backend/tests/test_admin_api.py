"""Platform admin backend: flag-gated routes, overview counts, waitlist
export and workspace plan changes.

Reuses the SQLite + TestClient fixture pattern from test_branding_api.py.
The platform admin flag itself is never settable over HTTP; tests grant it
by writing directly to the test database, mirroring what
``scripts/set_admin.py`` does against a real one.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.entitlements import PlanTier, set_workspace_plan
from app.db.base import Base, get_db
from app.db.models import AuditEvent, Simulation, SimulationStatus, Startup, User, WaitlistEntry
from app.main import app

PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def api() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
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


def _signup(client: TestClient, email: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/signup",
        json={"name": "Founder", "email": email, "password": PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client: TestClient, email: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def _grant_admin(factory: sessionmaker[Session], user_id: str) -> None:
    with factory() as db:
        user = db.get(User, user_id)
        assert user is not None
        user.is_platform_admin = True
        db.commit()


def _set_plan(factory: sessionmaker[Session], workspace_id: str, plan: PlanTier) -> None:
    with factory() as db:
        set_workspace_plan(db, workspace_id=workspace_id, plan=plan, actor_id=None)
        db.commit()


def _seed_waitlist(factory: sessionmaker[Session], email: str = "lead@example.com") -> None:
    with factory() as db:
        db.add(WaitlistEntry(email=email, plan_interest="consultor", source="landing"))
        db.commit()


def _overview(client: TestClient) -> httpx.Response:
    return client.get("/api/v1/admin/overview")


def _waitlist(client: TestClient, format: str | None = None) -> httpx.Response:
    params = {"format": format} if format else None
    return client.get("/api/v1/admin/waitlist", params=params)


def _workspaces(client: TestClient, email: str) -> httpx.Response:
    return client.get("/api/v1/admin/workspaces", params={"email": email})


def _change_plan(client: TestClient, workspace_id: str, plan: str) -> httpx.Response:
    headers = _csrf_headers(client) if client.cookies else {}
    return client.post(
        f"/api/v1/admin/workspaces/{workspace_id}/plan",
        json={"plan": plan},
        headers=headers,
    )


# --- gating: every route 403s a non-admin -----------------------------------


def test_non_admin_gets_403_on_overview(api: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, _ = api
    _signup(client, "plain-user@example.com")
    response = _overview(client)
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "admin_only"


def test_non_admin_gets_403_on_waitlist(api: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, _ = api
    _signup(client, "plain-user-2@example.com")
    response = _waitlist(client)
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "admin_only"


def test_non_admin_gets_403_on_workspace_search(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    _signup(client, "plain-user-3@example.com")
    response = _workspaces(client, "someone@example.com")
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "admin_only"


def test_non_admin_gets_403_on_plan_change(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    session = _signup(client, "plain-user-4@example.com")
    response = _change_plan(client, str(session["workspace_id"]), "consultor")
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "admin_only"


def test_unauthenticated_gets_401_on_admin_routes(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    assert _overview(client).status_code == 401
    assert _waitlist(client).status_code == 401
    assert _workspaces(client, "x@example.com").status_code == 401
    assert _change_plan(client, "whatever", "free").status_code == 401


# --- overview counts, business metadata only ---------------------------------


def test_overview_counts_and_no_financial_data_leak(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    admin_session = _signup(client, "admin@example.com")
    _grant_admin(factory, str(admin_session["user_id"]))

    other_session = _signup(client, "owner-two@example.com")
    _set_plan(factory, str(admin_session["workspace_id"]), PlanTier.free)
    _set_plan(factory, str(other_session["workspace_id"]), PlanTier.consultor)
    _seed_waitlist(factory)
    _login(client, "admin@example.com")

    # A simulation row exists, but overview must only ever expose a count.
    with factory() as db:
        db.add(
            Simulation(
                workspace_id=str(admin_session["workspace_id"]),
                scenario_revision_id="rev-1",
                model_version="v1",
                tax_version="v1",
                seed=1,
                simulation_count=1000,
                status=SimulationStatus.succeeded,
                idempotency_key="key-1",
            )
        )
        db.commit()

    response = _overview(client)
    assert response.status_code == 200, response.text
    body = response.json()

    assert set(body.keys()) == {
        "users",
        "workspaces_by_plan",
        "startups",
        "simulations",
        "simulations_last_7d",
        "reports",
        "waitlist_count",
    }
    assert set(body["workspaces_by_plan"].keys()) == {
        "free",
        "empresario",
        "consultor",
        "escritorio",
    }
    assert body["users"] == 2
    assert body["workspaces_by_plan"] == {
        "free": 1,
        "empresario": 0,
        "consultor": 1,
        "escritorio": 0,
    }
    assert body["startups"] == 0
    assert body["simulations"] == 1
    assert body["simulations_last_7d"] == 1
    assert body["reports"] == 0
    assert body["waitlist_count"] == 1

    # No scenario inputs, simulation summaries/results, report bytes or
    # branding content anywhere in the serialized response.
    for forbidden in ("summary", "result_hash", "canonical_inputs", "object_key", "logo"):
        assert forbidden not in body


def test_simulations_last_7d_excludes_older_rows(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    admin_session = _signup(client, "admin-old@example.com")
    _grant_admin(factory, str(admin_session["user_id"]))

    with factory() as db:
        db.add(
            Simulation(
                workspace_id=str(admin_session["workspace_id"]),
                scenario_revision_id="rev-old",
                model_version="v1",
                tax_version="v1",
                seed=1,
                simulation_count=1000,
                status=SimulationStatus.succeeded,
                idempotency_key="key-old",
                created_at=datetime.now(UTC) - timedelta(days=10),
            )
        )
        db.commit()

    response = _overview(client)
    assert response.status_code == 200, response.text
    assert response.json()["simulations"] == 1
    assert response.json()["simulations_last_7d"] == 0


# --- waitlist: JSON and CSV export -------------------------------------------


def test_waitlist_json_listing(api: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, factory = api
    admin_session = _signup(client, "admin-waitlist@example.com")
    _grant_admin(factory, str(admin_session["user_id"]))
    _seed_waitlist(factory, "lead-json@example.com")

    response = _waitlist(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert body[0]["email"] == "lead-json@example.com"
    assert body[0]["plan_interest"] == "consultor"
    assert body[0]["source"] == "landing"


def test_waitlist_csv_export_content_type_and_header(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    admin_session = _signup(client, "admin-csv@example.com")
    _grant_admin(factory, str(admin_session["user_id"]))
    _seed_waitlist(factory, "lead-csv@example.com")

    response = _waitlist(client, format="csv")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == 'attachment; filename="waitlist.csv"'
    lines = response.text.splitlines()
    assert lines[0] == "email,plan_interest,source,created_at"
    assert lines[1].startswith("lead-csv@example.com,consultor,landing,")


def test_waitlist_csv_export_neutralizes_formula_injection(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    """A malicious email/source starting with '=' must be prefixed with a
    leading single quote so Excel/Sheets treats the cell as text instead of
    evaluating it as a formula (or DDE payload) on open.
    """
    client, factory = api
    admin_session = _signup(client, "admin-csv-injection@example.com")
    _grant_admin(factory, str(admin_session["user_id"]))
    with factory() as db:
        db.add(
            WaitlistEntry(
                email="=1+1@x.co",
                plan_interest="consultor",
                source='=HYPERLINK("http://evil")',
            )
        )
        db.commit()

    response = _waitlist(client, format="csv")
    assert response.status_code == 200, response.text
    lines = response.text.splitlines()
    assert lines[0] == "email,plan_interest,source,created_at"
    row = next(csv.reader([lines[1]]))
    assert row[0] == "'=1+1@x.co"
    assert row[1] == "consultor"
    assert row[2] == "'=HYPERLINK(\"http://evil\")"


def test_waitlist_csv_export_leaves_normal_entry_unchanged(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    admin_session = _signup(client, "admin-csv-normal@example.com")
    _grant_admin(factory, str(admin_session["user_id"]))
    _seed_waitlist(factory, "normal-lead@example.com")

    response = _waitlist(client, format="csv")
    assert response.status_code == 200, response.text
    lines = response.text.splitlines()
    row = next(csv.reader([lines[1]]))
    assert row[0] == "normal-lead@example.com"
    assert row[1] == "consultor"
    assert row[2] == "landing"


# --- workspace search by member email ----------------------------------------


def test_workspace_search_by_member_email(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    admin_session = _signup(client, "admin-search@example.com")
    _grant_admin(factory, str(admin_session["user_id"]))

    target_session = _signup(client, "target-member@example.com")
    target_workspace_id = str(target_session["workspace_id"])
    _set_plan(factory, target_workspace_id, PlanTier.empresario)
    with factory() as db:
        db.add(Startup(workspace_id=target_workspace_id, name="Acme", currency="BRL"))
        db.add(Startup(workspace_id=target_workspace_id, name="Acme 2", currency="BRL"))
        db.commit()
    _login(client, "admin-search@example.com")

    response = _workspaces(client, "Target-Member@Example.com")
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert set(body[0].keys()) == {"id", "plan", "created_at", "startup_count", "member_email"}
    assert body[0]["id"] == target_workspace_id
    assert body[0]["plan"] == "empresario"
    assert body[0]["startup_count"] == 2
    assert body[0]["member_email"] == "target-member@example.com"


def test_workspace_search_no_match_returns_empty_list(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    admin_session = _signup(client, "admin-no-match@example.com")
    _grant_admin(factory, str(admin_session["user_id"]))

    response = _workspaces(client, "nobody@example.com")
    assert response.status_code == 200, response.text
    assert response.json() == []


# --- plan changes: persist + audited -----------------------------------------


def test_plan_change_persists_and_audits_with_actor_id(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    admin_session = _signup(client, "admin-plan@example.com")
    _grant_admin(factory, str(admin_session["user_id"]))

    target_session = _signup(client, "target-plan@example.com")
    target_workspace_id = str(target_session["workspace_id"])
    _login(client, "admin-plan@example.com")

    response = _change_plan(client, target_workspace_id, "consultor")
    assert response.status_code == 200, response.text
    assert response.json() == {"id": target_workspace_id, "plan": "consultor"}

    with factory() as db:
        from app.db.models import Workspace

        workspace = db.get(Workspace, target_workspace_id)
        assert workspace is not None
        assert workspace.plan == "consultor"

        event = db.scalar(
            select(AuditEvent).where(AuditEvent.action == "workspace.plan_changed")
        )
        assert event is not None
        assert event.resource_type == "workspace"
        assert event.resource_id == target_workspace_id
        assert event.actor_id == str(admin_session["user_id"])
        assert event.metadata_redacted == {"plan": "consultor"}


def test_plan_change_unknown_workspace_is_404(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    admin_session = _signup(client, "admin-plan-404@example.com")
    _grant_admin(factory, str(admin_session["user_id"]))

    response = _change_plan(client, "00000000-0000-0000-0000-000000000000", "consultor")
    assert response.status_code == 404, response.text


def test_plan_change_invalid_plan_is_422(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    admin_session = _signup(client, "admin-plan-422@example.com")
    _grant_admin(factory, str(admin_session["user_id"]))

    response = _change_plan(client, str(admin_session["workspace_id"]), "enterprise")
    assert response.status_code == 422, response.text


# --- /auth/me reflects the flag ----------------------------------------------


def test_auth_me_defaults_to_false(api: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, _ = api
    session = _signup(client, "normal-me@example.com")
    assert session["is_platform_admin"] is False

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200, response.text
    assert response.json()["is_platform_admin"] is False


def test_auth_me_reflects_grant(api: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, factory = api
    session = _signup(client, "soon-admin@example.com")
    _grant_admin(factory, str(session["user_id"]))

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200, response.text
    assert response.json()["is_platform_admin"] is True


# --- no HTTP path can grant the flag -----------------------------------------


def test_no_http_path_can_set_the_admin_flag(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    session = _signup(client, "cannot-self-grant@example.com")
    # SignupRequest/ApiModel forbid extra fields, so attempting to smuggle
    # the flag through signup is rejected outright rather than ignored.
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Attacker",
            "email": "attacker@example.com",
            "password": PASSWORD,
            "is_platform_admin": True,
        },
    )
    assert response.status_code == 422, response.text
    assert session["is_platform_admin"] is False
