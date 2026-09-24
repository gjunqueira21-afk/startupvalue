"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { login, signup } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { ArrowRight } from "./icons";

type AuthFormProps = { mode: "login" | "signup" };
type Errors = Partial<Record<"name" | "email" | "password" | "terms", string>>;

export function AuthForm({ mode }: AuthFormProps) {
  const router = useRouter();
  const [errors, setErrors] = useState<Errors>({});
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const next: Errors = {};
    const name = String(data.get("name") || "").trim();
    const email = String(data.get("email") || "").trim();
    const password = String(data.get("password") || "");

    if (mode === "signup" && name.length < 2) next.name = "Informe seu nome.";
    if (!/^\S+@\S+\.\S+$/.test(email)) next.email = "Informe um e-mail válido.";
    if (password.length < 12) next.password = "Use pelo menos 12 caracteres.";
    if (mode === "signup" && data.get("terms") !== "on") {
      next.terms = "Aceite os termos para continuar.";
    }
    setErrors(next);
    if (Object.keys(next).length > 0) {
      setNotice("Revise os campos indicados.");
      return;
    }

    setLoading(true);
    setNotice("");
    try {
      if (mode === "signup") {
        await signup({ name, email, password });
        router.push("/app/companies/new");
      } else {
        await login({ email, password });
        router.push("/app");
      }
    } catch (error) {
      const suffix = error instanceof ApiError ? ` Código HTTP: ${error.status}.` : "";
      setNotice(`Não foi possível autenticar agora.${suffix}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="auth-form" method="post" onSubmit={submit} noValidate>
      {mode === "signup" && (
        <label>
          Nome completo
          <input
            name="name"
            autoComplete="name"
            aria-invalid={Boolean(errors.name)}
            aria-describedby={errors.name ? "name-error" : undefined}
          />
          {errors.name && (
            <span className="field-error" id="name-error">
              {errors.name}
            </span>
          )}
        </label>
      )}
      <label>
        E-mail
        <input
          name="email"
          type="email"
          autoComplete="email"
          inputMode="email"
          placeholder="voce@empresa.com"
          aria-invalid={Boolean(errors.email)}
          aria-describedby={errors.email ? "email-error" : undefined}
        />
        {errors.email && (
          <span className="field-error" id="email-error">
            {errors.email}
          </span>
        )}
      </label>
      <label>
        Senha
        <input
          name="password"
          type="password"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          placeholder="Mínimo de 12 caracteres"
          aria-invalid={Boolean(errors.password)}
          aria-describedby={errors.password ? "password-error" : undefined}
        />
        {errors.password && (
          <span className="field-error" id="password-error">
            {errors.password}
          </span>
        )}
      </label>
      {mode === "login" && (
        <div className="auth-options">
          <label className="check-field">
            <input type="checkbox" name="remember" /> <span>Lembrar neste dispositivo</span>
          </label>
          <Link href="/forgot-password">Esqueci minha senha</Link>
        </div>
      )}
      {mode === "signup" && (
        <label className="check-field">
          <input type="checkbox" name="terms" aria-invalid={Boolean(errors.terms)} />
          <span>Li e aceito os Termos de Uso e a Política de Privacidade.</span>
          {errors.terms && <span className="field-error">{errors.terms}</span>}
        </label>
      )}
      <button className="button button-primary button-wide" type="submit" disabled={loading || !hydrated}>
        {loading ? "Conectando..." : mode === "login" ? "Entrar" : "Criar conta"}
        <ArrowRight />
      </button>
      {notice && (
        <p className={Object.keys(errors).length ? "form-notice error" : "form-notice"} role="status">
          {notice}
        </p>
      )}
    </form>
  );
}
