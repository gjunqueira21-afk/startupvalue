from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class SignupRequest(ApiModel):
    name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=256)
    workspace_name: str | None = Field(default=None, min_length=2, max_length=160)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        local, separator, domain = email.partition("@")
        if not separator or not local or "." not in domain or domain.startswith("."):
            raise ValueError("invalid email address")
        return email


class LoginRequest(ApiModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class SessionResponse(ApiModel):
    user_id: str
    workspace_id: str
    name: str
    email: str
    role: str
    expires_at: datetime


class MessageResponse(ApiModel):
    message: str


class StartupCreate(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    currency: str = Field(default="BRL", pattern=r"^[A-Z]{3}$")
    profile: dict[str, Any] = Field(default_factory=dict)


class StartupResponse(ApiModel):
    id: str
    workspace_id: str
    name: str
    currency: str
    profile: dict[str, Any]
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ScenarioCreate(ApiModel):
    name: str = Field(min_length=1, max_length=160)
    mode: Literal["simple", "professional"] = "simple"


class ScenarioResponse(ApiModel):
    id: str
    workspace_id: str
    startup_id: str
    name: str
    mode: str
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DistributionInput(ApiModel):
    model_config = ConfigDict(allow_inf_nan=False)

    kind: Literal["constant", "normal", "student_t", "triangular", "uniform", "lognormal"]
    value: float | None = None
    mean: float = 1.0
    standard_deviation: float | None = Field(default=None, gt=0)
    coefficient_of_variation: float | None = Field(default=None, ge=0)
    degrees_of_freedom: float | None = Field(default=None, gt=2)
    minimum: float | None = None
    mode: float | None = None
    maximum: float | None = None
    lower: float | None = None
    upper: float | None = None

    @model_validator(mode="after")
    def validate_parameters(self) -> DistributionInput:
        required: dict[str, tuple[str, ...]] = {
            "constant": ("value",),
            "normal": ("standard_deviation",),
            "student_t": ("standard_deviation", "degrees_of_freedom"),
            "triangular": ("minimum", "mode", "maximum"),
            "uniform": ("minimum", "maximum"),
            "lognormal": ("coefficient_of_variation",),
        }
        missing = [name for name in required[self.kind] if getattr(self, name) is None]
        if missing:
            raise ValueError(f"missing parameters for {self.kind}: {', '.join(missing)}")
        if self.kind == "triangular":
            assert self.minimum is not None and self.mode is not None and self.maximum is not None
            if not self.minimum <= self.mode <= self.maximum:
                raise ValueError("triangular requires minimum <= mode <= maximum")
        if self.kind == "uniform":
            assert self.minimum is not None and self.maximum is not None
            if self.minimum >= self.maximum:
                raise ValueError("uniform requires minimum < maximum")
        if self.lower is not None and self.upper is not None and self.lower >= self.upper:
            raise ValueError("lower must be less than upper")
        return self


class CanonicalValuationInputs(ApiModel):
    model_config = ConfigDict(allow_inf_nan=False)

    monthly_fcff: list[float] | None = Field(default=None, min_length=1, max_length=120)
    monthly_revenue: list[float] | None = Field(default=None, min_length=60, max_length=60)
    monthly_opex: list[float] | None = Field(default=None, min_length=60, max_length=60)
    monthly_capex: list[float] | None = Field(default=None, min_length=60, max_length=60)
    gross_margin: float | None = Field(default=None, ge=0, le=1)
    revenue_uncertainty: DistributionInput | None = None
    cost_uncertainty: DistributionInput | None = None
    margin_uncertainty_pp: float = Field(default=0.0, ge=0, le=1)
    serial_correlation: float = Field(default=0.0, gt=-1, lt=1)
    persistent_weight: float = Field(default=1.0, ge=0, le=1)
    annual_wacc: float = Field(gt=-1, le=5)
    terminal_growth: float | None = Field(default=None, gt=-1, le=1)
    excess_cash: float = 0.0
    debt: float = Field(default=0.0, ge=0)
    uncertainty: DistributionInput | None = None
    failure_probability_horizon: float = Field(default=0.0, ge=0, le=1)
    liquidation_value: float = 0.0

    @field_validator("monthly_revenue", "monthly_opex", "monthly_capex")
    @classmethod
    def nonnegative_projection(cls, value: list[float] | None) -> list[float] | None:
        if value is not None and any(item < 0 for item in value):
            raise ValueError("structured monthly projections must be non-negative")
        return value

    @staticmethod
    def _validate_nonnegative_factor(value: DistributionInput, name: str) -> None:
        lower: float | None
        if value.kind == "constant":
            lower = value.value
        elif value.kind in {"triangular", "uniform"}:
            lower = value.minimum
        elif value.kind in {"normal", "student_t"}:
            lower = value.lower
        else:
            lower = value.mean
        if lower is None or lower < 0:
            raise ValueError(f"{name} must have a non-negative support")

    @model_validator(mode="after")
    def validate_valuation_model(self) -> CanonicalValuationInputs:
        if self.terminal_growth is not None and self.terminal_growth >= self.annual_wacc:
            raise ValueError("terminal growth must be lower than WACC")
        structured = (
            self.monthly_revenue, self.monthly_opex, self.monthly_capex,
            self.gross_margin, self.revenue_uncertainty, self.cost_uncertainty,
        )
        if self.monthly_fcff is not None:
            if any(value is not None for value in structured):
                raise ValueError("monthly_fcff cannot be combined with structured projections")
            if self.uncertainty is None:
                raise ValueError("uncertainty is required with monthly_fcff")
        else:
            if any(value is None for value in structured):
                raise ValueError(
                    "structured projections require revenue, opex, capex, gross margin "
                    "and both uncertainties"
                )
            if self.uncertainty is not None:
                raise ValueError("uncertainty belongs to the monthly_fcff model")
            assert self.revenue_uncertainty is not None
            assert self.cost_uncertainty is not None
            self._validate_nonnegative_factor(self.revenue_uncertainty, "revenue_uncertainty")
            self._validate_nonnegative_factor(self.cost_uncertainty, "cost_uncertainty")
        return self


class RevisionCreate(ApiModel):
    inputs: CanonicalValuationInputs


class RevisionResponse(ApiModel):
    id: str
    workspace_id: str
    scenario_id: str
    revision_no: int
    canonical_inputs: dict[str, Any]
    input_hash: str
    created_by: str
    created_at: datetime


class SimulationRunRequest(ApiModel):
    seed: int = Field(ge=0, le=2**63 - 1)
    simulation_count: Literal[1000, 5000, 10000, 25000] = 1000
    idempotency_key: str | None = Field(
        default=None, min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
    )


class SimulationCreateRequest(SimulationRunRequest):
    scenario_revision_id: str = Field(min_length=36, max_length=36)


class SimulationHistogram(ApiModel):
    edges: list[float]
    counts: list[int]


UncertaintyLabelValue = Literal["LOW", "MODERATE", "HIGH", "VERY HIGH", "NOT AVAILABLE"]


class UncertaintyResponse(ApiModel):
    label: Literal["LOW", "MODERATE", "HIGH", "VERY HIGH"]
    reason: Literal["iqr_ratio", "median_not_positive", "material_non_positive_mass"]
    rule_version: str
    iqr: float
    iqr_ratio: float | None
    spread80: float
    spread80_ratio: float | None
    non_positive_probability: float = Field(ge=0, le=1)


class RankedDriverSummary(ApiModel):
    name: str
    rho: float | None
    srrc: float | None
    contribution: float | None = Field(default=None, ge=0, le=1)
    direction: Literal["positive", "negative", "neutral"] | None
    status: str


class DriverRankingSummary(ApiModel):
    method: Literal["spearman+srrc"]
    method_version: str
    scenario_count: int
    r_squared: float | None
    warnings: list[str]
    items: list[RankedDriverSummary]


class SimulationSummary(ApiModel):
    basis: str
    percentiles: dict[Literal["p5", "p10", "p25", "p50", "p75", "p90", "p95"], float]
    minimum: float
    maximum: float
    mean: float
    standard_deviation: float
    failure_probability: float = Field(ge=0, le=1)
    uncertainty_label: UncertaintyLabelValue = "NOT AVAILABLE"
    uncertainty_ratio: float | None
    uncertainty: UncertaintyResponse | None = None
    drivers: DriverRankingSummary | None = None
    breakeven_probabilities: dict[str, float] = Field(default_factory=dict)
    breakeven_month_percentiles: dict[str, float] = Field(default_factory=dict)
    non_positive_probability: float
    histogram: SimulationHistogram | None = None
    vc_method: dict[str, Any] | None = None


VariableUnit = Literal["currency", "ratio", "multiplier", "binary"]


class DriverResponse(RankedDriverSummary):
    label: str
    unit: VariableUnit | None
    count: int


class DecisionResponse(ApiModel):
    simulation_id: str
    result_hash: str
    basis: str
    scenario_count: int
    method: Literal["spearman+srrc"] = "spearman+srrc"
    method_version: str
    population: Literal["unconditional"] = "unconditional"
    r_squared: float | None
    warnings: list[str]
    drivers: list[DriverResponse]


class ConditionalStatisticsResponse(ApiModel):
    count: int
    p25: float | None
    p50: float | None
    p75: float | None
    reason: str | None


class TargetComparisonResponse(ApiModel):
    name: str
    label: str
    unit: VariableUnit | None
    role: Literal["driver", "outcome"]
    hit: ConditionalStatisticsResponse
    miss: ConditionalStatisticsResponse
    median_difference_hit_minus_miss: float | None
    status: str


class TargetResponse(ApiModel):
    simulation_id: str
    result_hash: str
    basis: str
    target: float
    scenario_count: int
    hit_count: int
    miss_count: int
    probability: float
    wilson95_low: float
    wilson95_high: float
    comparisons: list[TargetComparisonResponse]


class SimulationResponse(ApiModel):
    simulation_id: str
    scenario_revision_id: str
    model_version: str
    tax_version: str
    seed: int
    simulation_count: int
    status: str
    execution: Literal["synchronous"] = "synchronous"
    queue_status: Literal["not_configured"] = "not_configured"
    summary: SimulationSummary | None
    result_hash: str | None
    created_at: datetime
