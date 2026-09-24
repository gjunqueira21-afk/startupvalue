"""Compact pt-BR number formatting shared by the insight text, dashboard and PDF.

Only ASCII punctuation is emitted (hyphen for negatives) so base PDF fonts
render every glyph.
"""

from __future__ import annotations

SYMBOLS = {"BRL": "R$", "USD": "US$", "EUR": "EUR"}


def _decimal(value: float, decimals: int) -> str:
    return f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _scaled(value: float, singular: str, plural: str) -> str:
    decimals = 0 if value >= 99.95 else 1
    rounded = round(value, decimals)
    return f"{_decimal(rounded, decimals)} {singular if rounded < 2 else plural}"


def compact_money(value: float, currency: str, *, short: bool = False) -> str:
    """Long style for prose ("R$ 8,4 milhões"); short for tiles and tables ("R$ 8,4 mi")."""
    symbol = SYMBOLS.get(currency, currency)
    sign = "-" if value < 0 else ""
    absolute = abs(value)
    # Move to the next scale when the smaller one would round to 1.000 or more.
    if round(absolute / 1e6) >= 1000:
        amount = _scaled(absolute / 1e9, *(("bi", "bi") if short else ("bilhão", "bilhões")))
    elif round(absolute / 1e3) >= 1000:
        amount = _scaled(absolute / 1e6, *(("mi", "mi") if short else ("milhão", "milhões")))
    elif round(absolute) >= 1000:
        amount = f"{_decimal(round(absolute / 1e3), 0)} mil"
    else:
        amount = _decimal(round(absolute), 0)
    return f"{sign}{symbol} {amount}"


def percent(value: float, decimals: int = 1) -> str:
    if value in (0.0, 1.0):
        return f"{round(value * 100):d}%"
    return f"{_decimal(value * 100.0, decimals)}%"


def share(value: float) -> str:
    return percent(value, decimals=0)


def multiplier(value: float) -> str:
    return f"{_decimal(value, 2)}x"


def format_unit(unit: str | None, value: float, currency: str) -> str:
    """Format a catalog variable by its unit (currency, ratio, multiplier, binary)."""
    if unit == "currency":
        return compact_money(value, currency, short=True)
    if unit in {"ratio", "binary"}:
        return percent(value)
    if unit == "multiplier":
        return multiplier(value)
    return _decimal(value, 2)


def effect_label(delta: float, kind: str) -> str:
    """Cliff's delta magnitude bands (Romano et al., 2006); rate gap for 0/1 events."""
    if kind == "binary":
        return f"{'+' if delta >= 0 else '-'}{_decimal(abs(delta) * 100.0, 1)} p.p."
    size = abs(delta)
    if size >= 0.474:
        return "forte"
    if size >= 0.33:
        return "moderada"
    if size >= 0.147:
        return "fraca"
    return "desprezível"
