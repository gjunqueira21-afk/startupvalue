"""Vector charts of the PDF report, drawn in one visual language.

Print palette (validated with the dataviz CVD checker on white): #2563B8 raises
the valuation, #C43D4B lowers it; the distribution uses brand green for the
P25-P75 core, a same-hue tint for the remaining scenarios and #C43D4B for
negative values, always next to a labelled R$ 0 line. Sign and text carry
direction too, so every chart stays readable in grayscale.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import floor, log10

from reportlab.lib.colors import Color
from reportlab.lib.units import mm
from reportlab.platypus import Flowable

from app.insights.formatting import SYMBOLS, compact_money, format_unit, percent

from .pdf_theme import (
    DECREASE,
    GREEN,
    GREEN_TINT,
    INCREASE,
    INK,
    LINE,
    MUTED,
    PALE,
    TRACK,
    WHITE,
    WIDTH,
    fit,
)
from .schema import Histogram, PercentileKey, TornadoSection


def _decimal(value: float, decimals: int) -> str:
    return f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def nice_step(extent: float, target: int) -> float:
    """1-2-2.5-5 step giving roughly ``target`` intervals over ``extent``."""
    raw = max(extent, 1e-12) / max(target, 1)
    magnitude = float(10.0 ** floor(log10(raw)))
    for multiple in (1.0, 2.0, 2.5, 5.0, 10.0):
        if raw <= multiple * magnitude:
            return multiple * magnitude
    return 10 * magnitude


def ticks(start: float, end: float, step: float) -> list[float]:
    first = int(-(-start // step))  # ceil without float drift on exact multiples
    values: list[float] = []
    index = first
    while index * step <= end + step * 1e-9:
        values.append(index * step)
        index += 1
    return values


def money_tick(value: float, step: float, currency: str, scale_of: float) -> str:
    """Axis label in the scale of the whole axis: "R$ 10 mi", "R$ 2,5 mi", "R$ 0"."""
    symbol = SYMBOLS.get(currency, currency)
    if abs(value) < step * 1e-6:
        return f"{symbol} 0"
    for size, suffix in ((1e9, "bi"), (1e6, "mi"), (1e3, "mil")):
        if scale_of >= size:
            scaled_step = step / size
            decimals = 0 if abs(scaled_step - round(scaled_step)) < 1e-9 else 1
            if decimals and abs(scaled_step * 10 - round(scaled_step * 10)) > 1e-9:
                decimals = 2
            sign = "-" if value < 0 else ""
            return f"{sign}{symbol} {_decimal(abs(value) / size, decimals)} {suffix}"
    return f"{'-' if value < 0 else ''}{symbol} {_decimal(abs(value), 0)}"


class HistogramChart(Flowable):
    """Simulated valuation distribution with P25-P75 core, P10/P50/P90 and zero."""

    def __init__(
        self,
        histogram: Histogram,
        percentiles: dict[PercentileKey, float],
        currency: str,
        width: float = WIDTH,
        height: float = 92 * mm,
    ) -> None:
        super().__init__()
        self.histogram = histogram
        self.percentiles = percentiles
        self.currency = currency
        self.width = width
        self.height = height

    def draw(self) -> None:
        canvas = self.canv
        edges, counts = self.histogram.edges, self.histogram.counts
        start, end = edges[0], edges[-1]
        left, right = 15 * mm, self.width - 2 * mm
        bottom, top = 14 * mm, self.height - 10.5 * mm
        plot_w, plot_h = right - left, top - bottom

        def x_of(value: float) -> float:
            return left + plot_w * min(max((value - start) / (end - start), 0.0), 1.0)

        max_count = max(counts) or 1
        y_step = nice_step(max_count, 4)
        y_max = y_step * -(-max_count // y_step)

        def y_of(count: float) -> float:
            return bottom + plot_h * count / y_max

        p = self.percentiles
        core_left, core_right = x_of(p["p25"]), x_of(p["p75"])
        canvas.setFillColor(PALE)
        canvas.rect(core_left, bottom, core_right - core_left, plot_h, stroke=0, fill=1)

        canvas.setFont("Helvetica", 6.5)
        canvas.setLineWidth(0.35)
        for value in ticks(0, y_max, y_step):
            y = y_of(value)
            canvas.setStrokeColor(LINE)
            if value > 0:
                canvas.line(left, y, right, y)
            canvas.setFillColor(MUTED)
            canvas.drawRightString(left - 1.8 * mm, y - 2, _decimal(value, 0))
        canvas.saveState()
        canvas.translate(2.2 * mm, bottom + plot_h / 2)
        canvas.rotate(90)
        canvas.drawCentredString(0, 0, "Número de cenários")
        canvas.restoreState()

        splits = sorted({p["p25"], p["p75"], *((0.0,) if start < 0 < end else ())})
        for index, count in enumerate(counts):
            if count == 0:
                continue
            low, high = edges[index], edges[index + 1]
            bounds = [low, *(value for value in splits if low < value < high), high]
            height = y_of(count) - bottom
            for seg_low, seg_high in zip(bounds, bounds[1:], strict=False):
                middle = (seg_low + seg_high) / 2
                if middle < 0:
                    canvas.setFillColor(DECREASE)
                elif p["p25"] <= middle <= p["p75"]:
                    canvas.setFillColor(GREEN)
                else:
                    canvas.setFillColor(GREEN_TINT)
                x0, x1 = x_of(seg_low), x_of(seg_high)
                inset_left = 0.25 if seg_low == low else 0.0
                inset_right = 0.25 if seg_high == high else 0.0
                canvas.rect(
                    x0 + inset_left, bottom, max(x1 - x0 - inset_left - inset_right, 0.1),
                    height, stroke=0, fill=1,
                )

        canvas.setStrokeColor(MUTED)
        canvas.setLineWidth(0.6)
        canvas.line(left, bottom, right, bottom)

        x_step = nice_step(end - start, 8)
        scale_of = max(abs(start), abs(end))
        crosses_zero = start < 0 < end
        for value in ticks(start, end, x_step):
            x = x_of(value)
            canvas.setStrokeColor(MUTED)
            canvas.setLineWidth(0.5)
            canvas.line(x, bottom, x, bottom - 1.2 * mm)
            label = money_tick(value, x_step, self.currency, scale_of)
            is_zero = crosses_zero and abs(value) < x_step * 1e-6
            font = "Helvetica-Bold" if is_zero else "Helvetica"
            canvas.setFont(font, 6.6)
            canvas.setFillColor(INK if is_zero else MUTED)
            half = canvas.stringWidth(label, font, 6.6) / 2
            centre = min(max(x, half), self.width - half)
            canvas.drawCentredString(centre, bottom - 4.3 * mm, label)

        if crosses_zero:
            zero = x_of(0.0)
            canvas.setStrokeColor(DECREASE)
            canvas.setLineWidth(1.1)
            canvas.line(zero, bottom, zero, top)

        # Percentile markers with labels on up to two rows so they never collide.
        rows: list[float] = [-1e9, -1e9]
        markers: tuple[PercentileKey, ...] = ("p10", "p50", "p90")
        for key in markers:
            value = p[key]
            x = x_of(value)
            strong = key == "p50"
            label = f"{key.upper()}  {compact_money(value, self.currency, short=True)}"
            font = "Helvetica-Bold" if strong else "Helvetica"
            width = canvas.stringWidth(label, font, 6.8)
            centre = min(max(x, width / 2), self.width - width / 2)
            row = 0 if centre - width / 2 > rows[0] + 1.5 * mm else 1
            rows[row] = centre + width / 2
            label_y = top + (2.0 if row == 0 else 5.9) * mm
            canvas.setStrokeColor(INK if strong else MUTED)
            canvas.setLineWidth(1.1 if strong else 0.7)
            canvas.setDash([] if strong else [2, 1.6])
            canvas.line(x, bottom, x, label_y - 1.0 * mm)
            canvas.setDash([])
            canvas.setFont(font, 6.8)
            canvas.setFillColor(INK)
            canvas.drawCentredString(centre, label_y, label)

        # Legend and axis title share the bottom row.
        legend: list[tuple[Color, str]] = [
            (GREEN, "Faixa central P25–P75"),
            (GREEN_TINT, "Demais cenários"),
        ]
        if start < 0:
            legend.append((DECREASE, "Valuation negativo"))
        x = left
        canvas.setFont("Helvetica", 6.6)
        for colour, label in legend:
            canvas.setFillColor(colour)
            canvas.rect(x, 1.2 * mm, 2.6 * mm, 2.6 * mm, stroke=0, fill=1)
            canvas.setFillColor(MUTED)
            canvas.drawString(x + 3.8 * mm, 1.7 * mm, label)
            x += 3.8 * mm + canvas.stringWidth(label, "Helvetica", 6.6) + 5 * mm
        canvas.setStrokeColor(INK)
        canvas.setLineWidth(1.1)
        canvas.line(x, 2.5 * mm, x + 4 * mm, 2.5 * mm)
        canvas.drawString(x + 5.2 * mm, 1.7 * mm, "P50")
        x += 5.2 * mm + canvas.stringWidth("P50", "Helvetica", 6.6) + 4 * mm
        canvas.setStrokeColor(MUTED)
        canvas.setLineWidth(0.7)
        canvas.setDash([2, 1.6])
        canvas.line(x, 2.5 * mm, x + 4 * mm, 2.5 * mm)
        canvas.setDash([])
        canvas.drawString(x + 5.2 * mm, 1.7 * mm, "P10 / P90")
        symbol = SYMBOLS.get(self.currency, self.currency)
        canvas.drawRightString(right, 1.7 * mm, f"Valuation por cenário ({symbol})")


class RangeBar(Flowable):
    """Football-field bar: P10-P90 whisker, P25-P75 core, P50 tick, labelled values."""

    def __init__(
        self, percentiles: dict[PercentileKey, float], currency: str, width: float
    ) -> None:
        super().__init__()
        self.percentiles = percentiles
        self.currency = currency
        self.width = width
        self.height = 27 * mm

    def draw(self) -> None:
        canvas = self.canv
        p = self.percentiles
        low, high = p["p10"], p["p90"]
        extent = max(high - low, 1e-9)
        pad = 9 * mm

        def x_of(value: float) -> float:
            return pad + (self.width - 2 * pad) * (value - low) / extent

        mid = 13.5 * mm
        if low < 0 < high:
            zero = x_of(0.0)
            canvas.setStrokeColor(DECREASE)
            canvas.setLineWidth(0.8)
            canvas.setDash([1.6, 1.4])
            canvas.line(zero, mid - 5 * mm, zero, mid + 5 * mm)
            canvas.setDash([])
        canvas.setStrokeColor(MUTED)
        canvas.setLineWidth(0.9)
        canvas.line(x_of(low), mid, x_of(high), mid)
        for value in (low, high):
            canvas.line(x_of(value), mid - 1.6 * mm, x_of(value), mid + 1.6 * mm)
        canvas.setFillColor(GREEN)
        core_left, core_right = x_of(p["p25"]), x_of(p["p75"])
        canvas.rect(core_left, mid - 2.8 * mm, core_right - core_left, 5.6 * mm, stroke=0, fill=1)
        median = x_of(p["p50"])
        canvas.setStrokeColor(WHITE)
        canvas.setLineWidth(3.2)
        canvas.line(median, mid - 4.2 * mm, median, mid + 4.2 * mm)
        canvas.setStrokeColor(INK)
        canvas.setLineWidth(1.6)
        canvas.line(median, mid - 4.2 * mm, median, mid + 4.2 * mm)

        below_end = -1e9
        keys: tuple[PercentileKey, ...] = ("p10", "p25", "p50", "p75", "p90")
        for key in keys:
            value = p[key]
            x = x_of(value)
            amount = compact_money(value, self.currency, short=True)
            font = "Helvetica-Bold" if key == "p50" else "Helvetica"
            width = max(
                canvas.stringWidth(amount, font, 7.4), canvas.stringWidth(key.upper(), font, 6.4)
            )
            centre = min(max(x, width / 2), self.width - width / 2)
            if centre - width / 2 > below_end + 1.2 * mm:
                below_end = centre + width / 2
                name_y, value_y = mid - 7.6 * mm, mid - 11 * mm
            else:
                name_y, value_y = mid + 9.6 * mm, mid + 6.2 * mm
            canvas.setFont(font, 6.4)
            canvas.setFillColor(MUTED)
            canvas.drawCentredString(centre, name_y, key.upper())
            canvas.setFont(font, 7.4)
            canvas.setFillColor(INK)
            canvas.drawCentredString(centre, value_y, amount)


class ContributionBar(Flowable):
    """Share of explained variance, coloured by the driver's direction."""

    def __init__(self, share: float, rho: float | None, width: float = 46 * mm) -> None:
        super().__init__()
        self.share = max(0.0, min(1.0, share))
        self.rho = rho
        self.width = width
        self.height = 3 * mm

    def draw(self) -> None:
        canvas = self.canv
        canvas.setFillColor(TRACK)
        canvas.rect(0, 0, self.width, self.height, stroke=0, fill=1)
        canvas.setFillColor(DECREASE if (self.rho or 0.0) < 0 else INCREASE)
        canvas.rect(0, 0, max(self.width * self.share, 0.4), self.height, stroke=0, fill=1)


class DriverChart(Flowable):
    """Diverging Spearman bars on a -1..1 scale with value and share columns."""

    ROW = 6.8 * mm

    def __init__(self, rows: Sequence[tuple[str, float | None, float | None]]) -> None:
        super().__init__()
        self.rows = rows
        self.width = WIDTH
        self.height = self.ROW * len(rows) + 9 * mm

    def draw(self) -> None:
        canvas = self.canv
        label_w, plot_x, plot_w = 56 * mm, 60 * mm, 74 * mm
        value_x, share_x = 152 * mm, WIDTH
        centre = plot_x + plot_w / 2
        top = self.height - 3 * mm
        canvas.setFont("Helvetica-Bold", 6.6)
        canvas.setFillColor(MUTED)
        canvas.drawString(0, top, "Fator")
        canvas.drawRightString(value_x, top, "Spearman")
        canvas.drawRightString(share_x, top, "Participação")
        canvas.setFont("Helvetica", 6.4)
        for fraction, label in ((-1, "-1"), (-0.5, "-0,5"), (0, "0"), (0.5, "+0,5"), (1, "+1")):
            x = centre + fraction * plot_w / 2
            canvas.drawCentredString(x, top, label)
            canvas.setStrokeColor(MUTED if fraction == 0 else LINE)
            canvas.setLineWidth(0.6 if fraction == 0 else 0.35)
            canvas.line(x, 1 * mm, x, top - 1.8 * mm)
        canvas.setStrokeColor(INK)
        canvas.setLineWidth(0.9)
        canvas.line(0, top - 2.2 * mm, WIDTH, top - 2.2 * mm)
        for index, (label, rho, share) in enumerate(self.rows):
            y = top - 2.2 * mm - self.ROW * (index + 1) + 2.4 * mm
            if index < len(self.rows) - 1:
                canvas.setStrokeColor(LINE)
                canvas.setLineWidth(0.35)
                canvas.line(0, y - 2.4 * mm, WIDTH, y - 2.4 * mm)
            canvas.setFillColor(INK)
            canvas.setFont("Helvetica", 8)
            canvas.drawString(0, y, fit(canvas, label, "Helvetica", 8, label_w))
            if rho is None:
                canvas.setFillColor(MUTED)
                canvas.drawString(plot_x, y, "não estimável (constante)")
                continue
            length = abs(rho) * plot_w / 2
            canvas.setFillColor(INCREASE if rho >= 0 else DECREASE)
            canvas.rect(
                centre if rho >= 0 else centre - length, y - 0.7 * mm, max(length, 0.4), 3.2 * mm,
                stroke=0, fill=1,
            )
            canvas.setFillColor(INK)
            canvas.setFont("Helvetica-Bold", 8)
            canvas.drawRightString(value_x, y, f"{rho:+.2f}".replace(".", ","))
            canvas.setFont("Helvetica", 8)
            canvas.drawRightString(share_x, y, "-" if share is None else percent(share, decimals=0))


class TornadoChart(Flowable):
    """Swing of the median valuation per assumption around the base, zero-centred."""

    ROW = 11.5 * mm

    def __init__(self, tornado: TornadoSection, currency: str) -> None:
        super().__init__()
        self.tornado = tornado
        self.currency = currency
        self.width = WIDTH
        self.height = self.ROW * len(tornado.items) + 10 * mm

    def draw(self) -> None:
        canvas = self.canv
        base = self.tornado.base_value
        label_w, plot_x = 46 * mm, 50 * mm
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
        axis_y = 6 * mm
        for fraction in (-1.0, -0.5, 0.5, 1.0):
            canvas.setStrokeColor(LINE)
            canvas.setLineWidth(0.35)
            x = centre + fraction * half
            canvas.line(x, axis_y, x, self.height)
        canvas.setStrokeColor(MUTED)
        canvas.setLineWidth(0.6)
        canvas.line(plot_x, axis_y, WIDTH, axis_y)
        canvas.setStrokeColor(INK)
        canvas.setLineWidth(0.8)
        canvas.line(centre, axis_y, centre, self.height)
        for index, item in enumerate(self.tornado.items):
            y = self.height - self.ROW * (index + 1)
            canvas.setFillColor(INK)
            canvas.setFont("Helvetica-Bold", 8)
            label = item.label + (" *" if item.clamped else "")
            canvas.drawString(0, y + 5.8 * mm, fit(canvas, label, "Helvetica-Bold", 8, label_w))
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(MUTED)
            levels = (
                f"{format_unit(item.unit, item.low_level, self.currency)} a "
                f"{format_unit(item.unit, item.high_level, self.currency)}"
            )
            canvas.drawString(0, y + 2.4 * mm, levels)
            for offset, value, level in (
                (5.9 * mm, item.value_at_low, item.low_level),
                (1.7 * mm, item.value_at_high, item.high_level),
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
                canvas.setFont("Helvetica-Bold", 7)
                canvas.setFillColor(INK)
                if delta >= 0:
                    canvas.drawString(centre + length + 1.5 * mm, bar_y + 0.8 * mm, change)
                    canvas.setFont("Helvetica", 7)
                    canvas.setFillColor(MUTED)
                    canvas.drawRightString(centre - 1.5 * mm, bar_y + 0.8 * mm, level_text)
                else:
                    canvas.drawRightString(centre - length - 1.5 * mm, bar_y + 0.8 * mm, change)
                    canvas.setFont("Helvetica", 7)
                    canvas.setFillColor(MUTED)
                    canvas.drawString(centre + 1.5 * mm, bar_y + 0.8 * mm, level_text)
        canvas.setFont("Helvetica", 6.8)
        canvas.setFillColor(MUTED)
        short = compact_money(scale, self.currency, short=True)
        canvas.drawCentredString(centre - half, 2 * mm, f"-{short}")
        canvas.drawCentredString(centre + half, 2 * mm, f"+{short}")
        canvas.setFont("Helvetica-Bold", 6.8)
        canvas.setFillColor(INK)
        canvas.drawCentredString(
            centre, 2 * mm, f"P50 base {compact_money(base, self.currency, short=True)}"
        )
