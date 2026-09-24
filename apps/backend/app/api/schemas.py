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


def distribution_support(value: DistributionInput) -> tuple[float, float]:
    """Closed support bounds used to prove rate constraints hold in every scenario."""
    if value.kind == "constant":
        assert value.value is not None
        return value.value, value.value
    if value.kind in {"triangular", "uniform"}:
        assert value.minimum is not None and value.maximum is not None
        return value.minimum, value.maximum
    if value.kind in {"normal", "student_t"}:
        return (
            value.lower if value.lower is not None else float("-inf"),
            value.upper if value.upper is not None else float("inf"),
        )
    return 0.0, float("inf")


class TornadoSettings(ApiModel):
    """Swing applied to fixed assumptions in the one-at-a-time sensitivity."""

    model_config = ConfigDict(allow_inf_nan=False)

    wacc_delta: float = Field(default=0.03, gt=0, le=0.5)
    terminal_growth_delta: float = Field(default=0.01, gt=0, le=0.2)
    exit_multiple_relative_delta: float = Field(default=0.25, gt=0, lt=1)
    failure_probability_delta: float = Field(default=0.10, gt=0, le=1)


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
    wacc_uncertainty: DistributionInput | None = None
    terminal_growth_uncertainty: DistributionInput | None = None
    terminal_method: Literal["gordon", "exit_multiple"] = "gordon"
    exit_multiple: float | None = Field(default=None, gt=0, le=200)
    exit_metric: Literal["revenue", "ebitda"] | None = None
    exit_multiple_uncertainty: DistributionInput | None = None
    tornado: TornadoSettings = Field(default_factory=TornadoSettings)

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
        self._validate_terminal_method()
        self._validate_rate_supports()
        return self

    def _validate_terminal_method(self) -> None:
        exit_fields = (self.exit_multiple, self.exit_metric, self.exit_multiple_uncertainty)
        if self.terminal_method == "gordon":
            if any(value is not None for value in exit_fields):
                raise ValueError("exit multiple fields require terminal_method='exit_multiple'")
            return
        if self.monthly_fcff is not None:
            raise ValueError("exit multiple terminal value requires structured projections")
        if self.exit_multiple is None or self.exit_metric is None:
            raise ValueError("exit multiple terminal value requires exit_multiple and exit_metric")
        if self.terminal_growth is not None or self.terminal_growth_uncertainty is not None:
            raise ValueError("choose either a perpetuity growth or an exit multiple")
        if self.exit_multiple_uncertainty is not None:
            low, high = distribution_support(self.exit_multiple_uncertainty)
            if low < 0:
                raise ValueError("exit_multiple_uncertainty must have a non-negative support")
            if not low <= self.exit_multiple <= high:
                raise ValueError("exit_multiple must lie inside exit_multiple_uncertainty")

    def _validate_rate_supports(self) -> None:
        if self.terminal_growth_uncertainty is not None and self.terminal_growth is None:
            raise ValueError("terminal_growth_uncertainty requires a terminal_growth base")
        growth_high = self.terminal_growth
        if self.terminal_growth_uncertainty is not None:
            assert self.terminal_growth is not None
            growth_low, growth_high = distribution_support(self.terminal_growth_uncertainty)
            if growth_low <= -1 or growth_high == float("inf"):
                raise ValueError("terminal_growth_uncertainty needs a bounded support above -100%")
            if not growth_low <= self.terminal_growth <= growth_high:
                raise ValueError("terminal_growth must lie inside terminal_growth_uncertainty")
        wacc_low = self.annual_wacc
        if self.wacc_uncertainty is not None:
            wacc_low, wacc_high = distribution_support(self.wacc_uncertainty)
            if wacc_low <= -1:
                raise ValueError("wacc_uncertainty needs a support above -100%")
            if not wacc_low <= self.annual_wacc <= wacc_high:
                raise ValueError("annual_wacc must lie inside wacc_uncertainty")
        if growth_high is not None and growth_high >= wacc_low:
            raise ValueError("terminal growth must stay below WACC in every scenario")


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


class TornadoItemSummary(ApiModel):
    parameter: Literal["annual_wacc", "terminal_growth", "exit_multiple", "failure_probability"]
    base_level: float
    low_level: float
    high_level: float
    value_at_low: float
    value_at_high: float
    swing: float = Field(ge=0)
    level_source: Literal["base_plus_minus_delta", "distribution_p10_p90"]
    clamped: bool


class TornadoSummary(ApiModel):
    method: Literal["one_at_a_time_common_random_numbers"]
    method_version: str
    statistic: Literal["p50"]
    base_value: float
    items: list[TornadoItemSummary]


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
    sensitivity: TornadoSummary | None = None
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


class TornadoItemResponse(TornadoItemSummary):
    label: str
    unit: VariableUnit | None


class TornadoResponse(ApiModel):
    method: Literal["one_at_a_time_common_random_numbers"]
    method_version: str
    statistic: Literal["p50"]
    base_value: float
    items: list[TornadoItemResponse]


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
    tornado: TornadoResponse | None = None


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


class UncertaintyInsightResponse(ApiModel):
    label: Literal["LOW", "MODERATE", "HIGH", "VERY HIGH"]
    label_pt: str
    reason: str
    sentence: str


class DriverInsightResponse(ApiModel):
    name: str
    label: str
    contribution: float
    direction: str | None


class TailInsightResponse(ApiModel):
    name: str
    label: str
    kind: Literal["continuous", "binary"]
    direction: Literal["higher", "lower"]
    text: str


class ConditionInsightResponse(ApiModel):
    name: str
    label: str
    unit: VariableUnit | None
    kind: Literal["continuous", "binary"]
    direction: Literal["higher", "lower"]
    hit_value: float
    miss_value: float
    cliffs_delta: float
    threshold: float | None


class TargetInsightResponse(ApiModel):
    target: float
    probability: float
    hit_count: int
    scenario_count: int
    wilson95_low: float
    wilson95_high: float
    sample_note: Literal["ok", "small_group", "insufficient", "empty_group"]
    headline: str
    probability_sentence: str
    interpretation: str
    statements: list[str]
    conditions: list[ConditionInsightResponse]
    disclaimer: str


class InsightResponse(ApiModel):
    simulation_id: str
    result_hash: str
    template_version: str
    headline: str
    valuation_paragraphs: list[str]
    uncertainty: UncertaintyInsightResponse
    key_drivers_sentence: str | None
    key_drivers: list[DriverInsightResponse]
    upside: list[TailInsightResponse]
    downside: list[TailInsightResponse]
    sensitivity_sentence: str | None
    risks: list[str]
    target: TargetInsightResponse | None
    executive_summary: list[str]
    method_notes: list[str]


class SimulationResponse(ApiModel):
    simulation_id: str
    scenario_revision_id: str
    model_version: str
    tax_version: str
    seed: int
    simulation_count: int
    status: str
    company_name: str | None = None
    scenario_name: str | None = None
    currency: str = "BRL"
    execution: Literal["synchronous"] = "synchronous"
    queue_status: Literal["not_configured"] = "not_configured"
    summary: SimulationSummary | None
    result_hash: str | None
    created_at: datetime
