# QuantoVale V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship QuantoVale V2: implied-multiple and target-plan metrics derived from existing Monte Carlo scenarios, white-label PDF reports for professional plans, published 4-tier pricing with a waitlist, a redesigned landing with a 7-second choreographed 3D intro, and a Hostinger deploy runbook.

**Architecture:** All new financial metrics are pure derived reads of already-persisted scenario vectors or simulation-time arrays — the audited valuation engine (`app/valuation`, `app/simulation`) is untouched. Entitlements are resolved server-side from a `plan` enum on `Workspace`; every limit is enforced in FastAPI routes, never only in the UI. The PDF renderer gains an optional branding object; the landing reuses the existing three.js scene with a re-timed three-act intro.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + numpy + reportlab (backend, Python 3.12, pytest); Next.js 16 + React 19 + react-three-fiber + vitest (frontend, Node 24); Playwright for landing e2e; Docker Compose + Caddy (deploy).

**Spec:** `docs/superpowers/specs/2026-10-02-quantovale-v2-design.md`

## Global Constraints

- No formula in `app/valuation`, `app/simulation`, `app/services/valuation_model.py` changes; no existing test's expected value changes (spec acceptance #6).
- All plan limits enforced in the backend (spec §4.2, principle P14); a forged request must never bypass a limit.
- `RESULT_SCHEMA_VERSION` bumps `"1.3.0"` → `"1.4.0"` exactly once (Task 2). `REPORT_TEMPLATE_VERSION` bumps `"1.2.0"` → `"1.3.0"` exactly once (Task 5).
- Methodological disclaimers appear in every PDF variant, branded or not (spec §3.2).
- New UI copy is pt-BR; money formatting follows existing helpers (`lib/format.ts`, `_number` in `from_result.py`).
- Implied multiples are labeled "implícito nas suas premissas — não é múltiplo de mercado" wherever rendered (spec §2.1).
- Plan names/prices everywhere: Grátis R$ 0 · Empresário R$ 97/mês · Consultor R$ 297/mês · Escritório R$ 697/mês; anual ~20% off (R$ 932 / R$ 2.851 / R$ 6.691). Landing says cobrança ainda não está ativa (waitlist only).
- Backend commands run from `apps/backend` with the project venv: `python -m pytest tests/<file> -v`. Frontend: `npm --workspace apps/frontend run test` / `run lint` from repo root.
- Alembic migrations in this plan chain: `d9673a8e2b10` → `c4a1e5b9d201` (Task 6) → `e7f2a9c3b115` (Task 8) → `f3d8b6a1c922` (Task 10). Keep that order.
- Design clarifications agreed vs. spec wording: (a) implied multiples divide the DCF equity valuation (present value) by the realized year-5 annual metric — labeled exactly that way — because per-scenario EV_exit only exists under the exit-multiple terminal and would merely echo the input; (b) SVG logos are rejected (PNG/JPEG only), which satisfies the spec's "sanitizado ou rejeitado"; (c) logo bytes live in the database (private, backed up, ≤ 1 MB), not on the filesystem; (d) "clientes" of the Consultor plan are enforced as startup slots (10) in this phase — multi-workspace switching stays roadmap, and landing copy says "até 10 empresas-clientes".

## Review Focus

1. Waitlist dedupe must be case/whitespace-insensitive (`User@X.com ` == `user@x.com`), else the unique constraint 500s — pinned in Task 10 tests.
2. A branded PDF whose stored logo bytes are corrupt must still render (skip the logo), never 500 — pinned in Task 9 tests.
3. Simulation at exactly the plan limit (10.000 for Empresário) must run; 10.001 must be rejected with 403 — boundary pinned in Task 7 tests.
4. Target plan with no usable base revenue (FCFF-only inputs) must return an empty trajectory, never NaN/division error — pinned in Task 3 tests.
5. Implied multiples when every scenario has non-positive equity must come back `not_available`-style (insufficient eligible), never crash or publish a junk multiple — pinned in Task 1 tests.

---

## Phase A — Derived metrics (backend)

### Task 1: Implied multiples module

**Files:**
- Create: `apps/backend/app/decision/multiples.py`
- Modify: `apps/backend/app/decision/__init__.py`
- Test: `apps/backend/tests/test_multiples.py`

**Interfaces:**
- Consumes: nothing new (numpy only).
- Produces: `compute_implied_multiples(valuations: np.ndarray, revenue_exit_year: np.ndarray | None, ebitda_exit_year: np.ndarray | None) -> ImpliedMultiples`; `implied_multiples_payload(result: ImpliedMultiples) -> dict[str, object]`; dataclasses `ImpliedMultiples(status, reason, value_to_revenue, value_to_ebitda)` and `MultipleSummary(p25, p50, p75, eligible_count, excluded_count)`; constant `MIN_ELIGIBLE_SCENARIOS = 30`. Task 2 and Task 5 consume these exact names.

- [ ] **Step 1: Write the failing tests**

```python
# apps/backend/tests/test_multiples.py
import numpy as np
import pytest

from app.decision.multiples import (
    MIN_ELIGIBLE_SCENARIOS,
    compute_implied_multiples,
    implied_multiples_payload,
)


def test_golden_quantiles_linear_interpolation():
    valuations = np.array([120.0, 300.0, 80.0, 240.0])
    revenue = np.array([10.0, 20.0, 16.0, 12.0])
    # multiples: [12, 15, 5, 20] -> sorted [5, 12, 15, 20]
    result = compute_implied_multiples(valuations * 0 + valuations, revenue, None)
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_multiples.py -v` (from `apps/backend`)
Expected: FAIL with `ModuleNotFoundError: No module named 'app.decision.multiples'`

- [ ] **Step 3: Implement the module**

```python
# apps/backend/app/decision/multiples.py
"""Implied valuation multiples derived from simulated scenarios.

These are presentation-layer reads: valuation (DCF equity, present value)
divided by the realized year-5 annual metric of the same scenario.  They are
implied by the user's own assumptions and are NOT market multiples.  No engine
formula is involved.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

MIN_ELIGIBLE_SCENARIOS = 30


@dataclass(frozen=True, slots=True)
class MultipleSummary:
    p25: float
    p50: float
    p75: float
    eligible_count: int
    excluded_count: int


@dataclass(frozen=True, slots=True)
class ImpliedMultiples:
    status: str  # "available" | "not_available"
    reason: str | None
    value_to_revenue: MultipleSummary | None
    value_to_ebitda: MultipleSummary | None


def _summary(valuations: np.ndarray, metric: np.ndarray) -> MultipleSummary | None:
    if metric.shape != valuations.shape:
        raise ValueError("metric vector must align with valuations")
    if not np.all(np.isfinite(metric)):
        raise ValueError("metric vector must be finite")
    eligible = (metric > 0.0) & (valuations > 0.0)
    count = int(np.sum(eligible))
    if count < MIN_ELIGIBLE_SCENARIOS:
        return None
    multiples = valuations[eligible] / metric[eligible]
    p25, p50, p75 = np.quantile(multiples, (0.25, 0.50, 0.75), method="linear")
    return MultipleSummary(
        float(p25), float(p50), float(p75), count, int(valuations.size - count)
    )


def compute_implied_multiples(
    valuations: np.ndarray,
    revenue_exit_year: np.ndarray | None,
    ebitda_exit_year: np.ndarray | None,
) -> ImpliedMultiples:
    values = np.asarray(valuations, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("valuations must be a non-empty finite one-dimensional array")
    if revenue_exit_year is None and ebitda_exit_year is None:
        return ImpliedMultiples(
            "not_available", "metrics_unavailable_for_input_mode", None, None
        )
    revenue = (
        _summary(values, np.asarray(revenue_exit_year, dtype=np.float64))
        if revenue_exit_year is not None
        else None
    )
    ebitda = (
        _summary(values, np.asarray(ebitda_exit_year, dtype=np.float64))
        if ebitda_exit_year is not None
        else None
    )
    if revenue is None and ebitda is None:
        return ImpliedMultiples(
            "not_available", "insufficient_eligible_scenarios", None, None
        )
    return ImpliedMultiples("available", None, revenue, ebitda)


def _summary_payload(summary: MultipleSummary | None) -> dict[str, object] | None:
    if summary is None:
        return None
    return {
        "p25": summary.p25,
        "p50": summary.p50,
        "p75": summary.p75,
        "eligible_count": summary.eligible_count,
        "excluded_count": summary.excluded_count,
    }


def implied_multiples_payload(result: ImpliedMultiples) -> dict[str, object]:
    return {
        "status": result.status,
        "reason": result.reason,
        "basis": "equity_dcf_over_year5_metric",
        "value_to_revenue": _summary_payload(result.value_to_revenue),
        "value_to_ebitda": _summary_payload(result.value_to_ebitda),
    }
```

Also append to `apps/backend/app/decision/__init__.py` exports:
`from .multiples import ImpliedMultiples, MultipleSummary, compute_implied_multiples, implied_multiples_payload` and extend `__all__` accordingly, matching the file's existing style.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_multiples.py -v`
Expected: all PASS

- [ ] **Step 5: Run the full backend suite (no regressions)**

Run: `python -m pytest -q`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/decision/multiples.py apps/backend/app/decision/__init__.py apps/backend/tests/test_multiples.py
git commit -m "feat(decision): implied value/revenue and value/EBITDA multiples from scenarios"
```

### Task 2: Persist implied multiples in the simulation summary

**Files:**
- Modify: `apps/backend/app/services/simulation.py` (constant at line ~37, summary assembly inside `execute_synchronously` after the `summary["vc_method"] = ...` line)
- Modify: `apps/backend/app/api/schemas.py` (the `SimulationSummary` model)
- Test: `apps/backend/tests/test_simulation.py` (append tests)

**Interfaces:**
- Consumes: `compute_implied_multiples`, `implied_multiples_payload` (Task 1); `paths.revenue_year5` / `paths.ebitda_year5` from `ScenarioPaths` (already exist).
- Produces: `result.summary["implied_multiples"]` dict with keys `status`, `reason`, `basis`, `value_to_revenue`, `value_to_ebitda` — consumed by Tasks 5, 7, 11. `RESULT_SCHEMA_VERSION == "1.4.0"`.

- [ ] **Step 1: Write the failing tests** — append to `apps/backend/tests/test_simulation.py`, reusing that file's existing fixtures/helpers for running a structured simulation and an FCFF-mode simulation (read the file first; follow its canonical-input builders exactly):

```python
def test_structured_simulation_persists_implied_multiples(...existing fixture args...):
    # run a structured-mode simulation exactly as the file's existing tests do
    stored = result.summary["implied_multiples"]
    assert stored["status"] == "available"
    assert stored["basis"] == "equity_dcf_over_year5_metric"
    assert stored["value_to_revenue"]["eligible_count"] >= 1
    assert result.schema_version == "1.4.0"


def test_fcff_simulation_marks_multiples_unavailable(...):
    # run an FCFF (monthly_fcff) simulation as existing tests do
    stored = result.summary["implied_multiples"]
    assert stored["status"] == "not_available"
    assert stored["reason"] == "metrics_unavailable_for_input_mode"
```

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/test_simulation.py -v -k implied` → FAIL (KeyError `implied_multiples`).

- [ ] **Step 3: Implement.** In `apps/backend/app/services/simulation.py`:
  - add import `from app.decision.multiples import compute_implied_multiples, implied_multiples_payload`;
  - change `RESULT_SCHEMA_VERSION = "1.3.0"` to `"1.4.0"`;
  - in `execute_synchronously`, directly after the `summary["vc_method"] = _vc_profile_summary(...)` statement, add:

```python
    summary["implied_multiples"] = implied_multiples_payload(
        compute_implied_multiples(equity_values, paths.revenue_year5, paths.ebitda_year5)
    )
```

  - In `apps/backend/app/api/schemas.py`, add to `SimulationSummary` an optional passthrough field, following that model's existing style (read the model first): `implied_multiples: dict[str, Any] | None = None` (use the file's existing `Any` import conventions; if the model forbids extras this field is what permits the new key).

- [ ] **Step 4: Run** `python -m pytest tests/test_simulation.py -v` → PASS.

- [ ] **Step 5: Full suite** `python -m pytest -q` → PASS. If any test asserts `schema_version == "1.3.0"` or snapshot-compares the summary keys, update ONLY those version/key-list assertions (they assert the contract, and the contract legitimately moved to 1.4.0) — never a monetary expected value.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/services/simulation.py apps/backend/app/api/schemas.py apps/backend/tests/test_simulation.py
git commit -m "feat(simulation): persist implied multiples in result summary (schema 1.4.0)"
```

### Task 3: Target plan module ("Plano para a meta")

**Files:**
- Create: `apps/backend/app/decision/target_plan.py`
- Modify: `apps/backend/app/decision/__init__.py`
- Test: `apps/backend/tests/test_target_plan.py`

**Interfaces:**
- Consumes: factor vectors as loaded by `load_sample_vectors` — relevant factor names are `"revenue_cagr_operating"` and `"ebitda_margin_year5_operating"` (produced conditionally by `_operating_outcomes` in `valuation_model.py`).
- Produces: `build_target_plan(valuations: np.ndarray, target: float, factors: Mapping[str, np.ndarray], base_year_revenue: float | None, horizon_years: int = 5) -> TargetPlan`; dataclasses `TargetPlan(status, hit_count, required_revenue_cagr, hit_ebitda_margin, miss_revenue_cagr, miss_ebitda_margin, trajectory)` and `YearTarget(year, revenue)`; constant `MIN_HIT_SAMPLE = 50`. Status values: `"available" | "insufficient_hits" | "not_available_for_inputs"`. Consumed by Tasks 4 and 5.

- [ ] **Step 1: Write the failing tests**

```python
# apps/backend/tests/test_target_plan.py
import numpy as np
import pytest

from app.decision.target_plan import MIN_HIT_SAMPLE, build_target_plan


def _factors(n_hit: int, n_miss: int) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    valuations = np.concatenate([np.full(n_hit, 200.0), np.full(n_miss, 50.0)])
    factors = {
        "revenue_cagr_operating": np.concatenate(
            [np.full(n_hit, 0.30), np.full(n_miss, 0.10)]
        ),
        "ebitda_margin_year5_operating": np.concatenate(
            [np.full(n_hit, 0.25), np.full(n_miss, 0.12)]
        ),
    }
    return valuations, factors


def test_available_plan_reports_hit_medians_and_trajectory():
    valuations, factors = _factors(60, 40)
    plan = build_target_plan(valuations, 100.0, factors, base_year_revenue=1_000_000.0)
    assert plan.status == "available"
    assert plan.hit_count == 60
    assert plan.required_revenue_cagr == pytest.approx(0.30)
    assert plan.hit_ebitda_margin == pytest.approx(0.25)
    assert plan.miss_revenue_cagr == pytest.approx(0.10)
    assert plan.miss_ebitda_margin == pytest.approx(0.12)
    assert [point.year for point in plan.trajectory] == [1, 2, 3, 4, 5]
    assert plan.trajectory[0].revenue == pytest.approx(1_000_000.0)
    assert plan.trajectory[4].revenue == pytest.approx(1_000_000.0 * 1.30**4)


def test_insufficient_hits_below_threshold():
    valuations, factors = _factors(MIN_HIT_SAMPLE - 1, 100)
    plan = build_target_plan(valuations, 100.0, factors, base_year_revenue=1_000_000.0)
    assert plan.status == "insufficient_hits"
    assert plan.required_revenue_cagr is None
    assert plan.trajectory == ()


def test_missing_cagr_factor_means_not_available_for_inputs():
    valuations = np.full(200, 200.0)
    plan = build_target_plan(valuations, 100.0, {}, base_year_revenue=1_000_000.0)
    assert plan.status == "not_available_for_inputs"


def test_no_base_revenue_yields_empty_trajectory_without_nan():
    valuations, factors = _factors(60, 40)
    plan = build_target_plan(valuations, 100.0, factors, base_year_revenue=None)
    assert plan.status == "available"
    assert plan.trajectory == ()
    assert plan.required_revenue_cagr == pytest.approx(0.30)


def test_margin_factor_optional():
    valuations, factors = _factors(60, 40)
    del factors["ebitda_margin_year5_operating"]
    plan = build_target_plan(valuations, 100.0, factors, base_year_revenue=1.0)
    assert plan.status == "available"
    assert plan.hit_ebitda_margin is None
```

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/test_target_plan.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# apps/backend/app/decision/target_plan.py
"""Reverse engineering of a valuation target from already-simulated scenarios.

Answers "what has to happen for the company to be worth X at the horizon":
the median revenue CAGR and year-5 EBITDA margin among scenarios that reach
the target, contrasted with scenarios that miss it, plus a reference
revenue trajectory built from that CAGR.  Associations, not causes; derived
reads, no re-simulation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite

import numpy as np

MIN_HIT_SAMPLE = 50

CAGR_FACTOR = "revenue_cagr_operating"
MARGIN_FACTOR = "ebitda_margin_year5_operating"


@dataclass(frozen=True, slots=True)
class YearTarget:
    year: int
    revenue: float


@dataclass(frozen=True, slots=True)
class TargetPlan:
    status: str  # "available" | "insufficient_hits" | "not_available_for_inputs"
    hit_count: int
    required_revenue_cagr: float | None
    hit_ebitda_margin: float | None
    miss_revenue_cagr: float | None
    miss_ebitda_margin: float | None
    trajectory: tuple[YearTarget, ...]


def _median(values: np.ndarray) -> float | None:
    return float(np.median(values)) if values.size else None


def build_target_plan(
    valuations: np.ndarray,
    target: float,
    factors: Mapping[str, np.ndarray],
    base_year_revenue: float | None,
    horizon_years: int = 5,
) -> TargetPlan:
    values = np.asarray(valuations, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("valuations must be a non-empty finite one-dimensional array")
    if not isfinite(float(target)):
        raise ValueError("target must be finite")
    hit_mask = values >= float(target)
    hit_count = int(np.sum(hit_mask))
    if CAGR_FACTOR not in factors:
        return TargetPlan("not_available_for_inputs", hit_count, None, None, None, None, ())
    if hit_count < MIN_HIT_SAMPLE:
        return TargetPlan("insufficient_hits", hit_count, None, None, None, None, ())
    cagr = np.asarray(factors[CAGR_FACTOR], dtype=np.float64)
    if cagr.shape != values.shape or not np.all(np.isfinite(cagr)):
        raise ValueError(f"{CAGR_FACTOR} must provide one finite value per valuation")
    required_cagr = _median(cagr[hit_mask])
    miss_cagr = _median(cagr[~hit_mask])
    hit_margin = miss_margin = None
    if MARGIN_FACTOR in factors:
        margin = np.asarray(factors[MARGIN_FACTOR], dtype=np.float64)
        if margin.shape != values.shape or not np.all(np.isfinite(margin)):
            raise ValueError(f"{MARGIN_FACTOR} must provide one finite value per valuation")
        hit_margin = _median(margin[hit_mask])
        miss_margin = _median(margin[~hit_mask])
    trajectory: tuple[YearTarget, ...] = ()
    if (
        base_year_revenue is not None
        and isfinite(base_year_revenue)
        and base_year_revenue > 0.0
        and required_cagr is not None
    ):
        trajectory = tuple(
            YearTarget(year, base_year_revenue * (1.0 + required_cagr) ** (year - 1))
            for year in range(1, horizon_years + 1)
        )
    return TargetPlan(
        "available", hit_count, required_cagr, hit_margin, miss_cagr, miss_margin, trajectory
    )
```

Export from `app/decision/__init__.py`: `from .target_plan import MIN_HIT_SAMPLE, TargetPlan, YearTarget, build_target_plan` plus `__all__` entries.

- [ ] **Step 4: Run** `python -m pytest tests/test_target_plan.py -v` → PASS.
- [ ] **Step 5: Full suite** `python -m pytest -q` → PASS.
- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/decision/target_plan.py apps/backend/app/decision/__init__.py apps/backend/tests/test_target_plan.py
git commit -m "feat(decision): target plan — required CAGR, margin and reference trajectory"
```

### Task 4: Target plan in the target API

**Files:**
- Modify: `apps/backend/app/api/routes/simulations.py` (`read_target`, lines ~275-326)
- Modify: `apps/backend/app/api/schemas.py` (`TargetResponse` + new models)
- Test: `apps/backend/tests/test_api_decision.py` (append)

**Interfaces:**
- Consumes: `build_target_plan` (Task 3); `get_revision` from `app.repositories.resources`; `revision.canonical_inputs["monthly_revenue"]`.
- Produces: `TargetResponse.plan: TargetPlanResponse | None` where `TargetPlanResponse` has fields `status: str`, `hit_count: int`, `required_revenue_cagr: float | None`, `hit_ebitda_margin: float | None`, `miss_revenue_cagr: float | None`, `miss_ebitda_margin: float | None`, `trajectory: list[YearTargetResponse]` and `YearTargetResponse(year: int, revenue: float)`. Consumed by Tasks 7, 11.

- [ ] **Step 1: Write failing tests** appended to `tests/test_api_decision.py`, using that file's existing authenticated-client fixtures and simulation-creation helpers (read it first and reuse exactly):

```python
def test_target_response_includes_plan_for_structured_inputs(...):
    # create structured simulation via existing helper, then:
    response = client.get(f"/api/v1/simulations/{simulation_id}/target", params={"value": <modest target the helper's scenario can hit>})
    assert response.status_code == 200
    plan = response.json()["plan"]
    assert plan["status"] in {"available", "insufficient_hits"}
    if plan["status"] == "available":
        assert len(plan["trajectory"]) == 5
        assert plan["trajectory"][0]["year"] == 1


def test_target_plan_base_revenue_comes_from_revision_year_one(...):
    # structured helper with known monthly_revenue; assert trajectory[0].revenue
    # == sum of the first 12 monthly_revenue entries when plan is available
```

- [ ] **Step 2: Run** `python -m pytest tests/test_api_decision.py -v -k plan` → FAIL (`plan` key missing).

- [ ] **Step 3: Implement.** In `api/schemas.py` add (matching file style):

```python
class YearTargetResponse(BaseModel):
    year: int
    revenue: float


class TargetPlanResponse(BaseModel):
    status: str
    hit_count: int
    required_revenue_cagr: float | None = None
    hit_ebitda_margin: float | None = None
    miss_revenue_cagr: float | None = None
    miss_ebitda_margin: float | None = None
    trajectory: list[YearTargetResponse] = []
```

and `plan: TargetPlanResponse | None = None` on `TargetResponse`. In `read_target`, after computing `target = analyze_target(...)`:

```python
    revision = get_revision(
        db, revision_id=simulation.scenario_revision_id, workspace_id=actor.workspace_id
    )
    monthly_revenue = (revision.canonical_inputs or {}).get("monthly_revenue") if revision else None
    base_year_revenue = (
        float(sum(monthly_revenue[:12])) if isinstance(monthly_revenue, list) and monthly_revenue else None
    )
    plan = build_target_plan(valuations, value, factors, base_year_revenue)
```

and map `plan` into the response (`asdict`-style explicit field mapping, trajectory → `[{"year": p.year, "revenue": p.revenue} for p in plan.trajectory]`). Import `build_target_plan` from `app.decision.target_plan`.

- [ ] **Step 4: Run** `python -m pytest tests/test_api_decision.py -v` → PASS.
- [ ] **Step 5: Full suite** `python -m pytest -q` → PASS.
- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/api/routes/simulations.py apps/backend/app/api/schemas.py apps/backend/tests/test_api_decision.py
git commit -m "feat(api): target endpoint returns the reverse-engineered plan for the goal"
```

### Task 5: Report contract + PDF sections for the new metrics

**Files:**
- Modify: `apps/backend/app/reports/schema.py` (new section models + `ReportData` fields)
- Modify: `apps/backend/app/reports/from_result.py` (`REPORT_TEMPLATE_VERSION`, payload assembly, new `target_plan` parameter)
- Modify: `apps/backend/app/reports/pdf.py` (two new story sections in `_build_story`)
- Modify: `apps/backend/app/api/routes/reports.py` (compute and pass `target_plan`)
- Test: `apps/backend/tests/test_reports.py`, `apps/backend/tests/test_report_api.py` (append)

**Interfaces:**
- Consumes: `summary["implied_multiples"]` (Task 2), `build_target_plan`/`TargetPlan` (Task 3).
- Produces (in `schema.py`):

```python
class MultipleBand(FrozenModel):
    p25: FiniteNumber
    p50: FiniteNumber
    p75: FiniteNumber
    eligible_count: int = Field(ge=1)
    excluded_count: int = Field(ge=0)

class ImpliedMultiplesSection(FrozenModel):
    status: Literal["available", "not_available"]
    reason: str | None = Field(default=None, max_length=120)
    basis: str = Field(min_length=1, max_length=120)
    value_to_revenue: MultipleBand | None = None
    value_to_ebitda: MultipleBand | None = None

class TargetPlanYear(FrozenModel):
    year: int = Field(ge=1, le=10)
    revenue: FiniteNumber

class TargetPlanSection(FrozenModel):
    status: Literal["available", "insufficient_hits", "not_available_for_inputs"]
    hit_count: int = Field(ge=0)
    required_revenue_cagr: FiniteNumber | None = None
    hit_ebitda_margin: FiniteNumber | None = None
    miss_revenue_cagr: FiniteNumber | None = None
    miss_ebitda_margin: FiniteNumber | None = None
    trajectory: tuple[TargetPlanYear, ...] = ()
```

plus `ReportData.implied_multiples: ImpliedMultiplesSection | None = None` and `ReportData.target_plan: TargetPlanSection | None = None`. `report_from_result` gains keyword `target_plan: TargetPlan | None = None` (the Task 3 dataclass) and maps it; it maps `summary.get("implied_multiples")` directly when the dict is present and status fields validate. Consumed by Task 9 (branding does not change these sections).

- [ ] **Step 1: Write failing tests.** In `tests/test_reports.py`, extend the existing valid-`ReportData` builder (read the file; it has a canonical payload fixture) with the two sections and assert `build_report_pdf` returns bytes starting with `%PDF`; add a validation test that `MultipleBand` rejects `eligible_count=0`. In `tests/test_report_api.py`, assert the PDF route still returns 200 with a `target` query param after wiring (and keep existing assertions untouched).
- [ ] **Step 2: Run** `python -m pytest tests/test_reports.py tests/test_report_api.py -v` → FAIL (unknown fields).
- [ ] **Step 3: Implement** schema additions above; bump `REPORT_TEMPLATE_VERSION = "1.3.0"` in `from_result.py`; in `report_from_result` payload add:

```python
        "implied_multiples": summary.get("implied_multiples"),
        "target_plan": (
            {
                "status": target_plan.status,
                "hit_count": target_plan.hit_count,
                "required_revenue_cagr": target_plan.required_revenue_cagr,
                "hit_ebitda_margin": target_plan.hit_ebitda_margin,
                "miss_revenue_cagr": target_plan.miss_revenue_cagr,
                "miss_ebitda_margin": target_plan.miss_ebitda_margin,
                "trajectory": [
                    {"year": point.year, "revenue": point.revenue}
                    for point in target_plan.trajectory
                ],
            }
            if target_plan is not None
            else None
        ),
```

(`summary.get("implied_multiples")` may be absent on pre-1.4 results → field stays None; guard with `if isinstance(..., dict) else None`.) In `pdf.py` `_build_story`, after the target section (`_target`), append two sections using the existing helpers (`SectionHeader`, `data_table`, `stat_strip`, `callout` from `pdf_theme`):
  - "Múltiplos implícitos": a 2-row table (Valor/Receita, Valor/EBITDA) with P25/P50/P75 columns formatted "N,NNx", a line "Baseado em X de Y cenários elegíveis", and the mandatory callout "Múltiplos implícitos nas suas premissas — não são múltiplos de mercado." Render nothing when the section is None; render the reason sentence when status is `not_available`.
  - "Plano para a meta": when available — stat strip (CAGR necessário, Margem EBITDA alvo, formatted pt-BR percent) + 5-row trajectory table (Ano, Receita de referência) + contrast line hit vs miss + the association disclaimer reused from the target section's wording; when `insufficient_hits` — one explanatory paragraph including `hit_count` and the threshold 50.
  In `routes/reports.py`, where `target_analysis` is computed, also compute the plan (same `base_year_revenue` derivation as Task 4 — extract a tiny shared helper `base_year_revenue_from_inputs(canonical_inputs: dict | None) -> float | None` into `app/decision/target_plan.py` and reuse it in both routes) and pass `target_plan=plan` to `report_from_result`.
- [ ] **Step 4: Run** `python -m pytest tests/test_reports.py tests/test_report_api.py -v` → PASS.
- [ ] **Step 5: Full suite + visual sanity.** `python -m pytest -q` → PASS. Also generate one PDF via the route test artifact or a small script and eyeball locally that sections render (store nothing).
- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/reports apps/backend/app/api/routes/reports.py apps/backend/app/decision/target_plan.py apps/backend/tests/test_reports.py apps/backend/tests/test_report_api.py
git commit -m "feat(reports): implied multiples and target plan sections (template 1.3.0)"
```

---

## Phase B — Entitlements, white label, waitlist (backend)

### Task 6: Plan tiers and entitlement resolver

**Files:**
- Create: `apps/backend/app/core/entitlements.py`
- Create: `apps/backend/alembic/versions/c4a1e5b9d201_add_workspace_plan.py`
- Create: `apps/backend/scripts/set_plan.py`
- Modify: `apps/backend/app/db/models.py` (`Workspace`)
- Modify: `apps/backend/app/api/routes/auth.py` or `resources.py` — wherever `/auth/me`-adjacent workspace info lives, add `GET /api/v1/workspace/entitlements`
- Test: `apps/backend/tests/test_entitlements.py`

**Interfaces:**
- Produces:

```python
# app/core/entitlements.py
class PlanTier(str, enum.Enum):
    free = "free"
    empresario = "empresario"
    consultor = "consultor"
    escritorio = "escritorio"

@dataclass(frozen=True, slots=True)
class Entitlements:
    plan: PlanTier
    max_startups: int | None          # None = unlimited
    max_scenarios_per_run: int
    white_label: bool
    full_report: bool                 # False => watermarked PDF
    target_plan_section: bool
    implied_multiples: bool

def entitlements_for(plan_value: str | None) -> Entitlements   # unknown/None -> free
def set_workspace_plan(db, *, workspace_id: str, plan: PlanTier, actor_id: str | None) -> None
```

Matrix: free → (1, 1_000, False, False, False, False); empresario → (5, 10_000, False, True, True, True); consultor → (10, 25_000, True, True, True, True); escritorio → (None, 25_000, True, True, True, True). `set_workspace_plan` writes the column and a `record_event(action="workspace.plan_changed", resource_type="workspace", metadata={"plan": plan.value})`. Endpoint `GET /api/v1/workspace/entitlements` returns `{"plan", "max_startups", "max_scenarios_per_run", "white_label", "full_report", "target_plan_section", "implied_multiples"}` for `actor.workspace_id`. Consumed by Tasks 7, 8, 9, 12.
- Model change: `Workspace.plan: Mapped[str] = mapped_column(String(20), default="free", server_default="free")`.

- [ ] **Step 1: Write failing tests** (`tests/test_entitlements.py`): matrix spot-checks (`entitlements_for("free").max_scenarios_per_run == 1000`, `entitlements_for("escritorio").max_startups is None`, `entitlements_for("nonsense").plan is PlanTier.free`); `set_workspace_plan` persists and writes an `AuditEvent` with action `workspace.plan_changed`; API test (reuse auth fixtures from `test_api_auth.py`) that a fresh workspace GET `/api/v1/workspace/entitlements` → 200 with `plan == "free"` and that the endpoint requires auth (401 unauthenticated).
- [ ] **Step 2: Run** → FAIL (module/column missing).
- [ ] **Step 3: Implement** resolver + model column + migration:

```python
# alembic/versions/c4a1e5b9d201_add_workspace_plan.py
"""Add commercial plan tier to workspaces."""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "c4a1e5b9d201"
down_revision: str | None = "d9673a8e2b10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("plan", sa.String(length=20), nullable=False, server_default="free"),
    )

def downgrade() -> None:
    op.drop_column("workspaces", "plan")
```

plus the endpoint (new small router or an addition beside the existing workspace-scoped routes — follow where `/auth/me` lives) and `scripts/set_plan.py` (argparse: `--workspace-id`, `--plan`; opens a session the way existing scripts in `apps/backend/scripts/` do, calls `set_workspace_plan`, prints confirmation).
- [ ] **Step 4: Run** `python -m pytest tests/test_entitlements.py -v` → PASS.
- [ ] **Step 5: Full suite** → PASS (conftest creates tables from metadata, so the new column is picked up automatically; verify).
- [ ] **Step 6: Commit** `git add -A apps/backend && git commit -m "feat(plans): workspace plan tier, entitlement resolver and audited plan change"`

### Task 7: Enforce entitlements in the API

**Files:**
- Modify: `apps/backend/app/api/routes/simulations.py` (`_run`, `read_target`, `_response`)
- Modify: `apps/backend/app/api/routes/resources.py` (startup creation route)
- Modify: `apps/backend/app/api/routes/reports.py` (gate target plan + multiples in PDF data)
- Test: `apps/backend/tests/test_entitlement_enforcement.py`

**Interfaces:**
- Consumes: `entitlements_for`, `set_workspace_plan` (Task 6). Pattern for loading the workspace plan inside a route: `plan = db.scalar(select(Workspace.plan).where(Workspace.id == actor.workspace_id))`; `ent = entitlements_for(plan)`.
- Produces: HTTP 403 `"plan_limit_scenarios"` when `payload.simulation_count > ent.max_scenarios_per_run`; 403 `"plan_limit_startups"` when creating a startup beyond `ent.max_startups`; `TargetResponse.plan is None` when not `ent.target_plan_section`; `summary["implied_multiples"]` stripped from `SimulationResponse` and from `ReportData` when not `ent.implied_multiples`; `report_from_result` receives `target_plan=None` when not entitled.

- [ ] **Step 1: Write failing tests** (reuse fixtures; use `set_workspace_plan` to arrange tiers):
  - free workspace, run with `simulation_count=1000` → 201 (boundary pass);
  - free workspace, `simulation_count=1001` → 403 with detail `plan_limit_scenarios`;
  - empresario workspace, `simulation_count=10_000` → 201; `10_001` → 403 (Review Focus #3);
  - free workspace: second startup creation → 403 `plan_limit_startups`; empresario: 5 pass, 6th → 403;
  - free workspace target response: `plan is None`; empresario: `plan` present;
  - free workspace `SimulationResponse.summary` has `implied_multiples == None`; empresario keeps it.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Add a tiny helper in `app/core/entitlements.py`: `workspace_entitlements(db, workspace_id: str) -> Entitlements` doing the scalar select above (single query, no join). Call it at the top of `_run`, the startup-create route (count existing: `db.scalar(select(func.count()).select_from(Startup).where(Startup.workspace_id == actor.workspace_id))`), `read_target` (skip plan build when not entitled), `_response` (copy summary dict and pop `implied_multiples` when not entitled — never mutate `result.summary` in place), and `routes/reports.py` (pass `target_plan=None`, and blank the section: build `data = report_from_result(...)` then, when not entitled, rebuild with `implied_multiples=None` by popping the key from the summary mapping passed through — simplest: thread an `include_multiples: bool` parameter into `report_from_result` defaulting True and gate the payload line from Task 5).
- [ ] **Step 4: Run** `python -m pytest tests/test_entitlement_enforcement.py -v` → PASS.
- [ ] **Step 5: Full suite** → PASS (existing tests run as `free` default workspaces — if any existing test now trips a limit (e.g. runs > 1.000 scenarios or creates > 1 startup), arrange that test's workspace to `empresario`/`escritorio` via `set_workspace_plan` in its setup rather than weakening the limit).
- [ ] **Step 6: Commit** `git commit -am "feat(plans): enforce scenario, startup and section entitlements server-side"`

### Task 8: Report branding storage and API

**Files:**
- Create: `apps/backend/app/api/routes/branding.py`
- Create: `apps/backend/alembic/versions/e7f2a9c3b115_add_report_branding.py`
- Modify: `apps/backend/app/db/models.py` (new `ReportBranding`)
- Modify: `apps/backend/app/main.py` (include router — follow how existing routers are included)
- Test: `apps/backend/tests/test_branding_api.py`

**Interfaces:**
- Produces model:

```python
class ReportBranding(TimestampMixin, Base):
    __tablename__ = "report_branding"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), unique=True, index=True
    )
    firm_name: Mapped[str | None] = mapped_column(String(120))
    primary_color: Mapped[str | None] = mapped_column(String(7))
    footer_text: Mapped[str | None] = mapped_column(String(300))
    logo_bytes: Mapped[bytes | None] = mapped_column(LargeBinary)
    logo_media_type: Mapped[str | None] = mapped_column(String(32))
```

- Routes (all require role in {owner, admin} and `ent.white_label`, else 403 `white_label_not_in_plan`):
  - `GET /api/v1/workspace/branding` → `{firm_name, primary_color, footer_text, has_logo: bool}`;
  - `PUT /api/v1/workspace/branding` body `{firm_name?, primary_color?, footer_text?}` — `primary_color` validated against `^#[0-9A-Fa-f]{6}$` (422 otherwise), strings trimmed, upsert;
  - `POST /api/v1/workspace/branding/logo` multipart file — accept only PNG (`\x89PNG\r\n\x1a\n` magic) or JPEG (`\xff\xd8\xff`), max 1_048_576 bytes (413 `logo_too_large`), anything else 422 `logo_format_unsupported` (SVG explicitly rejected);
  - `DELETE /api/v1/workspace/branding/logo` → clears logo fields.
  All writes `record_event(action="branding.updated", resource_type="workspace", ...)` without logging logo bytes. Consumed by Tasks 9, 12.

- [ ] **Step 1: Write failing tests**: entitled consultor workspace PUT+GET round trip; free workspace PUT → 403 `white_label_not_in_plan`; analyst role → 403; cross-tenant isolation (workspace B's GET never returns A's values — two clients, two workspaces); PNG upload ok then `has_logo is True`; 2 MB upload → 413; file with `.png` name but `GIF89a` bytes → 422; bad hex color `"verde"` → 422 (arrange plans with `set_workspace_plan`).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** model + migration (`e7f2a9c3b115`, `down_revision="c4a1e5b9d201"`, `op.create_table` mirroring the model, unique index on `workspace_id`) + router (use `UploadFile` with `await file.read(MAX+1)` guard pattern; FastAPI routes in this app are sync — read via `file.file.read(MAX + 1)`), include router in `main.py`.
- [ ] **Step 4: Run** `python -m pytest tests/test_branding_api.py -v` → PASS.
- [ ] **Step 5: Full suite** → PASS.
- [ ] **Step 6: Commit** `git commit -am "feat(branding): per-workspace report branding with validated logo upload"`

### Task 9: White-label and watermark PDF rendering

**Files:**
- Modify: `apps/backend/app/reports/schema.py` (add `ReportBrandingData`)
- Modify: `apps/backend/app/reports/pdf.py` (`build_report_pdf`, `_render`, `_document`, `_cover`, `_page_chrome`)
- Modify: `apps/backend/app/reports/pdf_theme.py` (accent-color override hook)
- Modify: `apps/backend/app/api/routes/reports.py` (resolve branding + watermark, filename)
- Test: `apps/backend/tests/test_reports.py`, `apps/backend/tests/test_report_api.py` (append)

**Interfaces:**
- Consumes: `ReportBranding` model + `workspace_entitlements` (Tasks 6-8).
- Produces: `build_report_pdf(data: ReportData, *, branding: ReportBrandingData | None = None, watermark: bool = False) -> bytes` where:

```python
class ReportBrandingData(FrozenModel):
    firm_name: str = Field(min_length=1, max_length=120)
    primary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    footer_text: str | None = Field(default=None, max_length=300)
    logo_bytes: bytes | None = None
    logo_media_type: str | None = Field(default=None, max_length=32)
```

Behavior: with branding — cover draws the firm logo (via `reportlab.lib.utils.ImageReader(io.BytesIO(logo_bytes))`, guarded: any exception loading the image skips the logo silently) and `firm_name` where `_brand_mark` + product name render today; `_page_chrome` footer shows `firm_name` + `footer_text` instead of the QuantoVale mark; the cover accent color uses `primary_color` when given. No QuantoVale name appears anywhere in the branded variant EXCEPT the methodology/audit identifiers (seed, versions) and disclaimers, which always render. With `watermark=True` — every page gets a diagonal translucent "QUANTOVALE · RESUMO GRATUITO" (canvas.saveState / translate / rotate(45) / setFillAlpha(0.08) / big Helvetica / restoreState) drawn in `_page_chrome`.
- Route behavior: load branding row; pass `branding=` only when `ent.white_label` and `firm_name` set; `watermark=not ent.full_report`; `Content-Disposition` filename becomes `quantovale-{simulation.id}.pdf`.

- [ ] **Step 1: Write failing tests**: `build_report_pdf(data, branding=ReportBrandingData(firm_name="Alfa Consultoria", primary_color="#123456", logo_bytes=<tiny valid 1x1 PNG bytes literal>, logo_media_type="image/png"))` returns `%PDF` bytes; corrupt `logo_bytes=b"not an image"` still returns `%PDF` bytes (Review Focus #2); `watermark=True` returns bytes (and differs from non-watermarked output length); route test: free workspace with branding row configured still downloads an UNbranded, watermarked PDF; consultor workspace with branding gets 200 and audit event unchanged; filename header contains `quantovale-`.
- [ ] **Step 2: Run** → FAIL (unexpected keyword).
- [ ] **Step 3: Implement** threading the two parameters through `_render`/`_document`/`_cover`/`_page_chrome` as explicit arguments (no globals); keep default calls (`build_report_pdf(data)`) byte-compatible in structure so existing contract tests pass untouched.
- [ ] **Step 4: Run** targeted tests → PASS.
- [ ] **Step 5: Full suite** → PASS. Generate one branded sample PDF manually and eyeball cover/footer/watermark.
- [ ] **Step 6: Commit** `git commit -am "feat(reports): white-label branding and free-tier watermark in PDF"`

### Task 10: Waitlist endpoint

**Files:**
- Create: `apps/backend/app/api/routes/waitlist.py`
- Create: `apps/backend/alembic/versions/f3d8b6a1c922_add_waitlist.py`
- Modify: `apps/backend/app/db/models.py` (new `WaitlistEntry`)
- Modify: `apps/backend/app/main.py` (include router)
- Test: `apps/backend/tests/test_waitlist.py`

**Interfaces:**
- Produces model `WaitlistEntry(id, email: String(320) unique, plan_interest: String(20), source: String(40), created_at)` — email stored lowercased/stripped. Public route (NO `Actor` dependency): `POST /api/v1/waitlist` body `{"email": str, "plan_interest": "free"|"empresario"|"consultor"|"escritorio", "source": str<=40}` → 201 `{"status": "ok"}`; repeat email → 200 `{"status": "ok"}` (idempotent, updates `plan_interest`); invalid email (regex `^[^@\s]+@[^@\s]+\.[^@\s]+$`, max 320) → 422; in-process rate limit 10 posts/minute/IP → 429 `waitlist_rate_limited` (module-level `dict[str, list[float]]`, pruned per request; documented as per-process, acceptable for a waitlist). Consumed by Task 13's form.

- [ ] **Step 1: Write failing tests**: create → 201; same email with different case/whitespace (`" User@X.com "` then `"user@x.com"`) → 200 and one row (Review Focus #1); invalid email → 422; unknown plan_interest → 422; 11th rapid request from same client → 429; endpoint works WITHOUT auth cookie.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** model, migration (`f3d8b6a1c922`, `down_revision="e7f2a9c3b115"`, unique index on `email`), pydantic request model with validator normalizing email, router with the limiter; `record_event` is NOT used (no workspace); no PII beyond email is stored.
- [ ] **Step 4: Run** `python -m pytest tests/test_waitlist.py -v` → PASS.
- [ ] **Step 5: Full suite** → PASS.
- [ ] **Step 6: Commit** `git commit -am "feat(waitlist): public rate-limited waitlist with idempotent email capture"`

---

## Phase C — App frontend

### Task 11: Results UI — implied multiples and target plan

**Files:**
- Modify: `apps/frontend/lib/api/simulations.ts` (types + target plan types)
- Modify: `apps/frontend/lib/results.ts` + Test: `apps/frontend/lib/results.test.ts` (presentation transforms)
- Modify: `apps/frontend/components/results/summary-sections.tsx` (multiples card)
- Modify: `apps/frontend/components/results/analysis-sections.tsx` (target plan block)
- Modify: `apps/frontend/components/results/results.module.css` (styles following existing patterns)

**Interfaces:**
- Consumes: `summary.implied_multiples` (Task 2 payload shape) and `TargetResponse.plan` (Task 4 shape) — mirror them as TS types `ImpliedMultiples`, `TargetPlan`, `YearTarget` in `lib/api/simulations.ts`.
- Produces pure helpers in `lib/results.ts`: `formatMultiple(value: number): string` → `"8,4x"` (one decimal, pt-BR comma); `formatPercentBR(value: number): string` → `"30,0%"`; `multiplesRows(m: ImpliedMultiples | null | undefined): {label: string; p25: string; p50: string; p75: string; note: string}[] ` (empty array when absent/not_available); `targetPlanView(plan: TargetPlan | null | undefined)` returning a discriminated view (`kind: "available" | "insufficient" | "unavailable" | "hidden"`) with preformatted strings. UI renders from these helpers only.

- [ ] **Step 1: Write failing vitest tests** in `lib/results.test.ts` for the four helpers: `formatMultiple(8.44) === "8,4x"`; `multiplesRows` with the Task 1 payload-shape fixture yields 2 rows with note "X de Y cenários elegíveis"; `multiplesRows(undefined)` → `[]`; `targetPlanView({status:"insufficient_hits", hit_count: 12, ...})` → `kind: "insufficient"` with a sentence containing "12"; `targetPlanView(null)` → `kind: "hidden"`.
- [ ] **Step 2: Run** `npm --workspace apps/frontend run test` → FAIL.
- [ ] **Step 3: Implement helpers + types**, then integrate into the two section components following their existing card markup/class conventions (read both files first). The multiples card carries the fixed caption "Múltiplos implícitos nas suas premissas — não são múltiplos de mercado." The target plan block shows: CAGR necessário, margem alvo, 5-year reference trajectory as a compact table, and the hit-vs-miss contrast line; `kind: "hidden"` renders nothing (free plan), `"insufficient"` renders the explanatory sentence.
- [ ] **Step 4: Run tests + typecheck** `npm --workspace apps/frontend run test && npm --workspace apps/frontend run lint` → PASS.
- [ ] **Step 5: Visual check** `npm run dev`, open a simulation result (or the demo route `/app/simulations/demo` if it renders fixtures) and confirm both sections render and degrade (no data → hidden).
- [ ] **Step 6: Commit** `git commit -am "feat(results): implied multiples card and target plan section"`

### Task 12: Branding settings page

**Files:**
- Create: `apps/frontend/app/app/settings/branding/page.tsx`
- Create: `apps/frontend/lib/api/branding.ts`
- Modify: `apps/frontend/components/app-shell.tsx` (nav link, visible only when entitled)
- Test: `apps/frontend/lib/api/branding.test.ts`

**Interfaces:**
- Consumes: Task 8 routes via a new `lib/api/branding.ts` using the same `client.ts` fetch wrapper as `lib/api/simulations.ts` (read `client.ts` first): `getEntitlements(): Promise<Entitlements>` (GET `/api/v1/workspace/entitlements`), `getBranding()`, `putBranding(payload)`, `uploadLogo(file: File)`, `deleteLogo()`.
- Produces: settings form (firm name, color picker constrained to hex, footer text, logo upload with client-side 1 MB/type pre-check mirroring — not replacing — the server rule) plus a static header/footer preview strip showing firm name + color. Non-entitled workspaces see an upsell card ("Disponível nos planos Consultor e Escritório") instead of the form; the API client still never renders another workspace's data.

- [ ] **Step 1: Write failing tests** for `lib/api/branding.ts` response mapping (mock fetch like existing `lib/api` tests — read `canonical-inputs.test.ts` for the mocking pattern): entitlements parse, branding round-trip payload shape, uploadLogo builds multipart FormData with the file under key `file`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** client + page + nav gating (`entitlements.white_label`).
- [ ] **Step 4: Run tests + lint** → PASS.
- [ ] **Step 5: Manual check** with a consultor-plan workspace (use `scripts/set_plan.py`): save branding, upload logo, download a PDF, confirm the brand appears.
- [ ] **Step 6: Commit** `git commit -am "feat(app): report branding settings for white-label plans"`

---

## Phase D — Landing

### Task 13: Pricing, waitlist form, copy pass and /pricing page

**Files:**
- Create: `apps/frontend/components/landing/waitlist-form.tsx` + Test: `apps/frontend/components/landing/waitlist-form.test.tsx`
- Create: `apps/frontend/app/pricing/page.tsx`
- Modify: `apps/frontend/app/page.tsx` (plans array → 4 plans with prices; audience section; FAQ; CTA wiring)
- Modify: `apps/frontend/components/site-header.tsx`, `site-footer.tsx` (Planos link → `/pricing` or `#planos`)
- Modify: `apps/frontend/app/globals.css` (4-column pricing grid breakpoint)
- Modify: `docs/PRODUCT_SPEC.md` §8 (record the published prices/tiers as the commercial decision of 2026-10-02, replacing "a definir")

**Interfaces:**
- Consumes: `POST /api/v1/waitlist` (Task 10).
- Produces: `<WaitlistForm plan="consultor" source="landing" />` client component — email input + submit; success state "Você está na lista — avisaremos no lançamento."; 429/network → "Tente novamente em instantes."; posts `{email, plan_interest: plan, source}`.
- Content (exact copy):
  - Plans array in `page.tsx` becomes:
    - Grátis · R$ 0 · "Para conhecer a análise" · [1 empresa, 1.000 cenários por execução, DCF + VC Method + Monte Carlo, Resumo em PDF com marca d'água]
    - Empresário · R$ 97/mês · "Para donos de empresa e CFOs" · [5 empresas, 10.000 cenários por execução, Múltiplos implícitos, Plano para a meta, Relatório PDF completo] — featured, badge "MAIS POPULAR"
    - Consultor · R$ 297/mês · "Para consultores, contadores e assessores" · [Até 10 empresas-clientes, 25.000 cenários por execução, Relatório white label com a sua marca, Tudo do Empresário]
    - Escritório · R$ 697/mês · "Para escritórios e portfólios" · [Empresas-clientes ilimitadas, Relatório white label com a sua marca, 25.000 cenários por execução, Multiusuário em breve]
  - Every card shows "ou R$ NNN/ano (~20% off)" (932/2.851/6.691) and a `WaitlistForm`; pricing note becomes: "Cobrança ainda não está ativa. Entre na lista de espera e seja avisado no lançamento — sem cartão, sem compromisso."
  - Audience section: the "Contadores & Consultores" card copy becomes "Entregue laudos de valuation com a sua marca, para múltiplos clientes." and gains an inline "white label" tag; FAQ adds `Posso usar o QuantoVale com meus clientes?` ("Sim. Nos planos Consultor e Escritório o relatório sai com a sua marca — logo, cores e nome da sua firma — mantendo a transparência metodológica.") and `Quando a cobrança começa?` ("No lançamento comercial. Hoje você entra na lista de espera e é avisado antes de qualquer cobrança.").
  - `/pricing`: hero line, the same 4 cards, a feature-comparison table (rows: empresas, cenários por execução, métodos, múltiplos implícitos, plano para a meta, relatório PDF, white label, suporte), the two FAQ items, `SiteHeader`/`SiteFooter`.
  - Copy sweep: `grep -ri "startup" apps/frontend/app apps/frontend/components --include=*.tsx` — rewrite any customer-facing "startup" to "empresa" (internal identifiers, imports and API field names like `startup_id` stay).
- [ ] **Step 1: Write failing component test** (`waitlist-form.test.tsx`, vitest + mocked `fetch`): renders input+button; submit posts JSON `{email, plan_interest: "consultor", source: "landing"}` to `/api/v1/waitlist`; success swaps to the confirmation sentence; 429 shows the retry sentence.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** form, page edits, `/pricing`, copy sweep, doc update.
- [ ] **Step 4: Run** `npm --workspace apps/frontend run test && npm --workspace apps/frontend run lint` → PASS.
- [ ] **Step 5: Visual check** `npm run dev`: landing pricing section (4 cards, mobile wrap), `/pricing`, form happy path against the running backend.
- [ ] **Step 6: Commit** `git commit -am "feat(landing): published 4-tier pricing with waitlist and white-label positioning"`

### Task 14: 7-second three-act 3D intro

**Files:**
- Create: `apps/frontend/components/landing/intro-timeline.ts` + Test: `apps/frontend/components/landing/intro-timeline.test.ts`
- Modify: `apps/frontend/components/landing/futures-scene.tsx` (timing constants, prelude act, skip handling)
- Modify: `apps/frontend/components/landing/hero-visual.tsx` (session gate, headline sync)
- Modify: `apps/frontend/components/landing/hero-visual.module.css` + `apps/frontend/app/globals.css` (headline entrance keyed off intro state)

**Interfaces:**
- Produces a PURE timeline module (all scene/DOM code consumes it; this is the TDD anchor):

```typescript
// intro-timeline.ts
export const PRELUDE_SECONDS = 2.0;   // act 1: the single number
export const SWEEP_SECONDS = 3.0;     // act 2: fan-out of futures
export const FALL_SECONDS = 1.4;      // act 3: distribution condenses
export const SETTLE_SECONDS = 0.6;
export const INTRO_TOTAL =
  PRELUDE_SECONDS + SWEEP_SECONDS + FALL_SECONDS + SETTLE_SECONDS; // 7.0

export type IntroFrame = {
  /** 0→1 inside act 1; paths collapsed onto the median while < 1 */
  prelude: number;
  /** 0→1 spread of the fan (act 2); drives the uSpread uniform */
  spread: number;
  /** 0→1 condensation into the terminal distribution (act 3) */
  fall: number;
  /** 0→1 camera settle; 1 = final resting composition */
  settle: number;
  /** labels/headline may enter */
  revealUi: boolean;
};

export function introFrame(elapsed: number): IntroFrame;
export function shouldPlayIntro(storage: Pick<Storage, "getItem">): boolean;      // true unless "qv-intro-seen" === "1"; try/catch -> true
export function markIntroSeen(storage: Pick<Storage, "setItem">): void;          // sets "qv-intro-seen"="1"; try/catch swallow
```

`introFrame` uses the easing helpers already present in `futures-scene.tsx` (`easeOutCubic`, `easeInOut` — export them from the scene or duplicate the 2-line functions in the module to keep it dependency-free; duplicate, with a comment, to keep the module pure and testable without three.js). `revealUi` becomes true at `elapsed >= PRELUDE_SECONDS + SWEEP_SECONDS * 0.9` (keeps today's label behavior relative to the sweep). `introFrame(Infinity)` returns the final frame (all 1s, revealUi true).
- Scene changes (consumes `introFrame`):
  - add uniform `uSpread` (float 0→1) to `PATH_VERT`: each path's lateral/vertical offset from the median path is multiplied by `uSpread`, so `uSpread=0` collapses the fan onto the median line (act 1 shows "one number"), and act 2 expands it — the existing per-path reveal sweep keeps working multiplied on top;
  - the `useFrame` driver replaces its ad-hoc `elapsed`-based math with `const frame = introFrame(elapsed)` and maps: `uSpread = frame.spread`, existing reveal easing driven by `frame.prelude`(draw median) then `frame.spread`, the terminal "fall" by `frame.fall`, camera: prelude holds a closer dolly (lerp camera distance from 0.82× to 1.0× of today's base as `frame.settle` grows) with today's drift/parallax preserved;
  - skip: one-time listeners on `window` for `pointerdown`, `wheel`, `keydown`, `touchstart` that set `elapsed = INTRO_TOTAL` (and remove themselves); scroll naturally triggers `wheel`/`touchstart`;
  - session gate: `FuturesScene` gains prop `playIntro: boolean`; when false it initializes `elapsed = INTRO_TOTAL` (scene mounts settled, still breathing with drift);
  - `onIntroDone` fires when `frame.revealUi` first becomes true (replaces the `SWEEP_SECONDS * 0.9` check), after which `markIntroSeen(sessionStorage)` runs in `hero-visual.tsx`.
- Hero/headline sync (`hero-visual.tsx` + CSS): compute `const playIntro = mode !== "static" && shouldPlayIntro(sessionStorage)` once on mount (state, not render-time branch — SSR renders headline visible); pass to the scene; set `data-intro="playing" | "done"` on the hero copy container; CSS: `[data-intro="playing"] .hero-copy-content { opacity: 0; transform: translateY(12px); }` transitioning to visible when `introDone` flips (`.labelsIn` already models this pattern). Default (no JS, reduced motion, static fallback, return visit) keeps the headline fully visible with no animation — LCP text is server-rendered visible and only hidden by a client effect when the intro actually plays.

- [ ] **Step 1: Write failing timeline tests** (`intro-timeline.test.ts`): `INTRO_TOTAL === 7`; `introFrame(0)` → `{prelude: 0, spread: 0, fall: 0, revealUi: false}`; `introFrame(2)` → `prelude === 1 && spread === 0`; `introFrame(5)` → `spread === 1`; `introFrame(3.8)` (= prelude + 0.9·sweep) → `revealUi === true`; `introFrame(7)` and `introFrame(Infinity)` → all fields 1/true; monotonicity: for `t2 > t1`, each of prelude/spread/fall/settle is `>=`; `shouldPlayIntro` honors the flag and a throwing storage returns true; `markIntroSeen` swallows a throwing storage.
- [ ] **Step 2: Run** `npm --workspace apps/frontend run test` → FAIL.
- [ ] **Step 3: Implement the timeline module** → tests PASS.
- [ ] **Step 4: Integrate into scene + hero** as specified above. Keep `lite` particle degradation untouched.
- [ ] **Step 5: Verify by hand (checklist):** `npm run dev` →
  - first visit: 3 acts read clearly, ~7 s, headline enters in act 3;
  - click/scroll mid-intro: jumps to settled state instantly, labels+headline visible;
  - reload: no intro (sessionStorage), scene settled;
  - DevTools "Emulate prefers-reduced-motion": static fallback with labels, headline visible immediately;
  - mobile viewport (760px): acceptable frame rate, no horizontal scroll;
  - `npm --workspace apps/frontend run lint` → PASS.
- [ ] **Step 6: Commit** `git commit -am "feat(landing): seven-second three-act intro with skip and session gate"`

### Task 15: Landing e2e (Playwright)

**Files:**
- Create: `apps/frontend/playwright.config.ts`
- Create: `apps/frontend/e2e/landing.spec.ts`
- Modify: `apps/frontend/package.json` (devDep `@playwright/test`, script `"test:e2e": "playwright test"`), root `package.json` (script `"test:e2e": "npm --workspace apps/frontend run test:e2e"`)

**Interfaces:**
- Consumes: Task 13 form markup, Task 14 intro states.
- Produces: 3 specs against `next dev` via Playwright `webServer` (port 3000, `reuseExistingServer: true`), chromium only:
  1. `reduced motion shows static hero`: context with `reducedMotion: "reduce"` → `canvas` never appears within 3 s and the static P50 label is visible;
  2. `intro skips on interaction`: default context → wait for canvas, `page.mouse.wheel(0, 200)` at ~1 s, assert the live P50 label is visible well before the 7 s mark (e.g. within 2.5 s of the wheel);
  3. `waitlist form submits`: `page.route("**/api/v1/waitlist", → fulfill 201 {"status":"ok"})`, fill email in the Consultor card, submit, expect the confirmation sentence.

- [ ] **Step 1: Install and scaffold** `npm --workspace apps/frontend install -D @playwright/test && npx --workspace apps/frontend playwright install chromium`; write config + the 3 specs.
- [ ] **Step 2: Run to red/green honestly** `npm run test:e2e` — specs must pass against the implemented Tasks 13-14; if any fails, fix the product code or the selector, never weaken the assertion (e.g. don't extend the skip deadline to mask a broken skip).
- [ ] **Step 3: Ensure vitest ignores e2e** (`vitest` config/test glob excludes `e2e/`; verify `npm run test:frontend` still passes).
- [ ] **Step 4: Commit** `git commit -am "test(e2e): landing intro, reduced motion and waitlist specs"`

---

## Phase E — Deploy preparation

### Task 16: Hostinger runbook and compose validation

**Files:**
- Create: `docs/DEPLOY_RUNBOOK.md`
- Modify: `README.md` (plans/status touch-up: QuantoVale naming where user-facing, link to runbook)
- Verify (no blind edits): `infra/env/production.env.example`, `docker-compose.hostinger.yml`, `docker-compose.gate.yml`, `infra/scripts/validate-compose.sh`

**Interfaces:** none produced for code; the runbook is the deliverable.

- [ ] **Step 1: Verify env parametrization.** Read `infra/env/production.env.example` and `docker-compose.hostinger.yml`; confirm `DOMAIN` is the single hostname knob and that no new environment variable is required by Tasks 1-10 (they add none — confirm by grepping `os.environ`/`get_settings` changes in the diff). If the hostinger compose or gate file hardcodes a hostname, parametrize it via `${DOMAIN}` following the existing files' style.
- [ ] **Step 2: Validate compose** (requires Docker; if unavailable on this Windows host, mark the runbook step "validated on VPS" and say so in the commit message — do not fake it): `cp infra/env/development.env.example .env && bash infra/scripts/validate-compose.sh .env infra/env/production.env.example`.
- [ ] **Step 3: Write `docs/DEPLOY_RUNBOOK.md`** — a one-page operator sequence distilled from `docs/DEPLOY_VPS.md` §everything, parameterized by `DOMAIN`, with these sections: (1) prerequisites (VPS Hostinger KVM ≥ 8 GB, Docker + Compose v2, registered domain, SSH key-only); (2) DNS A/AAAA → VPS, propagation check; (3) secrets file `/opt/quantovale/secrets/production.env` mode 600 — every `CHANGE_ME` replaced, `DOMAIN=<real>`, note the `$$` htpasswd escaping rule from the gate doc; (4) migration chain reminder: `alembic upgrade head` now runs `c4a1e5b9d201`, `e7f2a9c3b115`, `f3d8b6a1c922`; (5) start order postgres+redis → migrate → app → caddy (exact compose commands copied from README's production block); (6) smoke checklist: HTTPS + headers, `/health`, signup→wizard→simulation→PDF download, `POST /api/v1/waitlist` from the landing, branded PDF on a consultor-plan workspace (`scripts/set_plan.py`); (7) backup drill pointer (`infra/scripts/backup.sh`) and rollback note (expand/contract migrations — all three new migrations are additive, rollback-safe); (8) go-live gate list copied from `DEPLOY_VPS.md` §"Bloquear go-live".
- [ ] **Step 4: Commit** `git commit -am "docs(deploy): Hostinger runbook parameterized by DOMAIN"`

### Task 17: Final verification sweep

**Files:** none new.

- [ ] **Step 1:** `cd apps/backend && python -m pytest -q` → all green (paste the summary line into the final report).
- [ ] **Step 2:** `npm --workspace apps/frontend run test && npm --workspace apps/frontend run lint && npm --workspace apps/frontend run build` → all green.
- [ ] **Step 3:** `npm run test:e2e` → green.
- [ ] **Step 4:** Spec acceptance checklist from `docs/superpowers/specs/2026-10-02-quantovale-v2-design.md` §8 — walk items 1-7 and record evidence for each (test names / manual check notes).
- [ ] **Step 5:** Commit any stragglers; the branch is ready for the finishing flow (superpowers:finishing-a-development-branch).
