import { afterEach, describe, expect, it, vi } from "vitest";
import {
  deleteLogo,
  getBranding,
  getEntitlements,
  putBranding,
  uploadLogo,
} from "./branding";

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

describe("branding API client", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllGlobals();
  });

  it("getEntitlements parses the entitlements payload", async () => {
    const payload = {
      plan: "consultor",
      max_startups: 10,
      max_scenarios_per_run: 25_000,
      white_label: true,
      full_report: true,
      target_plan_section: true,
      implied_multiples: true,
    };
    const fetchMock = mockJsonFetch(payload);
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await getEntitlements();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/workspace/entitlements");
    expect(init.method).toBe("GET");
    expect(result).toEqual(payload);
  });

  it("getEntitlements passes max_startups through as null for unlimited plans", async () => {
    const fetchMock = mockJsonFetch({
      plan: "escritorio",
      max_startups: null,
      max_scenarios_per_run: 25_000,
      white_label: true,
      full_report: true,
      target_plan_section: true,
      implied_multiples: true,
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await getEntitlements();

    expect(result.max_startups).toBeNull();
  });

  it("getBranding requests the branding endpoint and parses the response", async () => {
    const payload = {
      firm_name: "Atlas Capital",
      primary_color: "#35E6A1",
      footer_text: "Atlas Capital — Confidencial",
      has_logo: true,
    };
    const fetchMock = mockJsonFetch(payload);
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await getBranding();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/workspace/branding");
    expect(init.method).toBe("GET");
    expect(result).toEqual(payload);
  });

  it("putBranding sends a full-replace PUT after fetching a CSRF token", async () => {
    const response = {
      firm_name: "Nova Firma",
      primary_color: "#112233",
      footer_text: "Rodapé",
      has_logo: false,
    };
    const fetchMock = mockCsrfThenJsonFetch(response);
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await putBranding({
      firm_name: "Nova Firma",
      primary_color: "#112233",
      footer_text: "Rodapé",
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [csrfUrl] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(csrfUrl).toContain("/api/v1/auth/csrf");
    const [url, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(url).toContain("/api/v1/workspace/branding");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body as string)).toEqual({
      firm_name: "Nova Firma",
      primary_color: "#112233",
      footer_text: "Rodapé",
    });
    const headers = new Headers(init.headers);
    expect(headers.get("X-CSRF-Token")).toBe("token_1");
    expect(result).toEqual(response);
  });

  it("uploadLogo sends the raw file bytes as the body with Content-Type from file.type — no FormData", async () => {
    const response = {
      firm_name: null,
      primary_color: null,
      footer_text: null,
      has_logo: true,
    };
    const fetchMock = mockCsrfThenJsonFetch(response);
    global.fetch = fetchMock as unknown as typeof fetch;
    const file = new File([new Uint8Array([1, 2, 3])], "logo.png", { type: "image/png" });

    const result = await uploadLogo(file);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [url, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(url).toContain("/api/v1/workspace/branding/logo");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(file);
    expect(init.body).not.toBeInstanceOf(FormData);
    const headers = new Headers(init.headers);
    expect(headers.get("Content-Type")).toBe("image/png");
    expect(result).toEqual(response);
  });

  it("deleteLogo sends a DELETE after fetching a CSRF token", async () => {
    const response = {
      firm_name: "Atlas Capital",
      primary_color: "#35E6A1",
      footer_text: null,
      has_logo: false,
    };
    const fetchMock = mockCsrfThenJsonFetch(response);
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await deleteLogo();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [url, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(url).toContain("/api/v1/workspace/branding/logo");
    expect(init.method).toBe("DELETE");
    expect(result).toEqual(response);
  });
});
