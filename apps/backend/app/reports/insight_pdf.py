"""Executive-intelligence blocks of the PDF: KPI panel, drivers, target and tornado.

The text comes verbatim from the deterministic ``insight`` block (same wording
as the dashboard); this module only lays it out with the shared report system.
"""

from __future__ import annotations

from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Table, TableStyle

from app.insights.formatting import compact_money, format_unit, percent

from .narrative import format_integer, format_money
from .pdf_charts import ContributionBar, DriverChart, RangeBar, TornadoChart
from .pdf_theme import (
    GAP_M,
    GAP_S,
    GAP_XS,
    GREEN,
    PALE,
    WIDTH,
    Numbering,
    bullets,
    callout,
    columns,
    data_table,
    figure,
    fit_size,
    gap,
    span,
    stat_strip,
    text,
)
from .schema import ReportData

__all__ = [
    "driver_blocks",
    "executive_summary_blocks",
    "kpi_cell",
    "sensitivity_blocks",
    "target_blocks",
    "text",
]


def kpi_cell(
    label: str,
    value: str,
    caption: str,
    styles: dict[str, ParagraphStyle],
    width: float,
    size: float = 13.5,
    label_style: str = "kpi_label",
) -> list[Any]:
    """Label, one-line value (shrunk to fit its tile) and caption."""
    fitted = fit_size(value, "Helvetica-Bold", size, width, minimum=9.5)
    value_style = ParagraphStyle(
        f"SVKpiFit{fitted}", parent=styles["kpi_value"], fontSize=fitted, leading=fitted * 1.25
    )
    return [
        Paragraph(escape(label), styles[label_style]),
        Paragraph(text(value), value_style),
        Paragraph(text(caption), styles["kpi_caption"]),
    ]


def _range_value(low: str, high: str) -> str:
    """"R$ 8,2–17,9 mi" when both ends are positive with the same scale, else both ends."""
    low_parts, high_parts = low.split(" "), high.split(" ")
    if (
        not low.startswith("-")
        and not high.startswith("-")
        and len(low_parts) == len(high_parts) == 3
        and low_parts[0] == high_parts[0]
        and low_parts[2] == high_parts[2]
    ):
        return f"{low_parts[0]} {low_parts[1]}–{high_parts[1]} {low_parts[2]}"
    return f"{low} – {high}"


def executive_summary_blocks(data: ReportData, styles: dict[str, ParagraphStyle]) -> list[Any]:
    """Hero valuation with range bar, KPI strip, top drivers and the executive text."""
    insight = data.insight
    assert insight is not None
    currency = data.company.currency
    p = data.valuation.percentiles

    def short(value: float) -> str:
        return compact_money(value, currency, short=True)

    hero_width = span(5)
    hero_cell = kpi_cell(
        "ESTIMATED VALUATION",
        compact_money(p["p50"], currency),
        f"P50 (mediana) · {format_money(p['p50'], currency)}",
        styles,
        hero_width - 11 * mm,
        size=24,
    )
    hero_cell.append(
        Paragraph(
            f"{text(data.valuation.basis)} · "
            f"{format_integer(data.audit.simulation_count)} cenários",
            styles["kpi_caption"],
        )
    )
    range_width = WIDTH - hero_width
    hero = Table(
        [[hero_cell, RangeBar(p, currency, range_width - 8 * mm)]],
        colWidths=[hero_width, range_width],
        hAlign="LEFT",
    )
    hero.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("LINEBEFORE", (0, 0), (0, -1), 2.2, GREEN),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (0, 0), 9),
                ("LEFTPADDING", (1, 0), (1, 0), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )

    if data.target is not None:
        probability = percent(data.target.probability)
        probability_caption = (
            f"Meta de {short(data.target.target_value)} ou mais · "
            f"{format_integer(data.target.hit_count)} de "
            f"{format_integer(data.audit.simulation_count)} cenários"
        )
    else:
        probability, probability_caption = "N/A", "Nenhuma meta informada na exportação."
    ratio = data.valuation.uncertainty_ratio
    uncertainty_caption = (
        f"Faixa P25–P75 = {percent(ratio, decimals=0)} da mediana"
        if ratio is not None
        else "Mediana não positiva; ver critério."
    )
    widths = [45 * mm, 27 * mm, 27 * mm, 39 * mm, 32 * mm]
    inner = [width - 12 for width in widths]
    tiles = stat_strip(
        [
            kpi_cell(
                "CORE RANGE",
                _range_value(short(p["p25"]), short(p["p75"])),
                f"P25–P75: {format_money(p['p25'], currency)} – "
                f"{format_money(p['p75'], currency)}",
                styles,
                inner[0],
            ),
            kpi_cell("DOWNSIDE", short(p["p10"]), "P10 · cenário conservador", styles, inner[1]),
            kpi_cell("UPSIDE", short(p["p90"]), "P90 · cenário otimista", styles, inner[2]),
            kpi_cell("PROBABILITY OF TARGET", probability, probability_caption, styles, inner[3]),
            kpi_cell(
                "UNCERTAINTY", insight.uncertainty_label_pt, uncertainty_caption, styles, inner[4]
            ),
        ],
        widths,
    )
    story: list[Any] = [
        Paragraph(text(insight.headline), styles["lead"]),
        gap(GAP_S),
        hero,
        gap(GAP_XS),
        Paragraph(
            "Faixa simulada de P10 a P90 · barra verde: faixa central P25–P75 · traço: "
            f"mediana (P50) · Fonte: StartupValue SimulationResult · "
            f"{escape(data.audit.simulation_id[:12])}",
            styles["caption"],
        ),
        gap(GAP_S),
        tiles,
        gap(GAP_M + 1 * mm),
    ]
    if insight.key_drivers:
        rows = [
            [
                Paragraph(f"{rank}", styles["rank"]),
                driver.label,
                ContributionBar(driver.contribution, driver.rho, width=40 * mm),
                percent(driver.contribution, decimals=0),
                "-"
                if driver.rho is None
                else (
                    f"associação {'positiva' if driver.rho >= 0 else 'negativa'} "
                    f"({driver.rho:+.2f})".replace(".", ",")
                ),
            ]
            for rank, driver in enumerate(insight.key_drivers, start=1)
        ]
        table = data_table(
            ["#", "Fator", "Participação na variância explicada", "", "Direção"],
            rows,
            [8 * mm, 58 * mm, 44 * mm, 14 * mm, 46 * mm],
            styles,
            numeric=[3],
            extra=[
                ("FONTNAME", (3, 1), (3, -1), "Helvetica-Bold"),
                ("TOPPADDING", (0, 1), (-1, -1), 4.6),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 4.6),
            ],
        )
        story.append(
            KeepTogether(
                [
                    Paragraph("TOP VALUATION DRIVERS", styles["eyebrow"]),
                    table,
                    Paragraph(
                        "Barra azul: associação positiva; vermelha: negativa. Associação "
                        "não é causa.",
                        styles["table_note"],
                    ),
                ]
            )
        )
        story.append(gap(GAP_M + 1 * mm))
    story.append(Paragraph("LEITURA EXECUTIVA", styles["eyebrow"]))
    story.extend(Paragraph(text(item), styles["body_lead"]) for item in insight.executive_summary)
    return story


def driver_blocks(
    data: ReportData, styles: dict[str, ParagraphStyle], numbering: Numbering
) -> list[Any]:
    insight = data.insight
    assert insight is not None
    story: list[Any] = []
    if insight.key_drivers_sentence:
        story.append(Paragraph(text(insight.key_drivers_sentence), styles["body_lead"]))
        story.append(gap(GAP_S))
    if data.drivers:
        chart = figure(
            DriverChart([(d.name, d.association, d.contribution) for d in data.drivers]),
            numbering.next_figure(),
            "Associação de cada fator com o valuation (Spearman, -1 a +1)",
            f"{data.audit.simulation_id[:12]} · "
            f"{format_integer(data.audit.simulation_count)} cenários",
            styles,
            note=(
                "Azul: associação positiva; vermelho: negativa. Participação: parcela da "
                "variância explicada (SRRC ao quadrado, normalizado)."
            ),
        )
        story.append(KeepTogether(chart))
        story.append(gap(GAP_M))
    halves: list[list[Any]] = []
    for title, entries, empty in (
        (
            "Upside · 10% melhores cenários",
            insight.upside,
            "Nenhum fator se desloca de forma relevante nos melhores cenários.",
        ),
        (
            "Downside · 10% piores cenários",
            insight.downside,
            "Nenhum fator se desloca de forma relevante nos piores cenários.",
        ),
    ):
        block: list[Any] = [Paragraph(escape(title), styles["h2"])]
        if entries:
            block.extend(bullets(entries, styles))
        else:
            block.append(Paragraph(empty, styles["body"]))
        halves.append(block)
    story.append(columns(halves[0], halves[1], span(6), span(6)))
    return story


def target_blocks(data: ReportData, styles: dict[str, ParagraphStyle]) -> list[Any]:
    insight = data.insight
    assert insight is not None and insight.target is not None
    narrative = insight.target
    currency = data.company.currency
    story: list[Any] = [
        Paragraph(text(narrative.interpretation), styles["lead_small"]),
        gap(GAP_XS),
    ]
    story.extend(bullets(narrative.statements, styles))
    story.extend(
        [
            gap(GAP_XS),
            callout([Paragraph(text(narrative.disclaimer), styles["small"])]),
        ]
    )
    if narrative.conditions:
        rows = [
            [
                row.label,
                format_unit(row.unit, row.hit_value, currency),
                format_unit(row.unit, row.miss_value, currency),
                row.effect,
            ]
            for row in narrative.conditions
        ]
        story.extend(
            [
                Paragraph("Condições nos cenários que atingem a meta vs. demais", styles["h2"]),
                data_table(
                    ["Condição", "Atinge a meta (mediana)", "Demais (mediana)", "Diferença"],
                    rows,
                    [70 * mm, 36 * mm, 32 * mm, 32 * mm],
                    styles,
                    numeric=[1, 2, 3],
                ),
                Paragraph(
                    "Mediana por grupo; taxa para eventos. Diferença: tamanho de efeito pelo "
                    "delta de Cliff (p.p. para eventos).",
                    styles["table_note"],
                ),
            ]
        )
    return story


def sensitivity_blocks(
    data: ReportData, styles: dict[str, ParagraphStyle], numbering: Numbering
) -> list[Any]:
    insight = data.insight
    assert insight is not None
    currency = data.company.currency
    story: list[Any] = [Paragraph("Principais riscos", styles["h2"])]
    if insight.risks:
        story.extend(bullets(insight.risks, styles, numbered=True))
    else:
        story.append(Paragraph("Nenhum risco material identificado.", styles["body"]))
    if data.tornado is not None:
        tornado = data.tornado
        rows = [
            [
                item.label + (" *" if item.clamped else ""),
                format_unit(item.unit, item.low_level, currency),
                compact_money(item.value_at_low, currency, short=True),
                format_unit(item.unit, item.high_level, currency),
                compact_money(item.value_at_high, currency, short=True),
            ]
            for item in tornado.items
        ]
        table = data_table(
            ["Premissa", "Nível baixo", "P50 no nível baixo", "Nível alto", "P50 no nível alto"],
            rows,
            [58 * mm, 24 * mm, 32 * mm, 24 * mm, 32 * mm],
            styles,
            numeric=[1, 2, 3, 4],
        )
        note = (
            "Uma premissa por vez, demais mantidas, sobre os mesmos cenários. Barra superior: "
            "premissa no nível baixo; inferior: nível alto (nível junto ao eixo). Azul aumenta "
            "e vermelho reduz o valuation mediano."
            + (
                " * Nível ajustado para manter o crescimento na perpetuidade abaixo do WACC."
                if any(item.clamped for item in tornado.items)
                else ""
            )
        )
        head: list[Any] = [Paragraph("Sensibilidade (tornado)", styles["h2"])]
        # The tornado headline is usually already a numbered risk above; never repeat it.
        if insight.sensitivity_sentence and insight.sensitivity_sentence not in insight.risks:
            head.append(Paragraph(text(insight.sensitivity_sentence), styles["body"]))
        story.append(
            KeepTogether(
                [
                    *head,
                    *figure(
                        TornadoChart(tornado, currency),
                        numbering.next_figure(),
                        "Variação do valuation mediano por premissa (tornado)",
                        f"{data.audit.simulation_id[:12]} · base P50 "
                        f"{compact_money(tornado.base_value, currency, short=True)}",
                        styles,
                        note=note,
                    ),
                    gap(GAP_S),
                    table,
                ]
            )
        )
    return story
