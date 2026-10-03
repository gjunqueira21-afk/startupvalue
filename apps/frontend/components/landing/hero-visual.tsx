"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { FALLBACK_VIEW, fallbackPercent, formatMillions, formatPercent, labelAnchors, type FuturesSummary, type LabelKey } from "./futures-model";
import { markIntroSeen, shouldPlayIntro } from "./intro-timeline";
import styles from "./hero-visual.module.css";

// WebGL scene is client-only and lives in its own chunk; it is only requested after the
// page is idle, when the hero is on screen, WebGL is available and motion is allowed.
const FuturesScene = dynamic(() => import("./futures-scene"), { ssr: false, loading: () => null });

type Mode = "static" | "loading" | "live";

function hasCapableWebGL() {
  try {
    const canvas = document.createElement("canvas");
    const options = { failIfMajorPerformanceCaveat: true } as WebGLContextAttributes;
    const gl = (canvas.getContext("webgl2", options) || canvas.getContext("webgl", options)) as WebGLRenderingContext | null;
    if (!gl) return false;
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    return true;
  } catch {
    return false;
  }
}

/** sessionStorage, or null where merely touching it throws (blocked storage, sandboxed frames). */
function sessionStore(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

// Interactions that skip the intro (mirrors the scene's own skip listeners).
const EARLY_SKIP_EVENTS = ["pointerdown", "wheel", "keydown", "touchstart", "scroll"] as const;

/**
 * The hero copy (headline, subtitle, CTAs) is server-rendered visible. Only when the intro
 * actually plays does a client effect mark it `data-intro="playing"` (hidden by CSS); it
 * flips to "done" when the scene reveals the UI, or whenever the intro is abandoned.
 */
function setCopyIntro(stage: HTMLElement | null, state: "playing" | "done") {
  const copy = stage?.closest("section")?.querySelector<HTMLElement>("[data-intro-target]");
  if (!copy) return;
  if (state === "done" && !copy.dataset.intro) return; // never played: leave it untouched
  copy.dataset.intro = state;
}

export function HeroVisual({ summary, fallback }: { summary: FuturesSummary; fallback: ReactNode }) {
  const stageRef = useRef<HTMLDivElement>(null);
  const labelRefs = useRef<Partial<Record<LabelKey, HTMLElement | null>>>({});
  const [mode, setMode] = useState<Mode>("static");
  const [lite, setLite] = useState(false);
  const [introDone, setIntroDone] = useState(false);
  // labels enter without the staged failure delay when the intro was skipped / never played
  const [introSettled, setIntroSettled] = useState(false);
  // decided once per scene mount; the scene reads it only when it is built
  const [playIntro, setPlayIntro] = useState(false);
  // Someone who scrolled/clicked/typed before the scene drew its first frame gets it settled.
  // These listeners stay alive through the chunk download until the scene reports ready (by
  // then its own skip listeners are registered); the scene reads the ref when it is built.
  const interactedRef = useRef(false);
  const removeEarlyRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    let idleHandle = 0;
    let timeoutHandle = 0;
    let observer: IntersectionObserver | null = null;

    const earlyOptions: AddEventListenerOptions = { capture: true, passive: true };
    const removeEarly = () => {
      removeEarlyRef.current?.();
      removeEarlyRef.current = null;
    };
    const addEarly = () => {
      if (removeEarlyRef.current || interactedRef.current) return;
      const onEarly = () => {
        interactedRef.current = true;
        removeEarly();
      };
      EARLY_SKIP_EVENTS.forEach((type) => window.addEventListener(type, onEarly, earlyOptions));
      removeEarlyRef.current = () => EARLY_SKIP_EVENTS.forEach((type) => window.removeEventListener(type, onEarly, earlyOptions));
    };

    const start = () => {
      if (reduced.matches || !hasCapableWebGL()) {
        removeEarly(); // static fallback: nothing will ever play
        return;
      }
      addEarly();
      observer = new IntersectionObserver(
        ([entry]) => {
          if (!entry.isIntersecting) return;
          observer?.disconnect();
          const mount = () => {
            const storage = sessionStore();
            const play = !interactedRef.current && (storage ? shouldPlayIntro(storage) : true);
            setPlayIntro(play);
            setIntroSettled(false);
            setLite(window.matchMedia("(max-width: 760px)").matches || (navigator.hardwareConcurrency || 8) <= 2);
            setMode("loading");
            // the headline is hidden only once the scene draws its first playing frame (onReady)
          };
          if ("requestIdleCallback" in window) idleHandle = window.requestIdleCallback(mount, { timeout: 1500 });
          else timeoutHandle = globalThis.setTimeout(mount, 400) as unknown as number;
        },
        { rootMargin: "200px" },
      );
      observer.observe(stage);
    };

    const onMotionChange = () => {
      if (reduced.matches) {
        observer?.disconnect();
        setMode("static");
        setIntroDone(false);
        setCopyIntro(stage, "done");
      } else {
        start();
      }
    };

    start();
    reduced.addEventListener("change", onMotionChange);
    return () => {
      observer?.disconnect();
      removeEarly();
      if (idleHandle) window.cancelIdleCallback(idleHandle);
      if (timeoutHandle) window.clearTimeout(timeoutHandle);
      reduced.removeEventListener("change", onMotionChange);
      setCopyIntro(stage, "done");
    };
  }, []);

  const onReady = useCallback((playing: boolean) => {
    setMode("live");
    // the scene's own skip listeners are live now: hand off from the early ones
    removeEarlyRef.current?.();
    removeEarlyRef.current = null;
    if (playing) setCopyIntro(stageRef.current, "playing");
  }, []);
  const onIntroDone = useCallback((settled: boolean) => {
    setIntroSettled(settled);
    setIntroDone(true);
    setCopyIntro(stageRef.current, "done");
    const storage = sessionStore();
    if (storage) markIntroSeen(storage);
  }, []);
  const onFail = useCallback(() => {
    removeEarlyRef.current?.();
    removeEarlyRef.current = null;
    setMode("static");
    setIntroDone(false);
    setCopyIntro(stageRef.current, "done");
  }, []);

  const anchors = labelAnchors(summary);
  const place = (key: LabelKey) => {
    const [left, top] = fallbackPercent(anchors[key]);
    return { left: `${left}%`, top: `${top}%` };
  };
  const ref = (key: LabelKey) => (node: HTMLElement | null) => {
    labelRefs.current[key] = node;
  };
  const { terminal } = summary;
  const live = mode === "live";
  const stageClass = [styles.stage, live ? styles.live : "", live && introDone ? styles.labelsIn : "", introSettled ? styles.labelsNow : ""].join(" ");

  return (
    <figure className={styles.visual}>
      <div className={styles.hud}>
        <span className={styles.hudTitle}>
          <i aria-hidden="true" /> Simulação Monte Carlo
        </span>
        <span className={styles.hudMeta}>10.000 cenários · seed 471829 · 60 meses</span>
      </div>

      <div className={stageClass} ref={stageRef}>
        <div className={styles.fallback}>
          <div className={styles.frame} style={{ aspectRatio: `${FALLBACK_VIEW.maxX - FALLBACK_VIEW.minX} / ${FALLBACK_VIEW.maxY - FALLBACK_VIEW.minY}` }}>
            {fallback}
            <div className={styles.labels} aria-hidden="true" data-layer="static">
              {!live && <StaticLabels place={place} summary={summary} />}
            </div>
          </div>
        </div>

        {mode !== "static" && (
          <div className={styles.canvasHost}>
            <FuturesScene summary={summary} lite={lite} labels={labelRefs} playIntro={playIntro} interacted={interactedRef} onReady={onReady} onIntroDone={onIntroDone} onFail={onFail} />
          </div>
        )}

        {live && (
          <div className={`${styles.labels} ${styles.liveLabels}`} aria-hidden="true">
            <span className={`${styles.label} ${styles.labelToday}`} ref={ref("today")}><b>Hoje</b></span>
            <span className={`${styles.label} ${styles.labelYear}`} ref={ref("year5")}><b>Ano 5</b></span>
            <span className={`${styles.label} ${styles.labelPct}`} ref={ref("p90")}><b>P90</b>{formatMillions(terminal.p90)}</span>
            <span className={`${styles.label} ${styles.labelPct} ${styles.labelMedian}`} ref={ref("p50")}><b>P50</b>{formatMillions(terminal.p50)}</span>
            <span className={`${styles.label} ${styles.labelPct}`} ref={ref("p10")}><b>P10</b>{formatMillions(terminal.p10)}</span>
            <span className={`${styles.label} ${styles.labelPct} ${styles.labelFailure}`} ref={ref("failure")}><b>Falência</b>{formatPercent(summary.failureRate)}</span>
          </div>
        )}
      </div>

      <figcaption className={styles.caption}>
        <ul className={styles.legend} aria-label="Legenda">
          <li><i className={styles.keyCube} aria-hidden="true" /> 1 cubo = 100 cenários</li>
          <li><i className={styles.keyMedian} aria-hidden="true" /> P50 · mediana</li>
          <li><i className={styles.keyBand} aria-hidden="true" /> P25–P75</li>
          <li><i className={styles.keyFailure} aria-hidden="true" /> Falência</li>
        </ul>
        <p className={styles.note}>Dados ilustrativos · Equity via DCF · BRL</p>
        <p className={styles.srOnly}>
          Distribuição ilustrativa após 5 anos: P10 {formatMillions(terminal.p10)}, P25 {formatMillions(terminal.p25)}, P50 {formatMillions(terminal.p50)},
          P75 {formatMillions(terminal.p75)}, P90 {formatMillions(terminal.p90)}. {formatPercent(summary.failureRate)} dos cenários terminam em falência.
        </p>
      </figcaption>
    </figure>
  );
}

function StaticLabels({ place, summary }: { place: (key: LabelKey) => { left: string; top: string }; summary: FuturesSummary }) {
  const { terminal } = summary;
  return (
    <>
      <span className={`${styles.label} ${styles.labelToday}`} style={place("today")}><b>Hoje</b></span>
      <span className={`${styles.label} ${styles.labelYear}`} style={place("year5")}><b>Ano 5</b></span>
      <span className={`${styles.label} ${styles.labelPct}`} style={place("p90")}><b>P90</b>{formatMillions(terminal.p90)}</span>
      <span className={`${styles.label} ${styles.labelPct} ${styles.labelMedian}`} style={place("p50")}><b>P50</b>{formatMillions(terminal.p50)}</span>
      <span className={`${styles.label} ${styles.labelPct}`} style={place("p10")}><b>P10</b>{formatMillions(terminal.p10)}</span>
      <span className={`${styles.label} ${styles.labelPct} ${styles.labelFailure}`} style={place("failure")}><b>Falência</b>{formatPercent(summary.failureRate)}</span>
    </>
  );
}
