"use client";

import { FormEvent, useState } from "react";
import { compactMoney, formatByUnit, percent } from "@/lib/format";
import { histogramTicks, targetPlanView } from "@/lib/results";
import type { InsightResponse, SimulationResponse, SimulationSummary, TargetInsight, TargetPlan } from "@/lib/api/simulations";
import styles from "./results.module.css";

const integer = new Intl.NumberFormat("pt-BR");

/** Cliff's delta magnitude bands (Romano et al., 2006). */
function effectLabel(delta: number, kind: "continuous" | "binary"): string {
  const size = Math.abs(delta);
  if (kind === "binary") {
    const points = (size * 100).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    return `${delta >= 0 ? "+" : "-"}${points} p.p.`;
  }
  if (size >= 0.474) return "forte";
  if (size >= 0.33) return "moderada";
  if (size >= 0.147) return "fraca";
  return "desprezível";
}

/**
 * "Plano para a meta": what the hitting scenarios need to look like, derived from
 * already-simulated samples (no re-simulation). Renders nothing when the plan is
 * absent — free-plan workspaces or a `null` response — so the card degrades silently.
 */
function TargetPlanSection({ plan }: { plan: TargetPlan | null | undefined }) {
  const view = targetPlanView(plan);
  if (view.kind === "hidden") return null;
  return (
    <div className={styles.plan} aria-labelledby="target-plan-title">
      <p className={styles.eyebrow} id="target-plan-title">Plano para a meta</p>
      {(view.kind === "insufficient" || view.kind === "unavailable") && (
        <p className={styles.sentence} style={{ marginBottom: 0 }}>{view.sentence}</p>
      )}
      {view.kind === "available" && (
        <>
          <dl className={styles.facts}>
            <dt>CAGR de receita necessário</dt>
            <dd>{view.requiredCagr}</dd>
            {view.hitMargin !== null && (
              <>
                <dt>Margem EBITDA alvo (ano 5)</dt>
                <dd>{view.hitMargin}</dd>
              </>
            )}
          </dl>
          {view.trajectory.length > 0 && (
            <div className={styles.tableScroll}><table className={styles.dataTable}>
              <caption className={styles.muted} style={{ textAlign: "left", fontSize: 12 }}>
                Trajetória de receita de referência implícita no CAGR necessário
              </caption>
              <thead><tr><th>Ano</th><th>Receita de referência</th></tr></thead>
              <tbody>
                {view.trajectory.map((row) => (
                  <tr key={row.year}><td>{row.year}</td><td>{row.revenue}</td></tr>
                ))}
              </tbody>
            </table></div>
          )}
          <p className={styles.note}>{view.contrast}</p>
        </>
      )}
    </div>
  );
}

export function TargetCard({
  target,
  plan,
  initialValue,
  busy,
  error,
  currency,
  onAnalyze,
}: {
  target: TargetInsight | null;
  plan?: TargetPlan | null;
  initialValue: number | null;
  busy: boolean;
  error: string;
  currency: string;
  onAnalyze: (value: number) => void;
}) {
  const [value, setValue] = useState(initialValue === null ? "" : String(initialValue));
  const [inputError, setInputError] = useState("");
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsed = Number(value);
    if (!value.trim() || !Number.isFinite(parsed)) {
      setInputError("Informe um valuation-alvo numérico, em reais.");
      return;
    }
    setInputError("");
    onAnalyze(parsed);
  };
  const empty = target?.sample_note === "empty_group";
  return (
    <section className={styles.target} id="meta" aria-labelledby="target-title">
      <div className={styles.targetAside}>
        <p className={styles.eyebrow}>What needs to be true?</p>
        <h2 className={styles.cardTitle} id="target-title">Probabilidade de atingir a meta</h2>
        <form className={styles.targetForm} onSubmit={submit} noValidate>
          <label htmlFor="target-value">Valuation-alvo (R$)</label>
          <div>
            <input
              id="target-value"
              inputMode="numeric"
              type="number"
              min={0}
              step={100000}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              aria-invalid={Boolean(inputError)}
              aria-describedby={inputError ? "target-error" : undefined}
            />
            <button className="button button-primary" type="submit" disabled={busy}>{busy ? "Analisando…" : "Analisar"}</button>
          </div>
          {(inputError || error) && <p className={styles.error} id="target-error" role="alert">{inputError || error}</p>}
        </form>
        {target && (
          <div aria-live="polite">
            <strong className={styles.probability}>{percent(target.probability)}</strong>
            <span className={styles.probabilityCaption}>
              {integer.format(target.hit_count)} de {integer.format(target.scenario_count)} cenários atingiram {compactMoney(target.target, "long", currency)} ou mais.
            </span>
            <div className={styles.track} aria-hidden="true"><i style={{ width: `${target.probability * 100}%` }} /></div>
            <p className={styles.note}>Erro Monte Carlo (intervalo de 95%): {percent(target.wilson95_low)} a {percent(target.wilson95_high)}.</p>
          </div>
        )}
      </div>
      <div className={styles.targetMain}>
        {target ? (
          <>
            <p className={styles.interpretation}>{empty ? target.probability_sentence : target.interpretation}</p>
            {target.statements.length > 0 && (
              <ul className={styles.statements}>{target.statements.map((statement) => <li key={statement}>{statement}</li>)}</ul>
            )}
            {target.conditions.length > 0 && (
              <div className={styles.tableScroll}><table className={styles.dataTable}>
                <caption className={styles.muted} style={{ textAlign: "left", fontSize: 12 }}>
                  Condições nos cenários que atingem a meta vs. demais (mediana; taxa para eventos)
                </caption>
                <thead><tr><th>Condição</th><th>Atinge a meta</th><th>Demais</th><th>Diferença</th></tr></thead>
                <tbody>
                  {target.conditions.map((condition) => (
                    <tr key={condition.name}>
                      <td>{condition.label}</td>
                      <td>{formatByUnit(condition.unit, condition.hit_value, currency)}</td>
                      <td>{formatByUnit(condition.unit, condition.miss_value, currency)}</td>
                      <td>{effectLabel(condition.cliffs_delta, condition.kind)}</td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
            )}
            <p className={styles.note}>{target.disclaimer} Alterar a meta consulta os cenários já salvos; não roda uma nova simulação.</p>
            <TargetPlanSection plan={plan} />
          </>
        ) : (
          <p className={styles.sentence}>Informe um valuation-alvo para ver a probabilidade de atingi-lo e o que os cenários bem-sucedidos têm em comum.</p>
        )}
      </div>
    </section>
  );
}

export function DistributionCard({ summary, basis, currency }: { summary: SimulationSummary; basis: string; currency: string }) {
  const histogram = summary.histogram;
  const p = summary.percentiles;
  const short = (value: number) => compactMoney(value, "short", currency);
  const valid = histogram && histogram.edges.length === histogram.counts.length + 1 && histogram.counts.length > 0;
  const min = valid ? histogram.edges[0] : summary.minimum;
  const max = valid ? histogram.edges[histogram.edges.length - 1] : summary.maximum;
  const span = max - min || 1;
  const at = (value: number) => Math.max(0, Math.min(100, ((value - min) / span) * 100));
  const maxCount = valid ? Math.max(...histogram.counts, 1) : 1;
  const rows: [string, number][] = [
    ["P5", p.p5], ["P10", p.p10], ["P25", p.p25], ["P50 · mediana", p.p50], ["P75", p.p75], ["P90", p.p90], ["P95", p.p95],
    ["Média", summary.mean], ["Desvio padrão", summary.standard_deviation], ["Mínimo", summary.minimum], ["Máximo", summary.maximum],
  ];
  return (
    <article className={styles.card} id="distribuicao" aria-labelledby="distribution-title">
      <p className={styles.eyebrow}>Distribuição do valuation</p>
      <h2 className={styles.cardTitle} id="distribution-title">Todos os cenários simulados</h2>
      <p className={styles.sentence}>Base: {basis}. Cada barra conta cenários numa faixa de valuation; a faixa sombreada é o intervalo P25–P75.</p>
      {valid && (
        <>
          <div
            className={styles.histogram}
            role="img"
            aria-label={`Histograma de ${integer.format(histogram.counts.reduce((sum, count) => sum + count, 0))} cenários entre ${short(min)} e ${short(max)}; P10 ${short(p.p10)}, mediana ${short(p.p50)}, P90 ${short(p.p90)}.`}
          >
            <span className={styles.histBand} style={{ left: `${at(p.p25)}%`, width: `${at(p.p75) - at(p.p25)}%` }} />
            <div className={styles.histBars}>
              {histogram.counts.map((count, index) => (
                <i
                  key={index}
                  style={{ height: `${count === 0 ? 0 : Math.max(1, (count / maxCount) * 100)}%` }}
                  title={`${short(histogram.edges[index])} a ${short(histogram.edges[index + 1])}: ${integer.format(count)} cenários`}
                />
              ))}
            </div>
            {min < 0 && max > 0 && <span className={styles.histZero} style={{ left: `${at(0)}%` }}><b>{compactMoney(0, "short", currency)}</b></span>}
            <span className={styles.histMarker} style={{ left: `${at(p.p10)}%` }}><b>P10</b></span>
            <span className={`${styles.histMarker} ${styles.histMarkerP50}`} style={{ left: `${at(p.p50)}%` }}><b>P50 {short(p.p50)}</b></span>
            <span className={styles.histMarker} style={{ left: `${at(p.p90)}%` }}><b>P90</b></span>
          </div>
          <div className={styles.histBaseline} />
          <div className={styles.histTicks} aria-hidden="true">
            {histogramTicks(min, max, 4).map((tick) => <span key={tick.position} style={{ left: `${tick.position}%` }}>{short(tick.value)}</span>)}
          </div>
        </>
      )}
      <p className={styles.note}>
        {summary.failure_probability > 0 ? `Inclui ${percent(summary.failure_probability)} de cenários em que a empresa encerra as operações. ` : ""}
        {summary.non_positive_probability > 0 ? `${percent(summary.non_positive_probability)} dos cenários têm valuation igual ou inferior a zero${min < 0 && max > 0 ? " (linha vermelha em R$ 0)" : ""}. ` : ""}
        Nenhum cenário é descartado.
      </p>
      <div className={styles.tableScroll}><table className={styles.dataTable} aria-label="Estatísticas da distribuição">
        <thead><tr><th>Estatística</th><th>Valuation</th></tr></thead>
        <tbody>{rows.map(([label, amount]) => <tr key={label}><td>{label}</td><td>{compactMoney(amount, "long", currency)}</td></tr>)}</tbody>
      </table></div>
    </article>
  );
}

export function MethodsCard({ insight, simulation }: { insight: InsightResponse; simulation: SimulationResponse }) {
  const audit: [string, string][] = [
    ["Simulation ID", simulation.simulation_id],
    ["Versão do modelo", simulation.model_version],
    ["Seed", String(simulation.seed)],
    ["Cenários", integer.format(simulation.simulation_count)],
    ["Result hash", simulation.result_hash ?? "N/A"],
    ["Texto executivo", insight.template_version],
  ];
  return (
    <article className={styles.card} id="metodo" aria-labelledby="methods-title">
      <p className={styles.eyebrow}>Método e auditoria</p>
      <h2 className={styles.cardTitle} id="methods-title">Como estes resultados foram calculados</h2>
      <ul className={styles.methods}>{insight.method_notes.map((note) => <li key={note}>{note}</li>)}</ul>
      <div className={styles.tableScroll}><table className={styles.dataTable}>
        <tbody>{audit.map(([label, value]) => <tr key={label}><td>{label}</td><td><code>{value}</code></td></tr>)}</tbody>
      </table></div>
      <p className={styles.note}>
        Todo o texto é gerado de forma determinística a partir do resultado salvo; nenhum número é estimado por
        modelo de linguagem. Os resultados são estimativas sob as premissas informadas, não preço de transação.
      </p>
    </article>
  );
}
