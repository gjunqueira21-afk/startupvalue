import { API_URL, apiRequest } from "./client";

/** Mirror of `WorkspacesByPlan` in `app/api/routes/admin.py`. */
export interface AdminWorkspacesByPlan {
  free: number;
  empresario: number;
  consultor: number;
  escritorio: number;
}

/** Mirror of `GET /api/v1/admin/overview` (`AdminOverviewResponse`, Task 18 shape). */
export interface AdminOverview {
  users: number;
  workspaces_by_plan: AdminWorkspacesByPlan;
  startups: number;
  simulations: number;
  simulations_last_7d: number;
  reports: number;
  waitlist_count: number;
}

/** Mirror of one entry in `GET /api/v1/admin/waitlist` (`WaitlistEntryResponse`). */
export interface AdminWaitlistEntry {
  id: string;
  email: string;
  plan_interest: string;
  source: string;
  created_at: string;
}

/** The four plan tiers a workspace can be on — mirrors `PlanTier` on the backend. */
export type PlanTier = "free" | "empresario" | "consultor" | "escritorio";

/** Mirror of one entry in `GET /api/v1/admin/workspaces` (`AdminWorkspaceResponse`). */
export interface AdminWorkspace {
  id: string;
  plan: string;
  created_at: string;
  startup_count: number;
  member_email: string;
}

/** Mirror of `POST /api/v1/admin/workspaces/{id}/plan` (`AdminPlanUpdateResponse`). */
export interface AdminPlanUpdateResult {
  id: string;
  plan: string;
}

export function getAdminOverview(signal?: AbortSignal) {
  return apiRequest<AdminOverview>("/api/v1/admin/overview", { method: "GET", signal });
}

/** JSON view of the waitlist — the `?format=csv` download is a plain link, see `getWaitlistCsvUrl`. */
export function getWaitlist(signal?: AbortSignal) {
  return apiRequest<AdminWaitlistEntry[]>("/api/v1/admin/waitlist", { method: "GET", signal });
}

/**
 * Absolute URL for the CSV export of the waitlist. Meant to be used as a
 * plain `<a href>` — the browser's own cookie jar authenticates the
 * download, so this is never fetched via `apiRequest`/`fetch` from the app.
 */
export function getWaitlistCsvUrl(): string {
  return `${API_URL}/api/v1/admin/waitlist?format=csv`;
}

/** `email` is matched exactly (case-insensitively) by the backend — no partial search. */
export function searchAdminWorkspaces(email: string, signal?: AbortSignal) {
  return apiRequest<AdminWorkspace[]>(
    `/api/v1/admin/workspaces?email=${encodeURIComponent(email)}`,
    { method: "GET", signal },
  );
}

export function updateWorkspacePlan(workspaceId: string, plan: PlanTier, signal?: AbortSignal) {
  return apiRequest<AdminPlanUpdateResult>(
    `/api/v1/admin/workspaces/${encodeURIComponent(workspaceId)}/plan`,
    { method: "POST", body: JSON.stringify({ plan }), signal },
  );
}
