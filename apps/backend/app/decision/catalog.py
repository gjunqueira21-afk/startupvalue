"""Roles, business labels and units of the aligned scenario vectors in a snapshot.

``driver`` variables are primitive stochastic inputs, sampled independently; only
they enter the driver ranking, so one source of randomness is never counted twice.
``outcome`` variables are business metrics derived from those draws (Receita do
Ano 5, Margem EBITDA...) and feed the target hit/miss comparison.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, TypeVar

Role = Literal["driver", "outcome"]
Unit = Literal["currency", "ratio", "multiplier", "binary"]


@dataclass(frozen=True, slots=True)
class VariableSpec:
    name: str
    role: Role
    label: str
    unit: Unit | None
    description: str


def _spec(name: str, role: Role, label: str, unit: Unit, description: str) -> VariableSpec:
    return VariableSpec(name, role, label, unit, description)


CATALOG: dict[str, VariableSpec] = {
    spec.name: spec
    for spec in (
        # Structured model, snapshot v1.2+.
        _spec(
            "revenue_factor_mean",
            "driver",
            "Receita vs. plano",
            "multiplier",
            "Choque multiplicativo médio da receita sobre a projeção-base (1,00x = plano).",
        ),
        _spec(
            "cost_factor_mean",
            "driver",
            "Custos operacionais vs. plano",
            "multiplier",
            "Choque multiplicativo médio do OPEX sobre a projeção-base (1,00x = plano).",
        ),
        _spec(
            "gross_margin_mean",
            "driver",
            "Margem bruta",
            "ratio",
            "Margem bruta média simulada nos 60 meses.",
        ),
        _spec(
            "failure_state",
            "driver",
            "Encerramento das operações",
            "binary",
            "1 quando o cenário encerra as operações dentro do horizonte.",
        ),
        _spec(
            "revenue_year5_operating",
            "outcome",
            "Receita do Ano 5",
            "currency",
            "Receita dos meses 49-60 na trajetória operacional, antes de eventual encerramento.",
        ),
        _spec(
            "opex_year5_operating",
            "outcome",
            "OPEX do Ano 5",
            "currency",
            "OPEX dos meses 49-60 na trajetória operacional.",
        ),
        _spec(
            "ebitda_margin_year5_operating",
            "outcome",
            "Margem EBITDA do Ano 5",
            "ratio",
            "(Lucro bruto - OPEX) / Receita no Ano 5; aproximação sem D&A explícita.",
        ),
        _spec(
            "revenue_cagr_operating",
            "outcome",
            "Crescimento anual da receita (CAGR)",
            "ratio",
            "Taxa composta anual entre a receita do Ano 1 e a do Ano 5.",
        ),
        # Simple (FCFF) model.
        _spec(
            "scenario_factor_mean",
            "driver",
            "Fluxo de caixa vs. plano",
            "multiplier",
            "Choque multiplicativo médio do FCFF sobre a projeção-base.",
        ),
        # Structured snapshots written before v1.2 (read-only compatibility).
        _spec(
            "revenue_year5",
            "outcome",
            "Receita realizada do Ano 5",
            "currency",
            "Receita realizada no Ano 5; zero após encerramento.",
        ),
        _spec(
            "opex_year5",
            "outcome",
            "OPEX realizado do Ano 5",
            "currency",
            "OPEX realizado no Ano 5; zero após encerramento.",
        ),
        _spec(
            "modeled_gross_margin_year5",
            "driver",
            "Margem bruta (Ano 5)",
            "ratio",
            "Margem bruta simulada nos meses 49-60.",
        ),
    )
}


def describe(name: str) -> VariableSpec:
    spec = CATALOG.get(name)
    if spec is not None:
        return spec
    return VariableSpec(name, "outcome", name.replace("_", " "), None, "")


T = TypeVar("T")


def split_by_role(factors: Mapping[str, T]) -> tuple[dict[str, T], dict[str, T]]:
    drivers = {name: value for name, value in factors.items() if describe(name).role == "driver"}
    outcomes = {name: value for name, value in factors.items() if name not in drivers}
    return drivers, outcomes
