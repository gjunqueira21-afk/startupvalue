import { afterEach, describe, expect, it, vi } from "vitest";
import { listScenarios, listStartups } from "./startups";

function mockJsonFetch(body: unknown) {
  return vi.fn().mockResolvedValue({ ok: true, json: async () => body });
}

describe("startups client", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("lists active companies with a credentialed GET", async () => {
    const payload = [{ id: "s1", name: "Acme", currency: "BRL", archived_at: null, created_at: "2026-01-01T00:00:00Z" }];
    const fetchMock = mockJsonFetch(payload);
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await listStartups();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/v1\/startups$/);
    expect(init.method).toBe("GET");
    expect(init.credentials).toBe("include");
    expect(result).toEqual(payload);
  });

  it("lists a company's scenarios", async () => {
    const fetchMock = mockJsonFetch([]);
    global.fetch = fetchMock as unknown as typeof fetch;

    await listScenarios("s1");

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/v1\/startups\/s1\/scenarios$/);
    expect(init.method).toBe("GET");
  });
});
