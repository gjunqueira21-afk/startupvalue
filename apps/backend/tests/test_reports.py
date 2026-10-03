from __future__ import annotations

import base64
from datetime import UTC, date, datetime
from io import BytesIO

import pytest
from pydantic import ValidationError
from pypdf import PdfReader

from app.reports import ReportBrandingData, ReportData, build_report_pdf

# Canonical minimal 1x1 opaque PNG (68 bytes), decodable by reportlab's ImageReader.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def report_payload() -> dict[str, object]:
    return {
        "audit": {
            "simulation_id": "sim-471829-alpha",
            "simulation_result_id": "result-immutable-001",
            "result_hash": "b" * 64,
            "model_version": "3.0.0-dev",
            "tax_version": "br-simplified-2026-01",
            "result_schema_version": "1.0.0",
            "report_template_version": "1.0.0",
            "seed": 471829,
            "simulation_count": 10_000,
            "generated_at": datetime(2026, 9, 22, 14, 30, tzinfo=UTC),
            "analysis_date": date(2026, 9, 22),
        },
        "company": {
            "name": "Árvore Analytics & Partners <Beta>",
            "scenario_name": "Base Case",
            "sector": "SaaS B2B",
            "stage": "Series A",
            "business_model": "Subscription",
            "country": "Brasil",
            "currency": "BRL",
        },
        "valuation": {
            "basis": "Enterprise Value",
            "percentiles": {
                "p5": 3_100_000.0,
                "p10": 4_300_000.0,
                "p25": 6_100_000.0,
                "p50": 8_400_000.0,
                "p75": 11_700_000.0,
                "p90": 15_200_000.0,
                "p95": 18_900_000.0,
            },
            "mean": 9_050_000.0,
            "standard_deviation": 4_100_000.0,
            "failure_probability": 0.082,
            "uncertainty_label": "MODERATE",
            "uncertainty_ratio": 0.667,
            "breakeven_probabilities": {
                "within_12_months": 0.18,
                "within_24_months": 0.63,
                "within_60_months": 0.89,
            },
            "breakeven_month_percentiles": {"p25": 14, "p50": 19, "p75": 27},
        },
        "assumptions": [
            {"name": "Revenue Year 5", "value": "R$ 9.200.000", "source": "User"},
            {"name": "WACC", "value": "24,0", "unit": "% a.a.", "source": "User"},
            {
                "name": "Terminal growth",
                "value": "4,0",
                "unit": "% a.a.",
                "source": "User",
            },
        ],
        "dcf": {
            "status": "available",
            "metrics": [
                {"name": "Enterprise Value", "value": "R$ 8.400.000"},
                {"name": "Present value of FCFF", "value": "R$ 3.220.000"},
                {"name": "Present value of terminal value", "value": "R$ 5.180.000"},
            ],
            "note": "Terminal growth is lower than WACC.",
        },
        "venture_capital": {
            "status": "available",
            "metrics": [
                {"name": "Future Exit Value", "value": "R$ 28.000.000"},
                {"name": "Present Value", "value": "R$ 7.250.000"},
                {"name": "Required ownership", "value": "17,2%"},
            ],
        },
        "drivers": [
            {
                "name": "Revenue Year 5",
                "association": 0.713,
                "population": "unconditional",
                "sample_size": 10_000,
            },
            {
                "name": "WACC",
                "association": -0.462,
                "population": "unconditional",
                "sample_size": 10_000,
            },
        ],
        "target": {
            "target_value": 15_000_000.0,
            "probability": 0.274,
            "hit_count": 2_740,
            "miss_count": 7_260,
            "metrics": [
                {
                    "name": "Revenue Year 5",
                    "unit": "BRL",
                    "target_hit": {"p25": 8_100_000, "median": 9_200_000, "p75": 10_700_000},
                    "target_miss": {"p25": 4_900_000, "median": 5_800_000, "p75": 6_800_000},
                }
            ],
        },
        "implied_multiples": {
            "status": "available",
            "basis": "equity_dcf_over_year5_metric",
            "value_to_revenue": {
                "p25": 6.2,
                "p50": 8.4,
                "p75": 11.1,
                "eligible_count": 9_400,
                "excluded_count": 600,
            },
            "value_to_ebitda": {
                "p25": 18.5,
                "p50": 24.0,
                "p75": 31.2,
                "eligible_count": 9_100,
                "excluded_count": 900,
            },
        },
        "target_plan": {
            "status": "available",
            "hit_count": 2_740,
            "required_revenue_cagr": 0.30,
            "hit_ebitda_margin": 0.22,
            "miss_revenue_cagr": 0.14,
            "miss_ebitda_margin": 0.11,
            "trajectory": [
                {"year": 1, "revenue": 3_200_000.0},
                {"year": 2, "revenue": 4_160_000.0},
                {"year": 3, "revenue": 5_408_000.0},
                {"year": 4, "revenue": 7_030_400.0},
                {"year": 5, "revenue": 9_139_520.0},
            ],
        },
        "risks": {
            "warnings": ("Projeções de longo prazo possuem dispersão material.",),
            "limitations": ("O relatório não constitui recomendação de investimento.",),
            "downside_notes": ("Revenue miss apresentou associação com o downside.",),
            "upside_notes": ("Margin expansion apareceu com maior frequência no upside.",),
        },
        "disclaimer": (
            "Estimativa probabilística baseada nas premissas informadas. Resultados não são "
            "garantia "
            "de valor, preço de transação ou retorno futuro."
        ),
    }


def test_report_pdf_uses_persisted_result_values_and_audit_metadata() -> None:
    data = ReportData.model_validate(report_payload())

    pdf_bytes = build_report_pdf(data)
    reader = PdfReader(BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    # Short sections share a page since the layout redesign: check structure, not page count.
    assert len(reader.pages) >= 6
    for heading in (
        "Executive Summary",
        "Company Overview",
        "Financial Assumptions",
        "Monte Carlo Distribution",
        "DCF Analysis",
        "Venture Capital Method",
        "Valuation Drivers",
        "What Needs to Be True?",
        "Risk & Sensitivity",
        "Methodology & Audit Trail",
    ):
        assert heading in text, heading
    assert "Árvore Analytics & Partners <Beta>" in text
    assert "R$ 8.400.000,00" in text
    assert "R$ 6.100.000,00 - R$ 11.700.000,00" in text
    assert "27,4%" in text
    assert "2.740" in text
    assert "sim-471829-alpha" in text
    assert "result-immutable-001" in text
    assert "3.0.0-dev" in text
    assert "471829" in text
    assert "10000" in text
    assert "Revenue Year 5 apresentou a associação" in text
    assert "não implica causalidade" in text
    assert "Implied Multiples" in text
    assert "Target Plan" in text
    assert "8,4x" in text
    assert "24,0x" in text
    assert "baseado em 9.400 de 10.000 cenários elegíveis" in text
    assert "30,0%" in text
    assert "22,0%" in text
    assert "Ano 5" in text
    assert "R$ 9.139.520,00" in text
    assert "não são múltiplos de mercado" in text
    assert "não relações de causa e efeito" in text


def test_report_pdf_omits_new_sections_when_absent() -> None:
    payload = report_payload()
    del payload["implied_multiples"]
    del payload["target_plan"]
    data = ReportData.model_validate(payload)

    pdf_bytes = build_report_pdf(data)

    assert pdf_bytes.startswith(b"%PDF")
    reader = PdfReader(BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Implied Multiples" not in text
    assert "Target Plan" not in text


def test_multiple_band_rejects_zero_eligible_count() -> None:
    from app.reports.schema import MultipleBand

    with pytest.raises(ValidationError):
        MultipleBand(p25=1.0, p50=2.0, p75=3.0, eligible_count=0, excluded_count=0)


def test_report_pdf_is_byte_deterministic_for_same_payload() -> None:
    data = ReportData.model_validate(report_payload())

    first = build_report_pdf(data)
    second = build_report_pdf(data)

    assert first == second
    assert first.startswith(b"%PDF-")


def test_report_rejects_inconsistent_target_counts() -> None:
    payload = report_payload()
    target = dict(payload["target"])  # type: ignore[arg-type]
    target["hit_count"] = 2_739
    payload["target"] = target

    with pytest.raises(ValidationError, match="must equal simulation_count"):
        ReportData.model_validate(payload)


def test_report_rejects_non_monotonic_percentiles() -> None:
    payload = report_payload()
    valuation = dict(payload["valuation"])  # type: ignore[arg-type]
    percentiles = dict(valuation["percentiles"])  # type: ignore[arg-type]
    percentiles["p75"] = 7_000_000.0
    valuation["percentiles"] = percentiles
    payload["valuation"] = valuation

    with pytest.raises(ValidationError, match="percentiles must be nondecreasing"):
        ReportData.model_validate(payload)


# --- Task 9: white-label branding and free-tier watermark --------------------


def test_branded_report_renders_firm_name_and_logo_and_hides_quantovale() -> None:
    data = ReportData.model_validate(report_payload())
    branding = ReportBrandingData(
        firm_name="Alfa Consultoria",
        primary_color="#123456",
        footer_text="Relatório preparado por Alfa Consultoria",
        logo_bytes=TINY_PNG,
        logo_media_type="image/png",
    )

    pdf_bytes = build_report_pdf(data, branding=branding)

    assert pdf_bytes.startswith(b"%PDF")
    reader = PdfReader(BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Alfa Consultoria" in text
    # The product mark/name is replaced everywhere except audit identifiers
    # and disclaimers, which must always render. This includes chart-caption
    # "Fonte: ..." source attributions (pdf_theme.SOURCE), not just the
    # cover/chrome brand mark.
    assert "STARTUPVALUE" not in text
    assert "QuantoVale" not in text
    assert "sim-471829-alpha" in text  # audit identifier: always present
    assert "não são garantia de valor" in text  # disclaimer: always present
    # PDF document metadata (title/author/creator) must not expose the vendor
    # on a white-label report either.
    assert reader.metadata is not None
    assert reader.metadata.author == "Alfa Consultoria"
    assert "Alfa Consultoria" in (reader.metadata.title or "")
    assert "QuantoVale" not in (reader.metadata.title or "")
    assert "QuantoVale" not in (reader.metadata.author or "")
    assert "QuantoVale" not in (reader.metadata.creator or "")


def test_branded_report_with_corrupt_logo_bytes_still_renders() -> None:
    data = ReportData.model_validate(report_payload())
    branding = ReportBrandingData(
        firm_name="Beta Capital",
        logo_bytes=b"not an image",
        logo_media_type="image/png",
    )

    pdf_bytes = build_report_pdf(data, branding=branding)

    assert pdf_bytes.startswith(b"%PDF")
    reader = PdfReader(BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Beta Capital" in text
    assert "STARTUPVALUE" not in text
    assert "QuantoVale" not in text
    assert reader.metadata is not None
    assert reader.metadata.author == "Beta Capital"
    assert "QuantoVale" not in (reader.metadata.title or "")


def test_unbranded_report_still_shows_product_name() -> None:
    data = ReportData.model_validate(report_payload())

    pdf_bytes = build_report_pdf(data)

    reader = PdfReader(BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "QUANTOVALE" in text


def test_watermark_renders_and_changes_output_size() -> None:
    data = ReportData.model_validate(report_payload())

    plain = build_report_pdf(data)
    watermarked = build_report_pdf(data, watermark=True)

    assert watermarked.startswith(b"%PDF")
    assert len(watermarked) != len(plain)
    reader = PdfReader(BytesIO(watermarked))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "QUANTOVALE" in text
    assert "RESUMO GRATUITO" in text


def test_default_build_report_pdf_call_is_unaffected_by_new_parameters() -> None:
    data = ReportData.model_validate(report_payload())

    pdf_bytes = build_report_pdf(data)

    assert pdf_bytes.startswith(b"%PDF-")

def test_branded_report_clips_overlong_firm_name_and_footer_text() -> None:
    data = ReportData.model_validate(report_payload())
    firm_name = "Consultoria " + "X" * 108  # 120 chars, the schema maximum
    footer_text = "Rodape " + "Y" * 293  # 300 chars
    assert len(firm_name) == 120 and len(footer_text) == 300
    branding = ReportBrandingData(firm_name=firm_name, footer_text=footer_text)

    pdf_bytes = build_report_pdf(data, branding=branding)

    assert pdf_bytes.startswith(b"%PDF")
    reader = PdfReader(BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    # Cover and page chrome draw clipped strings (with an ellipsis), never the
    # full user-supplied text that would run over the badge / context block.
    assert firm_name not in text
    assert footer_text not in text
    assert "Consultoria XXX" in text
    assert "Rodape YYY" in text
    assert "X..." in text
    assert "Y..." in text
