from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

import numpy as np
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.schemas import SimulationRunRequest
from app.db.base import Base
from app.db.models import SimulationSamples
from app.insights.engine import INSIGHT_TEMPLATE_VERSION, InsightReport, build_insight
from app.insights.formatting import compact_money, percent
from app.services.simulation import execute_synchronously, load_sample_vectors


def _inputs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "monthly_revenue": [100_000.0 * 1.04**month for month in range(60)],
        "monthly_opex": [90_000.0] * 60,
        "monthly_capex": [5_000.0] * 60,
        "gross_margin": 0.7,
        "revenue_uncertainty": {"kind": "lognormal", "mean": 1.0, "coefficient_of_variation": 0.3},
        "cost_uncertainty": {"kind": "lognormal", "mean": 1.0, "coefficient_of_variation": 0.1},
        "margin_uncertainty_pp": 0.05,
        "serial_correlation": 0.5,
        "persistent_weight": 0.6,
        "annual_wacc": 0.25,
        "terminal_growth": 0.04,
        "failure_probability_horizon": 0.15,
        "excess_cash": 350_000.0,
    }
    return {**base, **overrides}


_CACHE: dict[str, Any] = {}


Run = tuple[dict[str, Any], np.ndarray, dict[str, np.ndarray]]


def _run(key: str = "base", **overrides: Any) -> Run:
    if key not in _CACHE:
        engine = create_engine("sqlite+pysqlite://")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            simulation, result = execute_synchronously(
                db,
                workspace_id="00000000-0000-0000-0000-000000000001",
                revision_id="00000000-0000-0000-0000-000000000002",
                canonical_inputs=_inputs(**overrides),
                request=SimulationRunRequest(seed=471829, simulation_count=5000),
            )
            db.commit()
            snapshot = db.scalar(select(SimulationSamples))
            assert snapshot is not None
            valuations, factors = load_sample_vectors(
                snapshot, result=result, simulation=simulation
            )
            _CACHE[key] = (dict(result.summary), np.array(valuations), dict(factors))
        engine.dispose()
    return _CACHE[key]


def _insight(target: float | None = None, key: str = "base", **overrides: Any) -> InsightReport:
    summary, valuations, factors = _run(key, **overrides)
    return build_insight(
        summary=summary,
        valuations=valuations,
        factors=factors,
        currency="BRL",
        target=target,
    )


def _all_text(report: InsightReport) -> list[str]:
    texts: list[str] = []

    def collect(value: object) -> None:
        if isinstance(value, str):
            texts.append(value)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key not in {"name", "label_key", "unit", "direction", "kind", "reason",
                               "sample_note", "label", "rule_version"}:
                    collect(item)
        elif isinstance(value, list | tuple):
            for item in value:
                collect(item)

    collect(asdict(report))
    return texts


def test_valuation_insight_reads_like_the_executive_brief() -> None:
    summary, _, _ = _run()
    p = summary["percentiles"]
    report = _insight()
    assert report.template_version == INSIGHT_TEMPLATE_VERSION
    assert compact_money(p["p50"], "BRL") in report.headline
    first, second, third = report.valuation_paragraphs[:3]
    assert first.startswith("Nos 5.000 cenários simulados, o valuation mediano da empresa foi de")
    assert "Metade dos cenários produziu valuations abaixo desse valor e metade acima." in first
    assert compact_money(p["p25"], "BRL") in second and compact_money(p["p75"], "BRL") in second
    assert "(P10)" in third and "(P90)" in third
    assert any("encerrou as operações" in text for text in report.valuation_paragraphs)


def test_half_below_half_above_is_not_claimed_when_values_tie_at_the_median() -> None:
    summary, valuations, factors = _run()
    tied = valuations.copy()
    tied[: int(tied.size * 0.6)] = 0.0
    tied_summary = {**summary, "percentiles": {**summary["percentiles"], "p50": 0.0}}
    report = build_insight(
        summary=tied_summary, valuations=tied, factors=factors, currency="BRL", target=None
    )
    assert "Metade dos cenários" not in report.valuation_paragraphs[0]
    assert "exatamente nesse valor" in report.valuation_paragraphs[0]


def test_uncertainty_sentence_states_the_published_criterion() -> None:
    summary, _, _ = _run()
    report = _insight()
    uncertainty = summary["uncertainty"]
    assert report.uncertainty.label == uncertainty["label"]
    if uncertainty["reason"] == "iqr_ratio":
        assert percent(uncertainty["iqr_ratio"], decimals=0) in report.uncertainty.sentence
        assert "do valuation mediano" in report.uncertainty.sentence


def test_key_drivers_name_the_top_three_in_ranking_order() -> None:
    summary, _, _ = _run()
    report = _insight()
    ranked = [item for item in summary["drivers"]["items"] if (item["contribution"] or 0) >= 0.05]
    assert [driver.name for driver in report.key_drivers] == [item["name"] for item in ranked[:3]]
    sentence = report.key_drivers_sentence
    assert sentence is not None
    positions = [sentence.index(driver.label) for driver in report.key_drivers]
    assert positions == sorted(positions)
    count = {1: "O fator que mais explicou", 2: "Os dois fatores que mais explicaram",
             3: "Os três fatores que mais explicaram"}[len(report.key_drivers)]
    assert sentence.startswith(f"{count} a dispersão do valuation")
    assert "da variância explicada" in sentence


def test_upside_and_downside_drivers_are_business_phrases() -> None:
    report = _insight()
    upside = " ".join(item.text for item in report.upside)
    downside = " ".join(item.text for item in report.downside)
    assert "Receita acima do plano" in upside
    assert "melhores cenários" in upside
    assert "Mais encerramentos das operações" in downside or "Receita abaixo do plano" in downside
    assert "piores cenários" in downside


def test_sensitivity_and_risks_come_from_the_persisted_tornado() -> None:
    summary, _, _ = _run()
    report = _insight()
    top = summary["sensitivity"]["items"][0]
    assert report.sensitivity_sentence is not None
    assert compact_money(top["value_at_low"], "BRL") in report.sensitivity_sentence
    assert any("encerramento" in risk.lower() for risk in report.risks)


def test_target_answers_what_needs_to_be_true() -> None:
    summary, _, _ = _run()
    target = summary["percentiles"]["p75"]
    report = _insight(target=target)
    assert report.target is not None
    block = report.target
    assert compact_money(target, "BRL") in block.probability_sentence
    assert "intervalo de 95%" in block.probability_sentence
    assert block.interpretation.startswith("Nos cenários em que o valuation atinge")
    assert any("dos cenários que atingem a meta" in item for item in block.statements)
    assert block.conditions[0].label
    assert "não relações de causa e efeito" in block.disclaimer
    names = {condition.name for condition in block.conditions}
    assert "revenue_year5_operating" in names
    assert "revenue_factor_mean" not in names  # redundant latent factor stays out of conditions


def test_unreached_target_is_not_called_impossible() -> None:
    summary, _, _ = _run()
    report = _insight(target=summary["maximum"] * 2)
    assert report.target is not None
    sentence = report.target.probability_sentence
    assert "Nenhum dos 5.000 cenários" in sentence
    assert "não significa que o resultado seja impossível" in sentence
    assert report.target.conditions == ()


def test_executive_summary_has_one_to_three_paragraphs_with_target_and_risks() -> None:
    summary, _, _ = _run()
    report = _insight(target=summary["percentiles"]["p75"])
    assert 1 <= len(report.executive_summary) <= 3
    joined = " ".join(report.executive_summary)
    assert compact_money(summary["percentiles"]["p50"], "BRL") in joined
    assert "probabilidade" in joined
    assert "não implicam causalidade" in joined


def test_no_internal_identifier_leaks_into_user_facing_text() -> None:
    summary, _, _ = _run()
    report = _insight(target=summary["percentiles"]["p75"])
    for text in _all_text(report):
        assert not re.search(r"\b[a-z]+_[a-z0-9_]+\b", text), text
        assert "NOT AVAILABLE" not in text and "failure" not in text.lower()


def test_insight_is_deterministic() -> None:
    summary, _, _ = _run()
    target = summary["percentiles"]["p75"]
    assert _insight(target=target) == _insight(target=target)


def test_fixed_valuation_parameters_are_not_described_as_drivers() -> None:
    report = _insight()
    assert all(driver.name != "annual_wacc" for driver in report.key_drivers)


@pytest.mark.parametrize("currency", ["USD"])
def test_currency_symbol_follows_the_startup(currency: str) -> None:
    summary, valuations, factors = _run()
    report = build_insight(
        summary=summary, valuations=valuations, factors=factors, currency=currency, target=None
    )
    assert "US$" in report.headline


def test_risks_do_not_repeat_the_failure_rate() -> None:
    report = _insight()
    failure_mentions = [risk for risk in report.risks if "encerramento" in risk.lower()]
    assert len(failure_mentions) == 1


def test_sensitivity_sentence_names_the_assumption_without_article_issues() -> None:
    report = _insight()
    assert report.sensitivity_sentence is not None
    assert report.sensitivity_sentence.startswith("Premissa de maior impacto no tornado — ")


def test_deterministic_simulation_has_no_invented_drivers_or_tails() -> None:
    constant = {"kind": "constant", "value": 1.0}
    summary, _, _ = _run(
        "deterministic",
        revenue_uncertainty=constant,
        cost_uncertainty=constant,
        margin_uncertainty_pp=0.0,
        failure_probability_horizon=0.0,
    )
    report = _insight(key="deterministic", target=summary["percentiles"]["p50"])
    assert report.key_drivers == ()
    assert report.key_drivers_sentence is None
    assert report.upside == () and report.downside == ()
    assert "100% exatamente nesse valor" in report.valuation_paragraphs[0]
    assert report.uncertainty.label == "LOW"
    assert report.target is not None
    assert report.target.probability == 1.0
