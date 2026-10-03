"use client";

import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { ApiError } from "@/lib/api/client";
import {
  deleteLogo,
  getBranding,
  getEntitlements,
  putBranding,
  uploadLogo,
  type Branding,
} from "@/lib/api/branding";
import { AppShell } from "./app-shell";

const MAX_LOGO_BYTES = 1_048_576;
const ACCEPTED_LOGO_TYPES = ["image/png", "image/jpeg"];
const DEFAULT_COLOR = "#35e6a1";
const ACTIVE = "/app/settings/branding";

// `plan`: workspace isn't on a white-label plan (upsell). `role`: the plan
// qualifies but this user's role doesn't (owner/admin only) — the backend's
// 403 for either case degrades here, never a crash.
type Access = "loading" | "form" | "plan" | "role" | "error";

/**
 * Pulls the backend's error code out of an `ApiError`'s `details` — FastAPI's
 * default `HTTPException` body is `{ "detail": "<code>" }`. Used to tell the
 * two possible 403s on `getBranding()` apart: `white_label_not_in_plan`
 * (plan — show the upsell) from anything else, notably `action_not_allowed`
 * (role lacks owner/admin — show the role notice).
 */
function errorCode(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null;
  const details = error.details;
  if (details && typeof details === "object" && "detail" in details) {
    const detail = (details as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return null;
}

function AccessNotice({ variant }: { variant: "plan" | "role" | "error" }) {
  const copy = {
    plan: {
      eyebrow: "PLANO",
      title: "Marca do relatório em PDF",
      text: "Disponível nos planos Consultor e Escritório. Atualize seu plano para personalizar o nome, a cor e o logotipo exibidos nos relatórios em PDF deste workspace.",
    },
    role: {
      eyebrow: "PERMISSÃO",
      title: "Acesso restrito",
      text: "Apenas proprietários ou administradores do workspace podem editar a marca do relatório. Peça para alguém com esse papel fazer as alterações.",
    },
    error: {
      eyebrow: "ERRO",
      title: "Não foi possível carregar",
      text: "Não foi possível carregar as configurações de marca agora. Tente novamente mais tarde.",
    },
  }[variant];
  return (
    <section className="assumptions-note" aria-live="polite">
      <div>
        <p className="eyebrow">{copy.eyebrow}</p>
        <h2>{copy.title}</h2>
      </div>
      <p>{copy.text}</p>
    </section>
  );
}

export function BrandingSettingsView() {
  const [access, setAccess] = useState<Access>("loading");
  const [branding, setBranding] = useState<Branding | null>(null);
  const [firmName, setFirmName] = useState("");
  const [color, setColor] = useState(DEFAULT_COLOR);
  const [footerText, setFooterText] = useState("");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [noticeIsError, setNoticeIsError] = useState(false);
  const [logoBusy, setLogoBusy] = useState(false);
  const [logoError, setLogoError] = useState("");

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    getEntitlements(controller.signal)
      .then((entitlements) => {
        if (!mounted) return;
        if (!entitlements.white_label) {
          setAccess("plan");
          return undefined;
        }
        return getBranding(controller.signal).then((value) => {
          if (!mounted) return;
          setBranding(value);
          setFirmName(value.firm_name ?? "");
          setColor(value.primary_color ?? DEFAULT_COLOR);
          setFooterText(value.footer_text ?? "");
          setAccess("form");
        });
      })
      .catch((error: unknown) => {
        if (!mounted) return;
        if (error instanceof DOMException && error.name === "AbortError") return;
        // A 403 here only happens from the nested getBranding call —
        // getEntitlements never 403s on its own. It can still be
        // `white_label_not_in_plan` (the plan was downgraded between the two
        // fetches), so the code decides the notice, not just the status.
        if (error instanceof ApiError && error.status === 403) {
          setAccess(errorCode(error) === "white_label_not_in_plan" ? "plan" : "role");
          return;
        }
        setAccess("error");
      });

    return () => {
      mounted = false;
      controller.abort();
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice("");
    setNoticeIsError(false);
    setSaving(true);
    try {
      const updated = await putBranding({
        firm_name: firmName.trim() || undefined,
        primary_color: color || undefined,
        footer_text: footerText.trim() || undefined,
      });
      setBranding(updated);
      setFirmName(updated.firm_name ?? "");
      setColor(updated.primary_color ?? DEFAULT_COLOR);
      setFooterText(updated.footer_text ?? "");
      setNotice("Marca do relatório atualizada.");
    } catch (error) {
      setNoticeIsError(true);
      setNotice(
        error instanceof ApiError
          ? `Não foi possível salvar a marca. Código HTTP: ${error.status}.`
          : "Não foi possível salvar a marca.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleLogoChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    event.target.value = "";
    if (!file) return;
    setLogoError("");
    // Client-side pre-check only mirrors the server rule for fast feedback —
    // the backend still validates magic bytes and size itself (never trusts
    // this check, or the client-sent Content-Type).
    if (!ACCEPTED_LOGO_TYPES.includes(file.type)) {
      setLogoError("Envie um arquivo PNG ou JPEG.");
      return;
    }
    if (file.size > MAX_LOGO_BYTES) {
      setLogoError("O logotipo deve ter até 1 MB.");
      return;
    }
    setLogoBusy(true);
    try {
      const updated = await uploadLogo(file);
      setBranding(updated);
      setNotice("Logotipo atualizado.");
      setNoticeIsError(false);
    } catch (error) {
      setLogoError(
        error instanceof ApiError
          ? `Não foi possível enviar o logotipo. Código HTTP: ${error.status}.`
          : "Não foi possível enviar o logotipo.",
      );
    } finally {
      setLogoBusy(false);
    }
  }

  async function handleLogoRemove() {
    setLogoBusy(true);
    setLogoError("");
    try {
      const updated = await deleteLogo();
      setBranding(updated);
      setNotice("Logotipo removido.");
      setNoticeIsError(false);
    } catch (error) {
      setLogoError(
        error instanceof ApiError
          ? `Não foi possível remover o logotipo. Código HTTP: ${error.status}.`
          : "Não foi possível remover o logotipo.",
      );
    } finally {
      setLogoBusy(false);
    }
  }

  if (access === "loading") {
    return (
      <AppShell active={ACTIVE}>
        <main id="main-content" className="dashboard-page">
          <header className="app-page-header">
            <div>
              <p className="eyebrow">CONFIGURAÇÕES</p>
              <h1>Marca do relatório</h1>
            </div>
          </header>
          <p>Carregando…</p>
        </main>
      </AppShell>
    );
  }

  if (access !== "form") {
    return (
      <AppShell active={ACTIVE}>
        <main id="main-content" className="dashboard-page">
          <header className="app-page-header">
            <div>
              <p className="eyebrow">CONFIGURAÇÕES</p>
              <h1>Marca do relatório</h1>
            </div>
          </header>
          <AccessNotice variant={access} />
        </main>
      </AppShell>
    );
  }

  return (
    <AppShell active={ACTIVE}>
      <main id="main-content" className="dashboard-page">
        <header className="app-page-header">
          <div>
            <p className="eyebrow">CONFIGURAÇÕES</p>
            <h1>Marca do relatório</h1>
            <span>Personalize o nome, a cor e o logotipo exibidos nos relatórios em PDF deste workspace.</span>
          </div>
        </header>

        <article className="result-card">
          <form className="settings-form" onSubmit={handleSubmit} noValidate>
            <label>
              Nome da firma
              <input
                value={firmName}
                onChange={(event) => setFirmName(event.target.value)}
                maxLength={120}
                placeholder="Ex.: Atlas Capital"
              />
            </label>
            <label>
              Cor primária
              <input
                type="color"
                value={color}
                onChange={(event) => setColor(event.target.value)}
                aria-describedby="primary-color-hint"
              />
              <small id="primary-color-hint">Usada em títulos e destaques do relatório.</small>
            </label>
            <label>
              Texto do rodapé
              <textarea
                value={footerText}
                onChange={(event) => setFooterText(event.target.value)}
                maxLength={300}
                placeholder="Ex.: Atlas Capital — Confidencial"
              />
            </label>
            <button className="button button-primary" type="submit" disabled={saving}>
              {saving ? "Salvando…" : "Salvar marca"}
            </button>
            {notice && (
              <p className={noticeIsError ? "form-notice error" : "form-notice"} role="status">
                {notice}
              </p>
            )}
          </form>

          <div className="settings-form">
            <label>
              Logotipo
              <input
                type="file"
                accept="image/png,image/jpeg"
                onChange={handleLogoChange}
                disabled={logoBusy}
                aria-describedby="logo-hint"
              />
              <small id="logo-hint">PNG ou JPEG, até 1 MB.</small>
            </label>
            {branding?.has_logo && (
              <button
                className="button button-secondary"
                type="button"
                onClick={handleLogoRemove}
                disabled={logoBusy}
              >
                {logoBusy ? "Removendo…" : "Remover logotipo"}
              </button>
            )}
            {logoError && (
              <p className="form-notice error" role="alert">
                {logoError}
              </p>
            )}
          </div>
        </article>

        <article className="result-card brand-preview">
          <p className="eyebrow">PRÉ-VISUALIZAÇÃO</p>
          <div className="brand-preview-header" style={{ borderColor: color }}>
            <span className="brand-preview-logo">{branding?.has_logo ? "LOGO" : "—"}</span>
            <strong style={{ color }}>{firmName || "Nome da firma"}</strong>
          </div>
          <p className="brand-preview-footer">{footerText || "Texto do rodapé do relatório"}</p>
        </article>
      </main>
    </AppShell>
  );
}
