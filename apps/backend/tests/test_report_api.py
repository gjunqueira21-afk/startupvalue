"""PDF exports use saved results and enforce workspace access."""

from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, get_db
from app.main import app


@pytest.fixture
def clients() -> Iterator[tuple[TestClient, TestClient, TestClient]]:
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
    with TestClient(app) as owner, TestClient(app) as outsider, TestClient(app) as anonymous:
        yield owner, outsider, anonymous
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _signup(client: TestClient, name: str) -> None:
    response = client.post(
        "/api/v1/auth/signup",
        json={"name": name, "email": f"{name}@example.com", "password": "long-safe-password"},
    )
    assert response.status_code == 201, response.text
    csrf = client.get("/api/v1/auth/csrf")
    assert csrf.status_code == 200, csrf.text
    client.headers.update({"X-CSRF-Token": csrf.json()["csrf_token"]})


def _simulate(owner: TestClient) -> dict[str, object]:
    startup = owner.post(
        "/api/v1/startups",
        json={"name": "Árvore Analytics", "currency": "BRL", "profile": {"sector": "SaaS"}},
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
            "idempotency_key": "report-test-run",
        },
    )
    assert simulation.status_code == 201, simulation.text
    return simulation.json()  # type: ignore[no-any-return]


def test_report_download_uses_persisted_result_and_audit_metadata(
    clients: tuple[TestClient, TestClient, TestClient],
) -> None:
    owner, _, _ = clients
    _signup(owner, "owner")
    saved = _simulate(owner)
    simulation_id = str(saved["simulation_id"])

    first = owner.get(f"/api/v1/simulations/{simulation_id}/report.pdf")
    second = owner.get(f"/api/v1/simulations/{simulation_id}/report.pdf")

    assert first.status_code == second.status_code == 200
    assert first.headers["content-type"] == "application/pdf"
    assert first.headers["cache-control"] == "private, no-store"
    assert first.headers["content-disposition"].endswith(f'{simulation_id}.pdf"')
    assert first.content == second.content
    text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(first.content)).pages)
    assert simulation_id in text
    assert str(saved["result_hash"]) in text
    assert str(saved["model_version"]) in text
    assert "471829" in text
    assert "Árvore Analytics" in text
    assert "Base Case" in text
    assert "Venture Capital Method não foi calculado" in text
    assert "Fluxo de caixa vs. plano" in text
    assert "scenario_factor_mean" not in text
    assert str(saved["summary"]["uncertainty_label"]) in text  # type: ignore[index]
    assert "NOT AVAILABLE" not in text

    from app.reports.narrative import format_money

    saved_median = saved["summary"]["percentiles"]["p50"]  # type: ignore[index]
    assert format_money(saved_median, "BRL") in text  # type: ignore[arg-type]

    targeted = owner.get(f"/api/v1/simulations/{simulation_id}/report.pdf?target={saved_median}")
    assert targeted.status_code == 200, targeted.text
    targeted_text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(targeted.content)).pages
    )
    assert "Target hit" in targeted_text
    assert "Target miss" in targeted_text
    assert "Fluxo de caixa vs. plano" in targeted_text
    assert "não garantem efeito causal" in targeted_text
    assert targeted.content != first.content


def test_structured_report_formats_business_metrics_in_their_units(
    clients: tuple[TestClient, TestClient, TestClient],
) -> None:
    owner, _, _ = clients
    _signup(owner, "structured")
    startup = owner.post("/api/v1/startups", json={"name": "Receita Co", "currency": "BRL"})
    scenario = owner.post(
        f"/api/v1/startups/{startup.json()['id']}/scenarios",
        json={"name": "Base", "mode": "professional"},
    )
    revision = owner.post(
        f"/api/v1/scenarios/{scenario.json()['id']}/revisions",
        json={
            "inputs": {
                "monthly_revenue": [100000.0 + 5000.0 * month for month in range(60)],
                "monthly_opex": [60000.0] * 60,
                "monthly_capex": [5000.0] * 60,
                "gross_margin": 0.7,
                "revenue_uncertainty": {
                    "kind": "lognormal",
                    "mean": 1.0,
                    "coefficient_of_variation": 0.3,
                },
                "cost_uncertainty": {
                    "kind": "lognormal",
                    "mean": 1.0,
                    "coefficient_of_variation": 0.1,
                },
                "margin_uncertainty_pp": 0.05,
                "serial_correlation": 0.5,
                "persistent_weight": 0.6,
                "annual_wacc": 0.25,
                "terminal_growth": 0.04,
                "failure_probability_horizon": 0.2,
            }
        },
    )
    assert revision.status_code == 201, revision.text
    simulation = owner.post(
        "/api/v1/simulations",
        json={"scenario_revision_id": revision.json()["id"], "seed": 7, "simulation_count": 1000},
    ).json()
    simulation_id = simulation["simulation_id"]
    target = simulation["summary"]["percentiles"]["p75"]
    analysis = owner.get(
        f"/api/v1/simulations/{simulation_id}/target", params={"value": target}
    ).json()
    revenue = next(c for c in analysis["comparisons"] if c["name"] == "revenue_year5_operating")
    report = owner.get(f"/api/v1/simulations/{simulation_id}/report.pdf?target={target}")
    assert report.status_code == 200, report.text
    text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(report.content)).pages
    )

    from app.reports.narrative import format_money

    assert "Receita do Ano 5" in text
    assert "Margem EBITDA do Ano 5" in text
    assert "revenue_year5_operating" not in text
    assert format_money(revenue["hit"]["p50"], "BRL") in text


def test_report_download_requires_session_and_workspace(
    clients: tuple[TestClient, TestClient, TestClient],
) -> None:
    owner, outsider, anonymous = clients
    _signup(owner, "owner")
    _signup(outsider, "outsider")
    simulation_id = _simulate(owner)["simulation_id"]
    url = f"/api/v1/simulations/{simulation_id}/report.pdf"

    assert anonymous.get(url).status_code == 401
    assert outsider.get(url).status_code == 404
    assert outsider.get(f"{url}?target=20000000").status_code == 404
    assert owner.get("/api/v1/simulations/nonexistent/report.pdf").status_code == 404
