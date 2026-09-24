"""Validated, immutable input contract for reports.

The report layer intentionally accepts only persisted result data.  It does not
accept random generators, model inputs that could trigger valuation, or sample
paths, which keeps PDF generation a pure presentation operation.
"""

from __future__ import annotations

from datetime import date, datetime
from itertools import pairwise
from math import isfinite
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Probability = Annotated[float, Field(ge=0.0, le=1.0)]
FiniteNumber = Annotated[float, Field(allow_inf_nan=False)]
NonNegativeNumber = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
PercentileKey = Literal["p5", "p10", "p25", "p50", "p75", "p90", "p95"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class AuditMetadata(FrozenModel):
    simulation_id: str = Field(min_length=1, max_length=128)
    simulation_result_id: str = Field(min_length=1, max_length=128)
    result_hash: str = Field(min_length=8, max_length=128)
    model_version: str = Field(min_length=1, max_length=64)
    tax_version: str | None = Field(default=None, max_length=64)
    result_schema_version: str = Field(min_length=1, max_length=32)
    report_template_version: str = Field(min_length=1, max_length=32)
    seed: int = Field(ge=0, le=2**63 - 1)
    simulation_count: int = Field(ge=1, le=10_000_000)
    generated_at: datetime
    analysis_date: date


class CompanySnapshot(FrozenModel):
    name: str = Field(min_length=1, max_length=300)
    scenario_name: str = Field(min_length=1, max_length=200)
    sector: str | None = Field(default=None, max_length=160)
    stage: str | None = Field(default=None, max_length=80)
    business_model: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=80)
    currency: str = Field(default="BRL", min_length=3, max_length=3)


class Histogram(FrozenModel):
    edges: tuple[FiniteNumber, ...]
    counts: tuple[int, ...]

    @model_validator(mode="after")
    def validate_bins(self) -> Histogram:
        if len(self.edges) != len(self.counts) + 1 or not self.counts:
            raise ValueError("histogram edges must be one longer than counts")
        if any(left >= right for left, right in pairwise(self.edges)):
            raise ValueError("histogram edges must be strictly increasing")
        if any(count < 0 for count in self.counts):
            raise ValueError("histogram counts must be nonnegative")
        return self


class ValuationSummary(FrozenModel):
    basis: str = Field(min_length=1, max_length=120)
    percentiles: dict[PercentileKey, FiniteNumber]
    mean: FiniteNumber
    standard_deviation: NonNegativeNumber
    failure_probability: Probability
    uncertainty_label: Literal["LOW", "MODERATE", "HIGH", "VERY HIGH", "NOT AVAILABLE"]
    uncertainty_ratio: NonNegativeNumber | None = None
    breakeven_probabilities: dict[str, Probability] = Field(default_factory=dict)
    breakeven_month_percentiles: dict[str, NonNegativeNumber] = Field(default_factory=dict)
    histogram: Histogram | None = None

    @model_validator(mode="after")
    def validate_percentiles(self) -> ValuationSummary:
        required: tuple[PercentileKey, ...] = ("p5", "p10", "p25", "p50", "p75", "p90", "p95")
        if set(self.percentiles) != set(required):
            raise ValueError("percentiles must contain p5, p10, p25, p50, p75, p90 and p95")
        ordered = [self.percentiles[key] for key in required]
        if any(left > right for left, right in pairwise(ordered)):
            raise ValueError("percentiles must be nondecreasing")
        return self


class Assumption(FrozenModel):
    name: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=500)
    unit: str | None = Field(default=None, max_length=60)
    source: str | None = Field(default=None, max_length=160)


class MethodMetric(FrozenModel):
    name: str = Field(min_length=1, max_length=160)
    value: str = Field(min_length=1, max_length=160)
    explanation: str | None = Field(default=None, max_length=600)


class MethodAnalysis(FrozenModel):
    status: Literal["available", "not_available", "invalid"]
    metrics: tuple[MethodMetric, ...] = ()
    note: str | None = Field(default=None, max_length=1000)


class Driver(FrozenModel):
    name: str = Field(min_length=1, max_length=160)
    association: Annotated[float | None, Field(ge=-1.0, le=1.0)] = None
    contribution: Annotated[float | None, Field(ge=0.0, le=1.0)] = None
    direction: Literal["positive", "negative", "neutral"] | None = None
    population: str = Field(default="unconditional", min_length=1, max_length=120)
    sample_size: int = Field(ge=0)
    status: Literal["estimated", "not_estimable_constant", "insufficient_data"] = "estimated"


class ConditionalDistribution(FrozenModel):
    p25: FiniteNumber
    median: FiniteNumber
    p75: FiniteNumber

    @model_validator(mode="after")
    def validate_order(self) -> ConditionalDistribution:
        if not self.p25 <= self.median <= self.p75:
            raise ValueError("conditional distribution must satisfy p25 <= median <= p75")
        return self


class TargetMetric(FrozenModel):
    name: str = Field(min_length=1, max_length=160)
    unit: str | None = Field(default=None, max_length=40)
    target_hit: ConditionalDistribution | None = None
    target_miss: ConditionalDistribution | None = None


class TargetAnalysis(FrozenModel):
    target_value: FiniteNumber
    probability: Probability
    hit_count: int = Field(ge=0)
    miss_count: int = Field(ge=0)
    metrics: tuple[TargetMetric, ...] = ()

    @property
    def observation_count(self) -> int:
        return self.hit_count + self.miss_count


class RiskSummary(FrozenModel):
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    downside_notes: tuple[str, ...] = ()
    upside_notes: tuple[str, ...] = ()


class ReportData(FrozenModel):
    audit: AuditMetadata
    company: CompanySnapshot
    valuation: ValuationSummary
    assumptions: tuple[Assumption, ...]
    dcf: MethodAnalysis
    venture_capital: MethodAnalysis
    drivers: tuple[Driver, ...] = ()
    target: TargetAnalysis | None = None
    risks: RiskSummary = Field(default_factory=RiskSummary)
    disclaimer: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_cross_fields(self) -> ReportData:
        if (
            self.valuation.histogram is not None
            and sum(self.valuation.histogram.counts) != self.audit.simulation_count
        ):
            raise ValueError("histogram counts must equal simulation_count")
        if self.target is not None:
            if self.target.observation_count != self.audit.simulation_count:
                raise ValueError("target hit_count + miss_count must equal simulation_count")
            observed = self.target.hit_count / self.audit.simulation_count
            tolerance = max(1e-12, 0.5 / self.audit.simulation_count)
            if abs(observed - self.target.probability) > tolerance:
                raise ValueError("target probability must agree with hit_count/simulation_count")
        for driver in self.drivers:
            if driver.status == "estimated" and driver.association is None:
                raise ValueError("estimated drivers require an association")
            if driver.sample_size > self.audit.simulation_count:
                raise ValueError("driver sample_size cannot exceed simulation_count")
        values = [
            self.valuation.mean,
            self.valuation.standard_deviation,
            *self.valuation.percentiles.values(),
        ]
        if not all(isfinite(value) for value in values):
            raise ValueError("report values must be finite")
        return self
