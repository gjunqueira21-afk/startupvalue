import { apiRequest } from "./client";

/**
 * Mirror of `GET /api/v1/workspace/entitlements` — the plan-gated feature/limit
 * matrix for the caller's workspace. `max_startups` is `null` for unlimited
 * plans (Escritório).
 */
export interface Entitlements {
  plan: "free" | "empresario" | "consultor" | "escritorio";
  max_startups: number | null;
  max_scenarios_per_run: number;
  white_label: boolean;
  full_report: boolean;
  target_plan_section: boolean;
  implied_multiples: boolean;
}

/** Mirror of `GET /api/v1/workspace/branding` (`BrandingResponse`, Task 8 shape). */
export interface Branding {
  firm_name: string | null;
  primary_color: string | null;
  footer_text: string | null;
  has_logo: boolean;
}

/**
 * `PUT /api/v1/workspace/branding` body. Full-replace semantics: a field left
 * out of the request is persisted as `null` by the backend, so callers should
 * send every field the user can see, not just the ones that changed.
 */
export interface BrandingPayload {
  firm_name?: string;
  primary_color?: string;
  footer_text?: string;
}

export function getEntitlements(signal?: AbortSignal) {
  return apiRequest<Entitlements>("/api/v1/workspace/entitlements", { method: "GET", signal });
}

/**
 * Requires owner/admin role AND the `white_label` entitlement; otherwise the
 * backend answers 403 with `white_label_not_in_plan` (plan) or
 * `action_not_allowed` (role) — callers degrade to an upsell/notice, never a
 * crash, on either.
 */
export function getBranding(signal?: AbortSignal) {
  return apiRequest<Branding>("/api/v1/workspace/branding", { method: "GET", signal });
}

export function putBranding(payload: BrandingPayload, signal?: AbortSignal) {
  return apiRequest<Branding>("/api/v1/workspace/branding", {
    method: "PUT",
    body: JSON.stringify(payload),
    signal,
  });
}

/**
 * Uploads the workspace logo as a RAW request body — NOT multipart/form-data.
 * The backend reads the raw bytes directly (no `python-multipart` dependency)
 * and validates the file's magic bytes itself, so the client-sent
 * `Content-Type` is informational only; it is still set from `file.type` so
 * the server has a hint. Server limits: ≤ 1 MB, PNG or JPEG (413
 * `logo_too_large`, 422 `logo_format_unsupported`).
 */
export function uploadLogo(file: File, signal?: AbortSignal) {
  return apiRequest<Branding>("/api/v1/workspace/branding/logo", {
    method: "POST",
    body: file,
    headers: { "Content-Type": file.type },
    signal,
  });
}

export function deleteLogo(signal?: AbortSignal) {
  return apiRequest<Branding>("/api/v1/workspace/branding/logo", { method: "DELETE", signal });
}
