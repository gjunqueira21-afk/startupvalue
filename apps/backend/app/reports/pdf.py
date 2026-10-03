"""A4 institutional PDF renderer for immutable SimulationResult snapshots.

Page flow: cover; executive summary (one page); company overview, financial
assumptions and valuation methods grouped on one page; Monte Carlo
distribution; valuation drivers; what needs to be true; risk & sensitivity;
methodology & audit trail; optional appendix. Analytical sections open a new
page, short context sections share one. The document is built twice so the
footer can print "Página N de M"; both passes are deterministic.
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Callable
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Table,
    TableStyle,
)

from app.decision.target_plan import MIN_HIT_SAMPLE
from app.insights.formatting import compact_money

from .insight_pdf import (
    driver_blocks,
    executive_summary_blocks,
    kpi_cell,
    sensitivity_blocks,
    target_blocks,
)
from .narrative import executive_narrative, format_integer, format_money, format_percent
from .pdf_charts import DriverChart, HistogramChart
from .pdf_theme import (
    GAP_L,
    GAP_M,
    GAP_S,
    GREEN,
    INK,
    LINE,
    MUTED,
    PAGE_MARGIN_BOTTOM,
    PAGE_MARGIN_TOP,
    PAGE_MARGIN_X,
    PALE,
    SOURCE,
    WHITE,
    WIDTH,
    Numbering,
    SectionHeader,
    bullets,
    callout,
    columns,
    data_table,
    figure,
    gap,
    key_value_table,
    span,
    stat_strip,
    text,
)
from .pdf_theme import (
    styles as report_styles,
)
from .schema import MethodAnalysis, PercentileKey, ReportBrandingData, ReportData

PAGE_WIDTH, PAGE_HEIGHT = A4
COVER_TINT = colors.HexColor("#E3EEE8")
ASSUMPTIONS_INLINE = 14
WATERMARK_TEXT = "QUANTOVALE · RESUMO GRATUITO"

DRIVER_STATUS = {
    "estimated": "estimado",
    "not_estimable_constant": "constante",
    "insufficient_data": "dados insuficientes",
}
METHOD_STATUS = {"not_available": "NÃO DISPONÍVEL", "invalid": "INVÁLIDO"}
MULTIPLES_REASON = {
    "metrics_unavailable_for_input_mode": (
        "Este modo de entrada não produz receita ou EBITDA no ano 5 dos cenários simulados, "
        "etapa necessária para calcular múltiplos implícitos."
    ),
    "insufficient_eligible_scenarios": (
        "Poucos cenários simulados têm valuation e a métrica de referência positivos ao mesmo "
        "tempo para estimar múltiplos de forma confiável."
    ),
}
MULTIPLES_DISCLAIMER = (
    "Múltiplos implícitos nas suas premissas — não são múltiplos de mercado."
)
TARGET_PLAN_DISCLAIMER = (
    "Essas diferenças descrevem associações entre os cenários simulados, não relações de "
    "causa e efeito."
)


class _NumberedCanvas(Canvas):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["invariant"] = 1
        kwargs["pageCompression"] = 1
        super().__init__(*args, **kwargs)


def _date(data: ReportData) -> str:
    return data.audit.analysis_date.strftime("%d/%m/%Y")


def _short_id(data: ReportData) -> str:
    return data.audit.simulation_id[:12]


def _source_label(branding: ReportBrandingData | None) -> str:
    """Vendor-free computational-source label for figure captions when branded.

    Unbranded reports keep the full ``SOURCE`` constant ("QuantoVale
    SimulationResult"); a white-label report never mentions the vendor, and
    does not substitute the consultant's firm name either — the firm is not
    the computational source, so a neutral "SimulationResult" is used
    instead of mislabeling it.
    """
    return SOURCE if branding is None else "SimulationResult"


def _clip(canvas: Canvas, value: str, font: str, size: float, width: float) -> str:
    if canvas.stringWidth(value, font, size) <= width:
        return value
    while value and canvas.stringWidth(f"{value}...", font, size) > width:
        value = value[:-1]
    return f"{value.rstrip()}..."


def _target_metric_value(value: float, unit: str | None) -> str:
    if unit in {"BRL", "USD", "EUR"}:
        return format_money(value, unit)
    if unit == "%":
        return format_percent(value)
    if unit == "x":
        return f"{value:.2f}x".replace(".", ",")
    return f"{value:.2f}".replace(".", ",")


def _breakeven_label(name: str) -> str:
    match = re.fullmatch(r"within_(\d+)_months", name)
    return f"Em até {match.group(1)} meses" if match else name.replace("_", " ")


# --------------------------------------------------------------------------- chrome


def _brand_mark(canvas: Canvas, x: float, y: float, size: float, color: Any = GREEN) -> None:
    """Square brand mark: three ascending bars, a stylised distribution."""
    canvas.setFillColor(color)
    canvas.rect(x, y, size, size, stroke=0, fill=1)
    canvas.setFillColor(WHITE)
    bar = size * 0.16
    for index, height in enumerate((0.34, 0.56, 0.74)):
        canvas.rect(
            x + size * 0.18 + index * (bar + size * 0.08), y + size * 0.14, bar, size * height,
            stroke=0, fill=1,
        )


def _logo_reader(branding: ReportBrandingData | None) -> ImageReader | None:
    """Decode the firm's logo, or None on any failure (silently skipped).

    Any exception from reading/decoding the stored bytes — corrupt data, an
    unsupported format, a truncated upload — must never fail report
    generation; the cover simply renders without a logo.
    """
    if branding is None or not branding.logo_bytes:
        return None
    try:
        return ImageReader(BytesIO(branding.logo_bytes))
    except Exception:  # noqa: BLE001 - any decode failure skips the logo, never raises.
        return None


def _draw_watermark(canvas: Canvas) -> None:
    """Diagonal translucent free-tier watermark, drawn across the full page."""
    canvas.saveState()
    canvas.translate(PAGE_WIDTH / 2, PAGE_HEIGHT / 2)
    canvas.rotate(45)
    canvas.setFillColor(INK)
    canvas.setFillAlpha(0.08)
    canvas.setFont("Helvetica-Bold", 40)
    canvas.drawCentredString(0, 0, WATERMARK_TEXT)
    canvas.restoreState()


def _cover(
    data: ReportData,
    styles: dict[str, ParagraphStyle],
    branding: ReportBrandingData | None = None,
    watermark: bool = False,
) -> Callable[[Canvas, Any], None]:
    audit = data.audit
    accent = (
        colors.HexColor(branding.primary_color)
        if branding is not None and branding.primary_color
        else GREEN
    )
    logo = _logo_reader(branding)

    def draw(canvas: Canvas, document: Any) -> None:
        canvas.saveState()
        left = PAGE_MARGIN_X + 4 * mm
        right = PAGE_WIDTH - PAGE_MARGIN_X
        width = right - left
        canvas.setFillColor(accent)
        canvas.rect(0, 0, 6 * mm, PAGE_HEIGHT, stroke=0, fill=1)

        top = PAGE_HEIGHT - 28 * mm
        mark_size = 9 * mm
        if branding is not None:
            if logo is not None:
                # Any failure here (e.g. a format reportlab's drawImage rejects
                # at draw time despite ImageReader having decoded it) must not
                # fail the report; the logo is simply skipped.
                with contextlib.suppress(Exception):
                    canvas.drawImage(
                        logo,
                        left,
                        top,
                        width=mark_size,
                        height=mark_size,
                        preserveAspectRatio=True,
                        mask="auto",
                    )
            name_label = branding.firm_name
        else:
            _brand_mark(canvas, left, top, mark_size, accent)
            name_label = "STARTUPVALUE"
        canvas.setFillColor(INK)
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(left + 12.5 * mm, top + 4.4 * mm, name_label, charSpace=1.6)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        tagline = (
            branding.footer_text
            if branding is not None and branding.footer_text
            else "Valuation probabilístico de startups"
        )
        # ``tagline`` always falls back to a non-empty default above, so it is
        # unconditionally drawn.
        canvas.drawString(left + 12.5 * mm, top + 0.4 * mm, tagline)
        badge = "CONFIDENCIAL"
        canvas.setFont("Helvetica-Bold", 7.5)
        badge_w = canvas.stringWidth(badge, "Helvetica-Bold", 7.5) + 11 * 1 + 5 * mm
        canvas.setStrokeColor(INK)
        canvas.setLineWidth(0.7)
        canvas.rect(right - badge_w, top + 1.8 * mm, badge_w, 6 * mm, stroke=1, fill=0)
        canvas.setFillColor(INK)
        canvas.drawCentredString(right - badge_w / 2, top + 3.9 * mm, badge, charSpace=1)

        # Title block.
        y = PAGE_HEIGHT - 84 * mm
        canvas.setFillColor(accent)
        canvas.setFont("Helvetica-Bold", 8.5)
        canvas.drawString(left, y, "RELATÓRIO DE VALUATION", charSpace=1.4)
        canvas.setFillColor(INK)
        canvas.setFont("Helvetica-Bold", 31)
        canvas.drawString(left, y - 14 * mm, "Valuation & Monte Carlo")
        canvas.drawString(left, y - 26 * mm, "Analysis")
        canvas.setStrokeColor(accent)
        canvas.setLineWidth(2)
        canvas.line(left, y - 34 * mm, left + 22 * mm, y - 34 * mm)
        name = Paragraph(escape(data.company.name), styles["cover_company"])
        _, name_h = name.wrap(width, 60 * mm)
        name_top = y - 42 * mm
        name.drawOn(canvas, left, name_top - name_h)

        facts = Table(
            [
                [
                    [
                        Paragraph("CENÁRIO", styles["stat_label"]),
                        Paragraph(escape(data.company.scenario_name), styles["cover_fact"]),
                    ],
                    [
                        Paragraph("DATA-BASE", styles["stat_label"]),
                        Paragraph(_date(data), styles["cover_fact"]),
                    ],
                    [
                        Paragraph("CENÁRIOS SIMULADOS", styles["stat_label"]),
                        Paragraph(format_integer(audit.simulation_count), styles["cover_fact"]),
                    ],
                    [
                        Paragraph("BASE DO VALUATION", styles["stat_label"]),
                        Paragraph(escape(data.valuation.basis), styles["cover_fact"]),
                    ],
                ]
            ],
            colWidths=[width * 0.3, width * 0.17, width * 0.2, width * 0.33],
        )
        facts.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("LINEABOVE", (0, 0), (-1, 0), 0.6, LINE),
                ]
            )
        )
        _, facts_h = facts.wrap(width, 60 * mm)
        facts_top = name_top - name_h - 9 * mm
        facts.drawOn(canvas, left, facts_top - facts_h)

        # Audit block anchored at the bottom.
        def meta(label: str, value: str) -> list[Paragraph]:
            return [
                Paragraph(label, styles["stat_label"]),
                Paragraph(escape(value), styles["cover_mono"]),
            ]

        audit_table = Table(
            [
                [
                    meta("SIMULATION ID", audit.simulation_id),
                    meta("SIMULATION RESULT ID", audit.simulation_result_id),
                ],
                [meta("RESULT CHECKSUM (SHA-256)", audit.result_hash), ""],
                [
                    meta(
                        "MODELO · TEMPLATE",
                        f"{audit.model_version} · {audit.report_template_version}",
                    ),
                    meta("SEED · CENÁRIOS", f"{audit.seed} · {audit.simulation_count}"),
                ],
            ],
            colWidths=[width / 2, width / 2],
        )
        audit_table.setStyle(
            TableStyle(
                [
                    ("SPAN", (0, 1), (1, 1)),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ]
            )
        )
        _, audit_h = audit_table.wrap(width, 80 * mm)
        notice = Paragraph(
            "Documento confidencial, destinado exclusivamente aos destinatários autorizados. "
            "Estimativa probabilística baseada nas premissas informadas; não constitui "
            "garantia de valor, preço de transação ou retorno futuro.",
            styles["caption"],
        )
        _, notice_h = notice.wrap(width, 30 * mm)
        notice.drawOn(canvas, left, 14 * mm)
        audit_bottom = 14 * mm + notice_h + 6 * mm
        audit_table.drawOn(canvas, left, audit_bottom)
        rule_y = audit_bottom + audit_h + 4 * mm
        canvas.setStrokeColor(INK)
        canvas.setLineWidth(0.8)
        canvas.line(left, rule_y, right, rule_y)

        # Silhouette of the simulated distribution: the report's subject, drawn from data.
        histogram = data.valuation.histogram
        space_top = facts_top - facts_h - 12 * mm
        space_bottom = rule_y + 14 * mm
        if histogram is not None and space_top - space_bottom > 30 * mm:
            height = min(46 * mm, space_top - space_bottom)
            base_y = space_bottom
            counts = histogram.counts
            peak = max(counts) or 1
            step = width / len(counts)
            canvas.setFillColor(COVER_TINT)
            path = canvas.beginPath()
            path.moveTo(left, base_y)
            for index, count in enumerate(counts):
                bar_h = height * count / peak
                path.lineTo(left + index * step, base_y + bar_h)
                path.lineTo(left + (index + 1) * step, base_y + bar_h)
            path.lineTo(right, base_y)
            path.close()
            canvas.drawPath(path, stroke=0, fill=1)
            start, end = histogram.edges[0], histogram.edges[-1]
            median = data.valuation.percentiles["p50"]
            x = left + width * min(max((median - start) / (end - start), 0.0), 1.0)
            canvas.setStrokeColor(accent)
            canvas.setLineWidth(0.9)
            canvas.line(x, base_y, x, base_y + height + 3 * mm)
            canvas.setStrokeColor(LINE)
            canvas.setLineWidth(0.5)
            canvas.line(left, base_y, right, base_y)
            canvas.setFont("Helvetica", 6.8)
            canvas.setFillColor(MUTED)
            canvas.drawString(
                x + 1.5 * mm, base_y + height + 1 * mm, "Mediana (P50) dos cenários simulados"
            )
        if watermark:
            _draw_watermark(canvas)
        canvas.restoreState()

    return draw


def _page_chrome(
    data: ReportData,
    total: int | None,
    branding: ReportBrandingData | None = None,
    watermark: bool = False,
) -> Callable[[Canvas, Any], None]:
    def draw(canvas: Canvas, document: Any) -> None:
        canvas.saveState()
        left, right = PAGE_MARGIN_X, PAGE_WIDTH - PAGE_MARGIN_X
        header_y = PAGE_HEIGHT - 13 * mm
        brand_label = branding.firm_name if branding is not None else "STARTUPVALUE"
        canvas.setFont("Helvetica-Bold", 6.8)
        canvas.setFillColor(GREEN if branding is None else INK)
        canvas.drawString(left, header_y, brand_label, charSpace=0.9)
        brand_w = canvas.stringWidth(brand_label, "Helvetica-Bold", 6.8) + 11 * 0.9
        canvas.setFont("Helvetica", 6.8)
        canvas.setFillColor(MUTED)
        chrome_tagline = (
            branding.footer_text
            if branding is not None and branding.footer_text
            else "Valuation & Monte Carlo Analysis"
        )
        # ``chrome_tagline`` always falls back to a non-empty default above,
        # so it is unconditionally drawn.
        canvas.drawString(left + brand_w + 2 * mm, header_y, chrome_tagline)
        context = f"{data.company.scenario_name} · Data-base {_date(data)}"
        canvas.drawRightString(
            right, header_y, _clip(canvas, context, "Helvetica", 6.8, 90 * mm)
        )
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(left, header_y - 2.6 * mm, right, header_y - 2.6 * mm)

        canvas.line(left, 14 * mm, right, 14 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        footer_name = data.company.name
        if len(footer_name) > 40:
            footer_name = f"{footer_name[:37]}..."
        canvas.drawString(left, 9.5 * mm, f"CONFIDENCIAL | {footer_name}")
        page = f"Página {document.page}" + (f" de {total}" if total else "")
        canvas.drawRightString(right, 9.5 * mm, f"Simulation {_short_id(data)} | {page}")
        if watermark:
            _draw_watermark(canvas)
        canvas.restoreState()

    return draw


def _document(
    buffer: BytesIO,
    data: ReportData,
    styles: dict[str, ParagraphStyle],
    total: int | None,
    branding: ReportBrandingData | None = None,
    watermark: bool = False,
) -> BaseDocTemplate:
    if branding is not None:
        title = f"{branding.firm_name} - {data.company.name}"
        author = branding.firm_name
        creator = "Valuation report"
    else:
        title = f"QuantoVale - {data.company.name}"
        author = "QuantoVale"
        creator = f"QuantoVale report template {data.audit.report_template_version}"
    document = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=PAGE_MARGIN_X,
        rightMargin=PAGE_MARGIN_X,
        topMargin=PAGE_MARGIN_TOP,
        bottomMargin=PAGE_MARGIN_BOTTOM,
        title=title,
        author=author,
        subject="Valuation & Monte Carlo Analysis",
        creator=creator,
    )
    frame = Frame(
        document.leftMargin,
        document.bottomMargin,
        document.width,
        document.height,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    document.addPageTemplates(
        [
            PageTemplate(
                id="cover", frames=[frame], onPage=_cover(data, styles, branding, watermark)
            ),
            PageTemplate(
                id="report",
                frames=[frame],
                onPage=_page_chrome(data, total, branding, watermark),
            ),
        ]
    )
    return document


# --------------------------------------------------------------------------- sections


def _header(
    numbering: Numbering, eyebrow: str, title: str, room: float = 60 * mm
) -> list[Any]:
    """Section header preceded by a conditional break: never orphaned at a page foot."""
    return [CondPageBreak(room), SectionHeader(numbering.next_section(), eyebrow, title)]


def _legacy_summary(data: ReportData, styles: dict[str, ParagraphStyle]) -> list[Any]:
    """Summary for reports built without the executive insight block."""
    currency = data.company.currency
    p = data.valuation.percentiles
    story: list[Any] = [
        key_value_table(
            [
                ("Valuation mediano (P50)", format_money(p["p50"], currency)),
                (
                    "Core range (P25-P75)",
                    f"{format_money(p['p25'], currency)} - {format_money(p['p75'], currency)}",
                ),
                ("Downside (P10)", format_money(p["p10"], currency)),
                ("Upside (P90)", format_money(p["p90"], currency)),
                ("Incerteza", data.valuation.uncertainty_label),
                ("Probabilidade de failure", format_percent(data.valuation.failure_probability)),
            ],
            styles,
        ),
        gap(GAP_L),
        Paragraph("LEITURA EXECUTIVA", styles["eyebrow"]),
    ]
    story.extend(Paragraph(escape(item), styles["body_lead"]) for item in executive_narrative(data))
    return story


def _company_overview(data: ReportData, styles: dict[str, ParagraphStyle]) -> Table:
    company = data.company

    def fact(label: str, value: str | None) -> list[Paragraph]:
        return [
            Paragraph(label, styles["stat_label"]),
            Paragraph(escape(value or "N/A"), styles["fact_value"]),
        ]

    cells: list[list[Any]] = [
        [fact("EMPRESA", company.name), "", fact("CENÁRIO", company.scenario_name), ""],
        [
            fact("SETOR", company.sector),
            fact("ESTÁGIO", company.stage),
            fact("MODELO DE NEGÓCIO", company.business_model),
            fact("PAÍS", company.country),
        ],
        [
            fact("MOEDA", company.currency),
            fact("DATA-BASE", _date(data)),
            fact("CENÁRIOS SIMULADOS", format_integer(data.audit.simulation_count)),
            fact("BASE DO VALUATION", data.valuation.basis),
        ],
    ]
    table = Table(cells, colWidths=[WIDTH / 4] * 4, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (1, 0)),
                ("SPAN", (2, 0), (3, 0)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEABOVE", (0, 0), (-1, 0), 0.9, INK),
                ("LINEBELOW", (0, 0), (-1, -2), 0.35, LINE),
                ("LINEBELOW", (0, -1), (-1, -1), 0.6, MUTED),
            ]
        )
    )
    return table


def _assumption_table(data: ReportData, styles: dict[str, ParagraphStyle], rows: Any) -> Table:
    return data_table(
        ["Premissa", "Valor", "Unidade", "Origem"],
        [[item.name, item.value, item.unit or "-", item.source or "-"] for item in rows],
        [64 * mm, 32 * mm, 32 * mm, 42 * mm],
        styles,
        numeric=[1],
    )


def _method_card(title: str, method: MethodAnalysis, styles: dict[str, ParagraphStyle]) -> Table:
    card = Table(
        [
            [
                [
                    Paragraph(escape(title), styles["td_bold"]),
                    Paragraph(METHOD_STATUS.get(method.status, method.status), styles["eyebrow"]),
                    Paragraph(escape(method.note or "Análise não disponível."), styles["small"]),
                ]
            ]
        ],
        colWidths=[span(6)],
    )
    card.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return card


def _method_section(
    title: str,
    eyebrow: str,
    method: MethodAnalysis,
    styles: dict[str, ParagraphStyle],
    numbering: Numbering,
) -> list[Any]:
    # Short sections: keep header, table and note together and let them share a page.
    page_break, header = _header(numbering, eyebrow, title, room=35 * mm)
    block: list[Any] = [header]
    if method.status != "available":
        block.append(_method_card(title, method, styles))
    else:
        block.append(
            data_table(
                ["Métrica", "Valor", "Nota"],
                [
                    [metric.name, metric.value, metric.explanation or "-"]
                    for metric in method.metrics
                ],
                [56 * mm, 34 * mm, 80 * mm],
                styles,
                numeric=[1],
            )
        )
        if method.note:
            block.append(Paragraph(escape(method.note), styles["table_note"]))
    return [page_break, KeepTogether(block), gap(GAP_L)]


def _distribution(
    data: ReportData,
    styles: dict[str, ParagraphStyle],
    numbering: Numbering,
    source_label: str,
) -> list[Any]:
    currency = data.company.currency
    p = data.valuation.percentiles
    story = _header(numbering, "Distribuição Monte Carlo", "Monte Carlo Distribution")
    note = (
        "Os percentis incluem todos os resultados simulados, inclusive valores não positivos "
        "e estados de falha."
    )
    histogram = data.valuation.histogram
    if histogram is not None:
        chart = figure(
            HistogramChart(histogram, p, currency),
            numbering.next_figure(),
            f"Distribuição simulada do valuation — {data.valuation.basis}",
            f"{_short_id(data)} · {format_integer(data.audit.simulation_count)} cenários · "
            f"{len(histogram.counts)} faixas",
            styles,
            note=note,
            source_label=source_label,
        )
        story.append(KeepTogether(chart))
    else:
        story.append(
            Paragraph("Histograma não persistido neste resultado. " + note, styles["small"])
        )
    story.append(gap(GAP_M + 1 * mm))

    labels: dict[PercentileKey, str] = {
        "p5": "P5",
        "p10": "P10 · downside",
        "p25": "P25",
        "p50": "P50 · mediana",
        "p75": "P75",
        "p90": "P90 · upside",
        "p95": "P95",
    }
    rows = [[labels[key], format_money(p[key], currency)] for key in labels]
    rows.append(["Média", format_money(data.valuation.mean, currency)])
    rows.append(["Desvio padrão", format_money(data.valuation.standard_deviation, currency)])
    right_width = span(5)
    percentile_table = data_table(
        ["Estatística", f"Valor ({currency})"],
        rows,
        [right_width - 40 * mm, 40 * mm],
        styles,
        numeric=[1],
        extra=[
            ("FONTNAME", (1, 4), (1, 4), "Helvetica-Bold"),
            ("BACKGROUND", (0, 3), (-1, 5), PALE),
        ],
    )
    right: list[Any] = [Paragraph("PERCENTIS", styles["eyebrow"]), percentile_table]
    breakeven = data.valuation.breakeven_probabilities
    if breakeven:
        right.extend(
            [
                gap(GAP_M),
                Paragraph("BREAKEVEN", styles["eyebrow"]),
                data_table(
                    ["Horizonte", "Probabilidade"],
                    [
                        [_breakeven_label(name), format_percent(value)]
                        for name, value in breakeven.items()
                    ],
                    [right_width - 30 * mm, 30 * mm],
                    styles,
                    numeric=[1],
                ),
            ]
        )
    else:
        right.extend(
            [
                gap(GAP_S),
                Paragraph(
                    "Breakeven: N/A — não informado no resultado persistido.", styles["caption"]
                ),
            ]
        )
    left: list[Any] = [Paragraph("LEITURA DA DISTRIBUIÇÃO", styles["eyebrow"])]
    if data.insight is not None:
        left.extend(
            Paragraph(text(item), styles["body"]) for item in data.insight.valuation_paragraphs
        )
        left.append(Paragraph(text(data.insight.uncertainty_sentence), styles["body"]))
    else:
        left.append(
            Paragraph(
                f"Em {format_integer(data.audit.simulation_count)} cenários, a mediana foi "
                f"{escape(format_money(p['p50'], currency))}; probabilidade de failure "
                f"{format_percent(data.valuation.failure_probability)}.",
                styles["body"],
            )
        )
    story.append(columns(left, right, span(7), right_width))
    return story


def _drivers(
    data: ReportData,
    styles: dict[str, ParagraphStyle],
    numbering: Numbering,
    source_label: str,
) -> list[Any]:
    story = _header(numbering, "Drivers do valuation", "Valuation Drivers")
    if data.insight is not None:
        story.extend(driver_blocks(data, styles, numbering, source_label))
    elif data.drivers:
        story.append(
            KeepTogether(
                figure(
                    DriverChart([(d.name, d.association, d.contribution) for d in data.drivers]),
                    numbering.next_figure(),
                    "Associação de cada fator com o valuation (Spearman, -1 a +1)",
                    f"{_short_id(data)} · {format_integer(data.audit.simulation_count)} cenários",
                    styles,
                    source_label=source_label,
                )
            )
        )
    if data.drivers:
        rows = [
            [
                driver.name,
                "N/A" if driver.contribution is None else format_percent(driver.contribution),
                "N/A"
                if driver.association is None
                else f"{driver.association:+.3f}".replace(".", ","),
                format_integer(driver.sample_size),
                DRIVER_STATUS.get(driver.status, driver.status),
            ]
            for driver in data.drivers
        ]
        story.append(
            KeepTogether(
                [
                    Paragraph("Detalhe dos coeficientes", styles["h2"]),
                    data_table(
                        ["Fator", "Participação", "Spearman", "Cenários (N)", "Status"],
                        rows,
                        [70 * mm, 25 * mm, 25 * mm, 25 * mm, 25 * mm],
                        styles,
                        numeric=[1, 2, 3],
                    ),
                    Paragraph(
                        "Participação: parcela da variância dos postos do valuation explicada "
                        "por cada driver primitivo (coeficiente de regressão padronizada de "
                        "postos ao quadrado, normalizado). Coeficientes descrevem associação "
                        "monotônica nos cenários simulados; não demonstram causalidade.",
                        styles["table_note"],
                    ),
                ]
            )
        )
    else:
        story.append(Paragraph("N/A - drivers não informados.", styles["body"]))
    return story


def _target(
    data: ReportData, styles: dict[str, ParagraphStyle], numbering: Numbering
) -> list[Any]:
    story = _header(numbering, "O que precisa ser verdade", "What Needs to Be True?")
    target = data.target
    if target is None:
        story.append(
            callout(
                [
                    Paragraph(
                        "Target valuation não configurado. Informe uma meta na exportação para "
                        "ver a probabilidade de atingi-la e as condições associadas.",
                        styles["body"],
                    )
                ]
            )
        )
        return story
    currency = data.company.currency
    narrative = data.insight.target if data.insight is not None else None
    cells: list[tuple[str, str, str]] = [
        (
            "Valuation-alvo",
            compact_money(target.target_value, currency, short=True),
            format_money(target.target_value, currency),
        ),
        ("Probabilidade de atingir", format_percent(target.probability), "Fração dos cenários"),
        (
            "Cenários que atingem",
            format_integer(target.hit_count),
            f"de {format_integer(data.audit.simulation_count)}",
        ),
        (
            "Cenários que não atingem",
            format_integer(target.miss_count),
            f"de {format_integer(data.audit.simulation_count)}",
        ),
    ]
    if narrative is not None:
        cells.append(
            (
                "Erro Monte Carlo (IC 95%)",
                f"{format_percent(narrative.wilson95_low)} a "
                f"{format_percent(narrative.wilson95_high)}",
                "Intervalo de Wilson",
            )
        )
    # Sized so every label stays on one line (text extraction keeps it whole).
    widths = (
        [31 * mm, 34.5 * mm, 32 * mm, 36.5 * mm, 36 * mm]
        if len(cells) == 5
        else [WIDTH / len(cells)] * len(cells)
    )
    story.append(
        stat_strip(
            [
                kpi_cell(label, value, caption, styles, width - 12, label_style="stat_label")
                for (label, value, caption), width in zip(cells, widths, strict=True)
            ],
            widths,
        )
    )
    story.append(gap(GAP_M))
    if narrative is not None:
        story.extend(target_blocks(data, styles))
    if target.metrics:
        rows: list[list[Any]] = []
        extra: list[tuple[Any, ...]] = []
        group = 0
        # Quartiles of a 0/1 event carry no information; its rate is in the table above.
        for metric in (item for item in target.metrics if item.unit != "0/1"):
            present = [
                (label, distribution)
                for label, distribution in (
                    ("Atinge a meta", metric.target_hit),
                    ("Demais", metric.target_miss),
                )
                if distribution is not None
            ]
            if not present:
                continue
            first = len(rows) + 1
            for index, (label, distribution) in enumerate(present):
                rows.append(
                    [
                        metric.name if index == 0 else "",
                        label,
                        _target_metric_value(distribution.p25, metric.unit),
                        _target_metric_value(distribution.median, metric.unit),
                        _target_metric_value(distribution.p75, metric.unit),
                    ]
                )
            last = len(rows)
            if last > first:
                extra.append(("SPAN", (0, first), (0, last)))
                extra.append(("LINEBELOW", (1, first), (-1, last - 1), 0.35, WHITE))
            if group % 2 == 1:
                extra.append(("BACKGROUND", (0, first), (-1, last), PALE))
            extra.append(("FONTNAME", (1, first), (-1, first), "Helvetica-Bold"))
            group += 1
        if rows:
            story.append(
                KeepTogether(
                    [
                        Paragraph(
                            "Distribuição das condições (P25 / mediana / P75)", styles["h2"]
                        ),
                        data_table(
                            ["Parâmetro", "Grupo", "P25", "Mediana", "P75"],
                            rows,
                            [50 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm],
                            styles,
                            numeric=[2, 3, 4],
                            extra=[
                                ("VALIGN", (0, 1), (0, -1), "MIDDLE"),
                                ("TOPPADDING", (0, 1), (-1, -1), 2.4),
                                ("BOTTOMPADDING", (0, 1), (-1, -1), 2.6),
                                *extra,
                            ],
                        ),
                        Paragraph(
                            "Linha em negrito: cenários que atingem a meta. Valores na unidade "
                            "de cada parâmetro.",
                            styles["table_note"],
                        ),
                    ]
                )
            )
    if narrative is None:
        story.extend(
            [
                gap(GAP_S),
                Paragraph(
                    "As diferenças entre grupos são condicionais aos cenários simulados e não "
                    "garantem efeito causal.",
                    styles["body"],
                ),
            ]
        )
    return story


def _implied_multiples(
    data: ReportData, styles: dict[str, ParagraphStyle], numbering: Numbering
) -> list[Any]:
    """Implied value/revenue and value/EBITDA multiples; absent on pre-1.4 results."""
    section = data.implied_multiples
    if section is None:
        return []
    story = _header(numbering, "Múltiplos implícitos", "Implied Multiples", room=45 * mm)
    if section.status != "available":
        reason = MULTIPLES_REASON.get(
            section.reason or "", "Múltiplos implícitos não disponíveis para esta simulação."
        )
        story.append(Paragraph(escape(reason), styles["body"]))
        return story
    rows: list[list[Any]] = []
    notes: list[str] = []
    for label, band in (
        ("Valor / Receita", section.value_to_revenue),
        ("Valor / EBITDA", section.value_to_ebitda),
    ):
        if band is None:
            rows.append([label, "N/A", "N/A", "N/A"])
            continue
        rows.append(
            [
                label,
                f"{band.p25:.1f}x".replace(".", ","),
                f"{band.p50:.1f}x".replace(".", ","),
                f"{band.p75:.1f}x".replace(".", ","),
            ]
        )
        total = band.eligible_count + band.excluded_count
        notes.append(
            f"{label}: baseado em {format_integer(band.eligible_count)} de "
            f"{format_integer(total)} cenários elegíveis."
        )
    story.append(
        data_table(
            ["Múltiplo", "P25", "P50", "P75"],
            rows,
            [60 * mm, 36 * mm, 36 * mm, 36 * mm],
            styles,
            numeric=[1, 2, 3],
        )
    )
    for note in notes:
        story.append(Paragraph(escape(note), styles["table_note"]))
    story.append(gap(GAP_M))
    story.append(callout([Paragraph(escape(MULTIPLES_DISCLAIMER), styles["small"])]))
    return story


def _target_plan_section(
    data: ReportData, styles: dict[str, ParagraphStyle], numbering: Numbering
) -> list[Any]:
    """Reverse-engineered plan (required growth and margin) for the configured target."""
    section = data.target_plan
    if section is None:
        return []
    story = _header(numbering, "Plano para a meta", "Target Plan", room=60 * mm)
    if section.status == "insufficient_hits":
        story.append(
            Paragraph(
                f"Apenas {format_integer(section.hit_count)} cenários simulados atingem a "
                f"meta, abaixo do mínimo de {MIN_HIT_SAMPLE} necessário para estimar um plano "
                "de forma confiável.",
                styles["body"],
            )
        )
        return story
    if section.status == "not_available_for_inputs":
        story.append(
            Paragraph(
                "Este modo de entrada não produz os indicadores necessários para reverter um "
                "plano a partir da meta informada.",
                styles["body"],
            )
        )
        return story
    currency = data.company.currency
    cells = (
        (
            "CAGR DE RECEITA NECESSÁRIO",
            format_percent(section.required_revenue_cagr)
            if section.required_revenue_cagr is not None
            else "N/A",
            "Mediana nos cenários que atingem a meta",
        ),
        (
            "MARGEM EBITDA ALVO",
            format_percent(section.hit_ebitda_margin)
            if section.hit_ebitda_margin is not None
            else "N/A",
            "Ano 5 · mediana nos cenários que atingem a meta",
        ),
    )
    widths = [span(6), span(6)]
    story.append(
        stat_strip(
            [
                kpi_cell(label, value, caption, styles, width - 12, label_style="stat_label")
                for (label, value, caption), width in zip(cells, widths, strict=True)
            ],
            widths,
        )
    )
    story.append(gap(GAP_M))
    if section.trajectory:
        rows = [
            [f"Ano {point.year}", format_money(point.revenue, currency)]
            for point in section.trajectory
        ]
        story.append(
            KeepTogether(
                [
                    Paragraph("Trajetória de referência da receita", styles["h2"]),
                    data_table(
                        ["Ano", "Receita de referência"],
                        rows,
                        [span(6) - 40 * mm, 40 * mm],
                        styles,
                        numeric=[1],
                    ),
                ]
            )
        )
        story.append(gap(GAP_S))
    contrast_parts: list[str] = []
    if section.required_revenue_cagr is not None and section.miss_revenue_cagr is not None:
        contrast_parts.append(
            f"CAGR de receita de {format_percent(section.required_revenue_cagr)} nos "
            f"cenários que atingem a meta, contra {format_percent(section.miss_revenue_cagr)} "
            "nos demais"
        )
    if section.hit_ebitda_margin is not None and section.miss_ebitda_margin is not None:
        contrast_parts.append(
            f"margem EBITDA do ano 5 de {format_percent(section.hit_ebitda_margin)} nos "
            f"cenários que atingem a meta, contra {format_percent(section.miss_ebitda_margin)} "
            "nos demais"
        )
    if contrast_parts:
        story.append(Paragraph(escape("; ".join(contrast_parts) + "."), styles["body"]))
        story.append(gap(GAP_S))
    story.append(callout([Paragraph(escape(TARGET_PLAN_DISCLAIMER), styles["small"])]))
    return story


def _risk(
    data: ReportData,
    styles: dict[str, ParagraphStyle],
    numbering: Numbering,
    source_label: str,
) -> list[Any]:
    story = _header(numbering, "Risco e sensibilidade", "Risk & Sensitivity")
    sections: tuple[tuple[str, tuple[str, ...]], ...]
    if data.insight is not None:
        story.extend(sensitivity_blocks(data, styles, numbering, source_label))
        story.append(gap(GAP_S))
        sections = (("Alertas", data.risks.warnings), ("Limitações", data.risks.limitations))
    else:
        sections = (
            ("Alertas", data.risks.warnings),
            ("Downside drivers", data.risks.downside_notes),
            ("Upside drivers", data.risks.upside_notes),
            ("Limitações", data.risks.limitations),
        )
    blocks: list[list[Any]] = []
    for title, entries in sections:
        block: list[Any] = [Paragraph(title, styles["h2"])]
        if entries:
            block.extend(bullets(entries, styles))
        else:
            block.append(Paragraph("Nenhum item informado.", styles["small"]))
        blocks.append(block)
    for index in range(0, len(blocks), 2):
        pair = blocks[index : index + 2]
        if len(pair) == 2:
            story.append(columns(pair[0], pair[1], span(6), span(6)))
        else:
            story.extend(pair[0])
    return story


def _methodology(
    data: ReportData, styles: dict[str, ParagraphStyle], numbering: Numbering
) -> list[Any]:
    audit = data.audit
    intro: list[Any] = [
        *_header(numbering, "Metodologia e trilha de auditoria", "Methodology & Audit Trail"),
        Paragraph(
            "O DCF traz fluxos de caixa futuros a valor presente. O Venture Capital Method parte "
            "de um valor de saída e retorno requerido. Monte Carlo propaga premissas incertas por "
            "trajetórias reprodutíveis. Percentis resumem a distribuição simulada; não são "
            "garantias.",
            styles["body_lead"],
        ),
    ]
    notes = data.insight.method_notes if data.insight is not None else ()
    intro.extend(bullets(notes, styles))
    return [
        KeepTogether(intro),
        gap(GAP_S),
        KeepTogether(
            [
                Paragraph("Trilha de auditoria", styles["h2"]),
                key_value_table(
                    [
                        ("Simulation ID", audit.simulation_id),
                        ("Simulation Result ID", audit.simulation_result_id),
                        ("Versão do modelo", audit.model_version),
                        ("Versão tributária", audit.tax_version or "N/A"),
                        ("Versão do schema do resultado", audit.result_schema_version),
                        ("Versão do template do relatório", audit.report_template_version),
                        ("Semente aleatória (seed)", str(audit.seed)),
                        ("Número de cenários", str(audit.simulation_count)),
                        ("Checksum do resultado", audit.result_hash),
                        ("Resultado gerado em", audit.generated_at.isoformat()),
                    ],
                    styles,
                    mono=True,
                ),
            ]
        ),
        gap(GAP_L),
        KeepTogether(
            [
                Paragraph("Disclaimer", styles["h2"]),
                callout([Paragraph(escape(data.disclaimer), styles["small"])]),
            ]
        ),
    ]


def _build_story(
    data: ReportData, styles: dict[str, ParagraphStyle], branding: ReportBrandingData | None = None
) -> list[Any]:
    numbering = Numbering()
    methods_grouped = data.dcf.status != "available" and data.venture_capital.status != "available"
    long_assumptions = len(data.assumptions) > ASSUMPTIONS_INLINE
    source_label = _source_label(branding)

    story: list[Any] = [
        NextPageTemplate("report"),
        PageBreak(),
        *_header(numbering, "Sumário executivo", "Executive Summary"),
    ]
    if data.insight is not None:
        story.extend(executive_summary_blocks(data, styles, source_label))
    else:
        story.extend(_legacy_summary(data, styles))

    story.extend(
        [
            PageBreak(),
            *_header(numbering, "Perfil da empresa", "Company Overview"),
            _company_overview(data, styles),
            gap(GAP_L),
            *_header(numbering, "Premissas financeiras", "Financial Assumptions"),
        ]
    )
    if data.assumptions:
        shown = data.assumptions[: ASSUMPTIONS_INLINE - 2] if long_assumptions else data.assumptions
        story.append(_assumption_table(data, styles, shown))
        story.append(
            Paragraph(
                (
                    f"Exibindo {len(shown)} de {len(data.assumptions)} premissas; a lista "
                    "completa está no Apêndice A. "
                    if long_assumptions
                    else ""
                )
                + "Valores registrados na revisão do cenário usada nesta simulação.",
                styles["table_note"],
            )
        )
    else:
        story.append(Paragraph("N/A - nenhuma premissa registrada.", styles["body"]))
    story.append(gap(GAP_L))
    if methods_grouped:
        story.extend(
            [
                *_header(
                    numbering, "Métodos de valuation", "DCF & Venture Capital Method", 55 * mm
                ),
                columns(
                    [_method_card("DCF Analysis", data.dcf, styles)],
                    [_method_card("Venture Capital Method", data.venture_capital, styles)],
                    span(6),
                    span(6),
                ),
                Paragraph(
                    "O valuation deste relatório é a distribuição Monte Carlo da seção seguinte.",
                    styles["table_note"],
                ),
            ]
        )

    story.extend([PageBreak(), *_distribution(data, styles, numbering, source_label)])
    if not methods_grouped:
        story.append(gap(GAP_L))
        story.extend(_method_section("DCF Analysis", "Método DCF", data.dcf, styles, numbering))
        story.extend(
            _method_section(
                "Venture Capital Method",
                "Método Venture Capital",
                data.venture_capital,
                styles,
                numbering,
            )
        )
    story.extend([PageBreak(), *_drivers(data, styles, numbering, source_label)])
    story.extend([PageBreak(), *_target(data, styles, numbering)])
    multiples_story = _implied_multiples(data, styles, numbering)
    if multiples_story:
        story.extend([PageBreak(), *multiples_story])
    plan_story = _target_plan_section(data, styles, numbering)
    if plan_story:
        story.extend([PageBreak(), *plan_story])
    story.extend([PageBreak(), *_risk(data, styles, numbering, source_label)])
    story.extend([PageBreak(), *_methodology(data, styles, numbering)])
    if long_assumptions:
        story.extend(
            [
                PageBreak(),
                SectionHeader("A", "Apêndice A", "Detailed Assumptions"),
                _assumption_table(data, styles, data.assumptions),
            ]
        )
    return story


def _styles() -> dict[str, ParagraphStyle]:
    styles = report_styles()
    styles["cover_company"] = ParagraphStyle(
        "SVCoverCompany", parent=styles["body"], fontName="Helvetica-Bold", fontSize=20,
        leading=24, textColor=GREEN, spaceAfter=0,
    )
    styles["cover_fact"] = ParagraphStyle(
        "SVCoverFact", parent=styles["body"], fontSize=10, leading=13, spaceBefore=2, spaceAfter=0
    )
    styles["cover_mono"] = ParagraphStyle(
        "SVCoverMono", parent=styles["body"], fontName="Courier", fontSize=7.6, leading=9.6,
        spaceBefore=1, spaceAfter=0,
    )
    return styles


def _render(
    data: ReportData,
    total: int | None,
    branding: ReportBrandingData | None = None,
    watermark: bool = False,
) -> tuple[bytes, int]:
    styles = _styles()
    buffer = BytesIO()
    document = _document(buffer, data, styles, total, branding, watermark)
    document.build(_build_story(data, styles, branding), canvasmaker=_NumberedCanvas)
    return buffer.getvalue(), int(document.page)


def build_report_pdf(
    data: ReportData,
    *,
    branding: ReportBrandingData | None = None,
    watermark: bool = False,
) -> bytes:
    """Render a deterministic PDF without recalculating any simulation value.

    A first pass counts pages so every footer can say "Página N de M".

    ``branding`` swaps the QuantoVale mark/name for a white-label firm's own
    identity (logo, name, accent color) on the cover and page chrome; audit
    identifiers and the disclaimer always render regardless. ``watermark``
    stamps a diagonal, translucent free-tier notice on every page.
    """
    _, total = _render(data, None, branding, watermark)
    pdf, _ = _render(data, total, branding, watermark)
    return pdf

