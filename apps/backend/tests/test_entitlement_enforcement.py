"""Server-side enforcement of plan entitlements: scenario counts, startup caps,

the target-plan section and implied multiples. Reuses the SQLite + CSRF
fixture pattern established in test_entitlements.py / test_api_decision.py.
"""

from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO

import httpx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.entitlements import PlanTier, set_workspace_plan
from app.db.base import Base, get_db
from app.main import app


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


def _post(client: TestClient, path: str, payload: dict[str, object]) -> httpx.Response:
    token_response = client.get("/api/v1/auth/csrf")
    headers = (
        {"X-CSRF-Token": token_response.json()["csrf_token"]}
        if token_response.status_code == 200
        else {}
    )
    return client.post(path, json=payload, headers=headers)


def _signup(client: TestClient, email: str) -> dict[str, object]:
    response = _post(
        client,
        "/api/v1/auth/signup",
        {"name": "Founder", "email": email, "password": "strong-password-123"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _set_plan(factory: sessionmaker[Session], workspace_id: str, plan: PlanTier) -> None:
    with factory() as db:
        set_workspace_plan(db, workspace_id=workspace_id, plan=plan, actor_id=None)
        db.commit()


def _create_revision(client: TestClient, name: str = "Co") -> str:
    startup = _post(client, "/api/v1/startups", {"name": name})
    assert startup.status_code == 201, startup.text
    scenario = _post(
        client,
        f"/api/v1/startups/{startup.json()['id']}/scenarios",
        {"name": "Base", "mode": "professional"},
    )
    assert scenario.status_code == 201, scenario.text
    revision = _post(
        client,
        f"/api/v1/scenarios/{scenario.json()['id']}/revisions",
        {
            "inputs": {
                "monthly_fcff": [100_000.0] * 12,
                "annual_wacc": 0.2,
                "terminal_growth": 0.03,
                "uncertainty": {
                    "kind": "lognormal",
                    "mean": 1.0,
                    "coefficient_of_variation": 0.25,
                },
                "failure_probability_horizon": 0.1,
            }
        },
    )
    assert revision.status_code == 201, revision.text
    return str(revision.json()["id"])


def _create_structured_revision(client: TestClient, name: str = "Structured Co") -> str:
    startup = _post(client, "/api/v1/startups", {"name": name})
    assert startup.status_code == 201, startup.text
    scenario = _post(
        client,
        f"/api/v1/startups/{startup.json()['id']}/scenarios",
        {"name": "Base", "mode": "professional"},
    )
    assert scenario.status_code == 201, scenario.text
    revision = _post(
        client,
        f"/api/v1/scenarios/{scenario.json()['id']}/revisions",
        {
            "inputs": {
                "monthly_revenue": [100.0] * 60,
                "monthly_opex": [20.0] * 60,
                "monthly_capex": [10.0] * 60,
                "gross_margin": 0.5,
                "revenue_uncertainty": {"kind": "constant", "value": 1.0},
                "cost_uncertainty": {"kind": "constant", "value": 1.0},
                "margin_uncertainty_pp": 0.0,
                "serial_correlation": 0.65,
                "persistent_weight": 0.6,
                "annual_wacc": 0.2,
                "terminal_growth": 0.03,
                "failure_probability_horizon": 0.0,
            }
        },
    )
    assert revision.status_code == 201, revision.text
    return str(revision.json()["id"])


def _run_simulation(
    client: TestClient, revision_id: str, simulation_count: int, seed: int = 471829
) -> httpx.Response:
    return _post(
        client,
        "/api/v1/simulations",
        {
            "scenario_revision_id": revision_id,
            "seed": seed,
            "simulation_count": simulation_count,
        },
    )


# --- scenario count boundaries ----------------------------------------------


def test_free_workspace_allows_preset_at_limit_and_blocks_over_preset(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    _signup(client, "free-scenarios@example.com")
    revision_id = _create_revision(client)

    at_limit = _run_simulation(client, revision_id, 1000)
    assert at_limit.status_code == 201, at_limit.text

    over_limit = _run_simulation(client, revision_id, 5000)
    assert over_limit.status_code == 403, over_limit.text
    assert over_limit.json()["detail"] == "plan_limit_scenarios"


def test_free_workspace_blocks_the_largest_preset_too(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    """The entitlement check fires for ANY over-cap preset, not only the next

    one up: a client sending the largest valid preset (25.000) is still
    capped at the plan's limit, proving this is a business-rule 403, not an
    accidental edge of the schema validation.
    """
    client, _ = api
    _signup(client, "free-scenarios-forged@example.com")
    revision_id = _create_revision(client)

    forged = _run_simulation(client, revision_id, 25_000)
    assert forged.status_code == 403, forged.text
    assert forged.json()["detail"] == "plan_limit_scenarios"


def test_empresario_workspace_allows_preset_at_limit_and_blocks_over_preset(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    session = _signup(client, "empresario-scenarios@example.com")
    _set_plan(factory, str(session["workspace_id"]), PlanTier.empresario)
    revision_id = _create_revision(client)

    at_limit = _run_simulation(client, revision_id, 10_000)
    assert at_limit.status_code == 201, at_limit.text

    over_limit = _run_simulation(client, revision_id, 25_000)
    assert over_limit.status_code == 403, over_limit.text
    assert over_limit.json()["detail"] == "plan_limit_scenarios"


def test_consultor_workspace_allows_the_largest_preset(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    session = _signup(client, "consultor-scenarios@example.com")
    _set_plan(factory, str(session["workspace_id"]), PlanTier.consultor)
    revision_id = _create_revision(client)

    at_limit = _run_simulation(client, revision_id, 25_000)
    assert at_limit.status_code == 201, at_limit.text


def test_non_preset_scenario_count_is_rejected_by_the_literal_contract(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    """``simulation_count`` is a fixed product contract (PRODUCT_SPEC §8):

    only 1.000/5.000/10.000/25.000 are valid; anything else 422s at the
    schema layer, before any entitlement check runs.
    """
    client, _ = api
    _signup(client, "non-preset-scenarios@example.com")
    revision_id = _create_revision(client)

    response = _run_simulation(client, revision_id, 1001)
    assert response.status_code == 422, response.text


# --- startup count boundaries -----------------------------------------------


def test_free_workspace_limits_to_one_startup(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    _signup(client, "free-startups@example.com")

    first = _post(client, "/api/v1/startups", {"name": "First Co"})
    assert first.status_code == 201, first.text

    second = _post(client, "/api/v1/startups", {"name": "Second Co"})
    assert second.status_code == 403, second.text
    assert second.json()["detail"] == "plan_limit_startups"


def test_empresario_workspace_limits_to_five_startups(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    session = _signup(client, "empresario-startups@example.com")
    _set_plan(factory, str(session["workspace_id"]), PlanTier.empresario)

    for index in range(5):
        response = _post(client, "/api/v1/startups", {"name": f"Co {index}"})
        assert response.status_code == 201, response.text

    sixth = _post(client, "/api/v1/startups", {"name": "Co 6"})
    assert sixth.status_code == 403, sixth.text
    assert sixth.json()["detail"] == "plan_limit_startups"


# --- target plan section gating ---------------------------------------------


def test_free_workspace_target_response_omits_plan(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    _signup(client, "free-target@example.com")
    revision_id = _create_revision(client)
    run = _run_simulation(client, revision_id, 1000)
    assert run.status_code == 201, run.text
    body = run.json()
    p50 = body["summary"]["percentiles"]["p50"]

    target = client.get(
        f"/api/v1/simulations/{body['simulation_id']}/target", params={"value": p50}
    )
    assert target.status_code == 200, target.text
    assert target.json()["plan"] is None


def test_empresario_workspace_target_response_includes_plan(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    session = _signup(client, "empresario-target@example.com")
    _set_plan(factory, str(session["workspace_id"]), PlanTier.empresario)
    revision_id = _create_revision(client)
    run = _run_simulation(client, revision_id, 1000)
    assert run.status_code == 201, run.text
    body = run.json()
    p50 = body["summary"]["percentiles"]["p50"]

    target = client.get(
        f"/api/v1/simulations/{body['simulation_id']}/target", params={"value": p50}
    )
    assert target.status_code == 200, target.text
    assert target.json()["plan"] is not None


# --- implied multiples gating -----------------------------------------------


def test_free_workspace_summary_strips_implied_multiples(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    _signup(client, "free-multiples@example.com")
    revision_id = _create_revision(client)
    run = _run_simulation(client, revision_id, 1000)
    assert run.status_code == 201, run.text
    assert run.json()["summary"]["implied_multiples"] is None

    reread = client.get(f"/api/v1/simulations/{run.json()['simulation_id']}")
    assert reread.status_code == 200, reread.text
    assert reread.json()["summary"]["implied_multiples"] is None


def test_empresario_workspace_summary_keeps_implied_multiples(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    session = _signup(client, "empresario-multiples@example.com")
    _set_plan(factory, str(session["workspace_id"]), PlanTier.empresario)
    revision_id = _create_revision(client)
    run = _run_simulation(client, revision_id, 1000)
    assert run.status_code == 201, run.text
    assert run.json()["summary"]["implied_multiples"] is not None


# --- PDF report gating (target plan section + multiples thread through) ----


def test_free_workspace_report_pdf_omits_target_plan_section(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    _signup(client, "free-report@example.com")
    revision_id = _create_structured_revision(client)
    run = _run_simulation(client, revision_id, 1000)
    assert run.status_code == 201, run.text
    body = run.json()
    p50 = body["summary"]["percentiles"]["p50"]

    report = client.get(
        f"/api/v1/simulations/{body['simulation_id']}/report.pdf", params={"target": p50}
    )
    assert report.status_code == 200, report.text
    text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(report.content)).pages
    )
    assert "Target Plan" not in text


def test_empresario_workspace_report_pdf_includes_target_plan_section(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    session = _signup(client, "empresario-report@example.com")
    _set_plan(factory, str(session["workspace_id"]), PlanTier.empresario)
    revision_id = _create_structured_revision(client)
    run = _run_simulation(client, revision_id, 1000)
    assert run.status_code == 201, run.text
    body = run.json()
    p50 = body["summary"]["percentiles"]["p50"]

    report = client.get(
        f"/api/v1/simulations/{body['simulation_id']}/report.pdf", params={"target": p50}
    )
    assert report.status_code == 200, report.text
    text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(report.content)).pages
    )
    assert "Target Plan" in text
