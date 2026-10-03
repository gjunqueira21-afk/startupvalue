import { describe, expect, it, vi } from "vitest";
import { submitWaitlist, WAITLIST_RETRY_MESSAGE } from "./waitlist-form";

/**
 * This repo has no React Testing Library, and vitest runs in the default
 * "node" environment (no DOM), so rendering <WaitlistForm /> and clicking
 * through it isn't feasible here. Instead this exercises the pure
 * `submitWaitlist` helper the component delegates to on submit, which covers
 * the payload shape and the success / 429 / network-error outcomes the
 * component maps to the brief's two copy strings.
 */
function mockFetch(response: { ok: boolean; status?: number }) {
  return vi.fn().mockResolvedValue({
    ok: response.ok,
    status: response.status ?? (response.ok ? 200 : 500),
  });
}

describe("submitWaitlist", () => {
  it("posts {email, plan_interest, source} to /api/v1/waitlist and reports ok on success", async () => {
    const fetchMock = mockFetch({ ok: true, status: 201 });

    const result = await submitWaitlist(fetchMock as unknown as typeof fetch, {
      email: "dono@empresa.com.br",
      plan: "consultor",
      source: "landing",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/waitlist");
    expect(init.method).toBe("POST");
    // A session cookie would trip the backend CSRF guard for logged-in visitors.
    expect(init.credentials).toBe("omit");
    expect(JSON.parse(init.body as string)).toEqual({
      email: "dono@empresa.com.br",
      plan_interest: "consultor",
      source: "landing",
    });
    expect(result).toEqual({ ok: true });
  });

  it("returns the retry message on a 429 (waitlist_rate_limited) response", async () => {
    const fetchMock = mockFetch({ ok: false, status: 429 });

    const result = await submitWaitlist(fetchMock as unknown as typeof fetch, {
      email: "dono@empresa.com.br",
      plan: "empresario",
      source: "pricing",
    });

    expect(result).toEqual({ ok: false, message: WAITLIST_RETRY_MESSAGE });
  });

  it("returns the retry message when fetch rejects (network error)", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    const result = await submitWaitlist(fetchMock as unknown as typeof fetch, {
      email: "dono@empresa.com.br",
      plan: "free",
      source: "landing",
    });

    expect(result).toEqual({ ok: false, message: WAITLIST_RETRY_MESSAGE });
  });
});
