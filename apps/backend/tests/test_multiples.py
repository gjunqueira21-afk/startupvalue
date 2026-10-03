import numpy as np
import pytest

from app.decision.multiples import (
    MIN_ELIGIBLE_SCENARIOS,
    compute_implied_multiples,
    implied_multiples_payload,
)


def test_small_sample_below_minimum_yields_none():
    valuations = np.array([120.0, 300.0, 80.0, 240.0])
    revenue = np.array([10.0, 20.0, 16.0, 12.0])
    # multiples: [12, 15, 5, 20] -> sorted [5, 12, 15, 20]
    assert valuations.size < MIN_ELIGIBLE_SCENARIOS
    result = compute_implied_multiples(valuations, revenue, None)
    summary = result.value_to_revenue
    assert summary is None  # only 4 eligible < MIN_ELIGIBLE_SCENARIOS


def test_golden_quantiles_with_sufficient_sample():
    base_val = np.array([120.0, 300.0, 80.0, 240.0])
    base_rev = np.array([10.0, 20.0, 16.0, 12.0])
    valuations = np.tile(base_val, 10)   # 40 scenarios, same multiple set
    revenue = np.tile(base_rev, 10)
    result = compute_implied_multiples(valuations, revenue, None)
    summary = result.value_to_revenue
    assert summary is not None
    assert summary.eligible_count == 40
    assert summary.excluded_count == 0
    # np.quantile(..., method="linear") over 10x-tiled [5,12,15,20]
    expected_p25, expected_p50, expected_p75 = np.quantile(
        np.tile(np.array([12.0, 15.0, 5.0, 20.0]), 10), (0.25, 0.50, 0.75)
    )
    assert summary.p25 == pytest.approx(expected_p25)
    assert summary.p50 == pytest.approx(expected_p50)
    assert summary.p75 == pytest.approx(expected_p75)
    assert result.status == "available"
    assert result.value_to_ebitda is None


def test_non_positive_metric_and_valuation_are_excluded_and_counted():
    valuations = np.concatenate([np.full(40, 100.0), [-50.0, 100.0]])
    revenue = np.concatenate([np.full(40, 10.0), [10.0, 0.0]])
    result = compute_implied_multiples(valuations, revenue, None)
    summary = result.value_to_revenue
    assert summary is not None
    assert summary.eligible_count == 40
    assert summary.excluded_count == 2
    assert summary.p50 == pytest.approx(10.0)


def test_all_non_positive_equity_returns_not_available_without_crash():
    valuations = np.full(100, -1.0)
    revenue = np.full(100, 10.0)
    result = compute_implied_multiples(valuations, revenue, np.full(100, 5.0))
    assert result.status == "not_available"
    assert result.value_to_revenue is None
    assert result.value_to_ebitda is None
    assert result.reason == "insufficient_eligible_scenarios"


def test_missing_metric_arrays_mean_input_mode_without_metrics():
    result = compute_implied_multiples(np.full(100, 10.0), None, None)
    assert result.status == "not_available"
    assert result.reason == "metrics_unavailable_for_input_mode"


def test_shape_mismatch_raises():
    with pytest.raises(ValueError):
        compute_implied_multiples(np.full(40, 10.0), np.full(39, 1.0), None)


def test_payload_round_trip_shape():
    valuations = np.full(40, 100.0)
    payload = implied_multiples_payload(
        compute_implied_multiples(valuations, np.full(40, 10.0), np.full(40, 20.0))
    )
    assert payload["status"] == "available"
    assert payload["basis"] == "equity_dcf_over_year5_metric"
    assert payload["value_to_revenue"]["p50"] == pytest.approx(10.0)
    assert payload["value_to_ebitda"]["p50"] == pytest.approx(5.0)
    assert payload["value_to_revenue"]["eligible_count"] == 40
