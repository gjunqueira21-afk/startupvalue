import { describe, expect, it } from "vitest";
import { divergingBar, histogramTicks, suggestedTarget, tornadoRows, uncertaintyPosition } from "./results";

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
