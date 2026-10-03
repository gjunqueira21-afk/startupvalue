import type { RangeInput, TerminalMetric, ValuationWizardDraft } from "@/components/wizard/types";
import { apiRequest } from "./client";

export interface CreateSimulationResponse {
  simulation_id: string;
  scenario_revision_id: string;
  model_version: string;
  tax_version: string;
  seed: number;
  simulation_count: number;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  result_hash: string | null;
}

export type UncertaintyLabel = "LOW" | "MODERATE" | "HIGH" | "VERY HIGH";
export type VariableUnit = "currency" | "ratio" | "multiplier" | "binary";

export interface UncertaintyAssessment {
  label: UncertaintyLabel;
  reason: "iqr_ratio" | "median_not_positive" | "material_non_positive_mass";
  rule_version: string;
  iqr: number;
  iqr_ratio: number | null;
  spread80: number;
  spread80_ratio: number | null;
  non_positive_probability: number;
}

export interface RankedDriverSummary {
  name: string;
  rho: number | null;
  srrc: number | null;
  contribution: number | null;
  direction: "positive" | "negative" | "neutral" | null;
  status: string;
}

export interface DriverRankingSummary {
  method: "spearman+srrc";
  method_version: string;
  scenario_count: number;
  r_squared: number | null;
  warnings: string[];
  items: RankedDriverSummary[];
}

/** A single value-to-metric multiple distribution (Task 2 payload shape). */
export interface MultipleSummary {
  p25: number;
  p50: number;
  p75: number;
  eligible_count: number;
  excluded_count: number;
}

/**
 * Multiples implied by the user's own assumptions (valuation / year-5 metric
 * across simulated scenarios) — NOT market multiples. Stripped for free-plan
 * workspaces, so it may be absent even when the simulation has a summary.
 */
export interface ImpliedMultiples {
  status: "available" | "not_available";
  reason: string | null;
  basis: string;
  value_to_revenue: MultipleSummary | null;
  value_to_ebitda: MultipleSummary | null;
}

export interface SimulationSummary {
  basis: string;
  percentiles: Record<"p5" | "p10" | "p25" | "p50" | "p75" | "p90" | "p95", number>;
  minimum: number;
  maximum: number;
  mean: number;
  standard_deviation: number;
  failure_probability: number;
  uncertainty_label: UncertaintyLabel | "NOT AVAILABLE";
  uncertainty_ratio: number | null;
  uncertainty?: UncertaintyAssessment | null;
  drivers?: DriverRankingSummary | null;
  breakeven_probabilities: Record<string, number>;
  breakeven_month_percentiles: Record<string, number>;
  non_positive_probability: number;
  histogram?: { edges: number[]; counts: number[] };
  implied_multiples?: ImpliedMultiples | null;
}

export interface Driver extends RankedDriverSummary {
  label: string;
  unit: VariableUnit | null;
  count: number;
}

export interface TornadoItem {
  parameter: "annual_wacc" | "terminal_growth" | "exit_multiple" | "failure_probability";
  label: string;
  unit: VariableUnit | null;
  base_level: number;
  low_level: number;
  high_level: number;
  value_at_low: number;
  value_at_high: number;
  swing: number;
  level_source: "base_plus_minus_delta" | "distribution_p10_p90";
  clamped: boolean;
}

export interface TornadoResponse {
  method: "one_at_a_time_common_random_numbers";
  method_version: string;
  statistic: "p50";
  base_value: number;
  items: TornadoItem[];
}

export interface DecisionResponse {
  simulation_id: string;
  result_hash: string;
  basis: string;
  scenario_count: number;
  method: "spearman+srrc";
  method_version: string;
  population: "unconditional";
  r_squared: number | null;
  warnings: string[];
  drivers: Driver[];
  tornado: TornadoResponse | null;
}

export interface TailInsight {
  name: string;
  label: string;
  kind: "continuous" | "binary";
  direction: "higher" | "lower";
  text: string;
}

export interface ConditionInsight {
  name: string;
  label: string;
  unit: VariableUnit | null;
  kind: "continuous" | "binary";
  direction: "higher" | "lower";
  hit_value: number;
  miss_value: number;
  cliffs_delta: number;
  threshold: number | null;
}

/** One point of the reference revenue trajectory built from the required CAGR (Task 4 payload shape). */
export interface YearTarget {
  year: number;
  revenue: number;
}

/**
 * Reverse-engineered plan for reaching a valuation target: the required
 * revenue CAGR and EBITDA margin among scenarios that hit it, contrasted
 * with scenarios that miss it (Task 4 payload shape, `TargetResponse.plan`).
 * Null when the workspace is not entitled to this section.
 */
export interface TargetPlan {
  status: "available" | "insufficient_hits" | "not_available_for_inputs";
  hit_count: number;
  required_revenue_cagr: number | null;
  hit_ebitda_margin: number | null;
  miss_revenue_cagr: number | null;
  miss_ebitda_margin: number | null;
  trajectory: YearTarget[];
}

export interface ConditionalStatistics {
  count: number;
  p25: number | null;
  p50: number | null;
  p75: number | null;
  reason: string | null;
}

export interface TargetComparison {
  name: string;
  label: string;
  unit: VariableUnit | null;
  role: "driver" | "outcome";
  hit: ConditionalStatistics;
  miss: ConditionalStatistics;
  median_difference_hit_minus_miss: number | null;
  status: string;
}

/** Mirror of `GET /api/v1/simulations/{id}/target` (`TargetResponse`, Task 4 shape). */
export interface TargetResponse {
  simulation_id: string;
  result_hash: string;
  basis: string;
  target: number;
  scenario_count: number;
  hit_count: number;
  miss_count: number;
  probability: number;
  wilson95_low: number;
  wilson95_high: number;
  comparisons: TargetComparison[];
  plan: TargetPlan | null;
}

export interface TargetInsight {
  target: number;
  probability: number;
  hit_count: number;
  scenario_count: number;
  wilson95_low: number;
  wilson95_high: number;
  sample_note: "ok" | "small_group" | "insufficient" | "empty_group";
  headline: string;
  probability_sentence: string;
  interpretation: string;
  statements: string[];
  conditions: ConditionInsight[];
  disclaimer: string;
}

export interface InsightResponse {
  simulation_id: string;
  result_hash: string;
  template_version: string;
  headline: string;
  valuation_paragraphs: string[];
  uncertainty: { label: UncertaintyLabel; label_pt: string; reason: string; sentence: string };
  key_drivers_sentence: string | null;
  key_drivers: { name: string; label: string; contribution: number; direction: string | null }[];
  upside: TailInsight[];
  downside: TailInsight[];
  sensitivity_sentence: string | null;
  risks: string[];
  target: TargetInsight | null;
  executive_summary: string[];
  method_notes: string[];
}

export interface SimulationResponse extends CreateSimulationResponse {
  company_name: string | null;
  scenario_name: string | null;
  currency: string;
  execution: "synchronous";
  queue_status: "not_configured";
  summary: SimulationSummary | null;
  created_at: string;
}

interface StartupResponse {
  id: string;
}

interface ScenarioResponse {
  id: string;
}

interface RevisionResponse {
  id: string;
}

type DistributionPayload =
  | { kind: "constant"; value: number }
  | { kind: "lognormal"; mean: number; coefficient_of_variation: number }
  | {
      kind: "student_t";
      mean: number;
      standard_deviation: number;
      degrees_of_freedom: number;
      lower: number;
    }
  | { kind: "triangular"; minimum: number; mode: number; maximum: number }
  | { kind: "uniform"; minimum: number; maximum: number };

function monthlyRevenue(draft: ValuationWizardDraft): number[] {
  return draft.revenue.years.flatMap((value) =>
    Array.from({ length: 12 }, () => draft.revenue.cadence === "annual" ? value / 12 : value),
  );
}

function monthlyOpex(draft: ValuationWizardDraft): number[] {
  const annual = Object.entries(draft.operatingCosts)
    .filter(([key]) => key !== "capex")
    .reduce((sum, [, value]) => sum + value, 0);
  return Array.from({ length: 60 }, () => annual / 12);
}

function revenueUncertainty(draft: ValuationWizardDraft): DistributionPayload {
  const cv = draft.monteCarlo.revenueUncertainty / 100;
  if (cv === 0) return { kind: "constant", value: 1 };
  if (draft.monteCarlo.distribution === "student_t") {
    return {
      kind: "student_t",
      mean: 1,
      standard_deviation: cv,
      degrees_of_freedom: draft.monteCarlo.studentDegreesFreedom,
      lower: 0,
    };
  }
  if (draft.monteCarlo.distribution === "triangular") {
    return {
      kind: "triangular",
      minimum: draft.monteCarlo.triangularMinimum,
      mode: draft.monteCarlo.triangularMode,
      maximum: draft.monteCarlo.triangularMaximum,
    };
  }
  if (draft.monteCarlo.distribution === "uniform") {
    return { kind: "uniform", minimum: Math.max(0, 1 - cv), maximum: 1 + cv };
  }
  return { kind: "lognormal", mean: 1, coefficient_of_variation: cv };
}

function profilePayload(draft: ValuationWizardDraft) {
  return {
    sector: draft.company.sector,
    country: draft.company.country,
    business_model: draft.company.businessModel,
    stage: draft.company.stage,
    founding_year: draft.company.foundingYear,
    revenue: draft.revenue,
    operating_costs: draft.operatingCosts,
    metrics: draft.metrics,
    valuation_assumptions: draft.valuation,
    monte_carlo_assumptions: draft.monteCarlo,
    wizard_schema_version: draft.schemaVersion,
  };
}

interface TriangularPayload {
  kind: "triangular";
  minimum: number;
  mode: number;
  maximum: number;
}

/** Mirror of the backend CanonicalValuationInputs contract (structured model). */
export interface CanonicalInputsPayload {
  monthly_revenue: number[];
  monthly_opex: number[];
  monthly_capex: number[];
  gross_margin: number;
  revenue_uncertainty: DistributionPayload;
  cost_uncertainty: DistributionPayload;
  margin_uncertainty_pp: number;
  serial_correlation: number;
  persistent_weight: number;
  annual_wacc: number;
  wacc_uncertainty?: TriangularPayload;
  terminal_growth?: number;
  terminal_growth_uncertainty?: TriangularPayload;
  terminal_method?: "exit_multiple";
  exit_metric?: TerminalMetric;
  exit_multiple?: number;
  exit_multiple_uncertainty?: TriangularPayload;
  excess_cash: number;
  debt: number;
  failure_probability_horizon: number;
  liquidation_value: number;
}

function triangularRange(range: RangeInput, mostLikely: number, scale: number): TriangularPayload {
  return {
    kind: "triangular",
    minimum: range.minimum / scale,
    mode: mostLikely / scale,
    maximum: range.maximum / scale,
  };
}

/** Terminal value and valuation-parameter ranges; simple mode keeps a fixed perpetuity. */
function valuationOptions(
  draft: ValuationWizardDraft,
): Pick<
  CanonicalInputsPayload,
  | "wacc_uncertainty"
  | "terminal_growth"
  | "terminal_growth_uncertainty"
  | "terminal_method"
  | "exit_metric"
  | "exit_multiple"
  | "exit_multiple_uncertainty"
> {
  const { valuation } = draft;
  const professional = draft.mode === "professional";
  const ranges = valuation.ranges;
  const wacc = professional && ranges.wacc.enabled
    ? { wacc_uncertainty: triangularRange(ranges.wacc, valuation.wacc, 100) }
    : {};
  if (professional && valuation.terminalMethod === "exit_multiple") {
    return {
      ...wacc,
      terminal_method: "exit_multiple",
      exit_metric: valuation.terminalMetric,
      exit_multiple: valuation.terminalMultiple,
      ...(ranges.terminalMultiple.enabled
        ? { exit_multiple_uncertainty: triangularRange(ranges.terminalMultiple, valuation.terminalMultiple, 1) }
        : {}),
    };
  }
  return {
    ...wacc,
    terminal_growth: valuation.terminalGrowth / 100,
    ...(professional && ranges.terminalGrowth.enabled
      ? { terminal_growth_uncertainty: triangularRange(ranges.terminalGrowth, valuation.terminalGrowth, 100) }
      : {}),
  };
}

export function buildCanonicalInputs(draft: ValuationWizardDraft): CanonicalInputsPayload {
  if (draft.metrics.grossMargin === null) {
    throw new Error("Informe a margem bruta usada no DCF.");
  }
  return {
    monthly_revenue: monthlyRevenue(draft),
    monthly_opex: monthlyOpex(draft),
    monthly_capex: Array.from({ length: 60 }, () => draft.operatingCosts.capex / 12),
    gross_margin: draft.metrics.grossMargin / 100,
    revenue_uncertainty: revenueUncertainty(draft),
    cost_uncertainty: draft.monteCarlo.costUncertainty === 0
      ? { kind: "constant" as const, value: 1 }
      : { kind: "lognormal" as const, mean: 1, coefficient_of_variation: draft.monteCarlo.costUncertainty / 100 },
    margin_uncertainty_pp: draft.monteCarlo.marginUncertainty / 100,
    serial_correlation: draft.monteCarlo.serialCorrelation,
    persistent_weight: 0.6,
    annual_wacc: draft.valuation.wacc / 100,
    ...valuationOptions(draft),
    excess_cash: draft.metrics.cash,
    debt: draft.metrics.debt,
    failure_probability_horizon: draft.monteCarlo.failureProbability / 100,
    liquidation_value: 0,
  };
}

export async function createSimulation(
  draft: ValuationWizardDraft,
  signal?: AbortSignal,
): Promise<SimulationResponse> {
  const startup = await apiRequest<StartupResponse>("/api/v1/startups", {
    method: "POST",
    body: JSON.stringify({
      name: draft.company.name,
      currency: "BRL",
      profile: profilePayload(draft),
    }),
    signal,
  });
  const scenario = await apiRequest<ScenarioResponse>(
    `/api/v1/startups/${startup.id}/scenarios`,
    {
      method: "POST",
      body: JSON.stringify({ name: draft.company.scenarioName, mode: draft.mode }),
      signal,
    },
  );
  const revision = await apiRequest<RevisionResponse>(
    `/api/v1/scenarios/${scenario.id}/revisions`,
    {
      method: "POST",
      body: JSON.stringify({ inputs: buildCanonicalInputs(draft) }),
      signal,
    },
  );

  return apiRequest<SimulationResponse>("/api/v1/simulations", {
    method: "POST",
    body: JSON.stringify({
      scenario_revision_id: revision.id,
      seed: draft.monteCarlo.randomSeed,
      simulation_count: draft.monteCarlo.simulationCount,
      idempotency_key: `wizard:${draft.monteCarlo.randomSeed}:${revision.id.slice(0, 8)}`,
    }),
    signal,
  });
}

export function getSimulation(simulationId: string, signal?: AbortSignal) {
  return apiRequest<SimulationResponse>(`/api/v1/simulations/${simulationId}`, {
    method: "GET",
    signal,
  });
}

export function getDecision(simulationId: string, signal?: AbortSignal) {
  return apiRequest<DecisionResponse>(`/api/v1/simulations/${simulationId}/decision`, {
    method: "GET", signal,
  });
}


export function getInsight(simulationId: string, target: number | null, signal?: AbortSignal) {
  const query = target === null ? "" : `?target=${encodeURIComponent(target)}`;
  return apiRequest<InsightResponse>(`/api/v1/simulations/${simulationId}/insight${query}`, {
    method: "GET", signal,
  });
}

/** Fetches the same target's conditional comparisons plus the "Plano para a meta" plan (`plan: null` when not entitled). */
export function getTarget(simulationId: string, value: number, signal?: AbortSignal) {
  return apiRequest<TargetResponse>(`/api/v1/simulations/${simulationId}/target?value=${encodeURIComponent(value)}`, {
    method: "GET", signal,
  });
}
