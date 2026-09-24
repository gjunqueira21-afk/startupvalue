"""Venture Capital Method and simplified primary-round mathematics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite

import numpy as np


@dataclass(frozen=True, slots=True)
class VCRoundResult:
    investment: float
    post_money: float
    pre_money: float
    ownership_at_exit: float
    ownership_today: float
    future_ownership_retention: float


@dataclass(frozen=True, slots=True)
class VCValuationResult:
    annual_exit_metric: float
    exit_enterprise_value: float
    exit_equity_value: float
    present_exit_equity: float
    round: VCRoundResult | None


def value_vc_exit(
    exit_metric_monthly: Sequence[float],
    *,
    exit_multiple: float,
    target_return_annual: float,
    horizon_years: float,
    excess_cash_exit: float = 0.0,
    debt_exit: float = 0.0,
    other_claims_exit: float = 0.0,
    investment: float | None = None,
    future_ownership_retention: float = 1.0,
) -> VCValuationResult:
    metric = np.asarray(tuple(exit_metric_monthly), dtype=np.float64)
    if metric.ndim != 1 or metric.size != 12:
        raise ValueError("exit metric must contain exactly months 49 through 60")
    scalar_values = (
        exit_multiple,
        target_return_annual,
        horizon_years,
        excess_cash_exit,
        debt_exit,
        other_claims_exit,
        future_ownership_retention,
    )
    if not np.all(np.isfinite(metric)) or not all(isfinite(float(x)) for x in scalar_values):
        raise ValueError("VC method inputs must be finite")
    annual_metric = float(np.sum(metric, dtype=np.float64))
    multiple = float(exit_multiple)
    target_return = float(target_return_annual)
    horizon = float(horizon_years)
    retention = float(future_ownership_retention)
    if annual_metric <= 0.0:
        raise ValueError("the selected exit multiple requires a positive annual exit metric")
    if multiple < 0.0:
        raise ValueError("exit multiple cannot be negative")
    if target_return <= -1.0 or horizon <= 0.0:
        raise ValueError("target return must exceed -1 and horizon must be positive")
    if not 0.0 < retention <= 1.0:
        raise ValueError("future ownership retention must be in (0, 1]")
    exit_ev = annual_metric * multiple
    exit_equity = exit_ev + float(excess_cash_exit) - float(debt_exit) - float(other_claims_exit)
    if exit_equity <= 0.0:
        raise ValueError("exit equity must be positive for the VC method")
    present = exit_equity / ((1.0 + target_return) ** horizon)
    round_result = None
    if investment is not None:
        invested = float(investment)
        if not isfinite(invested) or invested < 0.0:
            raise ValueError("investment must be finite and non-negative")
        post_money = present * retention
        pre_money = post_money - invested
        ownership_exit = invested / present
        ownership_today = ownership_exit / retention
        if pre_money < 0.0 or ownership_today > 1.0:
            raise ValueError(
                "round is infeasible under the supplied return and dilution assumptions"
            )
        round_result = VCRoundResult(
            invested, post_money, pre_money, ownership_exit, ownership_today, retention
        )
    return VCValuationResult(annual_metric, exit_ev, exit_equity, present, round_result)
