from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.schemas import SimulationRunRequest
from app.db.base import Base
from app.services.simulation import execute_synchronously
from app.simulation.distributions import Triangular, inverse_cdf
from app.valuation.dcf import accumulated_discount_factors


def _inputs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "monthly_revenue": [100_000.0 + 4_000.0 * month for month in range(60)],
        "monthly_opex": [40_000.0] * 60,
        "monthly_capex": [2_000.0] * 60,
        "gross_margin": 0.7,
        "revenue_uncertainty": {"kind": "lognormal", "mean": 1.0, "coefficient_of_variation": 0.25},
        "cost_uncertainty": {"kind": "lognormal", "mean": 1.0, "coefficient_of_variation": 0.1},
        "margin_uncertainty_pp": 0.03,
        "serial_correlation": 0.5,
        "persistent_weight": 0.6,
        "annual_wacc": 0.25,
        "terminal_growth": 0.04,
        "failure_probability_horizon": 0.2,
    }
    return {**base, **overrides}


def _summary(inputs: dict[str, Any], seed: int = 99) -> dict[str, Any]:
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _, result = execute_synchronously(
            db,
            workspace_id="00000000-0000-0000-0000-000000000001",
            revision_id="00000000-0000-0000-0000-000000000002",
            canonical_inputs=inputs,
            request=SimulationRunRequest(seed=seed, simulation_count=1000),
        )
        summary = dict(result.summary)
    engine.dispose()
    return summary


def _items(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["parameter"]: item for item in summary["sensitivity"]["items"]}


def test_fixed_assumptions_are_swung_by_published_deltas_on_common_random_numbers() -> None:
    summary = _summary(_inputs())
    sensitivity = summary["sensitivity"]
    assert sensitivity["method"] == "one_at_a_time_common_random_numbers"
    assert sensitivity["method_version"] == "tornado-v1"
    assert sensitivity["statistic"] == "p50"
    base = summary["percentiles"]["p50"]
    assert sensitivity["base_value"] == base
    items = _items(summary)
    assert set(items) == {"annual_wacc", "terminal_growth", "failure_probability"}

    wacc = items["annual_wacc"]
    assert (wacc["low_level"], wacc["high_level"]) == pytest.approx((0.22, 0.28))
    assert wacc["level_source"] == "base_plus_minus_delta"
    assert wacc["value_at_low"] > base > wacc["value_at_high"]
    growth = items["terminal_growth"]
    assert (growth["low_level"], growth["high_level"]) == pytest.approx((0.03, 0.05))
    assert growth["value_at_low"] < base < growth["value_at_high"]
    failure = items["failure_probability"]
    assert (failure["low_level"], failure["high_level"]) == pytest.approx((0.1, 0.3))
    assert failure["value_at_low"] > failure["value_at_high"]

    swings = [item["swing"] for item in sensitivity["items"]]
    assert swings == sorted(swings, reverse=True)
    for item in sensitivity["items"]:
        assert item["swing"] == pytest.approx(abs(item["value_at_high"] - item["value_at_low"]))


def test_ranges_become_drivers_and_swing_between_their_p10_and_p90() -> None:
    wacc_range = {"kind": "triangular", "minimum": 0.18, "mode": 0.25, "maximum": 0.35}
    summary = _summary(_inputs(wacc_uncertainty=wacc_range))
    wacc = _items(summary)["annual_wacc"]
    p10, p90 = inverse_cdf(Triangular(0.18, 0.25, 0.35), np.array([0.1, 0.9]))
    assert wacc["level_source"] == "distribution_p10_p90"
    assert (wacc["low_level"], wacc["high_level"]) == pytest.approx((p10, p90))
    drivers = {item["name"]: item for item in summary["drivers"]["items"]}
    assert drivers["annual_wacc"]["direction"] == "negative"
    assert drivers["annual_wacc"]["contribution"] > 0


def test_fixed_inputs_without_ranges_keep_their_previous_valuations() -> None:
    first = _summary(_inputs())
    ranged = _summary(
        _inputs(wacc_uncertainty={"kind": "constant", "value": 0.25}), seed=99
    )
    assert ranged["percentiles"] == first["percentiles"]


def test_exit_multiple_terminal_value_on_revenue_and_ebitda() -> None:
    flat = _inputs(
        monthly_revenue=[100_000.0] * 60,
        revenue_uncertainty={"kind": "constant", "value": 1.0},
        cost_uncertainty={"kind": "constant", "value": 1.0},
        margin_uncertainty_pp=0.0,
        failure_probability_horizon=0.0,
        terminal_growth=None,
        terminal_method="exit_multiple",
        exit_multiple=5.0,
    )
    factors = accumulated_discount_factors(0.25, 60)
    monthly_fcff = 100_000.0 * 0.7 - 40_000.0 - 2_000.0
    explicit = float(np.sum(monthly_fcff / factors))
    revenue = _summary({**flat, "exit_metric": "revenue"})
    assert revenue["percentiles"]["p50"] == pytest.approx(
        explicit + 5.0 * 1_200_000.0 / factors[-1], rel=1e-12
    )
    ebitda = _summary({**flat, "exit_metric": "ebitda"})
    assert ebitda["percentiles"]["p50"] == pytest.approx(
        explicit + 5.0 * (70_000.0 - 40_000.0) * 12 / factors[-1], rel=1e-12
    )
    items = _items(ebitda)
    assert "terminal_growth" not in items
    multiple = items["exit_multiple"]
    assert (multiple["low_level"], multiple["high_level"]) == pytest.approx((3.75, 6.25))


def test_levels_are_clamped_so_growth_stays_below_wacc() -> None:
    items = _items(_summary(_inputs(annual_wacc=0.10, terminal_growth=0.095)))
    growth = items["terminal_growth"]
    wacc = items["annual_wacc"]
    assert growth["clamped"] is True
    assert growth["high_level"] < 0.10
    assert wacc["clamped"] is True
    assert wacc["low_level"] > 0.095
