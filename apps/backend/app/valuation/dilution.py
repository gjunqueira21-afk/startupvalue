"""Primary round ownership helpers."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class PrimaryRound:
    pre_money: float
    investment: float
    post_money: float
    investor_ownership: float


def round_for_target_ownership(pre_money: float, target_ownership: float) -> PrimaryRound:
    pre = float(pre_money)
    ownership = float(target_ownership)
    if not isfinite(pre) or pre < 0.0:
        raise ValueError("pre-money must be finite and non-negative")
    if not isfinite(ownership) or not 0.0 <= ownership < 1.0:
        raise ValueError("target ownership must be in [0, 1)")
    investment = pre * ownership / (1.0 - ownership)
    post = pre + investment
    return PrimaryRound(pre, investment, post, 0.0 if post == 0.0 else investment / post)


def round_for_investment(pre_money: float, investment: float) -> PrimaryRound:
    pre, invested = float(pre_money), float(investment)
    if not all(isfinite(value) and value >= 0.0 for value in (pre, invested)):
        raise ValueError("pre-money and investment must be finite and non-negative")
    post = pre + invested
    return PrimaryRound(pre, invested, post, 0.0 if post == 0.0 else invested / post)
