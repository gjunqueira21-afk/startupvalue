import { describe, expect, it } from "vitest";
import { INTRO_TOTAL, PRELUDE_SECONDS, REVEAL_UI_SECONDS, SWEEP_SECONDS, introFrame, markIntroSeen, shouldPlayIntro } from "./intro-timeline";

describe("introFrame", () => {
  it("lasts exactly seven seconds", () => {
    expect(INTRO_TOTAL).toBe(7);
  });

  it("starts with everything at rest", () => {
    const frame = introFrame(0);
    expect(frame.prelude).toBe(0);
    expect(frame.spread).toBe(0);
    expect(frame.fall).toBe(0);
    expect(frame.revealUi).toBe(false);
  });

  it("ends act 1 with the prelude complete and the fan still collapsed", () => {
    const frame = introFrame(2);
    expect(frame.prelude).toBe(1);
    expect(frame.spread).toBe(0);
  });

  it("ends act 2 with the fan fully spread", () => {
    expect(introFrame(5).spread).toBe(1);
  });

  it("reveals the UI at 5.0 s, the start of act 3", () => {
    expect(REVEAL_UI_SECONDS).toBe(5);
    expect(REVEAL_UI_SECONDS).toBe(PRELUDE_SECONDS + SWEEP_SECONDS);
    expect(introFrame(5.0).revealUi).toBe(true);
    expect(introFrame(4.99).revealUi).toBe(false);
    expect(introFrame(3.8).revealUi).toBe(false);
  });

  it("is fully settled at 7 s and at Infinity", () => {
    for (const elapsed of [7, Infinity]) {
      expect(introFrame(elapsed)).toEqual({ prelude: 1, spread: 1, fall: 1, settle: 1, revealUi: true });
    }
  });

  it("never moves backwards", () => {
    const fields = ["prelude", "spread", "fall", "settle"] as const;
    let previous = introFrame(0);
    for (let step = 1; step <= 800; step += 1) {
      const current = introFrame(step / 100);
      for (const field of fields) expect(current[field]).toBeGreaterThanOrEqual(previous[field]);
      if (previous.revealUi) expect(current.revealUi).toBe(true);
      previous = current;
    }
  });
});

describe("session gate", () => {
  const throwing = {
    getItem: () => {
      throw new Error("denied");
    },
    setItem: () => {
      throw new Error("denied");
    },
  };

  it("plays unless the intro was already seen this session", () => {
    expect(shouldPlayIntro({ getItem: () => null })).toBe(true);
    expect(shouldPlayIntro({ getItem: (key) => (key === "qv-intro-seen" ? "1" : null) })).toBe(false);
  });

  it("plays when storage throws", () => {
    expect(shouldPlayIntro(throwing)).toBe(true);
  });

  it("marks the intro as seen", () => {
    const store = new Map<string, string>();
    markIntroSeen({ setItem: (key, value) => void store.set(key, value) });
    expect(store.get("qv-intro-seen")).toBe("1");
    expect(shouldPlayIntro({ getItem: (key) => store.get(key) ?? null })).toBe(false);
  });

  it("swallows a throwing storage when marking", () => {
    expect(() => markIntroSeen(throwing)).not.toThrow();
  });
});
