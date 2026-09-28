"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "./app-shell";
import { ArrowRight, BuildingIcon, ChartIcon, FileIcon, GridIcon } from "./icons";
import { getSession, type SessionResponse } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { getDashboard, type DashboardAnalysis, type DashboardResponse } from "@/lib/api/dashboard";
import styles from "./dashboard-view.module.css";

const number = new Intl.NumberFormat("pt-BR");

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Data indisponível"
    : new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(date);
}

function formatMoney(value: number | null, currency: string): string {
  if (value === null) return "—";
  try {
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency,
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(value);
  } catch {
    return `${currency} ${number.format(Math.round(value))}`;
  }
}

function initials(name: string): string {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]?.toUpperCase() ?? "").join("") || "SV";
}

function RecentAnalysis({ analysis }: { analysis: DashboardAnalysis }) {
  return (
    <Link href={`/app/simulations/${analysis.simulation_id}`} className="table-row" role="row">
      <span className="company-cell">
        <b>{initials(analysis.startup_name)}</b>
        <span><strong>{analysis.startup_name}</strong><small>{analysis.scenario_name} · Seed {number.format(analysis.seed)}</small></span>
      </span>
      <span><strong>{formatMoney(analysis.p50, analysis.currency)}</strong><small>{analysis.p50 === null ? analysis.status : "Mediana da simulação"}</small></span>
      <span><strong>{analysis.p25 === null || analysis.p75 === null ? "—" : `${formatMoney(analysis.p25, analysis.currency)} — ${formatMoney(analysis.p75, analysis.currency)}`}</strong><small>P25 — P75</small></span>
      <span><code>{analysis.model_version}</code></span>
      <span>{formatDate(analysis.created_at)}</span>
      <span aria-hidden="true">→</span>
    </Link>
  );
}

function DashboardContent({ session, dashboard }: { session: SessionResponse; dashboard: DashboardResponse }) {
  const latest = dashboard.recent_analyses[0];
  const dateLabel = new Intl.DateTimeFormat("pt-BR", { dateStyle: "full" }).format(new Date()).toUpperCase();
  return (
    <main id="main-content" className="dashboard-page">
      <header className="app-page-header">
        <div><p>{dateLabel}</p><h1>Olá, {session.name.split(/\s+/)[0]}.</h1><span>Acompanhe suas empresas e análises salvas.</span></div>
        <Link className="button button-primary" href="/app/companies/new">Nova análise</Link>
      </header>

      <section className="app-metrics" id="empresas" aria-label="Resumo do workspace">
        <article><span><BuildingIcon /> EMPRESAS</span><strong>{number.format(dashboard.company_count)}</strong><small>Empresas ativas</small></article>
        <article><span><ChartIcon /> SIMULAÇÕES</span><strong>{number.format(dashboard.simulation_count)}</strong><small>{number.format(dashboard.scenario_runs)} cenários processados</small></article>
        <article><span><GridIcon /> CENÁRIOS</span><strong>{number.format(dashboard.scenario_count)}</strong><small>Cenários ativos</small></article>
        <article id="relatorios"><span><FileIcon /> RELATÓRIOS</span><strong>{number.format(dashboard.report_count)}</strong><small>Relatórios salvos</small></article>
      </section>

      <section className="dashboard-section" id="analises">
        <div className="section-title"><div><p>PORTFÓLIO</p><h2>Análises recentes</h2></div><Link href="/app/companies/new">Nova análise <ArrowRight /></Link></div>
        {dashboard.recent_analyses.length === 0 ? (
          <div className={styles.emptyState}>
            <span>PRIMEIRA ANÁLISE</span>
            <h3>Seus resultados aparecerão aqui.</h3>
            <p>Cadastre uma empresa, defina as premissas e rode uma simulação para acompanhar o valuation ao longo do tempo.</p>
            <Link className="button button-primary" href="/app/companies/new">Começar análise <ArrowRight /></Link>
          </div>
        ) : (
          <div className="analysis-table" role="table" aria-label="Análises recentes">
            <div className="table-head" role="row"><span>EMPRESA / CENÁRIO</span><span>VALUATION P50</span><span>CORE RANGE</span><span>MODELO</span><span>CRIADA EM</span><span /></div>
            {dashboard.recent_analyses.map((analysis) => <RecentAnalysis analysis={analysis} key={analysis.simulation_id} />)}
          </div>
        )}
      </section>

      <section className="dashboard-columns">
        <article>
          <div className="section-title compact"><div><p>ATIVIDADE</p><h2>Execuções recentes</h2></div></div>
          {dashboard.recent_analyses.length === 0 ? <p className={styles.secondary}>Ainda não há execuções neste workspace.</p> : (
            <div className="activity-list">
              {dashboard.recent_analyses.slice(0, 4).map((analysis) => (
                <div key={analysis.simulation_id}>
                  <i className={analysis.status === "succeeded" ? "success" : ""} />
                  <span><strong>{number.format(analysis.simulation_count)} cenários · {analysis.status === "succeeded" ? "concluídos" : analysis.status}</strong><small>{analysis.startup_name} · {analysis.scenario_name}</small></span>
                  <time dateTime={analysis.created_at}>{formatDate(analysis.created_at)}</time>
                </div>
              ))}
            </div>
          )}
        </article>
        <article>
          <div className="section-title compact"><div><p>PRÓXIMO PASSO</p><h2>Continue sua análise</h2></div></div>
          <div className="next-decision">
            {latest ? (
              <><span>{latest.startup_name.toUpperCase()} · {latest.scenario_name.toUpperCase()}</span><strong>Explore a distribuição de valuation.</strong><p>Revise percentis, risco e as premissas utilizadas nesta simulação.</p><Link href={`/app/simulations/${latest.simulation_id}`}>Abrir resultado <ArrowRight /></Link></>
            ) : (
              <><span>QUANTOVALE</span><strong>Crie seu primeiro cenário.</strong><p>O resultado ficará salvo na sua conta e poderá ser aberto novamente depois do login.</p><Link href="/app/companies/new">Iniciar <ArrowRight /></Link></>
            )}
          </div>
        </article>
      </section>
    </main>
  );
}

export function DashboardView() {
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [status, setStatus] = useState<"loading" | "unauthorized" | "error" | "ready">("loading");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    Promise.all([getSession(), getDashboard()])
      .then(([currentSession, currentDashboard]) => {
        if (!active) return;
        setSession(currentSession);
        setDashboard(currentDashboard);
        setStatus("ready");
      })
      .catch((error: unknown) => {
        if (!active) return;
        setStatus(error instanceof ApiError && error.status === 401 ? "unauthorized" : "error");
      });
    return () => { active = false; };
  }, [attempt]);

  return (
    <AppShell>
      {status === "ready" && session && dashboard ? <DashboardContent session={session} dashboard={dashboard} /> : (
        <main id="main-content" className="dashboard-page">
          {status === "loading" ? <p role="status" className={styles.secondary}>Carregando suas análises…</p> : (
            <div className={styles.emptyState} role="alert">
              <h1>{status === "unauthorized" ? "Entre para acessar seu dashboard." : "Não foi possível carregar suas análises."}</h1>
              <p>{status === "unauthorized" ? "Sua sessão expirou ou você ainda não fez login." : "Verifique a conexão com a API e tente novamente."}</p>
              {status === "unauthorized" ? <Link className="button button-primary" href="/login">Entrar</Link> : <button className="button button-primary" onClick={() => { setStatus("loading"); setAttempt((value) => value + 1); }}>Tentar novamente</button>}
            </div>
          )}
        </main>
      )}
    </AppShell>
  );
}
