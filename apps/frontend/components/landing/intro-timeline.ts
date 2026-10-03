/**
 * Pure timeline for the hero's three-act intro. No three.js, no DOM: the scene and the
 * hero copy both derive their state from `introFrame(elapsed)`, which keeps the
 * choreography testable and lets any caller jump to the end with `introFrame(Infinity)`.
 *
 *   act 1 (0–2 s)   the single number: every future collapsed onto the median line
 *   act 2 (2–5 s)   the fan of futures explodes open from that line
 *   act 3 (5–7 s)   failing futures plunge, the distribution condenses, the camera settles
 */
export const PRELUDE_SECONDS = 2.0; // act 1: the single number
export const SWEEP_SECONDS = 3.0; // act 2: fan-out of futures
export const FALL_SECONDS = 1.4; // act 3: distribution condenses
export const SETTLE_SECONDS = 0.6;
export const INTRO_TOTAL = PRELUDE_SECONDS + SWEEP_SECONDS + FALL_SECONDS + SETTLE_SECONDS; // 7.0

/**
 * Labels and headline enter at the start of act 3 (prelude + sweep = 5.0 s), in step with
 * the fall and the camera settle, per the approved spec.
 */
export const REVEAL_UI_SECONDS = PRELUDE_SECONDS + SWEEP_SECONDS;

export const INTRO_STORAGE_KEY = "qv-intro-seen";

export type IntroFrame = {
  /** 0→1 inside act 1; paths collapsed onto the median while < 1 */
  prelude: number;
  /** 0→1 spread of the fan (act 2); drives the uSpread uniform */
  spread: number;
  /** 0→1 condensation into the terminal distribution (act 3) */
  fall: number;
  /** 0→1 camera settle; 1 = final resting composition */
  settle: number;
  /** labels/headline may enter */
  revealUi: boolean;
};

// Duplicated from futures-scene.tsx on purpose (the scene still uses easeOutCubic for cube
// pops and fades): importing the scene would pull three.js into this module and its tests.
// Keep the copies identical.
const easeOutCubic = (x: number) => 1 - Math.pow(1 - Math.min(1, Math.max(0, x)), 3);
const easeInOut = (x: number) => {
  const v = Math.min(1, Math.max(0, x));
  return v < 0.5 ? 4 * v * v * v : 1 - Math.pow(-2 * v + 2, 3) / 2;
};

export function introFrame(elapsed: number): IntroFrame {
  const t = Number.isNaN(elapsed) ? 0 : elapsed;
  return {
    prelude: easeInOut(t / PRELUDE_SECONDS),
    spread: easeOutCubic((t - PRELUDE_SECONDS) / SWEEP_SECONDS),
    fall: easeInOut((t - PRELUDE_SECONDS - SWEEP_SECONDS) / FALL_SECONDS),
    settle: easeInOut(t / INTRO_TOTAL),
    revealUi: t >= REVEAL_UI_SECONDS,
  };
}

/** True unless the intro already played this session; unreadable storage ⇒ play. */
export function shouldPlayIntro(storage: Pick<Storage, "getItem">): boolean {
  try {
    return storage.getItem(INTRO_STORAGE_KEY) !== "1";
  } catch {
    return true;
  }
}

/** Remembers that the intro played; storage failures are swallowed. */
export function markIntroSeen(storage: Pick<Storage, "setItem">): void {
  try {
    storage.setItem(INTRO_STORAGE_KEY, "1");
  } catch {
    /* private mode / blocked storage: the intro simply plays again next time */
  }
}
