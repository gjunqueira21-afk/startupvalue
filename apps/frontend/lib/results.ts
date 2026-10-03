/** Pure geometry and defaults for the results charts (percentages of the plot width). */

import { compactMoney } from "./format";
import type { ImpliedMultiples, TargetPlan } from "./api/simulations";

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

const integer = new Intl.NumberFormat("pt-BR");

/**
 * One-decimal multiple, pt-BR comma (controller ruling R5): formatMultiple(8.44) === "8,4x".
 * These are multiples implied by the user's own assumptions, not market multiples.
 */
export function formatMultiple(value: number): string {
  return `${value.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}x`;
}

/** One-decimal percentage, pt-BR comma: formatPercentBR(0.3) === "30,0%". */
export function formatPercentBR(value: number): string {
  return `${(value * 100).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

export interface MultipleRow {
  label: string;
  p25: string;
  p50: string;
  p75: string;
  note: string;
}

function multipleNote(eligible: number, excluded: number): string {
  return `${integer.format(eligible)} de ${integer.format(eligible + excluded)} cenários elegíveis`;
}

/** Table rows for the implied-multiples card; empty when the section is absent or not available. */
export function multiplesRows(multiples: ImpliedMultiples | null | undefined): MultipleRow[] {
  if (!multiples || multiples.status !== "available") return [];
  const rows: MultipleRow[] = [];
  if (multiples.value_to_revenue) {
    const { p25, p50, p75, eligible_count, excluded_count } = multiples.value_to_revenue;
    rows.push({
      label: "Valor / Receita",
      p25: formatMultiple(p25),
      p50: formatMultiple(p50),
      p75: formatMultiple(p75),
      note: multipleNote(eligible_count, excluded_count),
    });
  }
  if (multiples.value_to_ebitda) {
    const { p25, p50, p75, eligible_count, excluded_count } = multiples.value_to_ebitda;
    rows.push({
      label: "Valor / EBITDA",
      p25: formatMultiple(p25),
      p50: formatMultiple(p50),
      p75: formatMultiple(p75),
      note: multipleNote(eligible_count, excluded_count),
    });
  }
  return rows;
}

/** Minimum number of hitting scenarios the backend requires to estimate a target plan. */
const TARGET_PLAN_MIN_HITS = 50;

export interface TargetPlanTrajectoryRow {
  year: number;
  revenue: string;
}

export type TargetPlanView =
  | { kind: "hidden" }
  | { kind: "insufficient"; sentence: string }
  | { kind: "unavailable"; sentence: string }
  | {
      kind: "available";
      requiredCagr: string;
      hitMargin: string | null;
      missCagr: string | null;
      missMargin: string | null;
      trajectory: TargetPlanTrajectoryRow[];
      contrast: string;
    };

/**
 * Discriminated, pre-formatted view of the "what needs to be true" target plan.
 * `hidden` covers both a missing plan (free plan, not entitled) and a `null` value.
 */
export function targetPlanView(plan: TargetPlan | null | undefined): TargetPlanView {
  if (!plan) return { kind: "hidden" };
  if (plan.status === "insufficient_hits") {
    const verb = plan.hit_count === 1 ? "atinge" : "atingem";
    const noun = plan.hit_count === 1 ? "cenário" : "cenários";
    return {
      kind: "insufficient",
      sentence: `Apenas ${plan.hit_count} ${noun} ${verb} esta meta — são necessários pelo menos ${TARGET_PLAN_MIN_HITS} para estimar um plano confiável.`,
    };
  }
  if (plan.status !== "available") {
    return {
      kind: "unavailable",
      sentence: "Não foi possível estimar um plano para esta meta com os dados informados.",
    };
  }
  const requiredCagr = plan.required_revenue_cagr === null ? "—" : formatPercentBR(plan.required_revenue_cagr);
  const hitMargin = plan.hit_ebitda_margin === null ? null : formatPercentBR(plan.hit_ebitda_margin);
  const missCagr = plan.miss_revenue_cagr === null ? null : formatPercentBR(plan.miss_revenue_cagr);
  const missMargin = plan.miss_ebitda_margin === null ? null : formatPercentBR(plan.miss_ebitda_margin);
  const contrast = [
    `Cenários que atingem a meta: CAGR de receita de ${requiredCagr}${hitMargin ? ` e margem EBITDA de ${hitMargin}` : ""}.`,
    missCagr
      ? `Cenários que não atingem: CAGR de ${missCagr}${missMargin ? ` e margem de ${missMargin}` : ""}.`
      : "",
  ].filter(Boolean).join(" ");
  return {
    kind: "available",
    requiredCagr,
    hitMargin,
    missCagr,
    missMargin,
    trajectory: plan.trajectory.map((item) => ({ year: item.year, revenue: compactMoney(item.revenue, "short") })),
    contrast,
  };
}
