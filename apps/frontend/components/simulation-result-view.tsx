"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ApiError } from "@/lib/api/client";
import { API_URL } from "@/lib/api/client";
import { getSimulation, type SimulationResponse } from "@/lib/api/simulations";
import { AppShell } from "./app-shell";
import { DecisionAnalysis } from "./decision-analysis";
import { ValuationHistogram } from "./valuation-histogram";

const money = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});
const integer = new Intl.NumberFormat("pt-BR");
const percent = new Intl.NumberFormat("pt-BR", {
  style: "percent",
  maximumFractionDigits: 1,
});

function compactMoney(value: number): string {
  const absolute = Math.abs(value);
  if (absolute >= 1_000_000) return `${value < 0 ? "-" : ""}R$ ${(absolute / 1_000_000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}M`;
  if (absolute >= 1_000) return `${value < 0 ? "-" : ""}R$ ${(absolute / 1_000).toLocaleString("pt-BR", { maximumFractionDigits: 0 })}k`;
  return money.format(value);
}

function Insight({ simulation }: { simulation: SimulationResponse }) {
  const summary = simulation.summary;
  if (!summary) return null;
  const p = summary.percentiles;
  return (
    <>
      <p>
        Nos {integer.format(simulation.simulation_count)} cenários simulados, o valuation
        mediano foi {money.format(p.p50)}. A metade central dos resultados ficou entre{" "}
        {money.format(p.p25)} e {money.format(p.p75)}.
      </p>
      <p>
        O cenário P10 resultou em {money.format(p.p10)}, enquanto o P90 atingiu{" "}
        {money.format(p.p90)}. A probabilidade observada de failure foi{" "}
        {percent.format(summary.failure_probability)}.
      </p>
      <p>
        A dispersão central (IQR / |P50|) foi{" "}
        {summary.uncertainty_ratio === null ? "indisponível porque a mediana está próxima de zero" : percent.format(summary.uncertainty_ratio)}.
        {" "}Valuations não positivos ocorreram em {percent.format(summary.non_positive_probability)} dos cenários.
      </p>
      <span>
        Texto calculado a partir do SimulationResult persistido. Nenhum percentil é
        recalculado no frontend.
      </span>
    </>
  );
}

function PercentileBars({ simulation }: { simulation: SimulationResponse }) {
  const percentiles = simulation.summary?.percentiles;
  const rows = useMemo(() => {
    if (!percentiles) return [];
    const values = [
      ["P5", percentiles.p5],
      ["P10", percentiles.p10],
      ["P25", percentiles.p25],
      ["P50", percentiles.p50],
      ["P75", percentiles.p75],
      ["P90", percentiles.p90],
      ["P95", percentiles.p95],
    ] as const;
    const min = Math.min(...values.map(([, value]) => value));
    const max = Math.max(...values.map(([, value]) => value));
    const span = max - min || 1;
    return values.map(([label, value]) => ({
      label,
      value,
      width: `${Math.max(4, ((value - min) / span) * 100)}%`,
    }));
  }, [percentiles]);

  return (
    <div className="percentile-table" role="table" aria-label="Percentis da simulação">
      {rows.map((row) => (
        <div className="percentile-row-real" role="row" key={row.label}>
          <span>{row.label}</span>
          <div><i style={{ width: row.width }} /></div>
          <strong>{compactMoney(row.value)}</strong>
        </div>
      ))}
    </div>
  );
}

function ResultContent({ simulation }: { simulation: SimulationResponse }) {
  const summary = simulation.summary;
  const p = summary?.percentiles;

  return (
    <AppShell active="/app/simulations/demo">
      <main id="main-content" className="result-page">
        <header className="result-header">
          <div>
            <Link href="/app">← Visão geral</Link>
            <p>SIMULAÇÃO REAL / {simulation.status.toUpperCase()}</p>
            <h1>Resultado da simulação</h1>
          </div>
          <div className="result-actions">
            <Link className="button button-secondary" href="/app/companies/new">
              Nova análise
            </Link>
            <a className="button button-primary" href={`${API_URL}/api/v1/simulations/${simulation.simulation_id}/report.pdf`}>
              Baixar PDF
            </a>
          </div>
        </header>

        <div className="audit-strip">
          <span><small>SIMULATION ID</small><code>{simulation.simulation_id}</code></span>
          <span><small>MODELO</small><code>{simulation.model_version}</code></span>
          <span><small>SEED</small><code>{simulation.seed}</code></span>
          <span><small>CENÁRIOS</small><code>{integer.format(simulation.simulation_count)}</code></span>
          <span><small>HASH</small><code>{simulation.result_hash?.slice(0, 16) ?? "N/A"}</code></span>
        </div>

        {p && summary ? (
          <>
            <nav className="result-tabs" aria-label="Seções do resultado">
              <a className="active" href="#overview">Visão geral</a>
              <a href="#distribution">Distribuição</a>
              <a href="#drivers">Drivers</a>
              <a href="#target">Meta</a>
              <a href="#audit">Auditoria</a>
            </nav>
            <section className="valuation-summary" id="overview">
              <article className="primary-metric">
                <p>ESTIMATIVA DE VALUATION</p>
                <span>P50 · MEDIANA</span>
                <strong>{compactMoney(p.p50)}</strong>
                <small>Metade da amostra está em ou abaixo desta mediana.</small>
              </article>
              <article>
                <p>CORE RANGE</p>
                <span>P25 - P75</span>
                <strong>{compactMoney(p.p25)} - {compactMoney(p.p75)}</strong>
                <small>Metade central dos cenários simulados.</small>
              </article>
              <article>
                <p>DOWNSIDE</p>
                <span>P10</span>
                <strong>{compactMoney(p.p10)}</strong>
                <small>10º percentil da amostra incondicional.</small>
              </article>
              <article>
                <p>UPSIDE</p>
                <span>P90</span>
                <strong>{compactMoney(p.p90)}</strong>
                <small>90º percentil da amostra incondicional.</small>
              </article>
            </section>

            <section className="result-grid" id="distribution">
              <article className="result-card">
                <header>
                  <div>
                    <p>DISTRIBUIÇÃO DE VALUATION</p>
                    <h2>Percentis persistidos</h2>
                  </div>
                  <span>{summary.basis}</span>
                </header>
                {summary.histogram && <ValuationHistogram histogram={summary.histogram} p10={p.p10} p50={p.p50} p90={p.p90} />}
                <PercentileBars simulation={simulation} />
                <p className="chart-note">
                  Valores negativos e cenários adversos permanecem na distribuição. A
                  visualização usa somente o resumo persistido.
                </p>
              </article>
              <article className="result-card insight-card">
                <p>EXECUTIVE VALUATION INSIGHT</p>
                <h2>Uma distribuição real, não um número isolado.</h2>
                <Insight simulation={simulation} />
              </article>
            </section>

            <DecisionAnalysis simulationId={simulation.simulation_id} suggestedTarget={p.p90} />

            <section className="assumptions-note" id="audit">
              <div>
                <p>AUDITORIA</p>
                <h2>Resultado reproduzível.</h2>
              </div>
              <p>
                Simulation ID <code>{simulation.simulation_id}</code>, model version{" "}
                <code>{simulation.model_version}</code>, seed <code>{simulation.seed}</code>,
                count <code>{simulation.simulation_count}</code> e result hash{" "}
                <code>{simulation.result_hash}</code>. Dashboard e PDF devem consumir este mesmo
                artefato.
              </p>
            </section>
          </>
        ) : (
          <section className="assumptions-note">
            <div>
              <p>SEM RESULTADO</p>
              <h2>A simulação ainda não possui resumo.</h2>
            </div>
            <p>Status atual: <code>{simulation.status}</code>. Recarregue a página ou volte para o wizard.</p>
          </section>
        )}
      </main>
    </AppShell>
  );
}

export function SimulationResultView({ simulationId }: { simulationId: string }) {
  const [simulation, setSimulation] = useState<SimulationResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    getSimulation(simulationId, controller.signal)
      .then(setSimulation)
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (err instanceof ApiError) {
          setError(`Não foi possível carregar a simulação. HTTP ${err.status}.`);
          return;
        }
        setError("Não foi possível carregar a simulação.");
      });
    return () => controller.abort();
  }, [simulationId]);

  if (error) {
    return (
      <AppShell active="/app/simulations/demo">
        <main id="main-content" className="result-page">
          <section className="assumptions-note">
            <div>
              <p>ERRO</p>
              <h2>Resultado indisponível.</h2>
            </div>
            <p>{error}</p>
          </section>
        </main>
      </AppShell>
    );
  }

  if (!simulation) {
    return (
      <AppShell active="/app/simulations/demo">
        <main id="main-content" className="result-page">
          <section className="assumptions-note">
            <div>
              <p>CARREGANDO</p>
              <h2>Buscando SimulationResult.</h2>
            </div>
            <p>O frontend está lendo o artefato persistido na API.</p>
          </section>
        </main>
      </AppShell>
    );
  }

  return <ResultContent simulation={simulation} />;
}
