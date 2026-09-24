"""Deterministic report narrative built exclusively from validated fields."""

from __future__ import annotations

from .schema import ReportData


def format_money(value: float, currency: str) -> str:
    """Return a locale-stable monetary representation suitable for PDF extraction."""

    symbols = {"BRL": "R$", "USD": "US$", "EUR": "EUR"}
    symbol = symbols.get(currency, currency)
    absolute = abs(value)
    sign = "-" if value < 0 else ""
    integer, decimals = f"{absolute:,.2f}".split(".")
    localized = integer.replace(",", ".") + "," + decimals
    return f"{sign}{symbol} {localized}"


def format_percent(value: float) -> str:
    return f"{value * 100:.1f}%".replace(".", ",")


def format_integer(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def executive_narrative(data: ReportData) -> tuple[str, ...]:
    p = data.valuation.percentiles
    currency = data.company.currency
    paragraphs = [
        (
            f"Em {format_integer(data.audit.simulation_count)} cenários, a mediana de "
            f"{data.valuation.basis} foi {format_money(p['p50'], currency)}. "
            f"O intervalo P25-P75 foi {format_money(p['p25'], currency)} a "
            f"{format_money(p['p75'], currency)}."
        )
    ]
    if data.target is not None:
        paragraphs.append(
            f"A meta de {format_money(data.target.target_value, currency)} foi atingida em "
            f"{format_integer(data.target.hit_count)} de "
            f"{format_integer(data.audit.simulation_count)} cenários "
            f"({format_percent(data.target.probability)})."
        )
    estimated = [driver for driver in data.drivers if driver.association is not None]
    if estimated:
        strongest = max(estimated, key=lambda driver: abs(driver.association or 0.0))
        paragraphs.append(
            f"{strongest.name} apresentou a associação de magnitude mais alta com os "
            f"resultados de valuation (Spearman {strongest.association:+.2f}); associação "
            "estatística não implica causalidade."
        )
    return tuple(paragraphs)
