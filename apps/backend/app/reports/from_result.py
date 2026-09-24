"""Translate a persisted simulation snapshot into the report presentation contract."""

from __future__ import annotations

from typing import Any

from app.db.models import Scenario, ScenarioRevision, Simulation, SimulationResult, Startup
from app.decision.catalog import describe
from app.decision.targets import ConditionalStatistics
from app.decision.targets import TargetAnalysis as CalculatedTargetAnalysis
from app.services.simulation import with_uncertainty

from .schema import ReportData

REPORT_TEMPLATE_VERSION = "1.0.0"


def _profile_text(profile: dict[str, Any], key: str, limit: int) -> str | None:
    value = profile.get(key)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()[:limit]


def _assumptions(inputs: dict[str, Any], currency: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    cash_flows = inputs.get("monthly_fcff")
    if isinstance(cash_flows, list):
        for month, amount in enumerate(cash_flows, start=1):
            rows.append(
                {
                    "name": f"FCFF projetado - mês {month}",
                    "value": f"{float(amount):,.2f}",
                    "unit": currency,
                    "source": "Revisão do cenário",
                }
            )
    labels = {
        "annual_wacc": ("WACC anual", "% a.a.", True),
        "terminal_growth": ("Crescimento terminal", "% a.a.", True),
        "excess_cash": ("Caixa excedente", currency, False),
        "debt": ("Dívida", currency, False),
        "failure_probability_horizon": ("Probabilidade de falha", "% no horizonte", True),
        "liquidation_value": ("Valor de liquidação", currency, False),
    }
    for key, (name, unit, percentage) in labels.items():
        value = inputs.get(key)
        if value is None:
            continue
        rendered = f"{float(value) * 100:.2f}" if percentage else f"{float(value):,.2f}"
        rows.append(
            {"name": name, "value": rendered, "unit": unit, "source": "Revisão do cenário"}
        )
    uncertainty = inputs.get("uncertainty")
    if isinstance(uncertainty, dict):
        for key, value in uncertainty.items():
            if value is None:
                continue
            rows.append(
                {
                    "name": f"Incerteza - {key.replace('_', ' ')}",
                    "value": str(value),
                    "source": "Revisão do cenário",
                }
            )
    return rows


def _conditional_payload(statistics: ConditionalStatistics) -> dict[str, float] | None:
    if statistics.p25 is None or statistics.p50 is None or statistics.p75 is None:
        return None
    return {"p25": statistics.p25, "median": statistics.p50, "p75": statistics.p75}


def _report_unit(unit: str | None, currency: str) -> str | None:
    return {"currency": currency, "ratio": "%", "multiplier": "x", "binary": "0/1"}.get(
        unit or ""
    )


def report_from_result(
    *,
    simulation: Simulation,
    result: SimulationResult,
    revision: ScenarioRevision,
    scenario: Scenario,
    startup: Startup,
    drivers: dict[str, Any] | None = None,
    target: CalculatedTargetAnalysis | None = None,
) -> ReportData:
    """Use saved values only; no valuation or random draw occurs here."""

    summary = with_uncertainty(result.summary)
    ranking = drivers or {"items": [], "scenario_count": simulation.simulation_count}
    company_profile = startup.profile or {}
    payload: dict[str, Any] = {
        "audit": {
            "simulation_id": simulation.id,
            "simulation_result_id": result.id,
            "result_hash": result.result_hash,
            "model_version": simulation.model_version,
            "tax_version": simulation.tax_version,
            "result_schema_version": result.schema_version,
            "report_template_version": REPORT_TEMPLATE_VERSION,
            "seed": simulation.seed,
            "simulation_count": simulation.simulation_count,
            "generated_at": result.created_at,
            "analysis_date": simulation.created_at.date(),
        },
        "company": {
            "name": startup.name,
            "scenario_name": scenario.name,
            "sector": _profile_text(company_profile, "sector", 160),
            "stage": _profile_text(company_profile, "stage", 80),
            "business_model": _profile_text(company_profile, "business_model", 120),
            "country": _profile_text(company_profile, "country", 80),
            "currency": startup.currency,
        },
        "valuation": {
            "basis": summary["basis"],
            "percentiles": summary["percentiles"],
            "mean": summary["mean"],
            "standard_deviation": summary["standard_deviation"],
            "failure_probability": summary["failure_probability"],
            "uncertainty_label": summary.get("uncertainty_label", "NOT AVAILABLE"),
            "uncertainty_ratio": summary.get("uncertainty_ratio"),
            "breakeven_probabilities": summary.get("breakeven_probabilities", {}),
            "breakeven_month_percentiles": summary.get("breakeven_month_percentiles", {}),
            "histogram": summary.get("histogram"),
        },
        "assumptions": _assumptions(revision.canonical_inputs, startup.currency),
        "dcf": {
            "status": "not_available",
            "note": (
                "A distribuição usa fluxos de caixa descontados. Um demonstrativo DCF "
                "isolado não foi persistido nesta simulação."
            ),
        },
        "venture_capital": {
            "status": "not_available",
            "note": "O Venture Capital Method não foi calculado nem persistido nesta simulação.",
        },
        "drivers": [
            {
                "name": describe(driver["name"]).label,
                "association": driver["rho"],
                "contribution": driver["contribution"],
                "direction": driver["direction"],
                "population": "unconditional",
                "sample_size": ranking["scenario_count"],
                "status": driver["status"],
            }
            for driver in ranking["items"]
        ],
        "target": (
            {
                "target_value": target.target,
                "probability": target.probability,
                "hit_count": target.hit_count,
                "miss_count": target.miss_count,
                "metrics": [
                    {
                        "name": describe(comparison.name).label,
                        "unit": _report_unit(describe(comparison.name).unit, startup.currency),
                        "target_hit": _conditional_payload(comparison.hit),
                        "target_miss": _conditional_payload(comparison.miss),
                    }
                    for comparison in target.comparisons
                ],
            }
            if target is not None
            else None
        ),
        "risks": {
            "limitations": (
                "As premissas e a distribuição são estimativas, não preços de transação.",
                "Indicadores ausentes não foram estimados no momento da exportação.",
            ),
        },
        "disclaimer": (
            "Estimativa probabilística baseada nas premissas informadas. Os resultados não "
            "garantem valor de mercado, preço de transação ou retorno futuro."
        ),
    }
    return ReportData.model_validate(payload)
