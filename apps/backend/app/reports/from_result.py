"""Translate a persisted simulation snapshot into the report presentation contract."""

from __future__ import annotations

from typing import Any

from app.db.models import Scenario, ScenarioRevision, Simulation, SimulationResult, Startup
from app.decision.catalog import describe
from app.decision.target_plan import TargetPlan
from app.decision.targets import ConditionalStatistics
from app.decision.targets import TargetAnalysis as CalculatedTargetAnalysis
from app.insights.engine import InsightReport
from app.insights.formatting import effect_label
from app.services.simulation import with_uncertainty

from .schema import ReportData

REPORT_TEMPLATE_VERSION = "1.3.0"
BASIS_LABELS = {"DCF equity value (signed)": "Equity via DCF · inclui valores negativos"}


def _profile_text(profile: dict[str, Any], key: str, limit: int) -> str | None:
    value = profile.get(key)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()[:limit]


def _number(value: float) -> str:
    """pt-BR decimal with two places ("350.000,00"), matching the rest of the report."""
    return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _assumptions(inputs: dict[str, Any], currency: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    cash_flows = inputs.get("monthly_fcff")
    if isinstance(cash_flows, list):
        for month, amount in enumerate(cash_flows, start=1):
            rows.append(
                {
                    "name": f"FCFF projetado - mês {month}",
                    "value": _number(float(amount)),
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
        rendered = _number(float(value) * 100 if percentage else float(value))
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


def _insight_payload(
    report: InsightReport, ranking: dict[str, Any]
) -> dict[str, Any]:
    rho_by_name = {item["name"]: item["rho"] for item in ranking.get("items", [])}
    target = report.target
    return {
        "template_version": report.template_version,
        "headline": report.headline,
        "valuation_paragraphs": report.valuation_paragraphs,
        "uncertainty_label": report.uncertainty.label,
        "uncertainty_label_pt": report.uncertainty.label_pt,
        "uncertainty_sentence": report.uncertainty.sentence,
        "key_drivers_sentence": report.key_drivers_sentence,
        "key_drivers": [
            {
                "label": driver.label,
                "contribution": driver.contribution,
                "rho": rho_by_name.get(driver.name),
            }
            for driver in report.key_drivers
        ],
        "upside": [item.text for item in report.upside],
        "downside": [item.text for item in report.downside],
        "sensitivity_sentence": report.sensitivity_sentence,
        "risks": report.risks,
        "executive_summary": report.executive_summary,
        "method_notes": report.method_notes,
        "target": (
            {
                "probability": target.probability,
                "wilson95_low": target.wilson95_low,
                "wilson95_high": target.wilson95_high,
                "probability_sentence": target.probability_sentence,
                "interpretation": target.interpretation,
                "statements": target.statements,
                "conditions": [
                    {
                        "label": condition.label,
                        "unit": condition.unit,
                        "hit_value": condition.hit_value,
                        "miss_value": condition.miss_value,
                        "effect": effect_label(condition.cliffs_delta, condition.kind),
                    }
                    for condition in target.conditions
                ],
                "disclaimer": target.disclaimer,
            }
            if target is not None
            else None
        ),
    }


def _tornado_payload(summary: dict[str, Any]) -> dict[str, Any] | None:
    stored = summary.get("sensitivity")
    if not isinstance(stored, dict) or not stored.get("items"):
        return None
    return {
        "base_value": stored["base_value"],
        "items": [
            {
                "label": describe(item["parameter"]).label,
                "unit": describe(item["parameter"]).unit,
                "low_level": item["low_level"],
                "high_level": item["high_level"],
                "value_at_low": item["value_at_low"],
                "value_at_high": item["value_at_high"],
                "clamped": item["clamped"],
            }
            for item in stored["items"]
        ],
    }


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
    insight: InsightReport | None = None,
    target_plan: TargetPlan | None = None,
    include_multiples: bool = True,
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
            "basis": BASIS_LABELS.get(summary["basis"], summary["basis"]),
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
        "insight": _insight_payload(insight, ranking) if insight is not None else None,
        "tornado": _tornado_payload(summary) if insight is not None else None,
        "implied_multiples": (
            summary.get("implied_multiples")
            if include_multiples and isinstance(summary.get("implied_multiples"), dict)
            else None
        ),
        "target_plan": (
            {
                "status": target_plan.status,
                "hit_count": target_plan.hit_count,
                "required_revenue_cagr": target_plan.required_revenue_cagr,
                "hit_ebitda_margin": target_plan.hit_ebitda_margin,
                "miss_revenue_cagr": target_plan.miss_revenue_cagr,
                "miss_ebitda_margin": target_plan.miss_ebitda_margin,
                "trajectory": [
                    {"year": point.year, "revenue": point.revenue}
                    for point in target_plan.trajectory
                ],
            }
            if target_plan is not None
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
