import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getAdminOverview,
  getWaitlist,
  getWaitlistCsvUrl,
  searchAdminWorkspaces,
  updateWorkspacePlan,
} from "./admin";

function mockJsonFetch(body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: true,
    json: async () => body,
  });
}

/** CSRF fetch first, then the real request — mirrors client.ts's mutation flow. */
function mockCsrfThenJsonFetch(body: unknown) {
  let call = 0;
  return vi.fn().mockImplementation(async () => {
    call += 1;
    if (call === 1) {
      return { ok: true, json: async () => ({ csrf_token: "token_1" }) };
    }
    return { ok: true, json: async () => body };
  });
}

describe("admin API client", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllGlobals();
  });

  it("getAdminOverview requests the overview endpoint and parses the response", async () => {
    const payload = {
      users: 42,
      workspaces_by_plan: { free: 30, empresario: 8, consultor: 3, escritorio: 1 },
      startups: 55,
      simulations: 120,
      simulations_last_7d: 9,
      reports: 17,
      waitlist_count: 64,
    };
    const fetchMock = mockJsonFetch(payload);
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await getAdminOverview();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/admin/overview");
    expect(init.method).toBe("GET");
    expect(result).toEqual(payload);
  });

  it("getWaitlist requests the JSON waitlist endpoint and parses the list", async () => {
    const payload = [
      {
        id: "wl_1",
        email: "lead@example.com",
        plan_interest: "consultor",
        source: "landing",
        created_at: "2026-09-01T10:00:00Z",
      },
    ];
    const fetchMock = mockJsonFetch(payload);
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await getWaitlist();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/admin/waitlist");
    expect(url).not.toContain("format=csv");
    expect(init.method).toBe("GET");
    expect(result).toEqual(payload);
  });

  it("getWaitlistCsvUrl builds an absolute URL to the csv format of the waitlist endpoint", () => {
    const url = getWaitlistCsvUrl();
    expect(url).toContain("/api/v1/admin/waitlist");
    expect(url).toContain("format=csv");
  });

  it("searchAdminWorkspaces URL-encodes the email query parameter", async () => {
    const payload = [
      {
        id: "ws_1",
        plan: "consultor",
        created_at: "2026-09-01T10:00:00Z",
        startup_count: 3,
        member_email: "owner+tag@example.com",
      },
    ];
    const fetchMock = mockJsonFetch(payload);
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await searchAdminWorkspaces("owner+tag@example.com");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/admin/workspaces?email=");
    expect(url).toContain(encodeURIComponent("owner+tag@example.com"));
    expect(url).not.toContain("owner+tag@example.com&");
    expect(init.method).toBe("GET");
    expect(result).toEqual(payload);
  });

  it("updateWorkspacePlan posts the plan payload after fetching a CSRF token", async () => {
    const response = { id: "ws_1", plan: "escritorio" };
    const fetchMock = mockCsrfThenJsonFetch(response);
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await updateWorkspacePlan("ws_1", "escritorio");

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [csrfUrl] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(csrfUrl).toContain("/api/v1/auth/csrf");
    const [url, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(url).toContain("/api/v1/admin/workspaces/ws_1/plan");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ plan: "escritorio" });
    const headers = new Headers(init.headers);
    expect(headers.get("X-CSRF-Token")).toBe("token_1");
    expect(result).toEqual(response);
  });
});
