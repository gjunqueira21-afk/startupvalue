export type WizardMode = "simple" | "professional";

export type RevenueCadence = "annual" | "monthly";

export type UncertaintyLevel = "low" | "medium" | "high";

export type DistributionKind = "lognormal" | "student_t" | "triangular" | "uniform";

export type BusinessModel =
  | "saas"
  | "marketplace"
  | "transactional"
  | "ecommerce"
  | "services"
  | "other";

export type StartupStage =
  | "pre_revenue"
  | "seed"
  | "series_a"
  | "growth"
  | "late_stage";

export type OperatingCostKey =
  | "administrative"
  | "salesMarketing"
  | "headcount"
  | "general"
  | "infrastructure"
  | "capex"
  | "other";

export interface CompanyInputs {
  name: string;
  sector: string;
  country: string;
  businessModel: BusinessModel;
  stage: StartupStage;
  foundingYear: number;
  scenarioName: string;
}

export interface RevenueInputs {
  cadence: RevenueCadence;
  years: [number, number, number, number, number];
}

export type OperatingCosts = Record<OperatingCostKey, number>;

export interface StartupMetrics {
  arr: number | null;
  mrr: number | null;
  grossMargin: number | null;
  churnMonthly: number | null;
  cac: number | null;
  ltv: number | null;
  burnMonthly: number | null;
  runwayMonths: number | null;
  cash: number;
  debt: number;
}

export type TerminalMethod = "gordon" | "exit_multiple";
export type TerminalMetric = "revenue" | "ebitda";

/** Optional uncertainty range; the fixed field is its most likely value. */
export interface RangeInput {
  enabled: boolean;
  minimum: number;
  maximum: number;
}

export interface ValuationRanges {
  wacc: RangeInput;
  terminalGrowth: RangeInput;
  terminalMultiple: RangeInput;
}

export interface ValuationAssumptions {
  wacc: number;
  terminalGrowth: number;
  terminalMethod: TerminalMethod;
  terminalMetric: TerminalMetric;
  terminalMultiple: number;
  ranges: ValuationRanges;
  vcTargetReturn: number;
  exitMultiple: number;
  targetOwnership: number;
  investmentAmount: number;
  investmentHorizonYears: number;
}

export interface MonteCarloAssumptions {
  simulationCount: 1_000 | 5_000 | 10_000 | 25_000;
  randomSeed: number;
  uncertaintyLevel: UncertaintyLevel;
  distribution: DistributionKind;
  revenueUncertainty: number;
  marginUncertainty: number;
  costUncertainty: number;
  failureProbability: number;
  serialCorrelation: number;
  studentDegreesFreedom: number;
  triangularMinimum: number;
  triangularMode: number;
  triangularMaximum: number;
}

export interface ValuationWizardDraft {
  schemaVersion: 1;
  mode: WizardMode;
  company: CompanyInputs;
  revenue: RevenueInputs;
  operatingCosts: OperatingCosts;
  metrics: StartupMetrics;
  valuation: ValuationAssumptions;
  monteCarlo: MonteCarloAssumptions;
  updatedAt: string;
}

export type WizardStep = 0 | 1 | 2 | 3 | 4 | 5 | 6;

export type ValidationErrors = Record<string, string>;
