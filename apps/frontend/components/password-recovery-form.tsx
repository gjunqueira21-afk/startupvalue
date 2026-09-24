"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { requestPasswordReset, resetPassword } from "@/lib/api/auth";
import { ArrowRight } from "./icons";

export function PasswordRecoveryForm({ mode }: { mode: "request" | "reset" }) {
  const [token, setToken] = useState("");
  const [hydrated, setHydrated] = useState(false);
  const [busy, setBusy] = useState(false);
  const [complete, setComplete] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    setHydrated(true);
    if (mode === "reset") {
      setToken(new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "");
    }
  }, [mode]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const email = String(data.get("email") ?? "").trim();
    const password = String(data.get("password") ?? "");
    const confirmation = String(data.get("confirmation") ?? "");
    if (mode === "request" && !/^\S+@\S+\.\S+$/.test(email)) {
      setNotice("Informe um e-mail válido.");
      return;
    }
    if (mode === "reset" && (!token || password.length < 12 || password !== confirmation)) {
      setNotice("Confira o link e use uma senha de 12 caracteres ou mais, igual nos dois campos.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      if (mode === "request") {
        await requestPasswordReset(email);
        setNotice("Se existir uma conta com esse e-mail, enviaremos um link para redefinir a senha. Confira também o spam.");
      } else {
        await resetPassword(token, password);
        setComplete(true);
        window.history.replaceState(null, "", "/reset-password");
        setNotice("Senha alterada. Todas as sessões anteriores foram encerradas.");
      }
    } catch {
      setNotice(
        mode === "request"
          ? "Não foi possível processar a solicitação agora. Tente novamente mais tarde."
          : "O link é inválido, expirou ou já foi usado. Solicite um novo link."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="auth-form" method="post" onSubmit={submit} noValidate>
      {mode === "request" ? (
        <label>
          E-mail da conta
          <input name="email" type="email" autoComplete="email" inputMode="email" required />
        </label>
      ) : (
        <>
          <label>
            Nova senha
            <input name="password" type="password" autoComplete="new-password" minLength={12} required />
          </label>
          <label>
            Confirme a nova senha
            <input name="confirmation" type="password" autoComplete="new-password" minLength={12} required />
          </label>
        </>
      )}
      <button
        className="button button-primary button-wide"
        type="submit"
        disabled={!hydrated || busy || complete || (mode === "reset" && !token)}
      >
        {busy ? "Processando..." : mode === "request" ? "Enviar link" : "Redefinir senha"}
        <ArrowRight />
      </button>
      {mode === "reset" && hydrated && !token && (
        <p className="form-notice error" role="alert">Link incompleto. Solicite um novo link.</p>
      )}
      {notice && <p className="form-notice" role="status">{notice}</p>}
      <p className="auth-switch">
        <Link href={complete ? "/login" : mode === "reset" ? "/forgot-password" : "/login"}>
          {complete ? "Entrar com a nova senha" : mode === "reset" ? "Solicitar novo link" : "Voltar ao login"}
        </Link>
      </p>
    </form>
  );
}
