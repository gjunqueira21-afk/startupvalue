import { apiRequest } from "./client";

export interface SessionResponse {
  user_id: string;
  workspace_id: string;
  name: string;
  email: string;
  role: string;
  expires_at: string;
  /** Platform-level admin flag (Task 18/19) — gates the Admin nav link, not any workspace role. */
  is_platform_admin: boolean;
}

export function signup(payload: {
  name: string;
  email: string;
  password: string;
  workspace_name?: string;
}) {
  return apiRequest<SessionResponse>("/api/v1/auth/signup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function login(payload: { email: string; password: string }) {
  return apiRequest<SessionResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getSession() {
  return apiRequest<SessionResponse>("/api/v1/auth/me", { method: "GET" });
}

export function logout() {
  return apiRequest<{ message: string }>("/api/v1/auth/logout", { method: "POST" });
}

export function requestPasswordReset(email: string) {
  return apiRequest<{ message: string }>("/api/v1/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function resetPassword(token: string, password: string) {
  return apiRequest<{ message: string }>("/api/v1/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, password }),
  });
}
