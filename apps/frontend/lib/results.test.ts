import { describe, expect, it } from "vitest";
import {
  divergingBar,
  formatMultiple,
  formatPercentBR,
  histogramTicks,
  multiplesRows,
  suggestedTarget,
  targetPlanView,
  tornadoRows,
  uncertaintyPosition,
} from "./results";
import type { ImpliedMultiples, TargetPlan } from "./api/simulations";

describe("suggestedTarget", () => {
  it("rounds P75 up to a clean two-significant-digit figure", () => {
    expect(suggestedTarget(17_100_000, 21_000_000)).toBe(18_000_000);
    expect(suggestedTarget(9_120_000, 12_000_000)).toBe(9_200_000);
    expect(suggestedTarget(840_000, 1_000_000)).toBe(840_000);
  });

  it("falls back to P90 when P75 is not positive and gives up when both are", () => {
    expect(suggestedTarget(-100, 2_050_000)).toBe(2_100_000);
    expect(suggestedTarget(-100, 0)).toBeNull();
  });
});

describe("divergingBar", () => {
  it("grows from the centre towards the sign on a -1..1 scale", () => {
    expect(divergingBar(0.5)).toEqual({ left: 50, width: 25, direction: "positive" });
    expect(divergingBar(-0.8)).toEqual({ left: 10, width: 40, direction: "negative" });
    expect(divergingBar(null)).toBeNull();
  });
});

describe("tornadoRows", () => {
  const items = [
    { parameter: "annual_wacc", value_at_low: 16_300_000, value_at_high: 10_600_000 },
    { parameter: "failure_probability", value_at_low: 14_200_000, value_at_high: 12_050_000 },
  ];

  it("places both swings around the base on a shared symmetric scale", () => {
    const rows = tornadoRows(items, 13_000_000);
    expect(rows[0].low).toEqual({ start: 50, width: 50, delta: 3_300_000, direction: "positive" });
    const high = rows[0].high;
    expect(high.direction).toBe("negative");
    expect(high.start + high.width).toBeCloseTo(50, 10);
    expect(high.width).toBeCloseTo(50 * (2_400_000 / 3_300_000), 10);
    expect(rows[1].low.width).toBeCloseTo(50 * (1_200_000 / 3_300_000), 10);
  });

  it("can leave room at both ends for value labels", () => {
    const rows = tornadoRows(items, 13_000_000, 34);
    expect(rows[0].low).toEqual({ start: 50, width: 34, delta: 3_300_000, direction: "positive" });
    expect(rows[0].high.start).toBeCloseTo(50 - 34 * (2_400_000 / 3_300_000), 10);
  });

  it("handles an assumption with no effect", () => {
    const rows = tornadoRows([{ parameter: "x", value_at_low: 5, value_at_high: 5 }], 5);
    expect(rows[0].low.width).toBe(0);
    expect(rows[0].high.width).toBe(0);
  });
});

describe("histogramTicks", () => {
  it("returns evenly spaced ticks across the range with positions", () => {
    const ticks = histogramTicks(-2_000_000, 22_000_000, 4);
    expect(ticks.map((tick) => tick.value)).toEqual([-2_000_000, 4_000_000, 10_000_000, 16_000_000, 22_000_000]);
    expect(ticks[2].position).toBeCloseTo(50);
  });
});

describe("uncertaintyPosition", () => {
  it("maps the IQR ratio onto a 0..2 track, clamped", () => {
    expect(uncertaintyPosition(0.4)).toBeCloseTo(20);
    expect(uncertaintyPosition(1.5)).toBeCloseTo(75);
    expect(uncertaintyPosition(3.6)).toBe(100);
    expect(uncertaintyPosition(null)).toBe(100);
  });
});

describe("formatMultiple", () => {
  it("formats with one decimal and a pt-BR comma", () => {
    expect(formatMultiple(8.44)).toBe("8,4x");
    expect(formatMultiple(2)).toBe("2,0x");
    expect(formatMultiple(10.96)).toBe("11,0x");
  });
});

describe("formatPercentBR", () => {
  it("formats a ratio with one decimal and a pt-BR comma", () => {
    expect(formatPercentBR(0.3)).toBe("30,0%");
    expect(formatPercentBR(0.0825)).toBe("8,3%");
    expect(formatPercentBR(0)).toBe("0,0%");
  });
});

describe("multiplesRows", () => {
  const fixture: ImpliedMultiples = {
    status: "available",
    reason: null,
    basis: "equity_dcf_over_year5_metric",
    value_to_revenue: { p25: 3.1, p50: 4.2, p75: 5.9, eligible_count: 420, excluded_count: 80 },
    value_to_ebitda: { p25: 7.5, p50: 8.44, p75: 10.2, eligible_count: 300, excluded_count: 200 },
  };

  it("maps both available multiples to formatted rows with an eligibility note", () => {
    const rows = multiplesRows(fixture);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toEqual({
      label: "Valor / Receita",
      p25: "3,1x",
      p50: "4,2x",
      p75: "5,9x",
      note: "420 de 500 cenários elegíveis",
    });
    expect(rows[1]).toEqual({
      label: "Valor / EBITDA",
      p25: "7,5x",
      p50: "8,4x",
      p75: "10,2x",
      note: "300 de 500 cenários elegíveis",
    });
  });

  it("omits a metric that is absent even when the other is available", () => {
    const rows = multiplesRows({ ...fixture, value_to_ebitda: null });
    expect(rows).toHaveLength(1);
    expect(rows[0].label).toBe("Valor / Receita");
  });

  it("returns an empty array when multiples are absent, not available, or undefined", () => {
    expect(multiplesRows(undefined)).toEqual([]);
    expect(multiplesRows(null)).toEqual([]);
    expect(multiplesRows({ status: "not_available", reason: "metrics_unavailable_for_input_mode", basis: "equity_dcf_over_year5_metric", value_to_revenue: null, value_to_ebitda: null })).toEqual([]);
  });
});

describe("targetPlanView", () => {
  it("is hidden when the plan is absent (free plan or not entitled)", () => {
    expect(targetPlanView(null)).toEqual({ kind: "hidden" });
    expect(targetPlanView(undefined)).toEqual({ kind: "hidden" });
  });

  it("explains the shortfall against the minimum hit sample when insufficient", () => {
    const plan: TargetPlan = {
      status: "insufficient_hits",
      hit_count: 12,
      required_revenue_cagr: null,
      hit_ebitda_margin: null,
      miss_revenue_cagr: null,
      miss_ebitda_margin: null,
      trajectory: [],
    };
    const view = targetPlanView(plan);
    expect(view.kind).toBe("insufficient");
    if (view.kind === "insufficient") {
      expect(view.sentence).toContain("12");
      expect(view.sentence).toContain("50");
    }
  });

  it("is a neutral unavailable note when the inputs do not support a plan", () => {
    const plan: TargetPlan = {
      status: "not_available_for_inputs",
      hit_count: 0,
      required_revenue_cagr: null,
      hit_ebitda_margin: null,
      miss_revenue_cagr: null,
      miss_ebitda_margin: null,
      trajectory: [],
    };
    const view = targetPlanView(plan);
    expect(view.kind).toBe("unavailable");
    if (view.kind === "unavailable") expect(view.sentence.length).toBeGreaterThan(0);
  });

  it("formats the required CAGR, target margin, trajectory, and hit-vs-miss contrast when available", () => {
    const plan: TargetPlan = {
      status: "available",
      hit_count: 120,
      required_revenue_cagr: 0.35,
      hit_ebitda_margin: 0.18,
      miss_revenue_cagr: 0.12,
      miss_ebitda_margin: 0.05,
      trajectory: [
        { year: 1, revenue: 1_000_000 },
        { year: 2, revenue: 1_350_000 },
      ],
    };
    const view = targetPlanView(plan);
    expect(view.kind).toBe("available");
    if (view.kind === "available") {
      expect(view.requiredCagr).toBe("35,0%");
      expect(view.hitMargin).toBe("18,0%");
      expect(view.missCagr).toBe("12,0%");
      expect(view.missMargin).toBe("5,0%");
      expect(view.trajectory).toEqual([
        { year: 1, revenue: "R$ 1,0 mi" },
        { year: 2, revenue: "R$ 1,4 mi" },
      ]);
      expect(view.contrast).toContain("35,0%");
      expect(view.contrast).toContain("12,0%");
    }
  });
});
