import type { Entitlements } from "@/lib/api/branding";
import type { MonteCarloAssumptions } from "./types";

export type SimulationCountPreset = MonteCarloAssumptions["simulationCount"];

export const SIMULATION_COUNT_PRESETS: readonly SimulationCountPreset[] = [1_000, 5_000, 10_000, 25_000];

/**
 * Mirror of `max_scenarios_per_run` per paid tier in the backend matrix
 * (`app/core/entitlements.py`), lowest first — used only to label a locked
 * preset with the cheapest plan that unlocks it. The backend still enforces.
 */
const PLAN_SCENARIO_LIMITS: readonly [label: string, maxPerRun: number][] = [
  ["Empresário", 10_000],
  ["Consultor", 25_000],
];

export interface SimulationCountOption {
  value: SimulationCountPreset;
  allowed: boolean;
  /** Cheapest plan that unlocks a locked preset; null when allowed. */
  requiredPlan: string | null;
}

/**
 * Resolves the presets against the workspace's per-run cap. With no
 * entitlements (still loading or the fetch failed) every preset stays
 * selectable — the backend remains the enforcement point.
 */
export function simulationCountOptions(maxPerRun: number | null): SimulationCountOption[] {
  return SIMULATION_COUNT_PRESETS.map((value) => {
    const allowed = maxPerRun === null || value <= maxPerRun;
    const requiredPlan = allowed
      ? null
      : PLAN_SCENARIO_LIMITS.find(([, limit]) => value <= limit)?.[0] ?? "superior";
    return { value, allowed, requiredPlan };
  });
}

/** Highest preset the plan allows (the smallest preset if the cap is below all of them). */
export function highestAllowedPreset(maxPerRun: number): SimulationCountPreset {
  const allowed = SIMULATION_COUNT_PRESETS.filter((value) => value <= maxPerRun);
  return allowed.length > 0 ? allowed[allowed.length - 1] : SIMULATION_COUNT_PRESETS[0];
}

/**
 * Clamps a draft's count to the plan: a count above the cap becomes the
 * highest allowed preset; an allowed count is kept as the user chose it.
 */
export function clampSimulationCount(current: SimulationCountPreset, maxPerRun: number | null): SimulationCountPreset {
  if (maxPerRun === null || current <= maxPerRun) return current;
  return highestAllowedPreset(maxPerRun);
}

export type PlanLimitCode = "plan_limit_startups" | "plan_limit_scenarios";

export type SubmissionCheck = { ok: true } | { ok: false; code: PlanLimitCode };

/**
 * Decides, before ANY resource is created, whether a run can succeed under
 * the plan. A doomed run must never POST a startup (that would burn a slot).
 * `companyCount` is the number of active companies from `GET /startups`;
 * null entitlements / count mean "unknown" and defer to the backend.
 */
export function checkSubmission(params: {
  entitlements: Pick<Entitlements, "max_startups" | "max_scenarios_per_run"> | null;
  companyCount: number | null;
  createsCompany: boolean;
  simulationCount: number;
}): SubmissionCheck {
  const { entitlements, companyCount, createsCompany, simulationCount } = params;
  if (entitlements === null) return { ok: true };
  if (simulationCount > entitlements.max_scenarios_per_run) return { ok: false, code: "plan_limit_scenarios" };
  if (
    createsCompany
    && entitlements.max_startups !== null
    && companyCount !== null
    && companyCount >= entitlements.max_startups
  ) {
    return { ok: false, code: "plan_limit_startups" };
  }
  return { ok: true };
}

export const PLAN_LIMIT_MESSAGES: Record<PlanLimitCode, string> = {
  plan_limit_startups:
    "Seu plano atingiu o limite de empresas. Selecione uma empresa existente para rodar uma nova análise ou faça upgrade do plano.",
  plan_limit_scenarios:
    "A quantidade de cenários escolhida excede o limite do seu plano. Escolha uma quantidade menor ou faça upgrade do plano.",
};

/** Extracts a plan-limit code from an API error body (`{"detail": "plan_limit_…"}`). */
export function planLimitCode(details: unknown): PlanLimitCode | null {
  if (typeof details !== "object" || details === null) return null;
  const detail = (details as { detail?: unknown }).detail;
  return detail === "plan_limit_startups" || detail === "plan_limit_scenarios" ? detail : null;
}
