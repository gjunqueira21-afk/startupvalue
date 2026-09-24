"""Free cash flow to the firm (FCFF) reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _finite(name: str, value: float) -> float:
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True, slots=True)
class FCFFBridge:
    """One-period operating-profit-to-FCFF reconciliation in one currency."""

    revenue: float
    cogs: float
    operating_expenses: float
    depreciation_amortization: float
    cash_operating_taxes: float
    capex: float
    delta_nwc: float
    ebitda: float
    ebit: float
    fcff: float


def calculate_fcff(
    *,
    revenue: float,
    cogs: float,
    operating_expenses: float,
    depreciation_amortization: float = 0.0,
    cash_operating_taxes: float = 0.0,
    capex: float = 0.0,
    delta_nwc: float = 0.0,
) -> FCFFBridge:
    """Calculate FCFF without treating financing flows as operating cash flow."""

    values = {
        name: _finite(name, value)
        for name, value in {
            "revenue": revenue,
            "cogs": cogs,
            "operating_expenses": operating_expenses,
            "depreciation_amortization": depreciation_amortization,
            "cash_operating_taxes": cash_operating_taxes,
            "capex": capex,
            "delta_nwc": delta_nwc,
        }.items()
    }
    ebitda = values["revenue"] - values["cogs"] - values["operating_expenses"]
    ebit = ebitda - values["depreciation_amortization"]
    fcff = (
        ebit
        - values["cash_operating_taxes"]
        + values["depreciation_amortization"]
        - values["capex"]
        - values["delta_nwc"]
    )
    return FCFFBridge(**values, ebitda=ebitda, ebit=ebit, fcff=fcff)
