/** Pure geometry and defaults for the results charts (percentages of the plot width). */

export type Direction = "positive" | "negative";

/** Round P75 up to two significant digits; a positive, clean default target. */
export function suggestedTarget(p75: number, p90: number): number | null {
  const base = p75 > 0 ? p75 : p90 > 0 ? p90 : null;
  if (base === null) return null;
  const step = 10 ** (Math.floor(Math.log10(base)) - 1);
  return Math.ceil(base / step - 1e-9) * step;
}

/** Bar from the centre of a -1..1 scale towards the coefficient's sign. */
export function divergingBar(value: number | null): { left: number; width: number; direction: Direction } | null {
  if (value === null) return null;
  const width = Math.abs(value) * 50;
  return { left: value >= 0 ? 50 : 50 - width, width, direction: value >= 0 ? "positive" : "negative" };
}

export interface TornadoSegment {
  start: number;
  width: number;
  delta: number;
  direction: Direction;
}

export interface TornadoRow {
  parameter: string;
  low: TornadoSegment;
  high: TornadoSegment;
}

/**
 * Both swings of each assumption around the base, on one symmetric scale. The
 * longest bar spans ``maxHalf`` percent from the centre, leaving room for labels.
 */
export function tornadoRows(
  items: { parameter: string; value_at_low: number; value_at_high: number }[],
  base: number,
  maxHalf = 50,
): TornadoRow[] {
  const scale = Math.max(1e-12, ...items.flatMap((item) => [Math.abs(item.value_at_low - base), Math.abs(item.value_at_high - base)]));
  const segment = (value: number): TornadoSegment => {
    const delta = value - base;
    const width = (Math.abs(delta) / scale) * maxHalf;
    return { start: delta >= 0 ? 50 : 50 - width, width, delta, direction: delta >= 0 ? "positive" : "negative" };
  };
  return items.map((item) => ({ parameter: item.parameter, low: segment(item.value_at_low), high: segment(item.value_at_high) }));
}

export function histogramTicks(minimum: number, maximum: number, intervals = 4): { value: number; position: number }[] {
  return Array.from({ length: intervals + 1 }, (_, index) => ({
    value: minimum + ((maximum - minimum) * index) / intervals,
    position: (index / intervals) * 100,
  }));
}

/** Position of the IQR/P50 ratio on a 0..2 track; a missing ratio pins to the end. */
export function uncertaintyPosition(ratio: number | null): number {
  if (ratio === null) return 100;
  return Math.min(100, Math.max(0, (ratio / 2) * 100));
}
