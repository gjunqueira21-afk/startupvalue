from __future__ import annotations

from app.decision.catalog import describe, split_by_role


def test_primitive_drivers_and_outcome_metrics_have_distinct_roles() -> None:
    for name in ("revenue_factor_mean", "cost_factor_mean", "gross_margin_mean", "failure_state"):
        assert describe(name).role == "driver"
    for name in (
        "revenue_year5_operating",
        "opex_year5_operating",
        "ebitda_margin_year5_operating",
        "revenue_cagr_operating",
    ):
        assert describe(name).role == "outcome"


def test_labels_are_business_language_with_units() -> None:
    revenue = describe("revenue_year5_operating")
    assert revenue.label == "Receita do Ano 5"
    assert revenue.unit == "currency"
    assert describe("ebitda_margin_year5_operating").unit == "ratio"
    assert describe("revenue_factor_mean").unit == "multiplier"
    assert describe("failure_state").unit == "binary"


def test_snapshots_written_before_v1_2_remain_readable() -> None:
    # Realized year-5 revenue/OPEX are zero after failure, so they are outcomes, never drivers.
    assert describe("revenue_year5").role == "outcome"
    assert describe("opex_year5").role == "outcome"
    assert describe("modeled_gross_margin_year5").role == "driver"
    assert describe("scenario_factor_mean").role == "driver"


def test_unknown_names_fall_back_to_outcome_with_readable_label() -> None:
    spec = describe("some_new_metric")
    assert spec.role == "outcome"
    assert spec.label == "some new metric"
    assert spec.unit is None


def test_split_by_role_preserves_order() -> None:
    drivers, outcomes = split_by_role(
        {"revenue_year5_operating": [1], "failure_state": [0], "revenue_factor_mean": [1]}
    )
    assert list(drivers) == ["failure_state", "revenue_factor_mean"]
    assert list(outcomes) == ["revenue_year5_operating"]
