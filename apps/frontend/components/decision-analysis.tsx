"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  getDecision,
  getTarget,
  type DecisionResponse,
  type TargetResponse,
} from "@/lib/api/simulations";
import { API_URL } from "@/lib/api/client";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const pct = new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 1 });
const integer = new Intl.NumberFormat("pt-BR");

function factorLabel(name: string): string {
  const known: Record<string, string> = {
    factor: "Fator econômico do cenário",
    cash_flow_factor: "Fator de fluxo de caixa",
    year_5_cash_flow: "Fluxo de caixa do Ano 5",
    revenue_year_5: "Receita do Ano 5",
    failure_month: "Mês de failure",
    scenario_factor_mean: "Choque médio do cenário",
    realized_cash_flow_total: "Fluxo de caixa realizado (total)",
    realized_cash_flow_final_12m: "Fluxo de caixa realizado (Ano 5)",
    failure_state: "Estado de encerramento (0/1)",
    revenue_year5: "Receita realizada no Ano 5",
    margin_year5: "Margem bruta realizada no Ano 5",
    modeled_gross_margin_year5: "Margem bruta simulada no Ano 5",
    opex_year5: "OPEX realizado no Ano 5",
    revenue_factor_mean: "Choque médio de receita",
    cost_factor_mean: "Choque médio de custos",
    margin_delta_mean: "Variação média da margem",
  };
  return known[name] ?? name.replaceAll("_", " ");
}

function FactorValue({ name, value }: { name: string; value: number | null }) {
  if (value === null) return <>—</>;
  if (/revenue|opex|cash_flow/.test(name)) return <>{brl.format(value)}</>;
  if (/margin/.test(name)) return <>{pct.format(value)}</>;
  return <>{Number.isInteger(value) ? integer.format(value) : value.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}</>;
}

export function DecisionAnalysis({ simulationId, suggestedTarget }: { simulationId: string; suggestedTarget: number }) {
  const [decision, setDecision] = useState<DecisionResponse | null>(null);
  const [decisionError, setDecisionError] = useState("");
  const [targetInput, setTargetInput] = useState(String(Math.max(0, Math.ceil(suggestedTarget / 1_000_000) * 1_000_000)));
  const [target, setTarget] = useState<TargetResponse | null>(null);
  const [targetError, setTargetError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getDecision(simulationId, controller.signal)
      .then(setDecision)
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setDecisionError("Os drivers desta execução não estão disponíveis.");
      });
    return () => controller.abort();
  }, [simulationId]);

  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = Number(targetInput);
    if (!Number.isFinite(value) || value < 0) {
      setTargetError("Informe uma meta válida, maior ou igual a zero.");
      return;
    }
    setBusy(true);
    setTargetError("");
    try {
      setTarget(await getTarget(simulationId, value));
    } catch {
      setTargetError("Não foi possível analisar a meta nesta execução.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="result-grid" id="drivers">
      <article className="result-card">
        <header>
          <div><p>KEY VALUATION DRIVERS</p><h2>Associação com o valuation</h2></div>
          <span>SPEARMAN · AMOSTRA COMPLETA</span>
        </header>
        {decision ? (
          <>
            {decision.drivers.filter((driver) => !driver.name.startsWith("realized_cash_flow_")).map((driver) => (
              <div className="driver-row" key={driver.name}>
                <span>{factorLabel(driver.name)}</span>
                <div><i className={driver.rho !== null && driver.rho < 0 ? "negative" : ""} style={{ width: `${Math.abs(driver.rho ?? 0) * 100}%` }} /></div>
                <strong>{driver.rho === null ? "—" : `${driver.rho >= 0 ? "+" : ""}${driver.rho.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}`}</strong>
              </div>
            ))}
            <p className="chart-note">Correlação de postos nos cenários simulados. Associação não demonstra causalidade. Fatores constantes aparecem sem coeficiente.</p>
          </>
        ) : <p className="chart-note" role="status">{decisionError || "Calculando associações dos cenários salvos..."}</p>}
      </article>
      <article className="result-card target-summary" id="target">
        <p>WHAT NEEDS TO BE TRUE?</p>
        <h2>Probabilidade de atingir sua meta</h2>
        <form className="target-form" onSubmit={analyze}>
          <label htmlFor="target-value">Valuation alvo (R$)</label>
          <div><input id="target-value" type="number" min="0" step="1000" value={targetInput} onChange={(event) => setTargetInput(event.target.value)} /><button className="button button-primary" type="submit" disabled={busy}>{busy ? "Analisando..." : "Analisar"}</button></div>
        </form>
        {targetError && <p className="chart-note" role="alert">{targetError}</p>}
        {target && (
          <>
            <strong>{pct.format(target.probability)}</strong>
            <span>{integer.format(target.hit_count)} de {integer.format(target.scenario_count)} cenários atingiram {brl.format(target.target)} ou mais.</span>
            <div className="probability-track"><i style={{ width: `${target.probability * 100}%` }} /></div>
            <p className="chart-note">Intervalo de Wilson de 95% para a frequência simulada: {pct.format(target.wilson95_low)}–{pct.format(target.wilson95_high)}.</p>
            {target.comparisons.length > 0 && (
              <table>
                <caption>Medianas condicionais · cenários que atingem vs. demais</caption>
                <thead><tr><th>Fator</th><th>Atinge</th><th>Não atinge</th></tr></thead>
                <tbody>{target.comparisons.map((row) => <tr key={row.name}><td>{factorLabel(row.name)}</td><td><FactorValue name={row.name} value={row.hit.p50} /></td><td><FactorValue name={row.name} value={row.miss.p50} /></td></tr>)}</tbody>
              </table>
            )}
            <p className="chart-note">As diferenças descrevem os grupos observados nesta simulação; não são metas causais garantidas.</p>
            <a className="button button-secondary" href={`${API_URL}/api/v1/simulations/${simulationId}/report.pdf?target=${encodeURIComponent(target.target)}`}>Baixar PDF com esta meta</a>
          </>
        )}
      </article>
    </section>
  );
}
