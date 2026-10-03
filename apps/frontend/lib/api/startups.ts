import { apiRequest } from "./client";

/** Mirror of the backend `StartupResponse` (fields the frontend uses). */
export interface StartupSummary {
  id: string;
  name: string;
  currency: string;
  archived_at: string | null;
  created_at: string;
}

/** Mirror of the backend `ScenarioResponse` (fields the frontend uses). */
export interface ScenarioSummary {
  id: string;
  startup_id: string;
  name: string;
  mode: string;
}

/**
 * `GET /api/v1/startups` — the workspace's ACTIVE (non-archived) companies,
 * newest first. Its length is the number the backend's company cap counts.
 */
export function listStartups(signal?: AbortSignal) {
  return apiRequest<StartupSummary[]>("/api/v1/startups", { method: "GET", signal });
}

/** `GET /api/v1/startups/{id}/scenarios` — the company's active scenarios. */
export function listScenarios(startupId: string, signal?: AbortSignal) {
  return apiRequest<ScenarioSummary[]>(`/api/v1/startups/${encodeURIComponent(startupId)}/scenarios`, {
    method: "GET",
    signal,
  });
}
