/**
 * Deterministic, illustrative Monte Carlo used by the landing hero.
 *
 * It is shared by the static SVG fallback (rendered on the server) and the
 * lazily-loaded WebGL scene, so both show exactly the same futures.
 * Nothing here is a real valuation — values are illustrative (R$ milhões).
 */

export const SEED = 471829;
export const YEARS = 5;
export const STEPS = 60; // monthly steps over the 5-year horizon

/** Illustrative terminal percentiles (R$ M) — same numbers used across the landing page. */
export const TARGET_PERCENTILES = { p10: 4.3, p25: 6.1, p50: 8.4, p75: 11.7, p90: 15.2 } as const;

const START_VALUE = 3.0; // R$ M "hoje"
const DRIFT = 0.2; // per year, log space
const VOL = 0.41; // per year, log space
const BARRIER = 1.0; // below R$ 1,0M the company runs out of runway -> failure

/* ------------------------------------------------------------------ world layout */
/** World-space layout shared by the 3D scene and the 2D fallback projection. */
export const WORLD = {
  x0: -3, // "hoje"
  x1: 2, // "ano 5"
  lnMin: Math.log(BARRIER),
  lnMax: Math.log(46),
  height: 3.3, // world height between lnMin and lnMax
  floor: -0.55, // "R$ 0" — failures land here
  histGap: 0.2, // distance between the year-5 plane and the first cube
  cubePitch: 0.1375, // = height / 24 bins
  bins: 24,
  zSpread: 0.62, // terminal std-dev of the (aesthetic) depth dispersion
} as const;

export const worldX = (step: number) => WORLD.x0 + (step / STEPS) * (WORLD.x1 - WORLD.x0);
export const worldY = (lnValue: number) => ((lnValue - WORLD.lnMin) / (WORLD.lnMax - WORLD.lnMin)) * WORLD.height;

/* ------------------------------------------------------------------ rng */
function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function gaussianFactory(random: () => number) {
  let spare: number | null = null;
  return () => {
    if (spare !== null) {
      const value = spare;
      spare = null;
      return value;
    }
    let u = 0;
    while (u === 0) u = random();
    const v = random();
    const mag = Math.sqrt(-2 * Math.log(u));
    spare = mag * Math.sin(2 * Math.PI * v);
    return mag * Math.cos(2 * Math.PI * v);
  };
}

function quantileSorted(sorted: Float32Array | Float64Array, q: number) {
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.min(sorted.length - 1, lo + 1);
  const a = sorted[lo];
  const b = sorted[hi];
  if (!Number.isFinite(a) || !Number.isFinite(b)) return Number.isFinite(b) ? b : a;
  return a + (b - a) * (pos - lo);
}

/* ------------------------------------------------------------------ model */
export type Band = number[];
export type Bands = { p10: Band; p25: Band; p50: Band; p75: Band; p90: Band };
export type CubeBin = { bin: number; cubes: number };

/** Small, serialisable summary of all 10.000 futures (computed once, on the server). */
export type FuturesSummary = {
  count: number;
  /** Percentile envelopes per month in ln space (failures count as value zero). */
  bands: Bands;
  /** Raw terminal quantiles used to calibrate paths to the illustrative percentiles. */
  rawKnots: number[];
  failureRate: number;
  /** Unit histogram: 100 cubes, each = 1% of scenarios. */
  cubeBins: CubeBin[];
  failureCubes: number;
  /** Terminal percentiles in R$ M. */
  terminal: { p10: number; p25: number; p50: number; p75: number; p90: number };
};

/** Individual trajectories, regenerated from the same seeded stream. */
export type FuturesPaths = {
  count: number;
  /** ln(value in R$ M) per path per month; NaN after failure. Length count*(STEPS+1). */
  logV: Float32Array;
  /** Aesthetic depth offset per path per month. Length count*(STEPS+1). */
  z: Float32Array;
  /** Month at which the path failed, or -1. */
  failStep: Int16Array;
};

const QS = [0.1, 0.25, 0.5, 0.75, 0.9];
const TARGET_LOGS = [TARGET_PERCENTILES.p10, TARGET_PERCENTILES.p25, TARGET_PERCENTILES.p50, TARGET_PERCENTILES.p75, TARGET_PERCENTILES.p90].map(Math.log);

/** Paths are generated sequentially, so the first n paths are identical whatever the total. */
function generateRaw(count: number): FuturesPaths {
  const random = mulberry32(SEED);
  const gauss = gaussianFactory(random);
  const stride = STEPS + 1;
  const logV = new Float32Array(count * stride);
  const z = new Float32Array(count * stride);
  const failStep = new Int16Array(count).fill(-1);
  const dt = YEARS / STEPS;
  const lnStart = Math.log(START_VALUE);
  const lnBarrier = Math.log(BARRIER);
  const zStep = WORLD.zSpread / Math.sqrt(STEPS);

  for (let i = 0; i < count; i += 1) {
    const base = i * stride;
    let x = lnStart;
    let depth = 0;
    let failed = false;
    logV[base] = x;
    for (let s = 1; s <= STEPS; s += 1) {
      // Early months are more uncertain for a startup: volatility decays over the horizon.
      const vol = VOL * (1.18 - 0.36 * (s / STEPS));
      x += (DRIFT - 0.5 * vol * vol * 0.35) * dt + vol * Math.sqrt(dt) * gauss();
      depth += zStep * gauss();
      z[base + s] = depth;
      if (failed) {
        logV[base + s] = Number.NaN;
      } else if (x < lnBarrier) {
        failed = true;
        failStep[i] = s;
        logV[base + s] = Number.NaN;
      } else {
        logV[base + s] = x;
      }
    }
  }
  return { count, logV, z, failStep };
}

/** Monotone piecewise map (log space) + linear bridge so each path stays continuous. */
function calibrate(paths: FuturesPaths, rawKnots: number[]) {
  const stride = STEPS + 1;
  const last = rawKnots.length - 1;
  const map = (value: number) => {
    if (value <= rawKnots[0]) return value - rawKnots[0] + TARGET_LOGS[0];
    if (value >= rawKnots[last]) return value - rawKnots[last] + TARGET_LOGS[last];
    for (let k = 0; k < last; k += 1) {
      if (value <= rawKnots[k + 1]) {
        const f = (value - rawKnots[k]) / (rawKnots[k + 1] - rawKnots[k] || 1);
        return TARGET_LOGS[k] + f * (TARGET_LOGS[k + 1] - TARGET_LOGS[k]);
      }
    }
    return value;
  };
  for (let i = 0; i < paths.count; i += 1) {
    if (paths.failStep[i] >= 0) continue;
    const base = i * stride;
    const delta = map(paths.logV[base + STEPS]) - paths.logV[base + STEPS];
    for (let s = 1; s <= STEPS; s += 1) paths.logV[base + s] += delta * (s / STEPS);
  }
}

/** Full 10.000-scenario run. ~150 ms — call on the server (static render), not in the browser. */
export function buildFuturesSummary(count = 10000): FuturesSummary {
  const paths = generateRaw(count);
  const stride = STEPS + 1;

  const terminalRaw = new Float64Array(count);
  for (let i = 0; i < count; i += 1) {
    terminalRaw[i] = paths.failStep[i] >= 0 ? Number.NEGATIVE_INFINITY : paths.logV[i * stride + STEPS];
  }
  terminalRaw.sort();
  const rawKnots = QS.map((q) => quantileSorted(terminalRaw, q));
  calibrate(paths, rawKnots);

  // Intermediate months use a 1-in-4 subsample (visual envelope only); the terminal
  // month uses every scenario so the labelled percentiles are exact.
  const bands: Bands = { p10: [], p25: [], p50: [], p75: [], p90: [] };
  const full = new Float32Array(count);
  const sub = new Float32Array(Math.ceil(count / 4));
  for (let s = 0; s <= STEPS; s += 1) {
    const column = s === STEPS ? full : sub;
    const every = s === STEPS ? 1 : 4;
    for (let i = 0, j = 0; i < count; i += every, j += 1) {
      const v = paths.logV[i * stride + s];
      column[j] = Number.isNaN(v) ? Number.NEGATIVE_INFINITY : v;
    }
    column.sort();
    const round = (v: number) => Math.round(v * 10000) / 10000;
    bands.p10.push(round(quantileSorted(column, 0.1)));
    bands.p25.push(round(quantileSorted(column, 0.25)));
    bands.p50.push(round(quantileSorted(column, 0.5)));
    bands.p75.push(round(quantileSorted(column, 0.75)));
    bands.p90.push(round(quantileSorted(column, 0.9)));
  }

  // Unit histogram — 100 cubes, each representing 1% of all simulated futures.
  let failures = 0;
  const binCounts = new Array<number>(WORLD.bins).fill(0);
  for (let i = 0; i < count; i += 1) {
    if (paths.failStep[i] >= 0) {
      failures += 1;
      continue;
    }
    const y = worldY(paths.logV[i * stride + STEPS]);
    binCounts[Math.max(0, Math.min(WORLD.bins - 1, Math.floor(y / WORLD.cubePitch)))] += 1;
  }
  const failureRate = failures / count;
  const failureCubes = Math.max(1, Math.round(failureRate * 100));
  const survivorCubes = 100 - failureCubes;
  const exact = binCounts.map((c) => (c / (count - failures)) * survivorCubes);
  const cubes = exact.map(Math.floor);
  let remaining = survivorCubes - cubes.reduce((a, b) => a + b, 0);
  const order = exact.map((value, index) => ({ index, rest: value - Math.floor(value) })).sort((a, b) => b.rest - a.rest);
  for (const item of order) {
    if (remaining <= 0) break;
    cubes[item.index] += 1;
    remaining -= 1;
  }
  const cubeBins = cubes.map((n, bin) => ({ bin, cubes: n })).filter((item) => item.cubes > 0);

  const last = STEPS;
  const terminal = {
    p10: Math.exp(bands.p10[last]),
    p25: Math.exp(bands.p25[last]),
    p50: Math.exp(bands.p50[last]),
    p75: Math.exp(bands.p75[last]),
    p90: Math.exp(bands.p90[last]),
  };
  return { count, bands, rawKnots, failureRate, cubeBins, failureCubes, terminal };
}

/** The first `count` calibrated trajectories of the same run — cheap enough for the browser. */
export function buildFuturesPaths(count: number, rawKnots: number[]): FuturesPaths {
  const paths = generateRaw(count);
  calibrate(paths, rawKnots);
  return paths;
}

/* ------------------------------------------------------------------ formatting */
export function formatMillions(value: number) {
  return `R$ ${value.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} mi`;
}

export function formatPercent(value: number) {
  return `${(value * 100).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

/* ------------------------------------------------------------------ label anchors */
export type LabelKey = "today" | "year5" | "p90" | "p50" | "p10" | "failure";

/** World-space anchors for the HTML labels (used by both renderers). */
export function labelAnchors(model: Pick<FuturesSummary, "bands" | "cubeBins" | "failureCubes">): Record<LabelKey, [number, number, number]> {
  const longest = Math.max(model.failureCubes, ...model.cubeBins.map((item) => item.cubes));
  const labelX = WORLD.x1 + WORLD.histGap + WORLD.cubePitch * (longest + 2.4);
  return {
    today: [WORLD.x0, worldY(model.bands.p50[0]), 0],
    year5: [WORLD.x1, WORLD.floor, 0],
    p90: [labelX, worldY(model.bands.p90[STEPS]), 0],
    p50: [labelX, worldY(model.bands.p50[STEPS]), 0],
    p10: [labelX, worldY(model.bands.p10[STEPS]), 0],
    failure: [labelX, WORLD.floor + WORLD.cubePitch / 2, 0],
  };
}

/* ------------------------------------------------------------------ static (fallback) projection */
/** Mild oblique projection so the static fallback reads as the flat twin of the 3D scene. */
export const FALLBACK_VIEW = { minX: -3.55, maxX: 5.45, minY: -0.8, maxY: 3.7 } as const;

export function obliqueProject(x: number, y: number, z: number): [number, number] {
  return [x + 0.34 * z, y + 0.2 * z];
}

/** Anchor position in % of the fallback box (left, top). */
export function fallbackPercent([x, y, z]: [number, number, number]): [number, number] {
  const [px, py] = obliqueProject(x, y, z);
  const { minX, maxX, minY, maxY } = FALLBACK_VIEW;
  return [((px - minX) / (maxX - minX)) * 100, ((maxY - py) / (maxY - minY)) * 100];
}

/** Cube colour role for a histogram bin (shared by both renderers). */
export type CubeRole = "median" | "core" | "inner" | "tail";
export function cubeRole(bin: number, bands: Bands): CubeRole {
  const lo = bin * WORLD.cubePitch;
  const hi = lo + WORLD.cubePitch;
  const y = (v: number) => worldY(v);
  const p50 = y(bands.p50[STEPS]);
  if (p50 >= lo && p50 < hi) return "median";
  const mid = (lo + hi) / 2;
  if (mid >= y(bands.p25[STEPS]) && mid <= y(bands.p75[STEPS])) return "core";
  if (mid >= y(bands.p10[STEPS]) && mid <= y(bands.p90[STEPS])) return "inner";
  return "tail";
}

/** Slot of the k-th cube of a bin (world space, z = 0). */
export function cubeSlot(bin: number, k: number): [number, number, number] {
  return [WORLD.x1 + WORLD.histGap + WORLD.cubePitch * (k + 0.5), (bin + 0.5) * WORLD.cubePitch, 0];
}

export function failureCubeSlot(k: number): [number, number, number] {
  return [WORLD.x1 + WORLD.histGap + WORLD.cubePitch * (k + 0.5), WORLD.floor + WORLD.cubePitch / 2, 0];
}
