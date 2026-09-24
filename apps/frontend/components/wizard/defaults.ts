import type { ValuationWizardDraft } from "./types";

export const DRAFT_STORAGE_KEY = "startupvalue:valuation-draft:v1";

export const DEFAULT_DRAFT: ValuationWizardDraft = {
  schemaVersion: 1,
  mode: "simple",
  company: {
    name: "",
    sector: "",
    country: "Brasil",
    businessModel: "saas",
    stage: "seed",
    foundingYear: new Date().getFullYear(),
    scenarioName: "Base case",
  },
  revenue: { cadence: "annual", years: [0, 0, 0, 0, 0] },
  operatingCosts: {
    administrative: 0,
    salesMarketing: 0,
    headcount: 0,
    general: 0,
    infrastructure: 0,
    capex: 0,
    other: 0,
  },
  metrics: {
    arr: null,
    mrr: null,
    grossMargin: null,
    churnMonthly: null,
    cac: null,
    ltv: null,
    burnMonthly: null,
    runwayMonths: null,
    cash: 0,
    debt: 0,
  },
  valuation: {
    wacc: 25,
    terminalGrowth: 4,
    vcTargetReturn: 40,
    exitMultiple: 6,
    targetOwnership: 20,
    investmentAmount: 0,
    investmentHorizonYears: 5,
  },
  monteCarlo: {
    simulationCount: 10_000,
    randomSeed: 471829,
    uncertaintyLevel: "medium",
    distribution: "lognormal",
    revenueUncertainty: 25,
    marginUncertainty: 15,
    costUncertainty: 15,
    failureProbability: 15,
    serialCorrelation: 0.65,
    studentDegreesFreedom: 5,
    triangularMinimum: 0.65,
    triangularMode: 1,
    triangularMaximum: 1.5,
  },
  updatedAt: new Date(0).toISOString(),
};

export const UNCERTAINTY_PRESETS = {
  low: { revenueUncertainty: 12, marginUncertainty: 8, costUncertainty: 8 },
  medium: { revenueUncertainty: 25, marginUncertainty: 15, costUncertainty: 15 },
  high: { revenueUncertainty: 40, marginUncertainty: 25, costUncertainty: 25 },
} as const;

export function freshDraft(): ValuationWizardDraft {
  return structuredClone({ ...DEFAULT_DRAFT, updatedAt: new Date().toISOString() });
}
