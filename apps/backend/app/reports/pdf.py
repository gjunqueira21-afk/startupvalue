"""A4 institutional PDF renderer for immutable SimulationResult snapshots."""

from __future__ import annotations

from collections.abc import Callable
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from .narrative import executive_narrative, format_money, format_percent
from .schema import Histogram, MethodAnalysis, PercentileKey, ReportData

INK = colors.HexColor("#10231E")
GREEN = colors.HexColor("#087A55")
BLUE = colors.HexColor("#175CD3")
MUTED = colors.HexColor("#52605B")
LINE = colors.HexColor("#D8E0DC")
PALE = colors.HexColor("#F2F7F4")


class _HistogramChart(Flowable):
    """Vector histogram using bin counts already persisted with the result."""

    def __init__(
        self, histogram: Histogram, percentiles: dict[PercentileKey, float], currency: str
    ) -> None:
        super().__init__()
        self.histogram = histogram
        self.percentiles = percentiles
        self.currency = currency
        self.width = 169 * mm
        self.height = 64 * mm

    def draw(self) -> None:
        canvas = self.canv
        start, end = self.histogram.edges[0], self.histogram.edges[-1]
        plot_left, plot_right = 6 * mm, self.width - 6 * mm
        plot_bottom, plot_top = 9 * mm, 48 * mm
        plot_width = plot_right - plot_left
        max_count = max(self.histogram.counts) or 1
        count = len(self.histogram.counts)
        step = plot_width / count

        canvas.setStrokeColor(LINE)
        canvas.line(plot_left, plot_bottom, plot_right, plot_bottom)
        canvas.setFillColor(GREEN)
        for index, bin_count in enumerate(self.histogram.counts):
            height = (plot_top - plot_bottom) * bin_count / max_count
            canvas.rect(
                plot_left + index * step + 0.4,
                plot_bottom,
                max(step - 0.8, 0.1),
                height,
                stroke=0,
                fill=1,
            )

        markers = (("p10", MUTED), ("p50", BLUE), ("p90", INK))
        canvas.setFont("Helvetica", 7)
        for index, (name, color) in enumerate(markers):
            value = self.percentiles[name]  # type: ignore[index]
            x = plot_left + plot_width * min(max((value - start) / (end - start), 0), 1)
            canvas.setStrokeColor(color)
            canvas.setLineWidth(1.2 if name == "p50" else 0.8)
            canvas.line(x, plot_bottom, x, plot_top + 1 * mm)
            canvas.setFillColor(color)
            legend_x = plot_left + index * 29 * mm
            canvas.rect(legend_x, 55 * mm, 5 * mm, 1.2 * mm, stroke=0, fill=1)
            canvas.drawString(legend_x + 7 * mm, 53.5 * mm, name.upper())

        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(plot_left, 2 * mm, format_money(start, self.currency))
        canvas.drawRightString(plot_right, 2 * mm, format_money(end, self.currency))


class _NumberedCanvas(Canvas):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["invariant"] = 1
        kwargs["pageCompression"] = 1
        super().__init__(*args, **kwargs)


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "SVTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=27,
            leading=31,
            textColor=INK,
            spaceAfter=6,
        ),
        "h1": ParagraphStyle(
            "SVH1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=21,
            textColor=INK,
            spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "SVH2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=GREEN,
            spaceBefore=7,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "SVBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.4,
            leading=13.2,
            textColor=INK,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "SVSmall",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=MUTED,
        ),
        "metric": ParagraphStyle(
            "SVMetric",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=22,
            alignment=TA_RIGHT,
            textColor=INK,
        ),
        "cover": ParagraphStyle(
            "SVCover",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=11,
            leading=16,
            alignment=TA_CENTER,
            textColor=MUTED,
        ),
    }


def _table(rows: list[list[Any]], widths: list[float] | None = None) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PALE),
                ("TEXTCOLOR", (0, 0), (-1, 0), INK),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.2),
                ("LEADING", (0, 0), (-1, -1), 11),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _target_metric_value(value: float, unit: str | None) -> str:
    if unit in {"BRL", "USD", "EUR"}:
        return format_money(value, unit)
    if unit == "%":
        return format_percent(value)
    if unit == "x":
        return f"{value:.2f}x".replace(".", ",")
    return f"{value:.2f}".replace(".", ",")


def _method_section(
    title: str, method: MethodAnalysis, styles: dict[str, ParagraphStyle]
) -> list[Any]:
    story: list[Any] = [Paragraph(title, styles["h1"])]
    if method.status != "available":
        story.append(Paragraph(method.note or "Análise não disponível.", styles["body"]))
        return story
    rows: list[list[Any]] = [["Métrica", "Valor", "Nota"]]
    rows.extend([metric.name, metric.value, metric.explanation or "-"] for metric in method.metrics)
    story.append(_table(rows, [49 * mm, 36 * mm, 84 * mm]))
    if method.note:
        story.extend([Spacer(1, 5 * mm), Paragraph(method.note, styles["body"])])
    return story


def _page_chrome(
    data: ReportData, styles: dict[str, ParagraphStyle]
) -> Callable[[Canvas, Any], None]:
    def draw(canvas: Canvas, document: Any) -> None:
        canvas.saveState()
        width, _ = A4
        canvas.setStrokeColor(LINE)
        canvas.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 7.2)
        footer_name = data.company.name
        if len(footer_name) > 40:
            footer_name = f"{footer_name[:37]}..."
        canvas.drawString(18 * mm, 10 * mm, f"CONFIDENCIAL | {footer_name}")
        canvas.drawRightString(
            width - 18 * mm,
            10 * mm,
            f"Simulation {data.audit.simulation_id[:12]} | Página {document.page}",
        )
        canvas.restoreState()

    return draw


def _document(
    buffer: BytesIO, data: ReportData, styles: dict[str, ParagraphStyle]
) -> BaseDocTemplate:
    document = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=f"StartupValue - {data.company.name}",
        author="StartupValue",
        subject="Valuation & Monte Carlo Analysis",
        creator=f"StartupValue report template {data.audit.report_template_version}",
    )
    frame = Frame(document.leftMargin, document.bottomMargin, document.width, document.height)
    document.addPageTemplates(
        [PageTemplate(id="report", frames=[frame], onPage=_page_chrome(data, styles))]
    )
    return document


def _build_story(data: ReportData, styles: dict[str, ParagraphStyle]) -> list[Any]:
    currency = data.company.currency
    p = data.valuation.percentiles
    audit = data.audit
    story: list[Any] = [
        Spacer(1, 39 * mm),
        Paragraph("STARTUPVALUE", styles["title"]),
        Paragraph("Valuation &amp; Monte Carlo Analysis", styles["cover"]),
        Spacer(1, 21 * mm),
        Paragraph(escape(data.company.name), styles["metric"]),
        Paragraph(f"Cenário: {escape(data.company.scenario_name)}", styles["cover"]),
        Paragraph(f"Data-base: {audit.analysis_date.isoformat()}", styles["cover"]),
        Spacer(1, 33 * mm),
        Paragraph("CONFIDENCIAL", styles["cover"]),
        Spacer(1, 14 * mm),
        Paragraph(f"Simulation ID: {audit.simulation_id}", styles["small"]),
        Paragraph(f"Simulation Result ID: {audit.simulation_result_id}", styles["small"]),
        Paragraph(f"Result checksum: {audit.result_hash}", styles["small"]),
        PageBreak(),
        Paragraph("Executive Summary", styles["h1"]),
        _table(
            [
                ["Métrica", "Resultado"],
                ["Valuation mediano (P50)", format_money(p["p50"], currency)],
                [
                    "Core range (P25-P75)",
                    f"{format_money(p['p25'], currency)} - {format_money(p['p75'], currency)}",
                ],
                ["Downside (P10)", format_money(p["p10"], currency)],
                ["Upside (P90)", format_money(p["p90"], currency)],
                ["Incerteza", data.valuation.uncertainty_label],
                [
                    "Probabilidade de failure",
                    format_percent(data.valuation.failure_probability),
                ],
            ],
            [91 * mm, 78 * mm],
        ),
        Spacer(1, 7 * mm),
    ]
    story.extend(Paragraph(escape(text), styles["body"]) for text in executive_narrative(data))
    percentile_keys: tuple[PercentileKey, ...] = (
        "p5",
        "p10",
        "p25",
        "p50",
        "p75",
        "p90",
        "p95",
    )
    story.extend(
        [
            PageBreak(),
            Paragraph("Company Overview", styles["h1"]),
            _table(
                [
                    ["Campo", "Valor"],
                    ["Empresa", data.company.name],
                    ["Cenário", data.company.scenario_name],
                    ["Setor", data.company.sector or "N/A"],
                    ["Estágio", data.company.stage or "N/A"],
                    ["Modelo de negócio", data.company.business_model or "N/A"],
                    ["País", data.company.country or "N/A"],
                    ["Moeda", currency],
                    ["Base do valuation", data.valuation.basis],
                ],
                [60 * mm, 109 * mm],
            ),
            PageBreak(),
            Paragraph("Financial Assumptions", styles["h1"]),
        ]
    )
    assumption_rows: list[list[Any]] = [["Premissa", "Valor", "Unidade", "Origem"]]
    assumption_rows.extend(
        [item.name, item.value, item.unit or "-", item.source or "-"] for item in data.assumptions
    )
    story.append(_table(assumption_rows, [51 * mm, 44 * mm, 28 * mm, 46 * mm]))
    story.extend(
        [
            PageBreak(),
            Paragraph("Monte Carlo Distribution", styles["h1"]),
            Paragraph(
                "Os percentis incluem todos os resultados simulados, inclusive valores "
                "não positivos e estados de falha.",
                styles["body"],
            ),
        ]
    )
    if data.valuation.histogram is not None:
        story.extend(
            [
                _HistogramChart(data.valuation.histogram, p, currency),
                Spacer(1, 4 * mm),
            ]
        )
    else:
        story.append(Paragraph("Histograma não persistido neste resultado.", styles["small"]))
    story.extend(
        [
            _table(
                [["Percentil", "Valuation"]]
                + [[key.upper(), format_money(p[key], currency)] for key in percentile_keys]
                + [
                    ["Média", format_money(data.valuation.mean, currency)],
                    ["Desvio padrão", format_money(data.valuation.standard_deviation, currency)],
                ],
                [85 * mm, 84 * mm],
            ),
            Spacer(1, 6 * mm),
            Paragraph("Breakeven", styles["h2"]),
        ]
    )
    if data.valuation.breakeven_probabilities:
        story.append(
            _table(
                [["Horizonte", "Probabilidade"]]
                + [
                    [name, format_percent(value)]
                    for name, value in data.valuation.breakeven_probabilities.items()
                ],
                [85 * mm, 84 * mm],
            )
        )
    else:
        story.append(Paragraph("N/A - não informado no resultado persistido.", styles["body"]))
    story.extend([PageBreak(), *_method_section("DCF Analysis", data.dcf, styles)])
    story.extend(
        [PageBreak(), *_method_section("Venture Capital Method", data.venture_capital, styles)]
    )
    story.extend([PageBreak(), Paragraph("Valuation Drivers", styles["h1"])])
    if data.drivers:
        driver_rows: list[list[Any]] = [["Driver", "Participação", "Spearman", "N", "Status"]]
        driver_rows.extend(
            [
                Paragraph(escape(driver.name), styles["small"]),
                "N/A" if driver.contribution is None else format_percent(driver.contribution),
                "N/A" if driver.association is None else f"{driver.association:+.3f}",
                str(driver.sample_size),
                driver.status,
            ]
            for driver in data.drivers
        )
        story.append(_table(driver_rows, [56 * mm, 28 * mm, 26 * mm, 22 * mm, 37 * mm]))
    else:
        story.append(Paragraph("N/A - drivers não informados.", styles["body"]))
    story.append(
        Paragraph(
            "Participação: parcela da variância dos postos do valuation explicada por cada "
            "driver primitivo (coeficiente de regressão padronizada de postos ao quadrado, "
            "normalizado). Coeficientes descrevem associação monotônica nos cenários "
            "simulados; não demonstram causalidade.",
            styles["body"],
        )
    )
    story.extend([PageBreak(), Paragraph("What Needs to Be True?", styles["h1"])])
    if data.target is None:
        story.append(Paragraph("Target valuation não configurado.", styles["body"]))
    else:
        target = data.target
        story.extend(
            [
                _table(
                    [
                        ["Métrica", "Resultado"],
                        ["Target valuation", format_money(target.target_value, currency)],
                        ["Probabilidade de atingir", format_percent(target.probability)],
                        ["Target hit", str(target.hit_count)],
                        ["Target miss", str(target.miss_count)],
                    ],
                    [85 * mm, 84 * mm],
                ),
                Spacer(1, 6 * mm),
            ]
        )
        if target.metrics:
            target_rows: list[list[Any]] = [["Parâmetro", "Grupo", "P25", "Mediana", "P75"]]
            for metric in target.metrics:
                for label, distribution in (
                    ("Target hit", metric.target_hit),
                    ("Target miss", metric.target_miss),
                ):
                    if distribution is not None:
                        target_rows.append(
                            [
                                Paragraph(escape(metric.name), styles["small"]),
                                label,
                                _target_metric_value(distribution.p25, metric.unit),
                                _target_metric_value(distribution.median, metric.unit),
                                _target_metric_value(distribution.p75, metric.unit),
                            ]
                        )
            story.append(_table(target_rows, [48 * mm, 35 * mm, 28 * mm, 30 * mm, 28 * mm]))
            story.append(
                Paragraph(
                    "As diferenças entre grupos são condicionais aos cenários simulados "
                    "e não garantem efeito causal.",
                    styles["body"],
                )
            )
    story.extend([PageBreak(), Paragraph("Risk &amp; Sensitivity", styles["h1"])])
    risk_sections = (
        ("Warnings", data.risks.warnings),
        ("Downside drivers", data.risks.downside_notes),
        ("Upside drivers", data.risks.upside_notes),
        ("Limitations", data.risks.limitations),
    )
    for title, entries in risk_sections:
        story.append(Paragraph(title, styles["h2"]))
        if entries:
            story.extend(Paragraph(f"• {escape(entry)}", styles["body"]) for entry in entries)
        else:
            story.append(Paragraph("Nenhum item informado.", styles["body"]))
    story.extend(
        [
            PageBreak(),
            Paragraph("Methodology &amp; Audit Trail", styles["h1"]),
            Paragraph(
                "O DCF traz fluxos de caixa futuros a valor presente. O Venture Capital "
                "Method parte de um valor de saída e retorno requerido. Monte Carlo "
                "propaga premissas incertas por trajetórias "
                "reprodutíveis. Percentis resumem a distribuição simulada; não são garantias.",
                styles["body"],
            ),
            _table(
                [
                    ["Campo de auditoria", "Valor"],
                    ["Simulation ID", audit.simulation_id],
                    ["Simulation Result ID", audit.simulation_result_id],
                    ["Model version", audit.model_version],
                    ["Tax version", audit.tax_version or "N/A"],
                    ["Result schema version", audit.result_schema_version],
                    ["Report template version", audit.report_template_version],
                    ["Random seed", str(audit.seed)],
                    ["Simulation count", str(audit.simulation_count)],
                    ["Result checksum", audit.result_hash],
                    ["Generated at", audit.generated_at.isoformat()],
                ],
                [59 * mm, 110 * mm],
            ),
            Spacer(1, 8 * mm),
            KeepTogether(
                [
                    Paragraph("Disclaimer", styles["h2"]),
                    Paragraph(escape(data.disclaimer), styles["small"]),
                ]
            ),
        ]
    )
    return story


def build_report_pdf(data: ReportData) -> bytes:
    """Render a deterministic PDF without recalculating any simulation value."""

    styles = _styles()
    buffer = BytesIO()
    document = _document(buffer, data, styles)
    document.build(_build_story(data, styles), canvasmaker=_NumberedCanvas)
    return buffer.getvalue()
