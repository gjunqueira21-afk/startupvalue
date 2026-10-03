"use client";

import { FormEvent, useEffect, useState } from "react";
import { ApiError } from "@/lib/api/client";
import {
  type AdminOverview,
  type AdminWaitlistEntry,
  type AdminWorkspace,
  type PlanTier,
  getAdminOverview,
  getWaitlist,
  getWaitlistCsvUrl,
  searchAdminWorkspaces,
  updateWorkspacePlan,
} from "@/lib/api/admin";
import { AppShell } from "./app-shell";
import styles from "./admin-view.module.css";

const ACTIVE = "/app/admin";

const PLAN_TIERS: PlanTier[] = ["free", "empresario", "consultor", "escritorio"];
const PLAN_LABELS: Record<PlanTier, string> = {
  free: "Free",
  empresario: "Empresário",
  consultor: "Consultor",
  escritorio: "Escritório",
};

function planLabel(plan: string): string {
  return PLAN_LABELS[plan as PlanTier] ?? plan;
}

function formatDate(value: string): string {
  try {
    return new Date(value).toLocaleString("pt-BR");
  } catch {
    return value;
  }
}

/** Mirrors `BrandingSettingsView`'s 403 handling: load → view, or a neutral notice. */
type Access = "loading" | "view" | "forbidden" | "error";

interface RowState {
  selectedPlan: PlanTier;
  confirming: boolean;
  busy: boolean;
  notice: string;
  noticeIsError: boolean;
}

function AccessNotice({ variant }: { variant: "forbidden" | "error" }) {
  const copy = {
    forbidden: {
      eyebrow: "ACESSO",
      title: "Acesso restrito",
      text: "Esta área é exclusiva para administradores da plataforma.",
    },
    error: {
      eyebrow: "ERRO",
      title: "Não foi possível carregar",
      text: "Não foi possível carregar o painel administrativo agora. Tente novamente mais tarde.",
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

export function AdminView() {
  const [access, setAccess] = useState<Access>("loading");
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [waitlist, setWaitlist] = useState<AdminWaitlistEntry[]>([]);
  const [waitlistError, setWaitlistError] = useState("");

  const [searchEmail, setSearchEmail] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [searched, setSearched] = useState(false);
  const [results, setResults] = useState<AdminWorkspace[]>([]);
  const [rowState, setRowState] = useState<Record<string, RowState>>({});

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    getAdminOverview(controller.signal)
      .then((value) => {
        if (!mounted) return;
        setOverview(value);
        setAccess("view");
      })
      .catch((error: unknown) => {
        if (!mounted) return;
        if (error instanceof DOMException && error.name === "AbortError") return;
        if (error instanceof ApiError && error.status === 403) {
          setAccess("forbidden");
          return;
        }
        setAccess("error");
      });

    getWaitlist(controller.signal)
      .then((value) => {
        if (mounted) setWaitlist(value);
      })
      .catch((error: unknown) => {
        if (!mounted) return;
        if (error instanceof DOMException && error.name === "AbortError") return;
        setWaitlistError(
          error instanceof ApiError
            ? `Não foi possível carregar a lista de espera. Código HTTP: ${error.status}.`
            : "Não foi possível carregar a lista de espera.",
        );
      });

    return () => {
      mounted = false;
      controller.abort();
    };
  }, []);

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const email = searchEmail.trim();
    if (!email) return;
    setSearching(true);
    setSearchError("");
    setSearched(true);
    try {
      const found = await searchAdminWorkspaces(email);
      setResults(found);
      setRowState(
        Object.fromEntries(
          found.map((workspace) => [
            workspace.id,
            {
              selectedPlan: (workspace.plan as PlanTier) ?? "free",
              confirming: false,
              busy: false,
              notice: "",
              noticeIsError: false,
            },
          ]),
        ),
      );
    } catch (error) {
      setResults([]);
      setRowState({});
      setSearchError(
        error instanceof ApiError
          ? `Não foi possível buscar workspaces. Código HTTP: ${error.status}.`
          : "Não foi possível buscar workspaces.",
      );
    } finally {
      setSearching(false);
    }
  }

  function patchRow(workspaceId: string, patch: Partial<RowState>) {
    setRowState((prev) => ({
      ...prev,
      [workspaceId]: { ...prev[workspaceId], ...patch },
    }));
  }

  function handlePlanSelect(workspaceId: string, plan: PlanTier) {
    patchRow(workspaceId, { selectedPlan: plan, confirming: false, notice: "" });
  }

  function requestPlanChange(workspaceId: string) {
    patchRow(workspaceId, { confirming: true, notice: "" });
  }

  function cancelPlanChange(workspaceId: string) {
    patchRow(workspaceId, { confirming: false });
  }

  async function confirmPlanChange(workspace: AdminWorkspace) {
    const row = rowState[workspace.id];
    if (!row) return;
    patchRow(workspace.id, { busy: true });
    try {
      const updated = await updateWorkspacePlan(workspace.id, row.selectedPlan);
      setResults((prev) =>
        prev.map((item) => (item.id === workspace.id ? { ...item, plan: updated.plan } : item)),
      );
      patchRow(workspace.id, {
        busy: false,
        confirming: false,
        notice: "Plano atualizado.",
        noticeIsError: false,
      });
    } catch (error) {
      patchRow(workspace.id, {
        busy: false,
        confirming: false,
        notice:
          error instanceof ApiError
            ? `Não foi possível alterar o plano. Código HTTP: ${error.status}.`
            : "Não foi possível alterar o plano.",
        noticeIsError: true,
      });
    }
  }

  if (access === "loading") {
    return (
      <AppShell active={ACTIVE}>
        <main id="main-content" className="dashboard-page">
          <header className="app-page-header">
            <div>
              <p className="eyebrow">ADMIN</p>
              <h1>Painel administrativo</h1>
            </div>
          </header>
          <p>Carregando…</p>
        </main>
      </AppShell>
    );
  }

  if (access !== "view") {
    return (
      <AppShell active={ACTIVE}>
        <main id="main-content" className="dashboard-page">
          <header className="app-page-header">
            <div>
              <p className="eyebrow">ADMIN</p>
              <h1>Painel administrativo</h1>
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
            <p className="eyebrow">ADMIN</p>
            <h1>Painel administrativo</h1>
            <span>Visão geral do negócio, lista de espera e gestão de planos por workspace.</span>
          </div>
        </header>

        {overview && (
          <div className={styles.metrics}>
            <article className={styles.metricCard}>
              <span>Usuários</span>
              <strong>{overview.users}</strong>
            </article>
            <article className={styles.metricCard}>
              <span>Empresas</span>
              <strong>{overview.startups}</strong>
            </article>
            <article className={styles.metricCard}>
              <span>Relatórios</span>
              <strong>{overview.reports}</strong>
            </article>
            <article className={styles.metricCard}>
              <span>Simulações</span>
              <strong>{overview.simulations}</strong>
              <small>+{overview.simulations_last_7d} nos últimos 7 dias</small>
            </article>
            <article className={styles.metricCard}>
              <span>Lista de espera</span>
              <strong>{overview.waitlist_count}</strong>
            </article>
            <article className={styles.metricCard}>
              <span>Workspaces por plano</span>
              <div className={styles.planBreakdown}>
                {PLAN_TIERS.map((tier) => (
                  <div key={tier}>
                    {PLAN_LABELS[tier]}
                    <strong>{overview.workspaces_by_plan[tier]}</strong>
                  </div>
                ))}
              </div>
            </article>
          </div>
        )}

        <section className={styles.section}>
          <div className={styles.sectionHeader}>
            <h2>Lista de espera</h2>
            <a className={styles.csvLink} href={getWaitlistCsvUrl()}>
              Baixar CSV
            </a>
          </div>
          {waitlistError && <p className="form-notice error" role="alert">{waitlistError}</p>}
          {!waitlistError && waitlist.length === 0 && (
            <p className={styles.empty}>Nenhuma entrada na lista de espera.</p>
          )}
          {waitlist.length > 0 && (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>E-mail</th>
                  <th>Interesse</th>
                  <th>Origem</th>
                  <th>Data</th>
                </tr>
              </thead>
              <tbody>
                {waitlist.map((entry) => (
                  <tr key={entry.id}>
                    <td>{entry.email}</td>
                    <td>{entry.plan_interest}</td>
                    <td>{entry.source}</td>
                    <td>{formatDate(entry.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className={styles.section}>
          <div className={styles.sectionHeader}>
            <h2>Buscar workspace por e-mail</h2>
          </div>
          <form className={styles.searchForm} onSubmit={handleSearch} noValidate>
            <input
              type="email"
              value={searchEmail}
              onChange={(event) => setSearchEmail(event.target.value)}
              placeholder="email@empresa.com"
              aria-label="E-mail do membro do workspace"
            />
            <button className="button button-primary" type="submit" disabled={searching}>
              {searching ? "Buscando…" : "Buscar"}
            </button>
          </form>

          {searchError && <p className="form-notice error" role="alert">{searchError}</p>}

          {!searchError && searched && !searching && results.length === 0 && (
            <p className={styles.empty}>Nenhum workspace encontrado para este e-mail.</p>
          )}

          {results.map((workspace) => {
            const row = rowState[workspace.id];
            if (!row) return null;
            return (
              <div className={styles.resultRow} key={workspace.id}>
                <div className={styles.resultInfo}>
                  <strong>{workspace.member_email}</strong>
                  <small>
                    Plano atual: {planLabel(workspace.plan)} · {workspace.startup_count} empresa(s) ·
                    {" "}criado em {formatDate(workspace.created_at)}
                  </small>
                </div>
                <div className={styles.resultActions}>
                  <select
                    aria-label={`Novo plano para ${workspace.member_email}`}
                    value={row.selectedPlan}
                    disabled={row.busy}
                    onChange={(event) =>
                      handlePlanSelect(workspace.id, event.target.value as PlanTier)
                    }
                  >
                    {PLAN_TIERS.map((tier) => (
                      <option key={tier} value={tier}>
                        {PLAN_LABELS[tier]}
                      </option>
                    ))}
                  </select>
                  <button
                    className="button button-secondary button-small"
                    type="button"
                    disabled={row.busy || row.selectedPlan === workspace.plan}
                    onClick={() => requestPlanChange(workspace.id)}
                  >
                    Alterar plano
                  </button>
                </div>
                {row.confirming && (
                  <div className={styles.confirmBox} role="alertdialog">
                    <p>
                      Alterar plano de {workspace.member_email} para {planLabel(row.selectedPlan)}?
                    </p>
                    <button
                      className="button button-primary button-small"
                      type="button"
                      disabled={row.busy}
                      onClick={() => confirmPlanChange(workspace)}
                    >
                      {row.busy ? "Aplicando…" : "Confirmar"}
                    </button>
                    <button
                      className="button button-secondary button-small"
                      type="button"
                      disabled={row.busy}
                      onClick={() => cancelPlanChange(workspace.id)}
                    >
                      Cancelar
                    </button>
                  </div>
                )}
                {row.notice && (
                  <p
                    className={row.noticeIsError ? "form-notice error" : "form-notice"}
                    role="status"
                    style={{ width: "100%" }}
                  >
                    {row.notice}
                  </p>
                )}
              </div>
            );
          })}
        </section>
      </main>
    </AppShell>
  );
}
