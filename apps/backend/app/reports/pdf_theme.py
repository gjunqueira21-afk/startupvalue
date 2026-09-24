"""Design tokens and layout primitives shared by every page of the PDF report.

One system for the whole document: a 12-column grid on a 170 mm measure, a
Helvetica type scale, a single table style, a numbered section header and
figure captions. Only WinAnsi glyphs are drawn (base fonts are not subset).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Flowable, Paragraph, Spacer, Table, TableStyle

# Print palette (CVD-validated on white). Text never uses a series colour.
INK = colors.HexColor("#111827")
GREEN = colors.HexColor("#087A55")
GREEN_TINT = colors.HexColor("#7FB89F")
MUTED = colors.HexColor("#52605B")
LINE = colors.HexColor("#D8E0DC")
PALE = colors.HexColor("#F2F7F4")
TRACK = colors.HexColor("#EEF2F0")
INCREASE = colors.HexColor("#2563B8")
DECREASE = colors.HexColor("#C43D4B")
WHITE = colors.white

# Page geometry: A4 portrait, 20 mm side margins, 12-column grid with 4 mm gutters.
PAGE_MARGIN_X = 20 * mm
PAGE_MARGIN_TOP = 24 * mm
PAGE_MARGIN_BOTTOM = 21 * mm
WIDTH = 170 * mm
GUTTER = 4 * mm
COLUMN = (WIDTH - 11 * GUTTER) / 12

# Vertical rhythm.
GAP_XS = 1.5 * mm
GAP_S = 3 * mm
GAP_M = 5 * mm
GAP_L = 8 * mm

SOURCE = "StartupValue SimulationResult"


def span(columns: int) -> float:
    """Width of ``columns`` grid columns including the gutters between them."""
    return columns * COLUMN + (columns - 1) * GUTTER


def text(value: str) -> str:
    """Escape for Paragraph markup and keep currency symbols attached to their amount."""
    return escape(value).replace("R$ ", "R$&nbsp;").replace("US$ ", "US$&nbsp;")


def fit(canvas: Any, value: str, font: str, size: float, width: float) -> str:
    """Truncate with an ellipsis so a label never runs into the plot."""
    if canvas.stringWidth(value, font, size) <= width:
        return value
    while value and canvas.stringWidth(f"{value}...", font, size) > width:
        value = value[:-1]
    return f"{value.rstrip()}..."


def fit_size(value: str, font: str, size: float, width: float, minimum: float = 8.0) -> float:
    """Largest font size (in 0.5 pt steps) at which ``value`` fits on one line."""
    while size > minimum and stringWidth(value, font, size) > width:
        size -= 0.5
    return size


def styles() -> dict[str, ParagraphStyle]:
    def style(name: str, **kwargs: Any) -> ParagraphStyle:
        base: dict[str, Any] = {
            "fontName": "Helvetica",
            "fontSize": 9.5,
            "leading": 13.6,
            "textColor": INK,
        }
        base.update(kwargs)
        return ParagraphStyle(f"SV{name}", **base)

    return {
        "body": style("Body", spaceAfter=5),
        "body_lead": style("BodyLead", fontSize=9.8, leading=14.2, spaceAfter=6),
        "bullet": style("Bullet", leftIndent=11, bulletIndent=1, spaceAfter=4),
        "lead": style(
            "Lead", fontName="Helvetica-Bold", fontSize=12.5, leading=16.5, spaceAfter=2
        ),
        "lead_small": style(
            "LeadSmall", fontName="Helvetica-Bold", fontSize=11, leading=15, spaceAfter=3
        ),
        "h2": style(
            "H2",
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13.5,
            spaceBefore=8,
            spaceAfter=4,
            keepWithNext=1,
        ),
        "eyebrow": style(
            "Eyebrow",
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=9,
            textColor=GREEN,
            spaceAfter=3,
            keepWithNext=1,
        ),
        "small": style("Small", fontSize=7.6, leading=10.2, textColor=MUTED),
        "caption_title": style(
            "CaptionTitle", fontName="Helvetica-Bold", fontSize=7.8, leading=10, spaceBefore=4
        ),
        "caption": style("Caption", fontSize=7, leading=9.2, textColor=MUTED),
        "table_note": style(
            "TableNote", fontSize=7, leading=9.2, textColor=MUTED, spaceBefore=3
        ),
        "kpi_label": style(
            "KpiLabel", fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=GREEN
        ),
        "stat_label": style(
            "StatLabel", fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=MUTED
        ),
        "kpi_value": style(
            "KpiValue", fontName="Helvetica-Bold", fontSize=13.5, leading=17, spaceBefore=3
        ),
        "kpi_caption": style(
            "KpiCaption", fontSize=7, leading=9.2, textColor=MUTED, spaceBefore=2
        ),
        "rank": style("Rank", fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=GREEN),
        "td": style("Td", fontSize=8.2, leading=10.4),
        "td_muted": style("TdMuted", fontSize=7.8, leading=10, textColor=MUTED),
        "td_bold": style("TdBold", fontName="Helvetica-Bold", fontSize=8.2, leading=10.4),
        "td_mono": style("TdMono", fontName="Courier", fontSize=7.8, leading=10),
        "num": style(
            "Num", fontName="Helvetica-Bold", fontSize=8.6, leading=10.4, alignment=TA_RIGHT
        ),
        "fact_value": style("FactValue", fontName="Helvetica-Bold", fontSize=9, leading=11.6),
    }


class SectionHeader(Flowable):
    """Numbered eyebrow, section title and a thin rule with a brand accent.

    Callers precede it with a CondPageBreak so a title never sits alone at the
    foot of a page; it registers a PDF outline entry (navigable contents).
    """

    def __init__(self, number: int | str, eyebrow: str, title: str) -> None:
        super().__init__()
        self.number = f"{number:02d}" if isinstance(number, int) else number
        self.eyebrow = eyebrow
        self.title = title
        self.width = WIDTH
        self.height = 15 * mm

    def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
        return self.width, self.height + GAP_M

    def draw(self) -> None:
        canvas = self.canv
        base = GAP_M
        key = f"section-{self.number}"
        canvas.bookmarkPage(key)
        canvas.addOutlineEntry(f"{self.number}  {self.title}", key, level=0)
        canvas.setFillColor(GREEN)
        canvas.setFont("Helvetica-Bold", 7.2)
        canvas.drawString(
            0, base + self.height - 2.6 * mm, f"{self.number}   {self.eyebrow.upper()}"
        )
        canvas.setFillColor(INK)
        canvas.setFont("Helvetica-Bold", 17)
        canvas.drawString(0, base + 3.4 * mm, self.title)
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.6)
        canvas.line(0, base, self.width, base)
        canvas.setStrokeColor(GREEN)
        canvas.setLineWidth(1.8)
        canvas.line(0, base, 14 * mm, base)


class Numbering:
    """Deterministic running counters for sections and figures within one build."""

    def __init__(self) -> None:
        self.section = 0
        self.figure = 0

    def next_section(self) -> int:
        self.section += 1
        return self.section

    def next_figure(self) -> int:
        self.figure += 1
        return self.figure


def figure(
    chart: Flowable,
    number: int,
    title: str,
    source: str,
    styles: dict[str, ParagraphStyle],
    note: str | None = None,
) -> list[Any]:
    """Chart, numbered caption and source.

    Returned flat: wrap it in exactly one KeepTogether at the call site, because
    ReportLab forces a page break when one KeepTogether is nested in another.
    """
    parts: list[Any] = [
        chart,
        Paragraph(f"Figura {number} — {text(title)}", styles["caption_title"]),
    ]
    if note:
        parts.append(Paragraph(text(note), styles["caption"]))
    parts.append(Paragraph(f"Fonte: {SOURCE} · {text(source)}", styles["caption"]))
    return parts


def bullets(
    items: Sequence[str], styles: dict[str, ParagraphStyle], numbered: bool = False
) -> list[Paragraph]:
    return [
        Paragraph(text(item), styles["bullet"], bulletText=f"{index}." if numbered else "•")
        for index, item in enumerate(items, start=1)
    ]


def data_table(
    header: Sequence[str],
    rows: Sequence[Sequence[Any]],
    widths: Sequence[float],
    styles: dict[str, ParagraphStyle],
    numeric: Sequence[int] = (),
    extra: Sequence[tuple[Any, ...]] = (),
) -> Table:
    """The single table style: hairline rows, ink rules, right-aligned numbers.

    Text cells become wrapping Paragraphs; numeric cells stay plain strings so
    amounts never break between the currency symbol and the value.
    """
    numeric_set = set(numeric)
    body: list[list[Any]] = [list(header)]
    for row in rows:
        body.append(
            [
                Paragraph(escape(cell), styles["td"])
                if isinstance(cell, str) and index not in numeric_set
                else cell
                for index, cell in enumerate(row)
            ]
        )
    table = Table(body, colWidths=list(widths), repeatRows=1, hAlign="LEFT")
    commands: list[tuple[Any, ...]] = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7.4),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8.2),
        ("LEADING", (0, 0), (-1, -1), 10.4),
        ("TEXTCOLOR", (0, 1), (-1, -1), INK),
        ("VALIGN", (0, 0), (-1, 0), "BOTTOM"),
        ("VALIGN", (0, 1), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, INK),
        ("LINEBELOW", (0, 1), (-1, -2), 0.35, LINE),
        ("LINEBELOW", (0, -1), (-1, -1), 0.6, MUTED),
    ]
    for column in numeric_set:
        commands.append(("ALIGN", (column, 0), (column, -1), "RIGHT"))
    commands.extend(extra)
    table.setStyle(TableStyle(commands))
    return table


def key_value_table(
    rows: Sequence[tuple[str, Any]],
    styles: dict[str, ParagraphStyle],
    label_width: float = span(4),
    width: float = WIDTH,
    mono: bool = False,
) -> Table:
    """Definition list: muted label, left-aligned value, hairline separators."""
    value_style = styles["td_mono" if mono else "td"]
    body = [
        [
            Paragraph(escape(label), styles["td_muted"]),
            Paragraph(escape(value), value_style) if isinstance(value, str) else value,
        ]
        for label, value in rows
    ]
    table = Table(body, colWidths=[label_width, width - label_width], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3.4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.4),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("LINEABOVE", (0, 0), (-1, 0), 0.9, INK),
                ("LINEBELOW", (0, 0), (-1, -2), 0.35, LINE),
                ("LINEBELOW", (0, -1), (-1, -1), 0.6, MUTED),
            ]
        )
    )
    return table


def stat_strip(cells: Sequence[Sequence[Any]], widths: Sequence[float]) -> Table:
    """KPI tiles separated by hairlines, with an ink rule on top.

    Each tile is (label, value, caption[, ...]); labels, values and captions sit
    on shared rows so values stay aligned even when a label wraps.
    """
    rows = [
        [cell[0] for cell in cells],
        [cell[1] for cell in cells],
        [list(cell[2:]) for cell in cells],
    ]
    table = Table(rows, colWidths=list(widths), hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("VALIGN", (0, 1), (-1, 1), "BOTTOM"),
                ("LINEABOVE", (0, 0), (-1, 0), 0.9, INK),
                ("LINEBELOW", (0, -1), (-1, -1), 0.35, LINE),
                ("LINEBEFORE", (1, 0), (-1, -1), 0.35, LINE),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 1), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -2), 0),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
            ]
        )
    )
    return table


def columns(
    left: Sequence[Any], right: Sequence[Any], left_width: float, right_width: float
) -> Table:
    """Two grid columns of flowables with a gutter between them."""
    table = Table(
        [[list(left), list(right)]], colWidths=[left_width + GUTTER, right_width], hAlign="LEFT"
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), GUTTER),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def callout(content: Sequence[Any], width: float = WIDTH) -> Table:
    """Pale panel with a brand rule on the left, for notes that must not be missed."""
    table = Table([[list(content)]], colWidths=[width], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("LINEBEFORE", (0, 0), (0, -1), 1.8, GREEN),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def gap(height: float) -> Spacer:
    return Spacer(1, height)
