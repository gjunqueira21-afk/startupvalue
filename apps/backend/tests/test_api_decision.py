from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, get_db
from app.db.models import SimulationResult, SimulationSamples
from app.main import app


@pytest.fixture
def clients() -> Iterator[tuple[TestClient, TestClient, sessionmaker[Session]]]:
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as owner, TestClient(app) as outsider:
        yield owner, outsider, factory
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _post(client: TestClient, path: str, payload: dict[str, object]) -> dict[str, object]:
    token_response = client.get("/api/v1/auth/csrf")
    headers = (
        {"X-CSRF-Token": token_response.json()["csrf_token"]}
        if token_response.status_code == 200
        else {}
    )
    response = client.post(path, json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _run(client: TestClient, email: str) -> dict[str, object]:
    _post(
        client,
        "/api/v1/auth/signup",
        {"name": "Decision Founder", "email": email, "password": "strong-password-123"},
    )
    startup = _post(client, "/api/v1/startups", {"name": "Decision Co"})
    scenario = _post(
        client,
        f"/api/v1/startups/{startup['id']}/scenarios",
        {"name": "Base", "mode": "professional"},
    )
    revision = _post(
        client,
        f"/api/v1/scenarios/{scenario['id']}/revisions",
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
    return _post(
        client,
        "/api/v1/simulations",
        {"scenario_revision_id": revision["id"], "seed": 471829, "simulation_count": 1000},
    )


def test_decision_reads_persisted_vectors_and_is_workspace_scoped(
    clients: tuple[TestClient, TestClient, sessionmaker[Session]], monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, outsider, factory = clients
    run = _run(owner, "decision-owner@example.com")
    simulation_id = str(run["simulation_id"])
    summary = run["summary"]
    assert isinstance(summary, dict)
    histogram = summary["histogram"]
    assert isinstance(histogram, dict)
    assert sum(histogram["counts"]) == 1000
    assert len(histogram["edges"]) == len(histogram["counts"]) + 1

    with factory() as db:
        snapshots = db.scalars(select(SimulationSamples)).all()
        assert len(snapshots) == 1
        assert snapshots[0].scenario_count == 1000
        assert snapshots[0].factor_names[0] == "valuation"

    def fail_if_resampled(*args: object, **kwargs: object) -> None:
        raise AssertionError("decision request resampled Monte Carlo")

    monkeypatch.setattr(
        "app.services.valuation_model.simulate_simple_cash_flows", fail_if_resampled
    )
    decision_response = owner.get(f"/api/v1/simulations/{simulation_id}/decision")
    assert decision_response.status_code == 200, decision_response.text
    decision = decision_response.json()
    assert decision["result_hash"] == run["result_hash"]
    assert decision["method"] == "spearman+srrc"
    assert decision["method_version"] == "drivers-v1"
    assert decision["scenario_count"] == 1000
    assert 0.0 <= decision["r_squared"] <= 1.0
    factor = next(d for d in decision["drivers"] if d["name"] == "scenario_factor_mean")
    assert factor["label"] == "Fluxo de caixa vs. plano"
    assert factor["unit"] == "multiplier"
    assert factor["direction"] == "positive"
    assert factor["srrc"] is not None and factor["contribution"] is not None
    assert all(driver["count"] == 1000 for driver in decision["drivers"])
    assert decision["drivers"] == [
        {**item, "count": 1000, "label": d["label"], "unit": d["unit"]}
        for item, d in zip(summary["drivers"]["items"], decision["drivers"], strict=True)
    ]
    uncertainty = summary["uncertainty"]
    assert uncertainty["rule_version"] == "uncertainty-v1"
    tornado = {item["parameter"]: item for item in decision["tornado"]["items"]}
    assert decision["tornado"]["method_version"] == "tornado-v1"
    assert tornado["annual_wacc"]["label"] == "WACC"
    assert tornado["annual_wacc"]["unit"] == "ratio"
    assert tornado["failure_probability"]["label"] == "Probabilidade de encerramento"
    assert tornado["annual_wacc"]["value_at_low"] > tornado["annual_wacc"]["value_at_high"]
    assert summary["uncertainty_label"] == uncertainty["label"]

    p50 = summary["percentiles"]["p50"]
    target_response = owner.get(
        f"/api/v1/simulations/{simulation_id}/target", params={"value": p50}
    )
    assert target_response.status_code == 200, target_response.text
    target = target_response.json()
    assert target["hit_count"] + target["miss_count"] == 1000
    assert target["probability"] == target["hit_count"] / 1000
    assert target["wilson95_low"] <= target["probability"] <= target["wilson95_high"]
    assert target["comparisons"]
    assert target["result_hash"] == run["result_hash"]
    failure = next(c for c in target["comparisons"] if c["name"] == "failure_state")
    assert failure["label"] == "Encerramento das operações"
    assert failure["unit"] == "binary"
    assert failure["role"] == "driver"

    _post(
        outsider,
        "/api/v1/auth/signup",
        {
            "name": "Other Founder",
            "email": "decision-outsider@example.com",
            "password": "strong-password-123",
        },
    )
    assert outsider.get(f"/api/v1/simulations/{simulation_id}/decision").status_code == 404
    assert outsider.get(
        f"/api/v1/simulations/{simulation_id}/target", params={"value": p50}
    ).status_code == 404


def test_target_handles_empty_subsets_and_detects_snapshot_tampering(
    clients: tuple[TestClient, TestClient, sessionmaker[Session]],
) -> None:
    owner, _, factory = clients
    run = _run(owner, "target-owner@example.com")
    simulation_id = str(run["simulation_id"])
    summary = run["summary"]
    assert isinstance(summary, dict)
    target_response = owner.get(
        f"/api/v1/simulations/{simulation_id}/target",
        params={"value": summary["maximum"] + 1},
    )
    assert target_response.status_code == 200, target_response.text
    result = target_response.json()
    assert result["hit_count"] == 0
    assert result["probability"] == 0
    assert all(item["hit"]["reason"] == "empty_subset" for item in result["comparisons"])
    assert owner.get(
        f"/api/v1/simulations/{simulation_id}/target", params={"value": "NaN"}
    ).status_code == 422

    with factory() as db:
        snapshot = db.scalar(select(SimulationSamples))
        assert snapshot is not None
        snapshot.payload = b"tampered"
        db.commit()
    assert owner.get(f"/api/v1/simulations/{simulation_id}/decision").status_code == 500


def test_snapshot_is_reproducible_for_same_revision_seed_and_count(
    clients: tuple[TestClient, TestClient, sessionmaker[Session]],
) -> None:
    owner, _, factory = clients
    first = _run(owner, "repeat-owner@example.com")
    second = _post(
        owner,
        "/api/v1/simulations",
        {
            "scenario_revision_id": first["scenario_revision_id"],
            "seed": 471829,
            "simulation_count": 1000,
        },
    )
    assert first["simulation_id"] != second["simulation_id"]
    assert first["summary"] == second["summary"]
    with factory() as db:
        snapshots = db.scalars(select(SimulationSamples)).all()
        assert len(snapshots) == 2
        assert snapshots[0].payload_hash == snapshots[1].payload_hash
        assert snapshots[0].payload == snapshots[1].payload


def test_results_persisted_before_schema_1_2_are_enriched_on_read(
    clients: tuple[TestClient, TestClient, sessionmaker[Session]],
) -> None:
    owner, _, factory = clients
    run = _run(owner, "legacy-owner@example.com")
    simulation_id = str(run["simulation_id"])
    with factory() as db:
        result = db.scalar(select(SimulationResult))
        assert result is not None
        legacy = dict(result.summary)
        for key in ("uncertainty", "drivers"):
            legacy.pop(key)
        legacy["uncertainty_label"] = "NOT AVAILABLE"
        result.summary = legacy
        result.schema_version = "1.1.0"
        db.commit()

    read = owner.get(f"/api/v1/simulations/{simulation_id}")
    assert read.status_code == 200, read.text
    summary = read.json()["summary"]
    assert summary["uncertainty"] == run["summary"]["uncertainty"]
    assert summary["uncertainty_label"] == run["summary"]["uncertainty_label"]
    decision = owner.get(f"/api/v1/simulations/{simulation_id}/decision").json()
    assert [d["name"] for d in decision["drivers"]] == [
        item["name"] for item in run["summary"]["drivers"]["items"]
    ]
