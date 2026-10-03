import { compactMoney, percent } from "@/lib/format";
import { multiplesRows, uncertaintyPosition } from "@/lib/results";
import type { ImpliedMultiples, InsightResponse, SimulationSummary, TargetInsight, UncertaintyLabel } from "@/lib/api/simulations";
import styles from "./results.module.css";

const LEVELS: { key: UncertaintyLabel; label: string; share: number }[] = [
  // Segment widths follow the published IQR/P50 bands on a 0..2 track: 0.4 / 0.8 / 1.5.
  { key: "LOW", label: "Baixa", share: 20 },
  { key: "MODERATE", label: "Moderada", share: 20 },
  { key: "HIGH", label: "Alta", share: 35 },
  { key: "VERY HIGH", label: "Muito alta", share: 25 },
];
const MEANING: Record<UncertaintyLabel, string> = {
  LOW: "BAIXA",
  MODERATE: "MODERADA",
  HIGH: "ALTA",
  "VERY HIGH": "MUITO ALTA",
};

export function KpiRow({ summary, target, currency }: { summary: SimulationSummary; target: TargetInsight | null; currency: string }) {
  const p = summary.percentiles;
  const short = (value: number) => compactMoney(value, "short", currency);
  return (
    <section className={styles.kpis} aria-label="Resumo do valuation">
      <article className={`${styles.kpi} ${styles.kpiHero}`}>
        <span className={styles.kpiLabel}>VALUATION ESTIMADO</span>
        <span className={styles.kpiSub}>P50 · mediana</span>
        <strong className={styles.kpiValue}>{short(p.p50)}</strong>
        <span className={styles.kpiNote}>Metade dos cenários fica em ou abaixo deste valor.</span>
      </article>
      <article className={`${styles.kpi} ${styles.kpiWide}`}>
        <span className={styles.kpiLabel}>FAIXA CENTRAL</span>
        <span className={styles.kpiSub}>P25 – P75</span>
        <strong className={styles.kpiValue}>{short(p.p25)} – {short(p.p75)}</strong>
        <span className={styles.kpiNote}>Onde se concentram os cenários centrais.</span>
      </article>
      <article className={styles.kpi}>
        <span className={styles.kpiLabel}>DOWNSIDE</span>
        <span className={styles.kpiSub}>P10</span>
        <strong className={styles.kpiValue}>{short(p.p10)}</strong>
        <span className={styles.kpiNote}>Cenário conservador.</span>
      </article>
      <article className={styles.kpi}>
        <span className={styles.kpiLabel}>UPSIDE</span>
        <span className={styles.kpiSub}>P90</span>
        <strong className={styles.kpiValue}>{short(p.p90)}</strong>
        <span className={styles.kpiNote}>Cenário otimista.</span>
      </article>
      <article className={`${styles.kpi} ${styles.kpiWide}`}>
        <span className={styles.kpiLabel}>PROBABILIDADE DA META</span>
        <span className={styles.kpiSub}>{target ? `≥ ${short(target.target)}` : "sem meta definida"}</span>
        <strong className={styles.kpiValue}>{target ? percent(target.probability) : "—"}</strong>
        <span className={styles.kpiNote}>{target ? <a href="#meta">Ver o que precisa acontecer</a> : "Defina uma meta abaixo."}</span>
      </article>
    </section>
  );
}

/**
 * Valuation ÷ year-5 revenue/EBITDA across the simulated scenarios. Renders nothing
 * when the section is absent — e.g. stripped for free-plan workspaces, or the engine
 * could not derive enough eligible scenarios — so the page degrades silently.
 */
export function MultiplesCard({ multiples }: { multiples: ImpliedMultiples | null | undefined }) {
  const rows = multiplesRows(multiples);
  if (rows.length === 0) return null;
  return (
    <article className={styles.card} aria-labelledby="multiples-title">
      <p className={styles.eyebrow}>Múltiplos implícitos</p>
      <h2 className={styles.cardTitle} id="multiples-title">O que o valuation implica em múltiplos</h2>
      <div className={styles.tableScroll}><table className={styles.dataTable}>
        <caption className={styles.muted} style={{ textAlign: "left", fontSize: 12 }}>
          Múltiplos implícitos nas suas premissas — não são múltiplos de mercado.
        </caption>
        <thead><tr><th>Múltiplo</th><th>P25</th><th>P50</th><th>P75</th></tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <td>{row.label}</td>
              <td>{row.p25}</td>
              <td>{row.p50}</td>
              <td>{row.p75}</td>
            </tr>
          ))}
        </tbody>
      </table></div>
      <p className={styles.note}>{rows.map((row) => `${row.label}: ${row.note}.`).join(" ")}</p>
    </article>
  );
}

export function InsightSection({ insight, summary, currency }: { insight: InsightResponse; summary: SimulationSummary; currency: string }) {
  const uncertainty = summary.uncertainty;
  const activeIndex = LEVELS.findIndex((level) => level.key === insight.uncertainty.label);
  const columns = LEVELS.map((level) => `${level.share}fr`).join(" ");
  const marker = uncertaintyPosition(uncertainty?.iqr_ratio ?? null);
  return (
    <section className={styles.insight} id="insight" aria-labelledby="insight-headline">
      <div className={styles.insightBody}>
        <p className={styles.eyebrow}>Valuation insight</p>
        <h2 className={styles.headline} id="insight-headline">{insight.headline}</h2>
        <div className={styles.prose}>
          {insight.valuation_paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
        </div>
      </div>
      <aside className={styles.uncertainty} aria-labelledby="uncertainty-title">
        <p className={styles.eyebrow} id="uncertainty-title">Incerteza do valuation</p>
        <strong className={styles.uncertaintyLabel}>{MEANING[insight.uncertainty.label]}</strong>
        <div
          className={styles.meter}
          style={{ gridTemplateColumns: columns }}
          role="img"
          aria-label={`Incerteza ${insight.uncertainty.label_pt.toLowerCase()} numa escala de baixa a muito alta`}
        >
          {LEVELS.map((level, index) => <i key={level.key} className={index <= activeIndex ? styles.meterOn : undefined} />)}
          <span className={styles.meterMarker} style={{ left: `${marker}%` }} aria-hidden="true" />
        </div>
        <div className={styles.meterScale} style={{ gridTemplateColumns: columns }} aria-hidden="true">
          {LEVELS.map((level, index) => <span key={level.key} className={index === activeIndex ? styles.meterScaleOn : undefined}>{level.label}</span>)}
        </div>
        <p className={styles.uncertaintySentence}>{insight.uncertainty.sentence}</p>
        {uncertainty && (
          <dl className={styles.facts}>
            <dt>Faixa P25–P75 / mediana</dt>
            <dd>{uncertainty.iqr_ratio === null ? "não se aplica" : percent(uncertainty.iqr_ratio, 0)}</dd>
            <dt>Faixa P10–P90 / mediana</dt>
            <dd>{uncertainty.spread80_ratio === null ? "não se aplica" : percent(uncertainty.spread80_ratio, 0)}</dd>
            <dt>Amplitude P25–P75</dt>
            <dd>{compactMoney(uncertainty.iqr, "short", currency)}</dd>
            <dt>Cenários com valuation ≤ 0</dt>
            <dd>{percent(uncertainty.non_positive_probability)}</dd>
          </dl>
        )}
      </aside>
    </section>
  );
}
