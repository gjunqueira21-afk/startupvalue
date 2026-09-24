export const API_URL = process.env.NEXT_PUBLIC_API_URL ??
  (process.env.NODE_ENV === "production" ? "" : "http://localhost:8000");

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiRequest<TResponse>(path: string, init: RequestInit): Promise<TResponse> {
  const apiUrl = API_URL;
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && ![
    "/api/v1/auth/login", "/api/v1/auth/signup", "/api/v1/auth/forgot-password", "/api/v1/auth/reset-password",
  ].includes(path)) {
    const csrfResponse = await fetch(`${apiUrl}/api/v1/auth/csrf`, {
      credentials: "include",
      signal: init.signal,
    });
    if (!csrfResponse.ok) {
      throw new ApiError("Sessão expirada ou indisponível.", csrfResponse.status);
    }
    const csrf = await csrfResponse.json() as { csrf_token: string };
    headers.set("X-CSRF-Token", csrf.csrf_token);
  }
  const response = await fetch(`${apiUrl}${path}`, {
    ...init,
    credentials: "include",
    headers,
  });

  const body = await response.json().catch(() => null) as unknown;
  if (!response.ok) {
    throw new ApiError("Não foi possível iniciar a simulação.", response.status, body);
  }
  return body as TResponse;
}
