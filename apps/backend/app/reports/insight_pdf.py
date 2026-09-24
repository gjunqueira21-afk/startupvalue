"""Executive-intelligence blocks of the PDF: KPI grid, driver and tornado charts.

Print palette (validated with the dataviz CVD checker on white): #2563B8 raises
the valuation, #C43D4B lowers it. Sign and text always carry direction too, so
the charts stay readable in grayscale. Only WinAnsi glyphs are drawn.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, KeepTogether, Paragraph, Spacer, Table, TableStyle

from app.insights.formatting import compact_money, format_unit, percent

from .narrative import format_integer, format_money
from .schema import ReportData, TornadoSection

INK = colors.HexColor("#10231E")
GREEN = colors.HexColor("#087A55")
MUTED = colors.HexColor("#52605B")
LINE = colors.HexColor("#D8E0DC")
PALE = colors.HexColor("#F2F7F4")
INCREASE = colors.HexColor("#2563B8")
DECREASE = colors.HexColor("#C43D4B")
TRACK = colors.HexColor("#EEF2F0")
WIDTH = 169 * mm


def text(value: str) -> str:
    """Escape for Paragraph markup and keep currency symbols attached to their amount."""
    return escape(value).replace("R$ ", "R$&nbsp;").replace("US$ ", "US$&nbsp;")


def _fit(canvas: Any, text: str, font: str, size: float, width: float) -> str:
    """Truncate with an ellipsis so a label never runs into the plot."""
    if canvas.stringWidth(text, font, size) <= width:
        return text
    while text and canvas.stringWidth(f"{text}...", font, size) > width:
        text = text[:-1]
    return f"{text.rstrip()}..."


class ContributionBar(Flowable):
    """Share of explained variance, coloured by the driver's direction."""

    def __init__(self, share: float, rho: float | None, width: float = 52 * mm) -> None:
        super().__init__()
        self.share = max(0.0, min(1.0, share))
        self.rho = rho
        self.width = width
        self.height = 3.2 * mm

    def draw(self) -> None:
        canvas = self.canv
        canvas.setFillColor(TRACK)
        canvas.rect(0, 0, self.width, self.height, stroke=0, fill=1)
        canvas.setFillColor(DECREASE if (self.rho or 0.0) < 0 else INCREASE)
        canvas.rect(0, 0, max(self.width * self.share, 0.4), self.height, stroke=0, fill=1)


class DriverChart(Flowable):
    """Diverging Spearman bars on a -1..1 scale with value and share columns."""

    ROW = 7 * mm

    def __init__(self, rows: Sequence[tuple[str, float | None, float | None]]) -> None:
        super().__init__()
        self.rows = rows
        self.width = WIDTH
        self.height = self.ROW * (len(rows) + 1) + 3 * mm

    def draw(self) -> None:
        canvas = self.canv
        label_w, plot_x, plot_w = 58 * mm, 60 * mm, 72 * mm
        centre = plot_x + plot_w / 2
        top = self.height - 4 * mm
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        for text, x in (("-1", plot_x), ("0", centre), ("+1", plot_x + plot_w)):
            canvas.drawCentredString(x, top, text)
        canvas.drawRightString(152 * mm, top, "Spearman")
        canvas.drawRightString(WIDTH, top, "Participação")
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.6)
        canvas.line(centre, 1 * mm, centre, top - 2 * mm)
        for index, (label, rho, share) in enumerate(self.rows):
            y = top - self.ROW * (index + 1)
            canvas.setFillColor(INK)
            canvas.setFont("Helvetica", 8)
            canvas.drawString(0, y, _fit(canvas, label, "Helvetica", 8, label_w))
            if rho is None:
                canvas.setFillColor(MUTED)
                canvas.drawString(plot_x, y, "não estimável (constante)")
                continue
            length = abs(rho) * plot_w / 2
            canvas.setFillColor(INCREASE if rho >= 0 else DECREASE)
            canvas.rect(
                centre if rho >= 0 else centre - length, y - 0.6 * mm, max(length, 0.4), 3.4 * mm,
                stroke=0, fill=1,
            )
            canvas.setFillColor(INK)
            canvas.setFont("Helvetica-Bold", 8)
            canvas.drawRightString(152 * mm, y, f"{rho:+.2f}".replace(".", ","))
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(MUTED)
            canvas.drawRightString(WIDTH, y, "-" if share is None else percent(share, decimals=0))


class TornadoChart(Flowable):
    """Swing of the median valuation per assumption around the base, zero-centred."""

    ROW = 12 * mm

    def __init__(self, tornado: TornadoSection, currency: str) -> None:
        super().__init__()
        self.tornado = tornado
        self.currency = currency
        self.width = WIDTH
        self.height = self.ROW * len(tornado.items) + 9 * mm

    def draw(self) -> None:
        canvas = self.canv
        base = self.tornado.base_value
        label_w, plot_x = 48 * mm, 50 * mm
        plot_w = WIDTH - plot_x
        centre = plot_x + plot_w / 2
        half = plot_w / 2 * 0.62  # room for the value label at each tip
        scale = max(
            1e-12,
            *(
                abs(value - base)
                for item in self.tornado.items
                for value in (item.value_at_low, item.value_at_high)
            ),
        )
        axis_y = 5 * mm
        canvas.setStrokeColor(MUTED)
        canvas.setLineWidth(0.6)
        canvas.line(centre, axis_y, centre, self.height)
        for index, item in enumerate(self.tornado.items):
            y = self.height - self.ROW * (index + 1)
            canvas.setFillColor(INK)
            canvas.setFont("Helvetica-Bold", 8)
            label = item.label + (" *" if item.clamped else "")
            canvas.drawString(0, y + 6 * mm, _fit(canvas, label, "Helvetica-Bold", 8, label_w))
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(MUTED)
            levels = (
                f"{format_unit(item.unit, item.low_level, self.currency)} a "
                f"{format_unit(item.unit, item.high_level, self.currency)}"
            )
            canvas.drawString(0, y + 2.4 * mm, levels)
            for offset, value, level in (
                (6.2 * mm, item.value_at_low, item.low_level),
                (1.8 * mm, item.value_at_high, item.high_level),
            ):
                delta = value - base
                length = abs(delta) / scale * half
                bar_y = y + offset
                canvas.setFillColor(INCREASE if delta >= 0 else DECREASE)
                start = centre if delta >= 0 else centre - length
                canvas.rect(start, bar_y, max(length, 0.4), 3.4 * mm, stroke=0, fill=1)
                sign = "+" if delta > 0 else ""
                change = f"{sign}{compact_money(delta, self.currency, short=True)}"
                level_text = format_unit(item.unit, level, self.currency)
                canvas.setFont("Helvetica", 7)
                canvas.setFillColor(INK)
                if delta >= 0:
                    canvas.drawString(centre + length + 1.5 * mm, bar_y + 0.8 * mm, change)
                    canvas.setFillColor(MUTED)
                    canvas.drawRightString(centre - 1.5 * mm, bar_y + 0.8 * mm, level_text)
                else:
                    canvas.drawRightString(centre - length - 1.5 * mm, bar_y + 0.8 * mm, change)
                    canvas.setFillColor(MUTED)
                    canvas.drawString(centre + 1.5 * mm, bar_y + 0.8 * mm, level_text)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        short = compact_money(scale, self.currency, short=True)
        canvas.drawCentredString(centre - half, 1 * mm, f"-{short}")
        canvas.drawCentredString(
            centre, 1 * mm, f"P50 base {compact_money(base, self.currency, short=True)}"
        )
        canvas.drawCentredString(centre + half, 1 * mm, f"+{short}")


def _kpi_cell(label: str, value: str, caption: str, styles: dict[str, ParagraphStyle],
              hero: bool = False, style: str | None = None) -> list[Any]:
    return [
        Paragraph(label, styles["kpi_label"]),
        Paragraph(text(value), styles[style or ("kpi_hero" if hero else "kpi_value")]),
        Paragraph(text(caption), styles["kpi_caption"]),
    ]


def executive_summary_blocks(data: ReportData, styles: dict[str, ParagraphStyle]) -> list[Any]:
    """KPI grid, top drivers and the 1-3 paragraph executive text."""
    insight = data.insight
    assert insight is not None
    currency = data.company.currency
    p = data.valuation.percentiles

    def short(value: float) -> str:
        return compact_money(value, currency, short=True)

    if data.target is not None:
        probability = percent(data.target.probability)
        probability_caption = (
            f"Meta de {short(data.target.target_value)} ou mais - "
            f"{format_integer(data.target.hit_count)} de "
            f"{format_integer(data.audit.simulation_count)} cenários"
        )
    else:
        probability, probability_caption = "N/A", "Nenhuma meta informada na exportação."
    ratio = data.valuation.uncertainty_ratio
    uncertainty_caption = (
        f"Faixa P25-P75 = {percent(ratio, decimals=0)} da mediana"
        if ratio is not None
        else "Mediana não positiva; ver critério."
    )
    cells = [
        _kpi_cell(
            "ESTIMATED VALUATION", compact_money(p["p50"], currency),
            f"P50 - {format_money(p['p50'], currency)}", styles, hero=True,
        ),
        _kpi_cell(
            "CORE RANGE", f"{short(p['p25'])} - {short(p['p75'])}",
            f"P25-P75: {format_money(p['p25'], currency)} - {format_money(p['p75'], currency)}",
            styles,
            style="kpi_range",
        ),
        _kpi_cell("DOWNSIDE", short(p["p10"]), "P10 - cenário conservador", styles),
        _kpi_cell("UPSIDE", short(p["p90"]), "P90 - cenário otimista", styles),
        _kpi_cell("PROBABILITY OF TARGET", probability, probability_caption, styles),
        _kpi_cell("UNCERTAINTY", insight.uncertainty_label_pt, uncertainty_caption, styles),
    ]
    grid = Table([cells[:3], cells[3:]], colWidths=[WIDTH / 3] * 3, hAlign="LEFT")
    grid.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("BACKGROUND", (0, 0), (0, 0), PALE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story: list[Any] = [
        Paragraph(text(insight.headline), styles["lead"]),
        Spacer(1, 3 * mm),
        grid,
        Spacer(1, 6 * mm),
    ]
    if insight.key_drivers:
        rows = [
            [
                Paragraph(f"{rank}.", styles["kpi_value_small"]),
                Paragraph(text(driver.label), styles["body"]),
                ContributionBar(driver.contribution, driver.rho),
                Paragraph(percent(driver.contribution, decimals=0), styles["num"]),
            ]
            for rank, driver in enumerate(insight.key_drivers, start=1)
        ]
        table = Table(rows, colWidths=[9 * mm, 80 * mm, 58 * mm, 22 * mm], hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.extend(
            [
                KeepTogether(
                    [
                        Paragraph("TOP VALUATION DRIVERS", styles["kpi_label"]),
                        Spacer(1, 1.5 * mm),
                        table,
                        Paragraph(
                            "Participação na variância explicada do valuation; barra azul: "
                            "associação positiva, vermelha: negativa. Associação não é causa.",
                            styles["small"],
                        ),
                    ]
                ),
                Spacer(1, 6 * mm),
            ]
        )
    story.append(Paragraph("LEITURA EXECUTIVA", styles["kpi_label"]))
    story.append(Spacer(1, 1.5 * mm))
    story.extend(Paragraph(text(item), styles["body_lead"]) for item in insight.executive_summary)
    return story


def driver_blocks(data: ReportData, styles: dict[str, ParagraphStyle]) -> list[Any]:
    insight = data.insight
    assert insight is not None
    story: list[Any] = []
    if insight.key_drivers_sentence:
        story.append(Paragraph(text(insight.key_drivers_sentence), styles["body"]))
    if data.drivers:
        story.extend(
            [
                Spacer(1, 2 * mm),
                DriverChart([(d.name, d.association, d.contribution) for d in data.drivers]),
                Paragraph(
                    "Barras: correlação de postos (Spearman) com o valuation, de -1 a +1. Azul: "
                    "associação positiva; vermelho: negativa. Participação: parcela da variância "
                    "explicada (SRRC ao quadrado, normalizado).",
                    styles["small"],
                ),
                Spacer(1, 4 * mm),
            ]
        )
    for title, entries, empty in (
        ("Upside drivers", insight.upside, "Nenhum fator se desloca de forma relevante nos "
         "melhores cenários."),
        ("Downside drivers", insight.downside, "Nenhum fator se desloca de forma relevante nos "
         "piores cenários."),
    ):
        story.append(Paragraph(title, styles["h2"]))
        if entries:
            story.extend(Paragraph(f"• {text(entry)}", styles["body"]) for entry in entries)
        else:
            story.append(Paragraph(empty, styles["body"]))
    return story


def target_blocks(data: ReportData, styles: dict[str, ParagraphStyle]) -> list[Any]:
    insight = data.insight
    assert insight is not None and insight.target is not None
    narrative = insight.target
    currency = data.company.currency
    story: list[Any] = [
        Paragraph(text(narrative.interpretation), styles["lead"]),
        Spacer(1, 2 * mm),
    ]
    story.extend(Paragraph(f"• {text(item)}", styles["body"]) for item in narrative.statements)
    if narrative.conditions:
        rows: list[list[Any]] = [["Condição", "Atinge a meta", "Demais", "Diferença"]]
        rows.extend(
            [
                Paragraph(escape(row.label), styles["small"]),
                format_unit(row.unit, row.hit_value, currency),
                format_unit(row.unit, row.miss_value, currency),
                row.effect,
            ]
            for row in narrative.conditions
        )
        table = Table(rows, colWidths=[70 * mm, 35 * mm, 32 * mm, 32 * mm], repeatRows=1,
                      hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), PALE),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.2),
                    ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.extend(
            [
                Spacer(1, 3 * mm),
                Paragraph(
                    "Condições nos cenários que atingem a meta vs. demais (mediana; taxa para "
                    "eventos). Diferença: tamanho de efeito pelo delta de Cliff.",
                    styles["small"],
                ),
                Spacer(1, 1.5 * mm),
                table,
            ]
        )
    story.append(Spacer(1, 3 * mm))
    return story


def sensitivity_blocks(data: ReportData, styles: dict[str, ParagraphStyle]) -> list[Any]:
    insight = data.insight
    assert insight is not None
    currency = data.company.currency
    story: list[Any] = [Paragraph("Principais riscos", styles["h2"])]
    if insight.risks:
        story.extend(
            Paragraph(f"{index}. {text(risk)}", styles["body"])
            for index, risk in enumerate(insight.risks, start=1)
        )
    else:
        story.append(Paragraph("Nenhum risco material identificado.", styles["body"]))
    if data.tornado is not None:
        tornado = data.tornado
        rows: list[list[Any]] = [["Premissa", "Nível baixo", "P50", "Nível alto", "P50"]]
        rows.extend(
            [
                Paragraph(escape(item.label), styles["small"]),
                format_unit(item.unit, item.low_level, currency),
                compact_money(item.value_at_low, currency, short=True),
                format_unit(item.unit, item.high_level, currency),
                compact_money(item.value_at_high, currency, short=True),
            ]
            for item in tornado.items
        )
        table = Table(rows, colWidths=[57 * mm, 28 * mm, 28 * mm, 28 * mm, 28 * mm],
                      repeatRows=1, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), PALE),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.2),
                    ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        figure: list[Any] = [Paragraph("Sensibilidade (tornado)", styles["h2"])]
        # The tornado headline is usually already a numbered risk above; never repeat it.
        if insight.sensitivity_sentence and insight.sensitivity_sentence not in insight.risks:
            figure.append(Paragraph(text(insight.sensitivity_sentence), styles["body"]))
        figure.extend(
            [
                TornadoChart(tornado, currency),
                Paragraph(
                    "Uma premissa por vez, demais mantidas, sobre os mesmos cenários. Barra "
                    "superior: premissa no nível baixo; inferior: nível alto (nível junto ao "
                    "eixo). Azul aumenta e vermelho reduz o valuation mediano."
                    + (
                        " * Nível ajustado para manter o crescimento na perpetuidade abaixo do "
                        "WACC."
                        if any(item.clamped for item in tornado.items)
                        else ""
                    ),
                    styles["small"],
                ),
                Spacer(1, 2 * mm),
                table,
            ]
        )
        story.append(KeepTogether(figure))
    return story
