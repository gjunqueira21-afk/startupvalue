"""Repeatable local benchmark for the vectorized simple-mode simulation kernel."""

from __future__ import annotations

import argparse
import json
import platform
import time
from dataclasses import asdict, dataclass

import numpy as np

from app.simulation.distributions import LogNormal
from app.simulation.monte_carlo import (
    SimpleCashFlowSimulationInput,
    simulate_simple_cash_flows,
)


@dataclass(frozen=True, slots=True)
class Measurement:
    scenarios: int
    median_seconds: float
    minimum_seconds: float
    runs: int
    result_bytes: int


def measure(scenarios: int, runs: int) -> Measurement:
    inputs = SimpleCashFlowSimulationInput(
        base_cash_flows=tuple(np.linspace(-50_000.0, 180_000.0, 60)),
        factor=LogNormal(1.0, 0.30),
        scenarios=scenarios,
        seed=471829,
        p_failure_horizon=0.18,
    )
    durations: list[float] = []
    result_bytes = 0
    for _ in range(runs):
        started = time.perf_counter()
        result = simulate_simple_cash_flows(inputs)
        durations.append(time.perf_counter() - started)
        result_bytes = sum(
            array.nbytes
            for array in (
                result.factor_paths,
                result.counterfactual_cash_flows,
                result.realized_cash_flows,
                result.failure_months,
            )
        )
    return Measurement(
        scenarios=scenarios,
        median_seconds=float(np.median(durations)),
        minimum_seconds=min(durations),
        runs=runs,
        result_bytes=result_bytes,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be positive")
    payload = {
        "scope": "simple cash-flow simulation kernel; excludes API, database and PDF",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "seed": 471829,
        "months": 60,
        "measurements": [
            asdict(measure(scenarios, args.runs))
            for scenarios in (1_000, 5_000, 10_000, 25_000)
        ],
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
