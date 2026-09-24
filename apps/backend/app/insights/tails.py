"""Upside and downside drivers: how the best and worst scenarios differ from all.

Groups are the scenarios at or above P90 (upside) and at or below P10
(downside) of valuation. Ties at a percentile stay in the group and the real
group size is reported. A driver is listed only when its shift is material:
the group median moves at least ``MIN_STANDARDIZED_SHIFT`` interquartile ranges,
or a 0/1 rate moves at least ``MIN_RATE_SHIFT``. Descriptive, not causal.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

MIN_STANDARDIZED_SHIFT = 0.25
MIN_RATE_SHIFT = 0.05


@dataclass(frozen=True, slots=True)
class TailShift:
    name: str
    tail: Literal["upside", "downside"]
    kind: Literal["continuous", "binary"]
    direction: Literal["higher", "lower"]
    group_value: float
    overall_value: float
    effect: float
    group_size: int
    group_share: float


def _is_binary(values: np.ndarray) -> bool:
    return bool(np.all((values == 0.0) | (values == 1.0)))


def _shift(
    name: str,
    tail: Literal["upside", "downside"],
    values: np.ndarray,
    mask: np.ndarray,
) -> TailShift | None:
    group = values[mask]
    size = int(group.size)
    share = size / values.size
    if _is_binary(values):
        group_value, overall = float(np.mean(group)), float(np.mean(values))
        effect = group_value - overall
        if abs(effect) < MIN_RATE_SHIFT:
            return None
        kind: Literal["continuous", "binary"] = "binary"
    else:
        p25, overall, p75 = (float(q) for q in np.quantile(values, (0.25, 0.5, 0.75)))
        if p75 <= p25:
            return None
        group_value = float(np.median(group))
        effect = (group_value - overall) / (p75 - p25)
        if abs(effect) < MIN_STANDARDIZED_SHIFT:
            return None
        kind = "continuous"
    direction: Literal["higher", "lower"] = "higher" if effect > 0 else "lower"
    return TailShift(name, tail, kind, direction, group_value, overall, effect, size, share)


def tail_shifts(
    drivers: Mapping[str, np.ndarray],
    valuations: np.ndarray,
    *,
    order: Sequence[str],
    limit: int = 3,
) -> tuple[list[TailShift], list[TailShift]]:
    values = np.asarray(valuations, dtype=np.float64)
    if np.all(values == values[0]):
        return [], []
    p10, p90 = np.quantile(values, (0.1, 0.9))
    tails: dict[Literal["upside", "downside"], np.ndarray] = {
        "upside": values >= p90,
        "downside": values <= p10,
    }
    result: dict[str, list[TailShift]] = {"upside": [], "downside": []}
    for tail, mask in tails.items():
        if mask.all():
            continue
        for name in order:
            if len(result[tail]) >= limit:
                break
            shift = _shift(name, tail, np.asarray(drivers[name], dtype=np.float64), mask)
            if shift is not None:
                result[tail].append(shift)
    return result["upside"], result["downside"]
