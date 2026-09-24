"""What needs to be true: how scenarios that reach a target differ from the rest.

Effect size is Cliff's delta, P(X_hit > X_miss) - P(X_hit < X_miss), computed
from average ranks (ties count half). It is unit-free, robust to skew and
comparable across variables. For a material effect (|delta| >= ``MIN_EFFECT``)
we publish a threshold: the lower quartile of the hit group when higher values
favour the target, the upper quartile when lower values do. Three quarters of
the successful scenarios lie beyond it; the hit rate beyond it is compared with
the base rate. All statements describe association inside the simulation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.stats import rankdata  # type: ignore[import-untyped]

MIN_EFFECT = 0.33
MIN_GROUP_FOR_THRESHOLD = 10
MIN_GROUP_FOR_CONFIDENCE = 30

SampleNote = Literal["ok", "small_group", "insufficient", "empty_group"]


@dataclass(frozen=True, slots=True)
class Condition:
    name: str
    kind: Literal["continuous", "binary"]
    direction: Literal["higher", "lower"]
    hit_value: float
    miss_value: float
    cliffs_delta: float
    threshold: float | None
    threshold_coverage: float | None
    hit_rate_beyond_threshold: float | None
    beyond_count: int | None


@dataclass(frozen=True, slots=True)
class TargetConditions:
    target: float
    hit_count: int
    miss_count: int
    base_rate: float
    sample_note: SampleNote
    conditions: tuple[Condition, ...]


def cliffs_delta(hit: np.ndarray, miss: np.ndarray) -> float:
    n_hit, n_miss = hit.size, miss.size
    ranks = rankdata(np.concatenate((hit, miss)), method="average")
    u_statistic = float(np.sum(ranks[:n_hit])) - n_hit * (n_hit + 1) / 2.0
    return 2.0 * u_statistic / (n_hit * n_miss) - 1.0


def _condition(
    name: str, values: np.ndarray, hit_mask: np.ndarray, allow_threshold: bool
) -> Condition:
    hit, miss = values[hit_mask], values[~hit_mask]
    delta = cliffs_delta(hit, miss)
    direction: Literal["higher", "lower"] = "higher" if delta >= 0 else "lower"
    if np.all((values == 0.0) | (values == 1.0)):
        return Condition(
            name, "binary", direction, float(np.mean(hit)), float(np.mean(miss)), delta,
            None, None, None, None,
        )
    threshold = coverage = hit_rate = None
    beyond_count = None
    if allow_threshold and abs(delta) >= MIN_EFFECT:
        threshold = float(np.quantile(hit, 0.25 if direction == "higher" else 0.75))
        beyond = values >= threshold if direction == "higher" else values <= threshold
        beyond_count = int(np.sum(beyond))
        coverage = float(np.mean(beyond[hit_mask]))
        hit_rate = float(np.mean(hit_mask[beyond]))
    return Condition(
        name, "continuous", direction, float(np.median(hit)), float(np.median(miss)), delta,
        threshold, coverage, hit_rate, beyond_count,
    )


def target_conditions(
    variables: Mapping[str, np.ndarray], valuations: np.ndarray, target: float
) -> TargetConditions:
    values = np.asarray(valuations, dtype=np.float64)
    hit_mask = values >= target
    hits = int(np.sum(hit_mask))
    misses = int(values.size - hits)
    base_rate = hits / values.size
    if hits == 0 or misses == 0:
        return TargetConditions(target, hits, misses, base_rate, "empty_group", ())
    smallest = min(hits, misses)
    note: SampleNote = (
        "insufficient"
        if smallest < MIN_GROUP_FOR_THRESHOLD
        else "small_group"
        if smallest < MIN_GROUP_FOR_CONFIDENCE
        else "ok"
    )
    conditions = [
        _condition(name, vector, hit_mask, note != "insufficient")
        for name, raw in variables.items()
        if not np.all((vector := np.asarray(raw, dtype=np.float64)) == vector[0])
    ]
    conditions.sort(key=lambda item: (-abs(item.cliffs_delta), item.name))
    return TargetConditions(target, hits, misses, base_rate, note, tuple(conditions))
