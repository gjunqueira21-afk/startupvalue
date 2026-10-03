import { afterEach, describe, expect, it, vi } from "vitest";
import { DEFAULT_DRAFT } from "../../components/wizard/defaults";
import { createSimulation, deleteSimulation, getTarget } from "./simulations";

function mockJsonFetch(body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: true,
    json: async () => body,
  });
}

describe("getTarget", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllGlobals();
  });

  it("requests the target endpoint with the value query param and passes the plan through typed", async () => {
    const payload = {
      simulation_id: "sim_1",
      result_hash: "hash_1",
      basis: "equity_dcf",
      target: 5_000_000,
      scenario_count: 1_000,
      hit_count: 120,
      miss_count: 880,
      probability: 0.12,
      wilson95_low: 0.1,
      wilson95_high: 0.14,
      comparisons: [],
      plan: {
        status: "available",
        hit_count: 120,
        required_revenue_cagr: 0.35,
        hit_ebitda_margin: 0.18,
        miss_revenue_cagr: 0.12,
        miss_ebitda_margin: 0.05,
        trajectory: [{ year: 1, revenue: 1_000_000 }],
      },
    };
    const fetchMock = mockJsonFetch(payload);
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await getTarget("sim_1", 5_000_000);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/simulations/sim_1/target?value=5000000");
    expect(init.method).toBe("GET");
    expect(result.plan).toEqual(payload.plan);
    expect(result.hit_count).toBe(120);
  });

  it("passes plan through as null when the workspace is not entitled to the section", async () => {
    const fetchMock = mockJsonFetch({
      simulation_id: "sim_1",
      result_hash: "hash_1",
      basis: "equity_dcf",
      target: 1,
      scenario_count: 1,
      hit_count: 0,
      miss_count: 1,
      probability: 0,
      wilson95_low: 0,
      wilson95_high: 0,
      comparisons: [],
      plan: null,
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await getTarget("sim_1", 1);

    expect(result.plan).toBeNull();
  });

  it("URL-encodes a fractional target value", async () => {
    const fetchMock = mockJsonFetch({
      simulation_id: "sim_1", result_hash: "hash_1", basis: "equity_dcf", target: 1.5,
      scenario_count: 1, hit_count: 0, miss_count: 1, probability: 0,
      wilson95_low: 0, wilson95_high: 0, comparisons: [], plan: null,
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    await getTarget("sim_1", 1_500_000.5);

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain(`value=${encodeURIComponent(1_500_000.5)}`);
  });
});

describe("createSimulation", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  function routedFetch(scenarios: unknown[]) {
    return vi.fn(async (url: string, init?: RequestInit) => {
      const method = (init?.method ?? "GET").toUpperCase();
      const path = url.replace(/^https?:\/\/[^/]+/, "");
      let body: unknown = {};
      if (path === "/api/v1/auth/csrf") body = { csrf_token: "tok" };
      else if (path === "/api/v1/startups" && method === "POST") body = { id: "new-startup" };
      else if (path.endsWith("/scenarios") && method === "GET") body = scenarios;
      else if (path.endsWith("/scenarios") && method === "POST") body = { id: "new-scenario" };
      else if (path.endsWith("/revisions")) body = { id: "revision-123456789" };
      else if (path === "/api/v1/simulations") body = { simulation_id: "sim", status: "succeeded", result_hash: null };
      return { ok: true, json: async () => body };
    });
  }

  function draft() {
    const value = structuredClone(DEFAULT_DRAFT);
    value.company.name = "Acme";
    value.metrics.grossMargin = 60;
    value.revenue.years = [100, 200, 300, 400, 500];
    return value;
  }

  const calls = (fetchMock: ReturnType<typeof routedFetch>) =>
    fetchMock.mock.calls.map(([url, init]) => `${(init?.method ?? "GET").toUpperCase()} ${String(url).replace(/^https?:\/\/[^/]+/, "")}`);

  it("attaches to an existing company without POSTing a new startup and reuses the same-named scenario", async () => {
    const fetchMock = routedFetch([{ id: "existing-scenario", startup_id: "s1", name: "Base case", mode: "simple" }]);
    global.fetch = fetchMock as unknown as typeof fetch;

    await createSimulation(draft(), undefined, { startupId: "s1" });

    const made = calls(fetchMock);
    expect(made).not.toContain("POST /api/v1/startups");
    expect(made).not.toContain("POST /api/v1/startups/s1/scenarios");
    expect(made).toContain("GET /api/v1/startups/s1/scenarios");
    expect(made).toContain("POST /api/v1/scenarios/existing-scenario/revisions");
  });

  it("creates a scenario under the existing company when no name matches", async () => {
    const fetchMock = routedFetch([]);
    global.fetch = fetchMock as unknown as typeof fetch;

    await createSimulation(draft(), undefined, { startupId: "s1" });

    const made = calls(fetchMock);
    expect(made).not.toContain("POST /api/v1/startups");
    expect(made).toContain("POST /api/v1/startups/s1/scenarios");
  });

  it("creates a new company when no startup id is given", async () => {
    const fetchMock = routedFetch([]);
    global.fetch = fetchMock as unknown as typeof fetch;

    await createSimulation(draft());

    const made = calls(fetchMock);
    expect(made).toContain("POST /api/v1/startups");
    expect(made).toContain("POST /api/v1/startups/new-startup/scenarios");
  });
});

describe("deleteSimulation", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("sends a DELETE request to the simulation endpoint and resolves the 204 empty body as null", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const path = String(url).replace(/^https?:\/\/[^/]+/, "");
      if (path === "/api/v1/auth/csrf") {
        return { ok: true, json: async () => ({ csrf_token: "tok" }) };
      }
      // A real 204 response has no body — `.json()` throws, which `apiRequest` catches.
      return {
        ok: true,
        status: 204,
        json: async () => {
          throw new SyntaxError("Unexpected end of JSON input");
        },
      };
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await deleteSimulation("sim_1");

    expect(result).toBeNull();
    const deleteCall = fetchMock.mock.calls.find(
      ([, init]) => ((init as RequestInit | undefined)?.method ?? "GET").toUpperCase() === "DELETE",
    );
    expect(deleteCall).toBeDefined();
    const [url, init] = deleteCall as [string, RequestInit];
    expect(url).toContain("/api/v1/simulations/sim_1");
    expect(init.method).toBe("DELETE");
  });
});
