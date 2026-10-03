from __future__ import annotations

import math

import numpy as np
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.schemas import CanonicalValuationInputs, SimulationRunRequest
from app.db.base import Base
from app.db.models import Scenario, ScenarioRevision, SimulationSamples, Startup, User, Workspace
from app.services.simulation import execute_synchronously, load_sample_vectors
from app.simulation.distributions import Constant, LogNormal
from app.simulation.monte_carlo import (
    StructuredCashFlowSimulationInput,
    simulate_structured_cash_flows,
)


def _structured_inputs() -> dict[str, object]:
    return {
        "monthly_revenue": [100.0] * 60,
        "monthly_opex": [20.0] * 60,
        "monthly_capex": [10.0] * 60,
        "gross_margin": 0.5,
        "revenue_uncertainty": {"kind": "constant", "value": 1.0},
        "cost_uncertainty": {"kind": "constant", "value": 1.0},
        "margin_uncertainty_pp": 0.0,
        "serial_correlation": 0.65,
        "persistent_weight": 0.6,
        "annual_wacc": 0.2,
        "terminal_growth": 0.03,
        "failure_probability_horizon": 0.0,
    }


def test_structured_schema_rejects_partial_mixed_and_negative_factor_support() -> None:
    valid = _structured_inputs()
    parsed = CanonicalValuationInputs.model_validate(valid)
    assert parsed.monthly_fcff is None
    assert len(parsed.monthly_revenue or ()) == 60

    invalid_cases = (
        {**valid, "monthly_revenue": [100.0] * 59},
        {**valid, "monthly_opex": [-1.0] + [20.0] * 59},
        {**valid, "monthly_fcff": [10.0] * 60},
        {**valid, "terminal_growth": 0.2},
        {**valid, "gross_margin": 1.1},
        {**valid, "monthly_capex": [float("nan")] * 60},
        {
            **valid,
            "revenue_uncertainty": {"kind": "normal", "mean": 1.0, "standard_deviation": 0.2},
        },
    )
    for item in invalid_cases:
        with pytest.raises(ValidationError):
            CanonicalValuationInputs.model_validate(item)


def test_structured_paths_obey_cash_flow_identity_and_absorbing_failure() -> None:
    base = dict(
        base_monthly_revenue=(100.0,) * 60,
        base_monthly_opex=(20.0,) * 60,
        base_monthly_capex=(10.0,) * 60,
        gross_margin=0.5,
        revenue_factor=Constant(1.0),
        cost_factor=Constant(1.0),
        margin_uncertainty_pp=0.0,
        serial_correlation=0.65,
        persistent_weight=0.6,
        scenarios=20,
        seed=471829,
    )
    operating = simulate_structured_cash_flows(StructuredCashFlowSimulationInput(**base))
    np.testing.assert_array_equal(operating.counterfactual_cash_flows, 20.0)
    np.testing.assert_array_equal(operating.realized_cash_flows, 20.0)
    np.testing.assert_array_equal(operating.realized_revenue, 100.0)
    np.testing.assert_array_equal(operating.realized_opex, 20.0)
    assert operating.factor_paths.shape == (20, 60, 3)
    assert operating.realized_cash_flows.flags.writeable is False

    failed = simulate_structured_cash_flows(
        StructuredCashFlowSimulationInput(
            **base, p_failure_horizon=1.0, liquidation_value=7.0
        )
    )
    assert np.all(failed.failure_months == 1)
    np.testing.assert_array_equal(failed.realized_cash_flows[:, 0], 7.0)
    np.testing.assert_array_equal(failed.realized_cash_flows[:, 1:], 0.0)
    np.testing.assert_array_equal(failed.realized_revenue, 0.0)
    np.testing.assert_array_equal(failed.realized_opex, 0.0)
    np.testing.assert_array_equal(failed.counterfactual_revenue, 100.0)
    np.testing.assert_array_equal(failed.counterfactual_opex, 20.0)
    assert failed.counterfactual_revenue.flags.writeable is False


def test_structured_stochastic_paths_are_seed_reproducible() -> None:
    inputs = StructuredCashFlowSimulationInput(
        base_monthly_revenue=(100.0,) * 60,
        base_monthly_opex=(20.0,) * 60,
        base_monthly_capex=(10.0,) * 60,
        gross_margin=0.5,
        revenue_factor=LogNormal(1.0, 0.2),
        cost_factor=LogNormal(1.0, 0.1),
        margin_uncertainty_pp=0.05,
        serial_correlation=0.65,
        persistent_weight=0.6,
        scenarios=1000,
        seed=471829,
        p_failure_horizon=0.2,
    )
    first = simulate_structured_cash_flows(inputs)
    second = simulate_structured_cash_flows(inputs)
    np.testing.assert_array_equal(first.factor_paths, second.factor_paths)
    np.testing.assert_array_equal(first.realized_cash_flows, second.realized_cash_flows)
    np.testing.assert_array_equal(first.failure_months, second.failure_months)
    assert np.all((first.factor_paths[:, :, 2] >= 0) & (first.factor_paths[:, :, 2] <= 1))
    assert np.any(first.factor_paths[:, 0, :] != first.factor_paths[:, -1, :])


def test_service_uses_normalized_terminal_and_persists_economic_drivers() -> None:
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    inputs = _structured_inputs()
    inputs["monthly_revenue"] = [100.0] * 59 + [200.0]
    request = SimulationRunRequest(seed=471829, simulation_count=1000)
    with Session(engine) as db:
        simulation, result = execute_synchronously(
            db,
            workspace_id="00000000-0000-0000-0000-000000000001",
            revision_id="00000000-0000-0000-0000-000000000002",
            canonical_inputs=inputs,
            request=request,
        )
        db.commit()
        snapshot = db.scalar(select(SimulationSamples))
        assert snapshot is not None
        valuations, factors = load_sample_vectors(snapshot, result=result, simulation=simulation)

    monthly_wacc = (1.0 + 0.2) ** (1.0 / 12.0) - 1.0
    monthly_growth = (1.0 + 0.03) ** (1.0 / 12.0) - 1.0
    cash_flows = [20.0] * 59 + [70.0]
    normalized = sum(cash_flows[-12:]) / 12.0
    expected_explicit = sum(
        flow / ((1.0 + 0.2) ** (month / 12.0))
        for month, flow in enumerate(cash_flows, 1)
    )
    expected_terminal = normalized * (1 + monthly_growth) / (monthly_wacc - monthly_growth)
    expected = expected_explicit + expected_terminal / (1.0 + 0.2) ** 5
    assert result.summary["percentiles"]["p50"] == pytest.approx(expected, rel=1e-12)
    assert result.summary["percentiles"]["p50"] != pytest.approx(
        expected_explicit + 70.0 * (1 + monthly_growth)
        / (monthly_wacc - monthly_growth) / (1.0 + 0.2) ** 5
    )
    assert len(valuations) == 1000
    assert math.isclose(float(valuations[0]), expected, rel_tol=1e-12)
    assert set(factors) == {
        "revenue_factor_mean",
        "cost_factor_mean",
        "gross_margin_mean",
        "failure_state",
        "revenue_year5_operating",
        "opex_year5_operating",
        "ebitda_margin_year5_operating",
        "revenue_cagr_operating",
    }
    assert factors["revenue_year5_operating"][0] == 1300.0
    assert factors["opex_year5_operating"][0] == 240.0
    assert factors["gross_margin_mean"][0] == 0.5
    assert factors["ebitda_margin_year5_operating"][0] == pytest.approx((650.0 - 240.0) / 1300.0)
    assert factors["revenue_cagr_operating"][0] == pytest.approx((1300.0 / 1200.0) ** 0.25 - 1)
    assert result.summary["vc_method"]["status"] == "unavailable"
    assert result.schema_version == "1.4.0"
    engine.dispose()


def _run_service(inputs: dict[str, object]) -> tuple[object, dict[str, object]]:
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        simulation, result = execute_synchronously(
            db,
            workspace_id="00000000-0000-0000-0000-000000000001",
            revision_id="00000000-0000-0000-0000-000000000002",
            canonical_inputs=inputs,
            request=SimulationRunRequest(seed=471829, simulation_count=1000),
        )
        db.commit()
        snapshot = db.scalar(select(SimulationSamples))
        assert snapshot is not None
        _, factors = load_sample_vectors(snapshot, result=result, simulation=simulation)
        summary = dict(result.summary)
    engine.dispose()
    return factors, summary


def test_outcome_metrics_describe_the_operating_path_even_after_failure() -> None:
    inputs = {**_structured_inputs(), "failure_probability_horizon": 1.0}
    factors, _ = _run_service(inputs)
    np.testing.assert_array_equal(factors["failure_state"], 1.0)
    # Realized revenue is zero after failure; the operating-path metric keeps the plan so a
    # high-OPEX survivor is never confused with "more OPEX, more valuation".
    np.testing.assert_array_equal(factors["revenue_year5_operating"], 1200.0)
    np.testing.assert_array_equal(factors["opex_year5_operating"], 240.0)


def test_ratio_outcomes_are_omitted_when_revenue_is_not_positive() -> None:
    inputs = {**_structured_inputs(), "monthly_revenue": [0.0] * 60}
    factors, _ = _run_service(inputs)
    assert "ebitda_margin_year5_operating" not in factors
    assert "revenue_cagr_operating" not in factors
    assert "revenue_year5_operating" in factors


def test_summary_persists_uncertainty_and_driver_ranking() -> None:
    inputs = {
        **_structured_inputs(),
        "revenue_uncertainty": {"kind": "lognormal", "mean": 1.0, "coefficient_of_variation": 0.3},
        "cost_uncertainty": {"kind": "lognormal", "mean": 1.0, "coefficient_of_variation": 0.1},
        "margin_uncertainty_pp": 0.03,
        "failure_probability_horizon": 0.2,
    }
    _, summary = _run_service(inputs)
    uncertainty = summary["uncertainty"]
    assert isinstance(uncertainty, dict)
    assert uncertainty["rule_version"] == "uncertainty-v1"
    assert summary["uncertainty_label"] == uncertainty["label"]
    assert uncertainty["label"] in {"LOW", "MODERATE", "HIGH", "VERY HIGH"}
    drivers = summary["drivers"]
    assert isinstance(drivers, dict)
    assert drivers["method"] == "spearman+srrc"
    names = [item["name"] for item in drivers["items"]]
    assert set(names) == {"revenue_factor_mean", "cost_factor_mean", "gross_margin_mean",
                          "failure_state"}
    shares = [item["contribution"] for item in drivers["items"]]
    assert sum(shares) == pytest.approx(1.0)
    assert shares == sorted(shares, reverse=True)


def test_vc_method_is_derived_from_saved_profile_in_same_workspace() -> None:
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    inputs = _structured_inputs()
    profile = {
        "revenue": {"cadence": "annual", "years": [100_000, 200_000, 400_000, 800_000, 1_200_000]},
        "valuation_assumptions": {
            "exitMultiple": 5,
            "vcTargetReturn": 25,
            "investmentHorizonYears": 5,
            "investmentAmount": 500_000,
            "targetOwnership": 10,
        },
    }
    with Session(engine) as db:
        user = User(name="VC Test", email="vc-test@example.com", password_hash="fixture")
        workspace = Workspace(name="VC Workspace")
        db.add_all((user, workspace))
        db.flush()
        startup = Startup(workspace_id=workspace.id, name="VC Co", currency="BRL", profile=profile)
        db.add(startup)
        db.flush()
        scenario = Scenario(
            workspace_id=workspace.id, startup_id=startup.id, name="Base", mode="professional"
        )
        db.add(scenario)
        db.flush()
        revision = ScenarioRevision(
            workspace_id=workspace.id,
            scenario_id=scenario.id,
            revision_no=1,
            canonical_inputs=inputs,
            input_hash="a" * 64,
            created_by=user.id,
        )
        db.add(revision)
        db.flush()
        _, result = execute_synchronously(
            db,
            workspace_id=workspace.id,
            revision_id=revision.id,
            canonical_inputs=inputs,
            request=SimulationRunRequest(seed=471829, simulation_count=1000),
        )
        vc = result.summary["vc_method"]
        assert vc["status"] == "available"
        assert vc["exit_enterprise_value"] == pytest.approx(6_000_000)
        assert vc["present_exit_equity"] == pytest.approx(6_000_000 / 1.25**5)
        assert vc["post_money"] == pytest.approx(vc["present_exit_equity"])
        assert vc["pre_money"] == pytest.approx(vc["post_money"] - 500_000)
        assert vc["target_ownership_meets_return"] is False
    engine.dispose()


def test_structured_simulation_persists_implied_multiples() -> None:
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    inputs = _structured_inputs()
    request = SimulationRunRequest(seed=471829, simulation_count=1000)
    with Session(engine) as db:
        _, result = execute_synchronously(
            db,
            workspace_id="00000000-0000-0000-0000-000000000001",
            revision_id="00000000-0000-0000-0000-000000000002",
            canonical_inputs=inputs,
            request=request,
        )
        db.commit()
        stored = result.summary["implied_multiples"]
        assert stored["status"] == "available"
        assert stored["basis"] == "equity_dcf_over_year5_metric"
        assert stored["value_to_revenue"]["eligible_count"] >= 1
        assert result.schema_version == "1.4.0"
    engine.dispose()


def test_fcff_simulation_marks_multiples_unavailable() -> None:
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    inputs = {
        "monthly_fcff": [100_000.0] * 12,
        "annual_wacc": 0.2,
        "terminal_growth": 0.03,
        "uncertainty": {"kind": "lognormal", "mean": 1.0, "coefficient_of_variation": 0.2},
        "failure_probability_horizon": 0.1,
    }
    request = SimulationRunRequest(seed=471829, simulation_count=1000)
    with Session(engine) as db:
        _, result = execute_synchronously(
            db,
            workspace_id="00000000-0000-0000-0000-000000000001",
            revision_id="00000000-0000-0000-0000-000000000002",
            canonical_inputs=inputs,
            request=request,
        )
        db.commit()
        stored = result.summary["implied_multiples"]
        assert stored["status"] == "not_available"
        assert stored["reason"] == "metrics_unavailable_for_input_mode"
    engine.dispose()
