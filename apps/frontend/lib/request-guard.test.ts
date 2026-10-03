import { describe, expect, it } from "vitest";
import { createRequestGuard } from "./request-guard";

describe("createRequestGuard", () => {
  it("keeps a single in-flight token current until a new request starts", () => {
    const guard = createRequestGuard();
    const token = guard.start();
    expect(guard.isCurrent(token)).toBe(true);
    expect(guard.isCurrent(token)).toBe(true);
  });

  it("invalidates an earlier token as soon as a new request starts", () => {
    const guard = createRequestGuard();
    const first = guard.start();
    const second = guard.start();
    expect(guard.isCurrent(first)).toBe(false);
    expect(guard.isCurrent(second)).toBe(true);
  });

  it("models the double-click race: the later click wins even if its response resolves first", () => {
    const guard = createRequestGuard();
    const clickA = guard.start(); // user clicks "Analisar" with value A
    const clickB = guard.start(); // user clicks again with value B before A resolves
    // B's response happens to resolve before A's — A must still be ignored.
    expect(guard.isCurrent(clickA)).toBe(false);
    expect(guard.isCurrent(clickB)).toBe(true);
  });

  it("treats a token from a different guard instance as never current", () => {
    const guardOne = createRequestGuard();
    const guardTwo = createRequestGuard();
    const token = guardOne.start();
    expect(guardTwo.isCurrent(token)).toBe(false);
  });
});
