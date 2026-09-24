import { describe, expect, it } from "vitest";
import { DEFAULT_DRAFT, hydrateDraft } from "./defaults";

describe("hydrateDraft", () => {
  it("fills valuation options missing from drafts saved before they existed", () => {
    const legacy = structuredClone(DEFAULT_DRAFT) as unknown as Record<string, unknown>;
    const valuation = { ...(legacy.valuation as Record<string, unknown>) };
    delete valuation.terminalMethod;
    delete valuation.terminalMetric;
    delete valuation.terminalMultiple;
    delete valuation.ranges;
    valuation.wacc = 31;
    const hydrated = hydrateDraft({ ...legacy, valuation });
    expect(hydrated?.valuation.wacc).toBe(31);
    expect(hydrated?.valuation.terminalMethod).toBe("gordon");
    expect(hydrated?.valuation.ranges.wacc.enabled).toBe(false);
    expect(hydrated?.valuation.ranges.terminalMultiple).toEqual(DEFAULT_DRAFT.valuation.ranges.terminalMultiple);
  });

  it("rejects drafts from another schema version", () => {
    expect(hydrateDraft({ schemaVersion: 2 })).toBeNull();
    expect(hydrateDraft(null)).toBeNull();
  });
});
