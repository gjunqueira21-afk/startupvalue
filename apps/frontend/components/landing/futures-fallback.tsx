import {
  FALLBACK_VIEW,
  STEPS,
  WORLD,
  buildFuturesPaths,
  cubeRole,
  cubeSlot,
  failureCubeSlot,
  obliqueProject,
  worldX,
  worldY,
  type CubeRole,
  type FuturesSummary,
} from "./futures-model";

/**
 * Static twin of the WebGL hero, rendered on the server. Shown while the 3D chunk loads,
 * when WebGL is unavailable and when the user prefers reduced motion.
 */

const SCALE = 100;
const STEP = 3; // quarterly points keep the server-rendered SVG light
const pt = (x: number, y: number, z = 0) => {
  const [px, py] = obliqueProject(x, y, z);
  return `${Math.round(px * SCALE)} ${Math.round(-py * SCALE)}`;
};

function pathFor(values: number[], z = 0) {
  return values
    .map((v, s) => (s % STEP === 0 || s === STEPS ? `${s === 0 ? "M" : "L"}${pt(worldX(s), worldY(v), z)}` : ""))
    .join("");
}

const CUBE_FILL: Record<CubeRole | "failure", [string, string, string]> = {
  // front, top, side
  median: ["#c9ffe8", "#effff7", "#8fe9c4"],
  core: ["#35e6a1", "#7ff2c4", "#1f9e70"],
  inner: ["#1d8f66", "#35c48c", "#146b4c"],
  tail: ["#2c5d93", "#4d86c7", "#1f4368"],
  failure: ["#ff6b78", "#ff9aa3", "#b8434f"],
};

function cubeFaces([x, y, z]: [number, number, number]) {
  const h = (WORLD.cubePitch * 0.8) / 2;
  const d = h; // cube half depth
  const front = `M${pt(x - h, y - h, z - d)}L${pt(x + h, y - h, z - d)}L${pt(x + h, y + h, z - d)}L${pt(x - h, y + h, z - d)}Z`;
  const top = `M${pt(x - h, y + h, z - d)}L${pt(x + h, y + h, z - d)}L${pt(x + h, y + h, z + d)}L${pt(x - h, y + h, z + d)}Z`;
  const side = `M${pt(x + h, y - h, z - d)}L${pt(x + h, y - h, z + d)}L${pt(x + h, y + h, z + d)}L${pt(x + h, y + h, z - d)}Z`;
  return { front, top, side };
}

export function FuturesFallback({ summary, paths = 80 }: { summary: FuturesSummary; paths?: number }) {
  const data = buildFuturesPaths(paths, summary.rawKnots);
  const stride = STEPS + 1;
  const survivors: string[] = [];
  const failures: string[] = [];
  const ends: string[] = [];

  for (let i = 0; i < data.count; i += 1) {
    const base = i * stride;
    const fail = data.failStep[i];
    const last = fail >= 0 ? fail - 1 : STEPS;
    const point = (step: number) => pt(worldX(step), worldY(data.logV[base + step]), data.z[base + step]);
    // failing futures look like any other until their final months, then turn red and plunge
    const redFrom = fail >= 0 ? Math.max(0, STEP * Math.floor((last - 10) / STEP)) : Number.POSITIVE_INFINITY; // on the step grid
    let healthy = "";
    let failing = "";
    for (let s = 0; s <= last; s = s === last ? last + 1 : Math.min(last, s + STEP)) {
      if (s <= redFrom) healthy += `${s === 0 ? "M" : "L"}${point(s)}`;
      if (s >= redFrom) failing += `${failing ? "L" : "M"}${point(s)}`;
    }
    if (healthy) survivors.push(healthy);
    if (fail >= 0) {
      const x = worldX(last);
      const y = worldY(data.logV[base + last]);
      const z = data.z[base + last];
      if (!failing) failing = `M${point(last)}`;
      failing += `Q${pt(x + 0.1, y, z)} ${pt(x + 0.16, WORLD.floor, z)}`;
      failures.push(failing);
    } else {
      const [px, py] = obliqueProject(worldX(STEPS), worldY(data.logV[base + STEPS]), data.z[base + STEPS]);
      ends.push(`M${Math.round(px * SCALE)} ${Math.round(-py * SCALE)}h0.1`);
    }
  }

  const { bands } = summary;
  const bandPath = `${pathFor(bands.p75)}${bands.p25
    .map((v, s) => ({ v, s }))
    .filter(({ s }) => s % STEP === 0 || s === STEPS)
    .reverse()
    .map(({ v, s }) => `L${pt(worldX(s), worldY(v))}`)
    .join("")}Z`;

  const faces: Record<CubeRole | "failure", { front: string[]; top: string[]; side: string[] }> = {
    median: { front: [], top: [], side: [] },
    core: { front: [], top: [], side: [] },
    inner: { front: [], top: [], side: [] },
    tail: { front: [], top: [], side: [] },
    failure: { front: [], top: [], side: [] },
  };
  for (const { bin, cubes } of summary.cubeBins) {
    const role = cubeRole(bin, bands);
    // draw back-to-front so nearer cubes overlap correctly
    for (let k = cubes - 1; k >= 0; k -= 1) {
      const f = cubeFaces(cubeSlot(bin, k));
      faces[role].front.push(f.front);
      faces[role].top.push(f.top);
      faces[role].side.push(f.side);
    }
  }
  for (let k = summary.failureCubes - 1; k >= 0; k -= 1) {
    const f = cubeFaces(failureCubeSlot(k));
    faces.failure.front.push(f.front);
    faces.failure.top.push(f.top);
    faces.failure.side.push(f.side);
  }

  const { minX, maxX, minY, maxY } = FALLBACK_VIEW;
  const viewBox = `${minX * SCALE} ${-maxY * SCALE} ${(maxX - minX) * SCALE} ${(maxY - minY) * SCALE}`;

  const floorLines: string[] = [];
  for (let year = 0; year <= 5; year += 1) {
    const x = WORLD.x0 + year;
    floorLines.push(`M${pt(x, WORLD.floor, -1.2)}L${pt(x, WORLD.floor, 1.2)}`);
  }
  for (let z = -1.2; z <= 1.21; z += 0.6) {
    floorLines.push(`M${pt(WORLD.x0 - 0.2, WORLD.floor, z)}L${pt(WORLD.x1 + 2.1, WORLD.floor, z)}`);
  }
  const frame = `M${pt(WORLD.x1, WORLD.floor, -1.2)}L${pt(WORLD.x1, WORLD.height, -1.2)}L${pt(WORLD.x1, WORLD.height, 1.2)}L${pt(WORLD.x1, WORLD.floor, 1.2)}`;
  const [ox, oy] = obliqueProject(WORLD.x0, worldY(bands.p50[0]), 0);

  return (
    <svg className="futures-fallback-svg" viewBox={viewBox} preserveAspectRatio="xMidYMid meet" aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id="ff-origin">
          <stop offset="0" stopColor="#bfe0ff" stopOpacity="0.9" />
          <stop offset="1" stopColor="#5ca7ff" stopOpacity="0" />
        </radialGradient>
      </defs>
      <g stroke="#26313d" strokeWidth="1" vectorEffect="non-scaling-stroke" fill="none" opacity="0.8">
        <path d={floorLines.join("")} vectorEffect="non-scaling-stroke" />
        <path d={frame} strokeDasharray="3 5" vectorEffect="non-scaling-stroke" />
      </g>
      <path d={bandPath} fill="#35e6a1" opacity="0.08" />
      <path d={survivors.join("")} fill="none" stroke="#35e6a1" strokeOpacity="0.2" strokeWidth="1" vectorEffect="non-scaling-stroke" />
      <path d={failures.join("")} fill="none" stroke="#ff6b78" strokeOpacity="0.55" strokeWidth="1" vectorEffect="non-scaling-stroke" />
      <path d={ends.join("")} fill="none" stroke="#7ff2c4" strokeOpacity="0.8" strokeWidth="2.4" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      <path d={pathFor(bands.p90)} fill="none" stroke="#a6b1bd" strokeOpacity="0.7" strokeDasharray="4 5" strokeWidth="1" vectorEffect="non-scaling-stroke" />
      <path d={pathFor(bands.p10)} fill="none" stroke="#a6b1bd" strokeOpacity="0.7" strokeDasharray="4 5" strokeWidth="1" vectorEffect="non-scaling-stroke" />
      <path d={pathFor(bands.p50)} fill="none" stroke="#dfffee" strokeWidth="2" vectorEffect="non-scaling-stroke" />
      <circle cx={ox * SCALE} cy={-oy * SCALE} r="22" fill="url(#ff-origin)" />
      <circle cx={ox * SCALE} cy={-oy * SCALE} r="3.2" fill="#e8f4ff" />
      {(Object.keys(faces) as (CubeRole | "failure")[]).map((role) => (
        <g key={role}>
          <path d={faces[role].side.join("")} fill={CUBE_FILL[role][2]} />
          <path d={faces[role].top.join("")} fill={CUBE_FILL[role][1]} />
          <path d={faces[role].front.join("")} fill={CUBE_FILL[role][0]} />
        </g>
      ))}
    </svg>
  );
}
