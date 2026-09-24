from __future__ import annotations

from io import BytesIO

import pytest
from pydantic import ValidationError
from pypdf import PdfReader

from app.reports import ReportData, build_report_pdf
from tests.test_reports import report_payload


def insight_payload() -> dict[str, object]:
    payload = report_payload()
    payload["insight"] = {
        "template_version": "insight-v1",
        "headline": (
            "Valuation mediano de R$ 8,4 milhões, com faixa central entre R$ 6,1 milhões e "
            "R$ 11,7 milhões"
        ),
        "valuation_paragraphs": (
            "Nos 10.000 cenários simulados, o valuation mediano da empresa foi de R$ 8,4 "
            "milhões. Metade dos cenários produziu valuations abaixo desse valor e metade acima.",
            "O intervalo central P25–P75 ficou entre R$ 6,1 milhões e R$ 11,7 milhões, faixa "
            "onde se concentra metade dos cenários simulados.",
        ),
        "uncertainty_label": "MODERATE",
        "uncertainty_label_pt": "Moderada",
        "uncertainty_sentence": (
            "Incerteza moderada: o intervalo P25–P75 representa 67% do valuation mediano."
        ),
        "key_drivers_sentence": (
            "Os três fatores que mais explicaram a dispersão do valuation foram Receita vs. "
            "plano, Encerramento das operações e WACC, com 45%, 40% e 11% da variância "
            "explicada, respectivamente."
        ),
        "key_drivers": (
            {"label": "Receita vs. plano", "contribution": 0.45, "rho": 0.71},
            {"label": "Encerramento das operações", "contribution": 0.40, "rho": -0.58},
            {"label": "WACC", "contribution": 0.11, "rho": -0.46},
        ),
        "upside": (
            "Receita acima do plano — mediana de 1,33x nos 10% melhores cenários, contra "
            "0,97x no conjunto.",
        ),
        "downside": (
            "Mais encerramentos das operações — 100% nos 10% piores cenários, contra 8,2% no "
            "conjunto.",
        ),
        "sensitivity_sentence": (
            "Premissa de maior impacto no tornado — WACC: entre 21,0% e 27,0%, o valuation "
            "mediano varia de R$ 10,2 milhões a R$ 7,1 milhões."
        ),
        "risks": (
            "Encerramento das operações em 8,2% dos cenários.",
            "Premissa de maior impacto no tornado — WACC: entre 21,0% e 27,0%, o valuation "
            "mediano varia de R$ 10,2 milhões a R$ 7,1 milhões.",
        ),
        "executive_summary": (
            "Nos 10.000 cenários simulados, o valuation mediano foi de R$ 8,4 milhões, com "
            "faixa central (P25–P75) entre R$ 6,1 milhões e R$ 11,7 milhões.",
            "Os melhores cenários combinam receita acima do plano e WACC mais baixo.",
            "A probabilidade simulada de o valuation atingir R$ 15,0 milhões ou mais foi de "
            "27,4%. As associações descritas neste resumo não implicam causalidade.",
        ),
        "method_notes": ("Drivers: método drivers-v1.", "Tornado: método tornado-v1."),
        "target": {
            "probability": 0.274,
            "wilson95_low": 0.265,
            "wilson95_high": 0.283,
            "probability_sentence": (
                "A probabilidade simulada de o valuation atingir R$ 15,0 milhões ou mais foi "
                "de 27,4% (2.740 de 10.000 cenários)."
            ),
            "interpretation": (
                "Nos cenários em que o valuation atinge R$ 15,0 milhões ou mais, as principais "
                "diferenças são receita do Ano 5 maior e margem EBITDA maior."
            ),
            "statements": (
                "Receita do Ano 5 acima de R$ 8,1 milhões: 75% dos cenários que atingem a meta "
                "estavam acima desse nível.",
            ),
            "conditions": (
                {
                    "label": "Receita do Ano 5",
                    "unit": "currency",
                    "hit_value": 9_200_000.0,
                    "miss_value": 5_800_000.0,
                    "effect": "forte",
                },
                {
                    "label": "Encerramento das operações",
                    "unit": "binary",
                    "hit_value": 0.0,
                    "miss_value": 0.113,
                    "effect": "-11,3 p.p.",
                },
            ),
            "disclaimer": (
                "Essas diferenças descrevem associações entre os cenários simulados, não "
                "relações de causa e efeito."
            ),
        },
    }
    payload["tornado"] = {
        "base_value": 8_400_000.0,
        "items": (
            {
                "label": "WACC",
                "unit": "ratio",
                "low_level": 0.21,
                "high_level": 0.27,
                "value_at_low": 10_200_000.0,
                "value_at_high": 7_100_000.0,
                "clamped": False,
            },
            {
                "label": "Probabilidade de encerramento",
                "unit": "ratio",
                "low_level": 0.0,
                "high_level": 0.182,
                "value_at_low": 8_900_000.0,
                "value_at_high": 7_900_000.0,
                "clamped": True,
            },
        ),
    }
    return payload


def _pages(data: ReportData) -> list[str]:
    reader = PdfReader(BytesIO(build_report_pdf(data)))
    # Line wraps become newlines on extraction; compare on normalized whitespace.
    return [" ".join((page.extract_text() or "").split()) for page in reader.pages]


def _page_with(pages: list[str], heading: str) -> str:
    return next(page for page in pages if heading in page)


def test_executive_summary_opens_with_the_valuation_intelligence() -> None:
    pages = _pages(ReportData.model_validate(insight_payload()))
    summary = pages[1]
    for label in (
        "ESTIMATED VALUATION",
        "CORE RANGE",
        "DOWNSIDE",
        "UPSIDE",
        "PROBABILITY OF TARGET",
        "UNCERTAINTY",
        "TOP VALUATION DRIVERS",
    ):
        assert label in summary, label
    assert "R$ 8,4 milhões" in summary
    assert "27,4%" in summary
    assert "Moderada" in summary
    order = [summary.index(name) for name in ("Receita vs. plano", "Encerramento das", "WACC")]
    assert order == sorted(order)
    assert "Os melhores cenários combinam receita acima do plano" in summary
    assert "não implicam causalidade" in summary


def test_insight_sections_carry_drivers_target_and_sensitivity() -> None:
    pages = _pages(ReportData.model_validate(insight_payload()))
    drivers = _page_with(pages, "Valuation Drivers")
    assert "Receita acima do plano" in drivers
    assert "Mais encerramentos das operações" in drivers
    target = _page_with(pages, "What Needs to Be True?")
    assert "as principais diferenças são receita do Ano 5 maior" in target
    assert "R$ 9,2 mi" in target and "11,3%" in target
    assert "não relações de causa e efeito" in target
    risk = _page_with(pages, "Risk & Sensitivity")
    assert "Probabilidade de encerramento" in risk
    assert "21,0%" in risk and "27,0%" in risk
    assert "Encerramento das operações em 8,2% dos cenários." in risk
    assert "estimated" not in drivers
    assert "+0,713" in drivers  # pt-BR decimals in the coefficient table
    assert risk.count("Premissa de maior impacto no tornado") == 1
    assert "Atinge a meta" in target and "Target hit" not in target
    methodology = _page_with(pages, "Methodology")
    assert "Tornado: método tornado-v1." in methodology
    assert all("NOT AVAILABLE" not in page for page in pages)


def test_insight_report_is_byte_deterministic() -> None:
    data = ReportData.model_validate(insight_payload())
    assert build_report_pdf(data) == build_report_pdf(data)


def test_insight_target_must_agree_with_the_target_analysis() -> None:
    payload = insight_payload()
    insight = dict(payload["insight"])  # type: ignore[call-overload]
    insight["target"] = {**insight["target"], "probability": 0.5}
    payload["insight"] = insight
    with pytest.raises(ValidationError, match="insight target probability"):
        ReportData.model_validate(payload)


def test_executive_summary_has_at_most_three_paragraphs() -> None:
    payload = insight_payload()
    insight = dict(payload["insight"])  # type: ignore[call-overload]
    insight["executive_summary"] = ("a", "b", "c", "d")
    payload["insight"] = insight
    with pytest.raises(ValidationError):
        ReportData.model_validate(payload)


def test_distribution_marks_zero_when_values_cross_it() -> None:
    payload = insight_payload()
    valuation = dict(payload["valuation"])  # type: ignore[call-overload]
    valuation["histogram"] = {
        "edges": (-1_000_000.0, 0.0, 1_000_000.0, 20_000_000.0),
        "counts": (1_000, 4_000, 5_000),
    }
    payload["valuation"] = valuation
    pages = _pages(ReportData.model_validate(payload))
    distribution = _page_with(pages, "Monte Carlo Distribution")
    assert "R$ 0" in distribution
