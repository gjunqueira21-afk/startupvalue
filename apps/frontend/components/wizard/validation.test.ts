import { describe, expect, it } from "vitest";
import { DEFAULT_DRAFT } from "./defaults";
import type { ValuationAssumptions, ValuationWizardDraft } from "./types";
import { validateStep } from "./validation";

function withValuation(overrides: Partial<ValuationAssumptions>): ValuationWizardDraft {
  const draft = structuredClone(DEFAULT_DRAFT);
  return { ...draft, mode: "professional", valuation: { ...draft.valuation, ...overrides } };
}

const ranges = DEFAULT_DRAFT.valuation.ranges;

describe("validateStep(valuation)", () => {
  it("accepts the default fixed assumptions", () => {
    expect(validateStep(withValuation({}), 4)).toEqual({});
  });

  it("requires the most likely WACC inside its range", () => {
    const errors = validateStep(withValuation({ ranges: { ...ranges, wacc: { enabled: true, minimum: 26, maximum: 32 } } }), 4);
    expect(errors["valuation.ranges.wacc"]).toBeDefined();
  });

  it("keeps the lowest WACC above the highest perpetuity growth", () => {
    const errors = validateStep(
      withValuation({
        ranges: {
          ...ranges,
          wacc: { enabled: true, minimum: 5, maximum: 32 },
          terminalGrowth: { enabled: true, minimum: 2, maximum: 6 },
        },
      }),
      4,
    );
    expect(errors["valuation.ranges.wacc"]).toMatch(/crescimento/i);
  });

  it("ignores growth when the terminal value is an exit multiple", () => {
    const errors = validateStep(withValuation({ terminalMethod: "exit_multiple", terminalGrowth: 40 }), 4);
    expect(errors).toEqual({});
  });

  it("validates the terminal multiple and its range", () => {
    expect(validateStep(withValuation({ terminalMethod: "exit_multiple", terminalMultiple: 0 }), 4)["valuation.terminalMultiple"]).toBeDefined();
    const errors = validateStep(
      withValuation({ terminalMethod: "exit_multiple", ranges: { ...ranges, terminalMultiple: { enabled: true, minimum: 7, maximum: 12 } } }),
      4,
    );
    expect(errors["valuation.ranges.terminalMultiple"]).toBeDefined();
  });

  it("does not validate disabled ranges", () => {
    const errors = validateStep(withValuation({ ranges: { ...ranges, wacc: { enabled: false, minimum: 90, maximum: 1 } } }), 4);
    expect(errors).toEqual({});
  });
});
