from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, get_db
from app.main import app


@pytest.fixture
def clients() -> Iterator[tuple[TestClient, TestClient]]:
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
    with TestClient(app) as first, TestClient(app) as second:
        yield first, second
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _signup(client: TestClient, tenant: str) -> None:
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "name": f"Founder {tenant}",
            "email": f"{tenant}@example.com",
            "password": f"strong-password-{tenant}",
            "workspace_name": f"Workspace {tenant}",
        },
    )
    assert response.status_code == 201, response.text
    csrf = client.get("/api/v1/auth/csrf")
    assert csrf.status_code == 200, csrf.text
    client.headers.update({"X-CSRF-Token": csrf.json()["csrf_token"]})


def _build_revision(client: TestClient) -> tuple[str, str, str]:
    startup_response = client.post(
        "/api/v1/startups",
        json={"name": "Acme SaaS", "currency": "BRL", "profile": {"sector": "SaaS"}},
    )
    assert startup_response.status_code == 201, startup_response.text
    startup_id = startup_response.json()["id"]
    scenario_response = client.post(
        f"/api/v1/startups/{startup_id}/scenarios",
        json={"name": "Base", "mode": "professional"},
    )
    assert scenario_response.status_code == 201, scenario_response.text
    scenario_id = scenario_response.json()["id"]
    revision_response = client.post(
        f"/api/v1/scenarios/{scenario_id}/revisions",
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
    assert revision_response.status_code == 201, revision_response.text
    return startup_id, scenario_id, revision_response.json()["id"]


def test_cross_tenant_ids_are_indistinguishable_from_missing(
    clients: tuple[TestClient, TestClient],
) -> None:
    owner, outsider = clients
    _signup(owner, "tenant-a")
    startup_id, scenario_id, revision_id = _build_revision(owner)
    _signup(outsider, "tenant-b")

    assert outsider.get(f"/api/v1/startups/{startup_id}").status_code == 404
    assert outsider.get(f"/api/v1/scenarios/{scenario_id}").status_code == 404
    assert (
        outsider.post(
            f"/api/v1/startups/{startup_id}/scenarios",
            json={"name": "Stolen", "mode": "simple"},
        ).status_code
        == 404
    )
    assert (
        outsider.post(
            "/api/v1/simulations",
            json={
                "scenario_revision_id": revision_id,
                "seed": 471829,
                "simulation_count": 1000,
                "idempotency_key": "outsider-run-0001",
            },
        ).status_code
        == 404
    )
    assert outsider.get("/api/v1/startups").json() == []


def test_simulation_is_reproducible_persisted_and_idempotent(
    clients: tuple[TestClient, TestClient],
) -> None:
    owner, _ = clients
    _signup(owner, "tenant-a")
    _, _, revision_id = _build_revision(owner)
    request = {
        "scenario_revision_id": revision_id,
        "seed": 471829,
        "simulation_count": 1000,
        "idempotency_key": "valuation-run-0001",
    }
    first = owner.post("/api/v1/simulations", json=request)
    second = owner.post("/api/v1/simulations", json=request)
    assert first.status_code == second.status_code == 201
    first_body = first.json()
    second_body = second.json()
    assert first_body["simulation_id"] == second_body["simulation_id"]
    assert first_body["result_hash"] == second_body["result_hash"]
    assert first_body["summary"] == second_body["summary"]
    assert first_body["status"] == "succeeded"
    assert first_body["execution"] == "synchronous"
    assert first_body["queue_status"] == "not_configured"
    assert first_body["summary"]["percentiles"]["p25"] <= first_body["summary"][
        "percentiles"
    ]["p50"]
    recovered = owner.get(f"/api/v1/simulations/{first_body['simulation_id']}")
    assert recovered.status_code == 200
    assert recovered.json() == first_body
