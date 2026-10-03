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

from app.core.entitlements import PlanTier, set_workspace_plan
from app.db.base import Base, get_db
from app.db.models import ReportBranding
from app.main import app


@pytest.fixture
def clients() -> Iterator[tuple[TestClient, TestClient, TestClient, sessionmaker[Session]]]:
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
        yield owner, outsider, anonymous, factory
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _signup(client: TestClient, name: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/signup",
        json={"name": name, "email": f"{name}@example.com", "password": "long-safe-password"},
    )
    assert response.status_code == 201, response.text
    csrf = client.get("/api/v1/auth/csrf")
    assert csrf.status_code == 200, csrf.text
    client.headers.update({"X-CSRF-Token": csrf.json()["csrf_token"]})
    return response.json()  # type: ignore[no-any-return]


def _upgrade_plan(factory: sessionmaker[Session], workspace_id: str, plan: PlanTier) -> None:
    with factory() as db:
        set_workspace_plan(db, workspace_id=workspace_id, plan=plan, actor_id=None)
        db.commit()


def _set_branding_row(
    factory: sessionmaker[Session],
    workspace_id: str,
    *,
    firm_name: str = "Alfa Consultoria",
    primary_color: str | None = "#123456",
) -> None:
    """Insert a branding row directly, bypassing the entitlement-gated API.

    Used to prove the report route still enforces ``white_label`` itself
    (defense in depth) even when a branding row already exists for a
    workspace that later downgrades, or never had access in the first place.
    """
    with factory() as db:
        db.add(
            ReportBranding(
                workspace_id=workspace_id,
                firm_name=firm_name,
                primary_color=primary_color,
            )
        )
        db.commit()


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
    clients: tuple[TestClient, TestClient, TestClient, sessionmaker[Session]],
) -> None:
    owner, _, _, factory = clients
    session = _signup(owner, "owner")
    # The target-plan section is empresario+; elevate so this PDF exercises it
    # rather than the free-tier gate added for entitlement enforcement.
    _upgrade_plan(factory, str(session["workspace_id"]), PlanTier.empresario)
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
    label = str(saved["summary"]["uncertainty_label"])  # type: ignore[index]
    portuguese = {"LOW": "Baixa", "MODERATE": "Moderada", "HIGH": "Alta", "VERY HIGH": "Muito alta"}
    assert portuguese[label] in text
    assert "NOT AVAILABLE" not in text

    from app.reports.narrative import format_money

    saved_median = saved["summary"]["percentiles"]["p50"]  # type: ignore[index]
    assert format_money(saved_median, "BRL") in text  # type: ignore[arg-type]

    targeted = owner.get(f"/api/v1/simulations/{simulation_id}/report.pdf?target={saved_median}")
    assert targeted.status_code == 200, targeted.text
    targeted_text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(targeted.content)).pages
    )
    assert "Cenários que atingem" in targeted_text
    assert "Cenários que não atingem" in targeted_text
    assert "Fluxo de caixa vs. plano" in targeted_text
    assert "não relações de causa e efeito" in " ".join(targeted_text.split())
    assert targeted.content != first.content
    # Target plan section renders (this fixture's inputs are FCFF-based, so no revenue CAGR
    # factor is available for the plan; the reason is explained rather than a trajectory).
    assert "Target Plan" in targeted_text


def test_structured_report_formats_business_metrics_in_their_units(
    clients: tuple[TestClient, TestClient, TestClient, sessionmaker[Session]],
) -> None:
    owner, _, _, factory = clients
    session = _signup(owner, "structured")
    # The target-plan section is empresario+; elevate so this PDF exercises it
    # rather than the free-tier gate added for entitlement enforcement.
    _upgrade_plan(factory, str(session["workspace_id"]), PlanTier.empresario)
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

    pages = [
        " ".join((page.extract_text() or "").split())
        for page in PdfReader(BytesIO(report.content)).pages
    ]
    insight = owner.get(
        f"/api/v1/simulations/{simulation_id}/insight", params={"target": target}
    ).json()
    summary_page = pages[1]
    for label in ("ESTIMATED VALUATION", "PROBABILITY OF TARGET", "TOP VALUATION DRIVERS"):
        assert label in summary_page
    # Same deterministic text as the dashboard: the PDF never rewrites the insight.
    assert insight["executive_summary"][0] in summary_page
    assert insight["key_drivers"][0]["label"] in summary_page
    target_page = next(page for page in pages if "What Needs to Be True?" in page)
    # Latent shocks are redundant with outcome metrics; the target tables use the insight's set.
    assert "Receita vs. plano" not in target_page
    risk_page = next(page for page in pages if "Risk & Sensitivity" in page)
    assert "Sensibilidade (tornado)" in risk_page
    assert "WACC" in risk_page
    assert "Equity via DCF" in " ".join(pages)
    assert all("NOT AVAILABLE" not in page for page in pages)
    # Operating-model inputs expose the revenue CAGR factor, so a target plan is produced.
    joined = " ".join(pages)
    assert "Target Plan" in joined


def test_report_download_requires_session_and_workspace(
    clients: tuple[TestClient, TestClient, TestClient, sessionmaker[Session]],
) -> None:
    owner, outsider, anonymous, _ = clients
    _signup(owner, "owner")
    _signup(outsider, "outsider")
    simulation_id = _simulate(owner)["simulation_id"]
    url = f"/api/v1/simulations/{simulation_id}/report.pdf"

    assert anonymous.get(url).status_code == 401
    assert outsider.get(url).status_code == 404
    assert outsider.get(f"{url}?target=20000000").status_code == 404
    assert owner.get("/api/v1/simulations/nonexistent/report.pdf").status_code == 404


# --- Task 9: white-label and watermark route behavior ------------------------


def test_free_workspace_with_branding_row_still_gets_unbranded_watermarked_pdf(
    clients: tuple[TestClient, TestClient, TestClient, sessionmaker[Session]],
) -> None:
    """Free tier never gets white-label, even if a branding row exists.

    This covers the case of a workspace that configured branding on a paid
    plan and then downgraded (or a row inserted out-of-band): the route must
    resolve entitlements itself rather than trusting the presence of a row.
    """
    owner, _, _, factory = clients
    session = _signup(owner, "free-branded")
    _set_branding_row(factory, str(session["workspace_id"]))
    simulation_id = _simulate(owner)["simulation_id"]

    response = owner.get(f"/api/v1/simulations/{simulation_id}/report.pdf")

    assert response.status_code == 200, response.text
    assert "quantovale-" in response.headers["content-disposition"]
    text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(response.content)).pages
    )
    assert "Alfa Consultoria" not in text
    assert "STARTUPVALUE" in text
    assert "RESUMO GRATUITO" in text


def test_consultor_workspace_with_branding_gets_branded_pdf_and_audit_event(
    clients: tuple[TestClient, TestClient, TestClient, sessionmaker[Session]],
) -> None:
    owner, _, _, factory = clients
    session = _signup(owner, "consultor-branded")
    workspace_id = str(session["workspace_id"])
    _upgrade_plan(factory, workspace_id, PlanTier.consultor)
    _set_branding_row(factory, workspace_id)
    simulation_id = _simulate(owner)["simulation_id"]

    response = owner.get(f"/api/v1/simulations/{simulation_id}/report.pdf")

    assert response.status_code == 200, response.text
    assert "quantovale-" in response.headers["content-disposition"]
    text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(response.content)).pages
    )
    assert "Alfa Consultoria" in text
    assert "STARTUPVALUE" not in text
    assert "RESUMO GRATUITO" not in text

    with factory() as db:
        from app.db.models import AuditEvent

        events = db.query(AuditEvent).filter(
            AuditEvent.workspace_id == workspace_id, AuditEvent.action == "report.download"
        ).all()
        assert len(events) == 1
        assert events[0].resource_id is not None


def test_report_filename_uses_quantovale_prefix(
    clients: tuple[TestClient, TestClient, TestClient, sessionmaker[Session]],
) -> None:
    owner, _, _, _ = clients
    _signup(owner, "filename-check")
    simulation_id = _simulate(owner)["simulation_id"]

    response = owner.get(f"/api/v1/simulations/{simulation_id}/report.pdf")

    assert response.status_code == 200, response.text
    disposition = response.headers["content-disposition"]
    assert f'filename="quantovale-{simulation_id}.pdf"' in disposition
    assert "startupvalue-" not in disposition
