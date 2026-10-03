import { afterEach, describe, expect, it, vi } from "vitest";
import { getTarget } from "./simulations";

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
