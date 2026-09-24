import { describe, expect, it } from "vitest";
import { DEFAULT_DRAFT } from "../../components/wizard/defaults";
import type { ValuationWizardDraft } from "../../components/wizard/types";
import { buildCanonicalInputs } from "./simulations";

function draft(overrides: Partial<ValuationWizardDraft["valuation"]> = {}, mode: ValuationWizardDraft["mode"] = "professional"): ValuationWizardDraft {
  const base = structuredClone(DEFAULT_DRAFT);
  return {
    ...base,
    mode,
    revenue: { cadence: "annual", years: [1_200_000, 2_400_000, 3_600_000, 4_800_000, 6_000_000] },
    metrics: { ...base.metrics, grossMargin: 70 },
    valuation: { ...base.valuation, ...overrides },
  };
}

describe("buildCanonicalInputs", () => {
  it("keeps the fixed Gordon model by default", () => {
    const inputs = buildCanonicalInputs(draft());
    expect(inputs.annual_wacc).toBeCloseTo(0.25);
    expect(inputs.terminal_growth).toBeCloseTo(0.04);
    expect(inputs).not.toHaveProperty("terminal_method");
    expect(inputs).not.toHaveProperty("wacc_uncertainty");
    expect(inputs).not.toHaveProperty("terminal_growth_uncertainty");
  });

  it("sends enabled ranges as triangular min / most likely / max in decimals", () => {
    const inputs = buildCanonicalInputs(
      draft({
        ranges: {
          ...DEFAULT_DRAFT.valuation.ranges,
          wacc: { enabled: true, minimum: 20, maximum: 32 },
          terminalGrowth: { enabled: true, minimum: 2, maximum: 6 },
        },
      }),
    );
    expect(inputs.wacc_uncertainty).toEqual({ kind: "triangular", minimum: 0.2, mode: 0.25, maximum: 0.32 });
    expect(inputs.terminal_growth_uncertainty).toEqual({ kind: "triangular", minimum: 0.02, mode: 0.04, maximum: 0.06 });
  });

  it("switches the terminal value to an exit multiple on the chosen metric", () => {
    const inputs = buildCanonicalInputs(
      draft({
        terminalMethod: "exit_multiple",
        terminalMetric: "ebitda",
        terminalMultiple: 8,
        ranges: { ...DEFAULT_DRAFT.valuation.ranges, terminalMultiple: { enabled: true, minimum: 5, maximum: 12 } },
      }),
    );
    expect(inputs.terminal_method).toBe("exit_multiple");
    expect(inputs.exit_metric).toBe("ebitda");
    expect(inputs.exit_multiple).toBe(8);
    expect(inputs.exit_multiple_uncertainty).toEqual({ kind: "triangular", minimum: 5, mode: 8, maximum: 12 });
    expect(inputs.terminal_growth).toBeUndefined();
  });

  it("uses a fixed perpetuity in simple mode regardless of professional settings", () => {
    const inputs = buildCanonicalInputs(
      draft(
        {
          terminalMethod: "exit_multiple",
          ranges: { ...DEFAULT_DRAFT.valuation.ranges, wacc: { enabled: true, minimum: 20, maximum: 32 } },
        },
        "simple",
      ),
    );
    expect(inputs).not.toHaveProperty("terminal_method");
    expect(inputs).not.toHaveProperty("wacc_uncertainty");
    expect(inputs.terminal_growth).toBeCloseTo(0.04);
  });
});
