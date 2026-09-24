"""Bridges between enterprise value, equity value, and limited-liability view."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class EquityBridge:
    enterprise_value: float
    excess_cash: float
    non_operating_assets: float
    debt: float
    other_claims: float
    equity_signed: float
    equity_limited_liability: float


def bridge_enterprise_to_equity(
    enterprise_value: float,
    *,
    excess_cash: float = 0.0,
    non_operating_assets: float = 0.0,
    debt: float = 0.0,
    other_claims: float = 0.0,
) -> EquityBridge:
    values = tuple(
        float(value)
        for value in (enterprise_value, excess_cash, non_operating_assets, debt, other_claims)
    )
    if not all(isfinite(value) for value in values):
        raise ValueError("equity bridge values must be finite")
    ev, cash, assets, debt_value, claims = values
    signed = ev + cash + assets - debt_value - claims
    return EquityBridge(ev, cash, assets, debt_value, claims, signed, max(signed, 0.0))
