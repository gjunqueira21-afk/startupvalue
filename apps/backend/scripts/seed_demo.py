"""Create a demo account with one finished simulation on a running local API.

Used by iniciar-site.bat on the first start of a fresh local database. Safe to
re-run: if the demo account already exists, nothing is created.
"""

from __future__ import annotations

import sys

import httpx

API = "http://localhost:8000"
EMAIL = "demo@startupvalue.local"
PASSWORD = "demo-startupvalue-2026"


def main() -> int:
    client = httpx.Client(base_url=API, timeout=180)

    def post(path: str, payload: dict[str, object]) -> httpx.Response:
        token = client.get("/api/v1/auth/csrf")
        headers = {"X-CSRF-Token": token.json()["csrf_token"]} if token.status_code == 200 else {}
        return client.post(path, json=payload, headers=headers)

    signup = post(
        "/api/v1/auth/signup", {"name": "Demo Founder", "email": EMAIL, "password": PASSWORD}
    )
    if signup.status_code != 201:
        print("Conta demo ja existe; nada foi criado.")
        return 0

    def created(path: str, payload: dict[str, object]) -> dict[str, object]:
        response = post(path, payload)
        if response.status_code != 201:
            raise RuntimeError(f"{path}: HTTP {response.status_code} {response.text}")
        return response.json()  # type: ignore[no-any-return]

    years = (1_200_000, 2_200_000, 3_600_000, 5_200_000, 7_500_000)
    startup = created("/api/v1/startups", {"name": "Aurora Fintech", "currency": "BRL", "profile": {
        "sector": "Fintech", "country": "Brasil", "business_model": "saas", "stage": "seed",
        "revenue": {"cadence": "annual", "years": list(years)},
        "metrics": {"cash": 350_000, "debt": 50_000, "grossMargin": 78},
        "valuation_assumptions": {"wacc": 25, "vcTargetReturn": 40, "exitMultiple": 6,
                                  "targetOwnership": 20, "investmentAmount": 2_000_000,
                                  "investmentHorizonYears": 5},
    }})
    scenario = created(f"/api/v1/startups/{startup['id']}/scenarios",
                       {"name": "Base case - multiplo de saida", "mode": "professional"})
    revision = created(f"/api/v1/scenarios/{scenario['id']}/revisions", {"inputs": {
        "monthly_revenue": [value / 12 for value in years for _ in range(12)],
        "monthly_opex": [1_310_000 / 12] * 60,
        "monthly_capex": [50_000 / 12] * 60,
        "gross_margin": 0.78,
        "revenue_uncertainty": {"kind": "lognormal", "mean": 1.0, "coefficient_of_variation": 0.25},
        "cost_uncertainty": {"kind": "lognormal", "mean": 1.0, "coefficient_of_variation": 0.15},
        "margin_uncertainty_pp": 0.15,
        "serial_correlation": 0.65,
        "persistent_weight": 0.6,
        "annual_wacc": 0.25,
        "wacc_uncertainty": {"kind": "triangular", "minimum": 0.20, "mode": 0.25, "maximum": 0.32},
        "terminal_method": "exit_multiple",
        "exit_metric": "ebitda",
        "exit_multiple": 8.0,
        "exit_multiple_uncertainty": {"kind": "triangular", "minimum": 5.0, "mode": 8.0,
                                      "maximum": 12.0},
        "excess_cash": 350_000,
        "debt": 50_000,
        "failure_probability_horizon": 0.15,
    }})
    simulation = created("/api/v1/simulations", {"scenario_revision_id": revision["id"],
                                                 "seed": 471829, "simulation_count": 10000})
    print(f"Conta demo criada: {EMAIL} / {PASSWORD}")
    print(f"Resultado demo: http://localhost:3000/app/simulations/{simulation['simulation_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
