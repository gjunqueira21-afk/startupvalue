import { describe, expect, it } from "vitest";
import {
  ENTITLEMENTS_UNKNOWN_MESSAGE,
  PLAN_LIMIT_MESSAGES,
  checkSubmission,
  clampSimulationCount,
  highestAllowedPreset,
  planLimitCode,
  simulationCountOptions,
} from "./plan-limits";

const FREE = { max_startups: 1, max_scenarios_per_run: 1_000 };
const EMPRESARIO = { max_startups: 5, max_scenarios_per_run: 10_000 };
const ESCRITORIO = { max_startups: null, max_scenarios_per_run: 25_000 };

describe("simulationCountOptions", () => {
  it("locks every preset above the free cap and names the plan that unlocks it", () => {
    expect(simulationCountOptions(1_000)).toEqual([
      { value: 1_000, allowed: true, requiredPlan: null },
      { value: 5_000, allowed: false, requiredPlan: "Empresário" },
      { value: 10_000, allowed: false, requiredPlan: "Empresário" },
      { value: 25_000, allowed: false, requiredPlan: "Consultor" },
    ]);
  });

  it("only locks 25.000 for Empresário", () => {
    expect(simulationCountOptions(10_000).filter((option) => !option.allowed).map((option) => option.value)).toEqual([25_000]);
  });

  it("leaves everything selectable while entitlements are unknown", () => {
    expect(simulationCountOptions(null).every((option) => option.allowed)).toBe(true);
  });
});

describe("clampSimulationCount", () => {
  it("drops the 10.000 default to the highest allowed preset on free", () => {
    expect(highestAllowedPreset(1_000)).toBe(1_000);
    expect(clampSimulationCount(10_000, 1_000)).toBe(1_000);
  });

  it("clamps 25.000 to 10.000 on Empresário and keeps allowed choices", () => {
    expect(clampSimulationCount(25_000, 10_000)).toBe(10_000);
    expect(clampSimulationCount(5_000, 10_000)).toBe(5_000);
  });

  it("keeps the count when entitlements are unknown", () => {
    expect(clampSimulationCount(25_000, null)).toBe(25_000);
  });
});

describe("checkSubmission", () => {
  it("blocks a new company when the free workspace already has one", () => {
    expect(checkSubmission({ entitlements: FREE, companyCount: 1, createsCompany: true, simulationCount: 1_000 }))
      .toEqual({ ok: false, code: "plan_limit_startups", message: PLAN_LIMIT_MESSAGES.plan_limit_startups });
  });

  it("allows a run on the existing company at the cap", () => {
    expect(checkSubmission({ entitlements: FREE, companyCount: 1, createsCompany: false, simulationCount: 1_000 }))
      .toEqual({ ok: true });
  });

  it("allows the first company on free", () => {
    expect(checkSubmission({ entitlements: FREE, companyCount: 0, createsCompany: true, simulationCount: 1_000 }))
      .toEqual({ ok: true });
  });

  it("blocks a count above the per-run cap before any company is created", () => {
    expect(checkSubmission({ entitlements: FREE, companyCount: 0, createsCompany: true, simulationCount: 10_000 }))
      .toEqual({ ok: false, code: "plan_limit_scenarios", message: PLAN_LIMIT_MESSAGES.plan_limit_scenarios });
    expect(checkSubmission({ entitlements: EMPRESARIO, companyCount: 0, createsCompany: true, simulationCount: 25_000 }))
      .toEqual({ ok: false, code: "plan_limit_scenarios", message: PLAN_LIMIT_MESSAGES.plan_limit_scenarios });
  });

  it("never caps companies on unlimited plans", () => {
    expect(checkSubmission({ entitlements: ESCRITORIO, companyCount: 500, createsCompany: true, simulationCount: 25_000 }))
      .toEqual({ ok: true });
  });

  it("fails closed at submit when entitlements could not be fetched", () => {
    expect(checkSubmission({ entitlements: null, companyCount: null, createsCompany: true, simulationCount: 25_000 }))
      .toEqual({ ok: false, message: ENTITLEMENTS_UNKNOWN_MESSAGE });
  });

  it("still defers to the backend when only the company count is unknown", () => {
    expect(checkSubmission({ entitlements: FREE, companyCount: null, createsCompany: true, simulationCount: 1_000 }))
      .toEqual({ ok: true });
  });
});

describe("planLimitCode", () => {
  it("extracts plan-limit codes from a FastAPI error body", () => {
    expect(planLimitCode({ detail: "plan_limit_startups" })).toBe("plan_limit_startups");
    expect(planLimitCode({ detail: "plan_limit_scenarios" })).toBe("plan_limit_scenarios");
    expect(planLimitCode({ detail: "action_not_allowed" })).toBeNull();
    expect(planLimitCode(null)).toBeNull();
  });
});
