"""report_from_result must render the DCF and VC method cards from persisted data.

Both cards used to be hardcoded to ``not_available`` even though the DCF inputs
and the VC method summary are always persisted on the scenario revision /
simulation result. These tests exercise ``report_from_result`` directly
against an in-memory database, the same way ``test_dashboard.py`` does, so
that the ORM attribute access (``revision.canonical_inputs``,
``result.summary``) is exercised for real.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import (
    Scenario,
    ScenarioRevision,
    Simulation,
    SimulationResult,
    SimulationStatus,
    Startup,
    User,
    Workspace,
)
from app.reports.from_result import report_from_result
from app.reports.narrative import format_money, format_percent


def _summary(
    *, p50: float = 9_000_000.0, vc_method: dict[str, Any] | None | object = "__absent__"
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "basis": "Equity value",
        "percentiles": {
            "p5": 2_000_000.0,
            "p10": 3_000_000.0,
            "p25": 5_000_000.0,
            "p50": p50,
            "p75": 11_000_000.0,
            "p90": 14_000_000.0,
            "p95": 17_000_000.0,
        },
        "mean": p50 * 1.02,
        "standard_deviation": 3_000_000.0,
        "failure_probability": 0.05,
        "uncertainty_label": "MODERATE",
        "uncertainty": {"label": "MODERATE"},
    }
    if vc_method != "__absent__":
        payload["vc_method"] = vc_method
    return payload


def _fixture(
    db: Session, *, suffix: str, canonical_inputs: dict[str, Any], summary: dict[str, Any]
) -> tuple[Simulation, SimulationResult, ScenarioRevision, Scenario, Startup]:
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
        canonical_inputs=canonical_inputs,
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
        summary=summary,
        result_hash=suffix,
        samples_object_key="",
        samples_hash="",
    )
    db.add(result)
    db.flush()
    return simulation, result, revision, scenario, startup


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def _metric_values(metrics: tuple[Any, ...]) -> dict[str, str]:
    return {metric.name: metric.value for metric in metrics}


# --- DCF card -----------------------------------------------------------------


def test_dcf_card_renders_available_with_gordon_terminal_and_p50() -> None:
    db = _session()
    canonical_inputs = {
        "annual_wacc": 0.22,
        "terminal_growth": 0.04,
        "excess_cash": 250_000.0,
        "debt": 100_000.0,
        "terminal_method": "gordon",
    }
    simulation, result, revision, scenario, startup = _fixture(
        db,
        suffix="dcf-gordon",
        canonical_inputs=canonical_inputs,
        summary=_summary(p50=9_400_000.0),
    )

    data = report_from_result(
        simulation=simulation, result=result, revision=revision, scenario=scenario,
        startup=startup,
    )

    assert data.dcf.status == "available"
    values = _metric_values(data.dcf.metrics)
    assert values["WACC anual"] == format_percent(0.22)
    assert values["Crescimento terminal"] == format_percent(0.04)
    assert values["Horizonte"] == "60 meses (5 anos)"
    assert values["Caixa excedente"] == format_money(250_000.0, "BRL")
    assert values["Dívida"] == format_money(100_000.0, "BRL")
    assert values["Equity mediano (P50)"] == format_money(9_400_000.0, "BRL")
    assert data.dcf.note is not None and "Monte Carlo" in data.dcf.note


def test_dcf_card_renders_exit_multiple_terminal_and_omits_missing_fields() -> None:
    db = _session()
    canonical_inputs = {
        "annual_wacc": 0.25,
        "terminal_method": "exit_multiple",
        "exit_multiple": 6.5,
        "exit_metric": "revenue",
    }
    simulation, result, revision, scenario, startup = _fixture(
        db,
        suffix="dcf-exit-multiple",
        canonical_inputs=canonical_inputs,
        summary=_summary(p50=5_000_000.0),
    )

    data = report_from_result(
        simulation=simulation, result=result, revision=revision, scenario=scenario,
        startup=startup,
    )

    assert data.dcf.status == "available"
    values = _metric_values(data.dcf.metrics)
    assert values["Múltiplo de saída (Receita)"] == "6,5x"
    assert "Crescimento terminal" not in values
    # excess_cash / debt were never persisted on this revision: never invent them.
    assert "Caixa excedente" not in values
    assert "Dívida" not in values
    assert values["Equity mediano (P50)"] == format_money(5_000_000.0, "BRL")


# --- VC card --------------------------------------------------------------


def _realistic_vc_method(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "status": "available",
        "reason_code": None,
        "reason": None,
        "method": "venture_capital",
        "exit_metric": "revenue_last_12_months",
        "exit_multiple_basis": "enterprise_value_to_annual_revenue",
        "exit_year": 5,
        "revenue_cadence": "annual",
        "annual_exit_revenue": 12_000_000.0,
        "exit_multiple": 5.0,
        "target_return_annual": 0.35,
        "exit_enterprise_value": 60_000_000.0,
        "exit_equity_value": 60_000_000.0,
        "present_exit_equity": 13_500_000.0,
        "exit_balance_sheet_policy": "zero_exit_cash_and_debt_unless_forecast_available",
        "current_cash_not_applied_to_exit": 400_000.0,
        "current_debt_not_applied_to_exit": 150_000.0,
        "investment": 2_000_000.0,
        "post_money": 13_500_000.0,
        "pre_money": 11_500_000.0,
        "required_ownership_today": 0.148,
        "required_ownership_at_exit": 0.148,
        "future_ownership_retention": 1.0,
        "target_ownership": 0.2,
        "target_ownership_meets_return": True,
    }
    base.update(overrides)
    return base


def test_vc_card_available_maps_full_metric_set() -> None:
    db = _session()
    vc_method = _realistic_vc_method()
    simulation, result, revision, scenario, startup = _fixture(
        db,
        suffix="vc-available",
        canonical_inputs={"annual_wacc": 0.2},
        summary=_summary(vc_method=vc_method),
    )

    data = report_from_result(
        simulation=simulation, result=result, revision=revision, scenario=scenario,
        startup=startup,
    )

    assert data.venture_capital.status == "available"
    values = _metric_values(data.venture_capital.metrics)
    assert values["Receita anual de saída (ano 5)"] == format_money(12_000_000.0, "BRL")
    assert values["Múltiplo de saída (EV/Receita)"] == "5,0x"
    assert values["EV na saída"] == format_money(60_000_000.0, "BRL")
    assert values["Equity na saída"] == format_money(60_000_000.0, "BRL")
    assert values["Valor presente do equity de saída"] == format_money(13_500_000.0, "BRL")
    assert values["Retorno-alvo anual"] == format_percent(0.35)
    assert values["Investimento"] == format_money(2_000_000.0, "BRL")
    assert values["Post-money"] == format_money(13_500_000.0, "BRL")
    assert values["Pre-money"] == format_money(11_500_000.0, "BRL")
    assert values["Participação requerida hoje"] == format_percent(0.148)
    assert values["Participação-alvo"] == format_percent(0.2)
    assert data.venture_capital.note is not None
    assert "zero" in data.venture_capital.note.lower()


def test_vc_card_infeasible_keeps_metrics_and_adds_infeasible_note() -> None:
    db = _session()
    vc_method = _realistic_vc_method(
        status="infeasible",
        reason_code="investment_exceeds_vc_post_money",
        reason=(
            "Investment exceeds the present value of exit equity; "
            "no non-negative pre-money meets the target return."
        ),
        investment=20_000_000.0,
        post_money=13_500_000.0,
        pre_money=-6_500_000.0,
        required_ownership_today=1.48,
        required_ownership_at_exit=1.48,
    )
    simulation, result, revision, scenario, startup = _fixture(
        db,
        suffix="vc-infeasible",
        canonical_inputs={"annual_wacc": 0.2},
        summary=_summary(vc_method=vc_method),
    )

    data = report_from_result(
        simulation=simulation, result=result, revision=revision, scenario=scenario,
        startup=startup,
    )

    assert data.venture_capital.status == "available"
    values = _metric_values(data.venture_capital.metrics)
    assert values["Valor presente do equity de saída"] == format_money(13_500_000.0, "BRL")
    assert data.venture_capital.note is not None
    assert "infeasível" in data.venture_capital.note.lower()


def test_vc_card_unavailable_maps_reason_code_to_actionable_note() -> None:
    db = _session()
    vc_method = {
        "status": "unavailable",
        "reason_code": "revenue_projection_missing",
        "reason": "Five years of revenue and its cadence are required.",
    }
    simulation, result, revision, scenario, startup = _fixture(
        db,
        suffix="vc-unavailable-reason",
        canonical_inputs={"annual_wacc": 0.2},
        summary=_summary(vc_method=vc_method),
    )

    data = report_from_result(
        simulation=simulation, result=result, revision=revision, scenario=scenario,
        startup=startup,
    )

    assert data.venture_capital.status == "not_available"
    assert data.venture_capital.note == (
        "Informe a projeção de receita de 5 anos no perfil da empresa para habilitar "
        "esta análise."
    )


def test_vc_card_unavailable_with_unmapped_reason_code_is_still_honest() -> None:
    db = _session()
    vc_method = {
        "status": "unavailable",
        "reason_code": "exit_year_unsupported",
        "reason": "The saved revenue projection supports only a year-five exit.",
    }
    simulation, result, revision, scenario, startup = _fixture(
        db,
        suffix="vc-unavailable-generic",
        canonical_inputs={"annual_wacc": 0.2},
        summary=_summary(vc_method=vc_method),
    )

    data = report_from_result(
        simulation=simulation, result=result, revision=revision, scenario=scenario,
        startup=startup,
    )

    assert data.venture_capital.status == "not_available"
    assert data.venture_capital.note is not None
    assert "year-five exit" in data.venture_capital.note


def test_vc_card_without_persisted_vc_method_uses_backward_compatible_note() -> None:
    """Results persisted before this feature have no ``vc_method`` key at all."""
    db = _session()
    simulation, result, revision, scenario, startup = _fixture(
        db,
        suffix="vc-absent",
        canonical_inputs={"annual_wacc": 0.2},
        summary=_summary(),
    )
    assert "vc_method" not in result.summary

    data = report_from_result(
        simulation=simulation, result=result, revision=revision, scenario=scenario,
        startup=startup,
    )

    assert data.venture_capital.status == "not_available"
    assert data.venture_capital.note == (
        "O Venture Capital Method não foi calculado nem persistido nesta simulação."
    )
