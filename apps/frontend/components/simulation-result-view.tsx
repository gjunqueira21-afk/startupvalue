"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { API_URL, ApiError } from "@/lib/api/client";
import {
  getDecision,
  getInsight,
  getSimulation,
  getTarget,
  type DecisionResponse,
  type InsightResponse,
  type SimulationResponse,
  type TargetPlan,
} from "@/lib/api/simulations";
import { basisLabel } from "@/lib/format";
import { suggestedTarget } from "@/lib/results";
import { AppShell } from "./app-shell";
import { DistributionCard, MethodsCard, TargetCard } from "./results/analysis-sections";
import { DriversCard, RisksCard, TailsCard, TornadoCard } from "./results/driver-sections";
import { InsightSection, KpiRow, MultiplesCard } from "./results/summary-sections";
import styles from "./results/results.module.css";

const integer = new Intl.NumberFormat("pt-BR");
const date = new Intl.DateTimeFormat("pt-BR", { dateStyle: "long" });

function StatusPanel({ eyebrow, title, children }: { eyebrow: string; title: string; children: React.ReactNode }) {
  return (
    <AppShell active="/app/simulations/demo">
      <main id="main-content" className="result-page">
        <section className="assumptions-note">
          <div><p>{eyebrow}</p><h2>{title}</h2></div>
          <p>{children}</p>
        </section>
      </main>
    </AppShell>
  );
}

function ResultContent({ simulation }: { simulation: SimulationResponse }) {
  const summary = simulation.summary;
  const currency = simulation.currency;
  const defaultTarget = summary ? suggestedTarget(summary.percentiles.p75, summary.percentiles.p90) : null;
  const [decision, setDecision] = useState<DecisionResponse | null>(null);
  const [insight, setInsight] = useState<InsightResponse | null>(null);
  const [target, setTarget] = useState<number | null>(defaultTarget);
  const [plan, setPlan] = useState<TargetPlan | null>(null);
  const [loadError, setLoadError] = useState("");
  const [targetError, setTargetError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!summary) return;
    const controller = new AbortController();
    Promise.all([
      getDecision(simulation.simulation_id, controller.signal),
      getInsight(simulation.simulation_id, defaultTarget, controller.signal),
      defaultTarget === null
        ? Promise.resolve(null)
        // The "Plano para a meta" section is supplementary: a failure here (not
        // entitled, transient error) degrades to hidden, it never blocks the rest
        // of the page, so it gets its own catch instead of joining the one below.
        : getTarget(simulation.simulation_id, defaultTarget, controller.signal).catch(() => null),
    ])
      .then(([decisionResult, insightResult, targetResult]) => {
        setDecision(decisionResult);
        setInsight(insightResult);
        setPlan(targetResult?.plan ?? null);
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setLoadError("A análise executiva desta simulação não pôde ser carregada.");
      });
    return () => controller.abort();
  }, [simulation.simulation_id, summary, defaultTarget]);

  const analyze = useCallback(async (value: number) => {
    setBusy(true);
    setTargetError("");
    try {
      const [insightResult, targetResult] = await Promise.all([
        getInsight(simulation.simulation_id, value),
        // Same degrade-to-hidden rule as the initial load: a target-plan failure
        // must not surface as a target-analysis error.
        getTarget(simulation.simulation_id, value).catch(() => null),
      ]);
      setInsight(insightResult);
      setTarget(value);
      setPlan(targetResult?.plan ?? null);
    } catch {
      setTargetError("Não foi possível analisar esta meta.");
    } finally {
      setBusy(false);
    }
  }, [simulation.simulation_id]);

  const reportUrl = `${API_URL}/api/v1/simulations/${simulation.simulation_id}/report.pdf${target === null ? "" : `?target=${encodeURIComponent(target)}`}`;

  return (
    <AppShell active="/app/simulations/demo">
      <main id="main-content" className="result-page">
        <div className={styles.results}>
          <header className={styles.header}>
            <div>
              <Link className={styles.back} href="/app">← Visão geral</Link>
              <p className={styles.eyebrow}>Resultado da simulação · {simulation.status === "succeeded" ? "concluída" : simulation.status}</p>
              <h1 className={styles.title}>{simulation.company_name ?? "Resultado da simulação"}</h1>
              <p className={styles.meta}>
                {simulation.scenario_name ? `${simulation.scenario_name} · ` : ""}
                {date.format(new Date(simulation.created_at))} · {integer.format(simulation.simulation_count)} cenários · seed {simulation.seed} · modelo {simulation.model_version}
              </p>
            </div>
            <div className={styles.actions}>
              <Link className="button button-secondary" href="/app/companies/new">Nova análise</Link>
              <a className="button button-primary" href={reportUrl}>Baixar PDF</a>
            </div>
          </header>

          {summary ? (
            <>
              <KpiRow summary={summary} target={insight?.target ?? null} currency={currency} />
              <MultiplesCard multiples={summary.implied_multiples} />
              {insight ? (
                <InsightSection insight={insight} summary={summary} currency={currency} />
              ) : (
                <p className={styles.sentence} role="status">{loadError || "Preparando a interpretação dos cenários…"}</p>
              )}
              <nav className={styles.jump} aria-label="Seções do resultado">
                <a href="#drivers">Drivers</a>
                <a href="#sensibilidade">Sensibilidade</a>
                <a href="#meta">Meta</a>
                <a href="#distribuicao">Distribuição</a>
                <a href="#metodo">Método e auditoria</a>
              </nav>
              {decision && insight && (
                <div className={styles.grid2}>
                  <DriversCard decision={decision} insight={insight} />
                  <TailsCard insight={insight} />
                </div>
              )}
              {decision?.tornado && insight && (
                <div className={styles.grid2}>
                  <TornadoCard tornado={decision.tornado} sentence={insight.sensitivity_sentence} currency={currency} />
                  <RisksCard insight={insight} />
                </div>
              )}
              {insight && (
                <TargetCard
                  target={insight.target}
                  plan={plan}
                  initialValue={defaultTarget}
                  busy={busy}
                  error={targetError}
                  currency={currency}
                  onAnalyze={analyze}
                />
              )}
              <DistributionCard summary={summary} basis={basisLabel(summary.basis)} currency={currency} />
              {insight && <MethodsCard insight={insight} simulation={simulation} />}
            </>
          ) : (
            <p className={styles.sentence}>Esta simulação ainda não tem resultado. Status atual: {simulation.status}.</p>
          )}
        </div>
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
        setError(err instanceof ApiError ? `Não foi possível carregar a simulação. HTTP ${err.status}.` : "Não foi possível carregar a simulação.");
      });
    return () => controller.abort();
  }, [simulationId]);

  if (error) return <StatusPanel eyebrow="ERRO" title="Resultado indisponível.">{error}</StatusPanel>;
  if (!simulation) return <StatusPanel eyebrow="CARREGANDO" title="Buscando o resultado da simulação.">Lendo o resultado salvo na API.</StatusPanel>;
  return <ResultContent simulation={simulation} />;
}
