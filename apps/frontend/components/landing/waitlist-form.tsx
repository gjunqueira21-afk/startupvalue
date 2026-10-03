"use client";

import { useState, type FormEvent } from "react";
import { ArrowRight } from "../icons";

export type PlanInterest = "free" | "empresario" | "consultor" | "escritorio";

export const WAITLIST_SUCCESS_MESSAGE = "Você está na lista — avisaremos no lançamento.";
export const WAITLIST_RETRY_MESSAGE = "Tente novamente em instantes.";

export type WaitlistSubmitResult = { ok: true } | { ok: false; message: string };

/**
 * Pure POST to the public waitlist endpoint (Task 10), isolated from React
 * state so the payload shape and error handling can be unit-tested without a
 * DOM — this repo has no React Testing Library and vitest runs in the
 * default "node" environment. See `waitlist-form.test.tsx`.
 *
 * Posts same-origin via a relative path with a plain `fetch` (no
 * `credentials: "include"`, no CSRF preflight): the backend's CSRF guard
 * (`app/auth/csrf.py`) only demands a token when a session cookie is present,
 * and a waitlist visitor never has one, so the `apiRequest` client's
 * cookie-mutation flow would do unneeded work for no benefit here.
 */
export async function submitWaitlist(
  fetchImpl: typeof fetch,
  params: { email: string; plan: PlanInterest; source: string },
): Promise<WaitlistSubmitResult> {
  try {
    const response = await fetchImpl("/api/v1/waitlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: params.email,
        plan_interest: params.plan,
        source: params.source,
      }),
    });
    if (response.ok) return { ok: true };
    return { ok: false, message: WAITLIST_RETRY_MESSAGE };
  } catch {
    return { ok: false, message: WAITLIST_RETRY_MESSAGE };
  }
}

type Status = "idle" | "loading" | "success" | "error";

export function WaitlistForm({
  plan,
  source,
  variant = "secondary",
}: {
  plan: PlanInterest;
  source: string;
  variant?: "primary" | "secondary";
}) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);

  if (status === "success") {
    return <p className="waitlist-success">{WAITLIST_SUCCESS_MESSAGE}</p>;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("loading");
    setError(null);
    const result = await submitWaitlist(fetch, { email, plan, source });
    if (result.ok) {
      setStatus("success");
    } else {
      setStatus("error");
      setError(result.message);
    }
  }

  return (
    <form className="waitlist-form" onSubmit={handleSubmit}>
      <input
        aria-label="Seu e-mail"
        type="email"
        required
        placeholder="seu@email.com"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
      />
      <button
        type="submit"
        className={variant === "primary" ? "button button-primary" : "button button-secondary"}
        disabled={status === "loading"}
      >
        {status === "loading" ? "Enviando…" : <>Entrar na lista <ArrowRight /></>}
      </button>
      {status === "error" && error ? <p className="waitlist-error" role="alert">{error}</p> : null}
    </form>
  );
}
