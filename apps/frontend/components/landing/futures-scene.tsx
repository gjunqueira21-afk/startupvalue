"use client";

import { useEffect, useRef, type RefObject } from "react";
import {
  AdditiveBlending,
  AmbientLight,
  BoxGeometry,
  BufferAttribute,
  BufferGeometry,
  Color,
  DirectionalLight,
  DoubleSide,
  DynamicDrawUsage,
  InstancedMesh,
  Line,
  LineSegments,
  Matrix4,
  Mesh,
  MeshLambertMaterial,
  PerspectiveCamera,
  Points,
  Scene,
  ShaderMaterial,
  Vector3,
  WebGLRenderer,
} from "three";
import {
  STEPS,
  WORLD,
  buildFuturesPaths,
  cubeRole,
  cubeSlot,
  failureCubeSlot,
  labelAnchors,
  worldX,
  worldY,
  type CubeRole,
  type FuturesSummary,
  type LabelKey,
} from "./futures-model";

export type FuturesSceneProps = {
  summary: FuturesSummary;
  lite: boolean;
  labels: RefObject<Partial<Record<LabelKey, HTMLElement | null>>>;
  onReady: () => void;
  onIntroDone: () => void;
  onFail: () => void;
};

const GREEN = new Color("#35e6a1");
const BLUE = new Color("#5ca7ff");
const RED = new Color("#ff6b78");

const INTRO_SECONDS = 3.4;

const ARIA_LABEL =
  "Visualização 3D ilustrativa: milhares de trajetórias simuladas de valuation partem de hoje e se abrem em leque ao longo de cinco anos, formando um histograma de 100 cubos, cada um representando 100 cenários. A mediana, a faixa P25–P75 e os percentis P10 e P90 estão destacados; trajetórias em vermelho terminam em falência.";

/* ------------------------------------------------------------------ shaders */
const PATH_VERT = /* glsl */ `
  attribute vec3 aData; // t (0..1 along the horizon), seed, failure weight (0 healthy .. 1 failing)
  uniform float uReveal;
  uniform float uTime;
  uniform vec3 uGreen;
  uniform vec3 uBlue;
  uniform vec3 uRed;
  uniform float uNear;
  uniform float uFar;
  uniform float uBoost;
  varying vec4 vColor;
  void main() {
    float t = aData.x;
    float seed = aData.y;
    float kind = aData.z;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mv;

    float head = uReveal * 1.3 - seed * 0.3;
    float shown = clamp((head - t) * 16.0, 0.0, 1.0);
    float tip = exp(-pow((head - t) * 16.0, 2.0)) * (1.0 - smoothstep(1.0, 1.25, uReveal));

    // Slow travelling pulses on roughly a quarter of the paths: futures "flowing".
    float cycle = fract(uTime * 0.045 + seed * 5.731);
    float pulse = exp(-pow((t - (cycle * 1.9 - 0.45)) * 11.0, 2.0)) * step(fract(seed * 17.13), 0.26);

    vec3 color = mix(uBlue, uGreen, smoothstep(0.0, 0.42, t));
    // thousands of paths share the origin: keep it from saturating
    float alpha = mix(0.045, 0.085, fract(seed * 3.7)) * (0.06 + 0.94 * smoothstep(0.0, 0.34, t)) * uBoost;
    // failing futures look like any other until their last months, then turn red
    color = mix(color, uRed, kind);
    alpha = mix(alpha, 0.22, kind);
    pulse *= 1.0 - kind;
    float glow = clamp(pulse * 0.55 + tip * 0.7, 0.0, 1.0);
    color = mix(color, vec3(0.86, 1.0, 0.95), glow * 0.6);
    alpha += pulse * 0.32 + tip * 0.45;

    float depth = -mv.z;
    float fade = smoothstep(uFar, uNear, depth);
    vColor = vec4(color, alpha * shown * mix(0.3, 1.0, fade));
  }
`;

const COLOR_FRAG = /* glsl */ `
  varying vec4 vColor;
  void main() {
    if (vColor.a < 0.002) discard;
    gl_FragColor = vColor;
  }
`;

const POINT_VERT = /* glsl */ `
  attribute vec3 aData; // t at which the point appears, seed, kind
  uniform float uReveal;
  uniform float uPixelRatio;
  uniform float uSize;
  uniform vec3 uGreen;
  uniform vec3 uRed;
  varying vec4 vColor;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mv;
    float head = uReveal * 1.3 - aData.y * 0.3;
    float shown = clamp((head - aData.x) * 10.0, 0.0, 1.0);
    gl_PointSize = uSize * uPixelRatio * (aData.z > 0.5 ? 1.25 : 1.0);
    vec3 color = aData.z > 0.5 ? uRed : mix(uGreen, vec3(0.85, 1.0, 0.95), 0.35);
    vColor = vec4(color, shown * (aData.z > 0.5 ? 0.6 : 0.5));
  }
`;

const POINT_FRAG = /* glsl */ `
  varying vec4 vColor;
  void main() {
    vec2 c = gl_PointCoord - 0.5;
    float d = length(c);
    float a = smoothstep(0.5, 0.2, d);
    if (a * vColor.a < 0.004) discard;
    gl_FragColor = vec4(vColor.rgb, vColor.a * a);
  }
`;

// Flat geometry (band, ribbons, dashed percentile lines) revealed along t.
const FLAT_VERT = /* glsl */ `
  attribute float aT;
  varying float vT;
  void main() {
    vT = aT;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;
const FLAT_FRAG = /* glsl */ `
  uniform vec3 uColor;
  uniform float uOpacity;
  uniform float uReveal;
  uniform float uDash;
  varying float vT;
  void main() {
    float shown = clamp((uReveal * 1.12 - vT) * 12.0, 0.0, 1.0);
    if (uDash > 0.0 && fract(vT * uDash) > 0.5) discard;
    float a = uOpacity * shown;
    if (a < 0.002) discard;
    gl_FragColor = vec4(uColor, a);
  }
`;

const GLOW_VERT = /* glsl */ `
  uniform float uSize;
  uniform float uPixelRatio;
  void main() {
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = uSize * uPixelRatio;
  }
`;
const GLOW_FRAG = /* glsl */ `
  uniform vec3 uColor;
  uniform float uOpacity;
  void main() {
    float d = length(gl_PointCoord - 0.5) * 2.0;
    float core = smoothstep(0.16, 0.0, d);
    float halo = pow(max(0.0, 1.0 - d), 2.6) * 0.55;
    float a = (core + halo) * uOpacity;
    if (a < 0.003) discard;
    gl_FragColor = vec4(mix(uColor, vec3(1.0), core), a);
  }
`;

const GRID_VERT = /* glsl */ `
  uniform vec3 uCenter;
  uniform float uRadius;
  varying float vFade;
  void main() {
    vFade = 1.0 - smoothstep(uRadius * 0.45, uRadius, distance(position, uCenter));
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;
const GRID_FRAG = /* glsl */ `
  uniform vec3 uColor;
  uniform float uOpacity;
  varying float vFade;
  void main() {
    gl_FragColor = vec4(uColor, uOpacity * vFade);
  }
`;

/* ------------------------------------------------------------------ helpers */
const easeOutCubic = (x: number) => 1 - Math.pow(1 - Math.min(1, Math.max(0, x)), 3);
const easeInOut = (x: number) => {
  const v = Math.min(1, Math.max(0, x));
  return v < 0.5 ? 4 * v * v * v : 1 - Math.pow(-2 * v + 2, 3) / 2;
};

function flatMaterial(color: string, opacity: number, dash = 0, additive = false) {
  return new ShaderMaterial({
    vertexShader: FLAT_VERT,
    fragmentShader: FLAT_FRAG,
    uniforms: { uColor: { value: new Color(color) }, uOpacity: { value: opacity }, uReveal: { value: 0 }, uDash: { value: dash } },
    transparent: true,
    depthWrite: false,
    side: DoubleSide,
    ...(additive ? { blending: AdditiveBlending } : {}),
  });
}

/** Ribbon (two rows of vertices) between lower(s) and upper(s), in the z = 0 plane. */
function ribbonGeometry(lower: (s: number) => number, upper: (s: number) => number) {
  const positions = new Float32Array((STEPS + 1) * 2 * 3);
  const t = new Float32Array((STEPS + 1) * 2);
  const index: number[] = [];
  for (let s = 0; s <= STEPS; s += 1) {
    const x = worldX(s);
    positions.set([x, lower(s), 0, x, upper(s), 0], s * 6);
    t[s * 2] = s / STEPS;
    t[s * 2 + 1] = s / STEPS;
    if (s < STEPS) {
      const a = s * 2;
      index.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
    }
  }
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new BufferAttribute(positions, 3));
  geometry.setAttribute("aT", new BufferAttribute(t, 1));
  geometry.setIndex(index);
  return geometry;
}

function lineGeometry(values: number[]) {
  const positions = new Float32Array((STEPS + 1) * 3);
  const t = new Float32Array(STEPS + 1);
  for (let s = 0; s <= STEPS; s += 1) {
    positions.set([worldX(s), worldY(values[s]), 0], s * 3);
    t[s] = s / STEPS;
  }
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new BufferAttribute(positions, 3));
  geometry.setAttribute("aT", new BufferAttribute(t, 1));
  return geometry;
}

/* ------------------------------------------------------------------ component */
export default function FuturesScene({ summary, lite, labels, onReady, onIntroDone, onFail }: FuturesSceneProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const callbacks = useRef({ onReady, onIntroDone, onFail });
  callbacks.current = { onReady, onIntroDone, onFail };

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    // A fresh canvas per mount: a force-lost context can never be reused (StrictMode remounts).
    const canvas = document.createElement("canvas");
    canvas.className = "futures-canvas";
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", ARIA_LABEL);
    host.appendChild(canvas);

    let renderer: WebGLRenderer;
    try {
      renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance", failIfMajorPerformanceCaveat: true });
    } catch {
      canvas.remove();
      callbacks.current.onFail();
      return;
    }
    const maxDpr = lite ? 1.75 : 2;
    let dpr = Math.min(window.devicePixelRatio || 1, maxDpr);
    renderer.setPixelRatio(dpr);
    renderer.setClearColor(0x000000, 0);

    const scene = new Scene();
    const camera = new PerspectiveCamera(26, 1, 0.1, 80);
    const disposables: { dispose: () => void }[] = [];
    const track = <T extends { dispose: () => void }>(item: T) => {
      disposables.push(item);
      return item;
    };

    /* ---------------- paths */
    const pathCount = lite ? 420 : 1300;
    const data = buildFuturesPaths(pathCount, summary.rawKnots);
    const stride = STEPS + 1;
    const seeds = new Float32Array(pathCount);
    let seedState = 91;
    for (let i = 0; i < pathCount; i += 1) {
      seedState = (seedState * 16807) % 2147483647;
      seeds[i] = seedState / 2147483647;
    }

    let segmentCount = 0;
    for (let i = 0; i < pathCount; i += 1) {
      const fail = data.failStep[i];
      segmentCount += Math.ceil((fail >= 0 ? fail - 1 : STEPS) / 2) + (fail >= 0 ? 4 : 0);
    }
    const positions = new Float32Array(segmentCount * 2 * 3);
    const attrs = new Float32Array(segmentCount * 2 * 3);
    const endPositions: number[] = [];
    const endData: number[] = [];
    let v = 0;
    const push = (x: number, y: number, z: number, t: number, seed: number, kind: number) => {
      positions[v * 3] = x;
      positions[v * 3 + 1] = y;
      positions[v * 3 + 2] = z;
      attrs[v * 3] = t;
      attrs[v * 3 + 1] = seed;
      attrs[v * 3 + 2] = kind;
      v += 1;
    };
    const X_SPAN = WORLD.x1 - WORLD.x0;
    for (let i = 0; i < pathCount; i += 1) {
      const base = i * stride;
      const fail = data.failStep[i];
      const last = fail >= 0 ? fail - 1 : STEPS;
      const weight = (s: number) => (fail >= 0 ? Math.min(1, Math.max(0, (s - (fail - 11)) / 10)) : 0);
      // two-month resolution: calmer curves and half the vertices
      for (let s = 0; s < last; ) {
        const n = Math.min(last, s + 2);
        push(worldX(s), worldY(data.logV[base + s]), data.z[base + s], s / STEPS, seeds[i], weight(s));
        push(worldX(n), worldY(data.logV[base + n]), data.z[base + n], n / STEPS, seeds[i], weight(n));
        s = n;
      }
      if (fail >= 0) {
        // plunge: curved drop to the "R$ 0" floor over ~2 months
        const x = worldX(last);
        const y = worldY(data.logV[base + last]);
        const z = data.z[base + last];
        let px = x;
        let py = y;
        for (let k = 1; k <= 4; k += 1) {
          const f = k / 4;
          const nx = x + f * 0.17;
          const ny = y + (WORLD.floor - y) * f * f;
          push(px, py, z, (px - WORLD.x0) / X_SPAN, seeds[i], 1);
          push(nx, ny, z, (nx - WORLD.x0) / X_SPAN, seeds[i], 1);
          px = nx;
          py = ny;
        }
        endPositions.push(px, WORLD.floor, z);
        endData.push((px - WORLD.x0) / X_SPAN, seeds[i], 1);
      } else {
        endPositions.push(worldX(STEPS), worldY(data.logV[base + STEPS]), data.z[base + STEPS]);
        endData.push(1, seeds[i], 0);
      }
    }
    const pathGeometry = track(new BufferGeometry());
    pathGeometry.setAttribute("position", new BufferAttribute(positions, 3));
    pathGeometry.setAttribute("aData", new BufferAttribute(attrs, 3));
    const pathUniforms = {
      uReveal: { value: 0 },
      uTime: { value: 0 },
      uGreen: { value: GREEN },
      uBlue: { value: BLUE },
      uRed: { value: RED },
      uNear: { value: 8 },
      uFar: { value: 16 },
      uBoost: { value: lite ? 1.5 : 0.78 },
    };
    const pathMaterial = track(
      new ShaderMaterial({ vertexShader: PATH_VERT, fragmentShader: COLOR_FRAG, uniforms: pathUniforms, transparent: true, depthWrite: false, blending: AdditiveBlending }),
    );
    scene.add(new LineSegments(pathGeometry, pathMaterial));

    const endGeometry = track(new BufferGeometry());
    endGeometry.setAttribute("position", new BufferAttribute(new Float32Array(endPositions), 3));
    endGeometry.setAttribute("aData", new BufferAttribute(new Float32Array(endData), 3));
    const pointUniforms = { uReveal: pathUniforms.uReveal, uPixelRatio: { value: dpr }, uSize: { value: lite ? 2.4 : 2.1 }, uGreen: { value: GREEN }, uRed: { value: RED } };
    const endMaterial = track(
      new ShaderMaterial({ vertexShader: POINT_VERT, fragmentShader: POINT_FRAG, uniforms: pointUniforms, transparent: true, depthWrite: false, blending: AdditiveBlending }),
    );
    scene.add(new Points(endGeometry, endMaterial));

    /* ---------------- "hoje": a single known present */
    const glowGeometry = track(new BufferGeometry());
    glowGeometry.setAttribute("position", new BufferAttribute(new Float32Array([worldX(0), worldY(summary.bands.p50[0]), 0]), 3));
    const glowUniforms = { uColor: { value: new Color("#9fcbff") }, uOpacity: { value: 0 }, uSize: { value: lite ? 30 : 38 }, uPixelRatio: pointUniforms.uPixelRatio };
    const glowMaterial = track(
      new ShaderMaterial({ vertexShader: GLOW_VERT, fragmentShader: GLOW_FRAG, uniforms: glowUniforms, transparent: true, depthWrite: false, blending: AdditiveBlending }),
    );
    scene.add(new Points(glowGeometry, glowMaterial));

    /* ---------------- percentile band, median ribbon and dashed P10/P90 */
    const { bands } = summary;
    const bandMaterial = track(flatMaterial("#35e6a1", 0.1));
    scene.add(new Mesh(track(ribbonGeometry((s) => worldY(bands.p25[s]), (s) => worldY(bands.p75[s]))), bandMaterial));
    const medianGlowMaterial = track(flatMaterial("#35e6a1", 0.16, 0, true));
    scene.add(new Mesh(track(ribbonGeometry((s) => worldY(bands.p50[s]) - 0.035, (s) => worldY(bands.p50[s]) + 0.035)), medianGlowMaterial));
    const medianMaterial = track(flatMaterial("#e6fff3", 0.95));
    scene.add(new Mesh(track(ribbonGeometry((s) => worldY(bands.p50[s]) - 0.011, (s) => worldY(bands.p50[s]) + 0.011)), medianMaterial));
    const tailMaterial = track(flatMaterial("#c3ccd6", 0.55, 34));
    scene.add(new Line(track(lineGeometry(bands.p10)), tailMaterial));
    scene.add(new Line(track(lineGeometry(bands.p90)), tailMaterial));
    const flatMaterials = [bandMaterial, medianGlowMaterial, medianMaterial, tailMaterial];

    /* ---------------- floor grid + year-5 measuring frame */
    const gridPositions: number[] = [];
    const zEdge = 1.35;
    for (let year = 0; year <= 5; year += 1) {
      const x = WORLD.x0 + year;
      gridPositions.push(x, WORLD.floor, -zEdge, x, WORLD.floor, zEdge);
    }
    for (let z = -zEdge; z <= zEdge + 0.001; z += zEdge / 3) {
      gridPositions.push(WORLD.x0 - 0.3, WORLD.floor, z, WORLD.x1 + 2.3, WORLD.floor, z);
    }
    const frameTop = WORLD.height + 0.1;
    gridPositions.push(
      WORLD.x1, WORLD.floor, -zEdge, WORLD.x1, frameTop, -zEdge,
      WORLD.x1, frameTop, -zEdge, WORLD.x1, frameTop, zEdge,
      WORLD.x1, frameTop, zEdge, WORLD.x1, WORLD.floor, zEdge,
    );
    const gridGeometry = track(new BufferGeometry());
    gridGeometry.setAttribute("position", new BufferAttribute(new Float32Array(gridPositions), 3));
    const gridMaterial = track(
      new ShaderMaterial({
        vertexShader: GRID_VERT,
        fragmentShader: GRID_FRAG,
        uniforms: { uColor: { value: new Color("#5b6b7c") }, uOpacity: { value: 0 }, uCenter: { value: new Vector3(0.2, WORLD.floor, 0) }, uRadius: { value: 5.2 } },
        transparent: true,
        depthWrite: false,
      }),
    );
    scene.add(new LineSegments(gridGeometry, gridMaterial));

    /* ---------------- unit histogram: 100 cubes, each = 100 futures */
    const cubeSize = WORLD.cubePitch * 0.78;
    const cubeGeometry = track(new BoxGeometry(cubeSize, cubeSize, cubeSize));
    const cubeMaterial = track(new MeshLambertMaterial({ color: 0xffffff, emissive: new Color("#06140f") }));
    const cubeColor: Record<CubeRole | "failure", Color> = {
      median: new Color("#d6fff0"),
      core: new Color("#35e6a1"),
      inner: new Color("#1f9e70"),
      tail: new Color("#3f7bc0"),
      failure: new Color("#ff6b78"),
    };
    type Cube = { slot: Vector3; start: number; color: Color };
    const cubes: Cube[] = [];
    for (const { bin, cubes: n } of summary.cubeBins) {
      const role = cubeRole(bin, bands);
      for (let k = 0; k < n; k += 1) cubes.push({ slot: new Vector3(...cubeSlot(bin, k)), start: 0.86 + k * 0.035 + bin * 0.004, color: cubeColor[role] });
    }
    for (let k = 0; k < summary.failureCubes; k += 1) {
      cubes.push({ slot: new Vector3(...failureCubeSlot(k)), start: 0.8 + k * 0.035, color: cubeColor.failure });
    }
    const cubeMesh = new InstancedMesh(cubeGeometry, cubeMaterial, cubes.length);
    cubeMesh.instanceMatrix.setUsage(DynamicDrawUsage);
    cubes.forEach((cube, index) => cubeMesh.setColorAt(index, cube.color));
    scene.add(cubeMesh);
    scene.add(new AmbientLight(0xffffff, 0.75));
    const sun = new DirectionalLight(0xffffff, 1.7);
    sun.position.set(2.5, 6, 4);
    scene.add(sun);

    const matrix = new Matrix4();
    const cubePosition = new Vector3();
    let cubesSettled = false;
    const updateCubes = (reveal: number) => {
      if (cubesSettled) return;
      let all = true;
      cubes.forEach((cube, index) => {
        const p = easeOutCubic((reveal - cube.start) / 0.22);
        if (p < 1) all = false;
        // cubes slide out of the year-5 plane into their stack slot
        cubePosition.set(WORLD.x1 + (cube.slot.x - WORLD.x1) * p, cube.slot.y, cube.slot.z);
        const scale = Math.max(0.0001, p);
        matrix.makeScale(scale, scale, scale).setPosition(cubePosition);
        cubeMesh.setMatrixAt(index, matrix);
      });
      cubeMesh.instanceMatrix.needsUpdate = true;
      cubesSettled = all;
    };
    updateCubes(0);

    /* ---------------- camera rig */
    const anchors = labelAnchors(summary);
    const anchorVectors = Object.fromEntries(Object.entries(anchors).map(([key, value]) => [key, new Vector3(...value)])) as Record<LabelKey, Vector3>;
    const center = new Vector3(0.3, 1.32, 0);
    const target = center.clone();
    const baseYaw = lite ? 0.3 : 0.36;
    const basePitch = 0.17;
    let distance = 12;
    let width = 1;
    let height = 1;
    const pointer = { x: 0, y: 0 };
    const eased = { yaw: baseYaw + 0.22, pitch: basePitch + 0.05, dolly: 1.12 };

    const resize = () => {
      for (const key of Object.keys(labelWidths)) delete labelWidths[key as LabelKey];
      width = Math.max(1, host.clientWidth);
      height = Math.max(1, host.clientHeight);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      // Fit the composition into the stage minus a right-hand gutter reserved for the HTML labels.
      const gutter = Math.min(width * 0.32, lite ? 112 : 140);
      const tanHalf = Math.tan((camera.fov * Math.PI) / 360);
      const fitWidth = 3.05 / (tanHalf * ((width - gutter) / height));
      const fitHeight = 2.05 / tanHalf;
      distance = Math.max(fitWidth, fitHeight);
      const pixelsPerUnit = height / (2 * distance * tanHalf);
      target.copy(center);
      target.x += gutter / 2 / pixelsPerUnit;
      camera.updateProjectionMatrix();
    };

    const projected = new Vector3();
    const labelWidths: Partial<Record<LabelKey, number>> = {};
    const placeLabels = () => {
      const nodes = labels.current;
      if (!nodes) return;
      (Object.keys(anchorVectors) as LabelKey[]).forEach((key) => {
        const node = nodes[key];
        if (!node) return;
        projected.copy(anchorVectors[key]).project(camera);
        let labelWidth = labelWidths[key];
        if (labelWidth === undefined) labelWidth = labelWidths[key] = node.offsetWidth;
        // keep labels inside the stage (no horizontal overflow on small screens)
        const x = Math.min((projected.x * 0.5 + 0.5) * width, width - labelWidth - 4);
        const y = (-projected.y * 0.5 + 0.5) * height;
        node.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`;
      });
    };

    /* ---------------- loop, pause & adaptive quality */
    let elapsed = 0;
    let last = performance.now();
    let raf = 0;
    let inView = true;
    let readySent = false;
    let introSent = false;
    let frameSamples = 0;
    let frameTotal = 0;

    const render = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      elapsed += dt;

      const reveal = Math.min(1.35, easeOutCubic(elapsed / INTRO_SECONDS) * 1.35);
      pathUniforms.uReveal.value = reveal;
      pathUniforms.uTime.value = elapsed;
      flatMaterials.forEach((material) => (material.uniforms.uReveal.value = Math.max(0, reveal - 0.12)));
      gridMaterial.uniforms.uOpacity.value = 0.34 * easeOutCubic(elapsed / 1.2);
      glowUniforms.uOpacity.value = easeOutCubic(elapsed / 0.8) * (0.9 + Math.sin(elapsed * 1.3) * 0.08);
      updateCubes(reveal);

      const settle = easeInOut(elapsed / (INTRO_SECONDS + 0.8));
      const drift = Math.sin(elapsed * 0.11) * 0.045;
      const k = 1 - Math.exp(-dt * 2.4);
      eased.yaw += (baseYaw + 0.22 * (1 - settle) + pointer.x * 0.16 + drift - eased.yaw) * k;
      eased.pitch += (basePitch + 0.05 * (1 - settle) - pointer.y * 0.07 + Math.cos(elapsed * 0.09) * 0.012 - eased.pitch) * k;
      eased.dolly += (1 + 0.12 * (1 - settle) - eased.dolly) * k;
      const r = distance * eased.dolly;
      camera.position.set(
        target.x + r * Math.sin(eased.yaw) * Math.cos(eased.pitch),
        target.y + r * Math.sin(eased.pitch),
        target.z + r * Math.cos(eased.yaw) * Math.cos(eased.pitch),
      );
      camera.lookAt(target);
      pathUniforms.uNear.value = r - 1.5;
      pathUniforms.uFar.value = r + 4.5;

      renderer.render(scene, camera);
      placeLabels();

      if (!readySent) {
        readySent = true;
        callbacks.current.onReady();
      }
      if (!introSent && elapsed > INTRO_SECONDS * 0.9) {
        introSent = true;
        callbacks.current.onIntroDone();
      }
      // Adaptive resolution: rolling 60-frame window; step the pixel ratio down while the GPU
      // can't hold ~48 fps (never below 1).
      if (elapsed > 0.6 && dpr > 1) {
        frameSamples += 1;
        frameTotal += dt;
        if (frameSamples === 60) {
          if (frameTotal / 60 > 1 / 48) {
            dpr = Math.max(1, dpr - 0.25);
            renderer.setPixelRatio(dpr);
            pointUniforms.uPixelRatio.value = dpr;
            resize();
          }
          frameSamples = 0;
          frameTotal = 0;
        }
      }
    };

    const loop = (now: number) => {
      raf = requestAnimationFrame(loop);
      render(now);
    };
    const updateRunning = () => {
      const shouldRun = inView && document.visibilityState === "visible";
      if (shouldRun && !raf) {
        last = performance.now();
        raf = requestAnimationFrame(loop);
      } else if (!shouldRun && raf) {
        cancelAnimationFrame(raf);
        raf = 0;
      }
    };

    const intersection = new IntersectionObserver(([entry]) => {
      inView = entry.isIntersecting;
      updateRunning();
    });
    intersection.observe(host);
    const resizeObserver = new ResizeObserver(() => {
      resize();
      if (!raf) render(performance.now());
    });
    resizeObserver.observe(host);
    const onVisibility = () => updateRunning();
    document.addEventListener("visibilitychange", onVisibility);
    const onPointer = (event: PointerEvent) => {
      pointer.x = Math.max(-1, Math.min(1, (event.clientX / window.innerWidth) * 2 - 1));
      pointer.y = Math.max(-1, Math.min(1, (event.clientY / window.innerHeight) * 2 - 1));
    };
    window.addEventListener("pointermove", onPointer, { passive: true });
    const onContextLost = (event: Event) => {
      event.preventDefault();
      callbacks.current.onFail();
    };
    canvas.addEventListener("webglcontextlost", onContextLost);

    resize();
    updateRunning();

    return () => {
      cancelAnimationFrame(raf);
      raf = 0;
      intersection.disconnect();
      resizeObserver.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("pointermove", onPointer);
      canvas.removeEventListener("webglcontextlost", onContextLost);
      cubeMesh.dispose();
      disposables.forEach((item) => item.dispose());
      scene.clear();
      renderer.dispose();
      renderer.forceContextLoss();
      canvas.remove();
    };
  }, [summary, lite, labels]);

  return <div ref={hostRef} className="futures-canvas-host" />;
}

