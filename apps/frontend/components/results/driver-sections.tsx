import { formatByUnit, percent, signedMoney, compactMoney } from "@/lib/format";
import { divergingBar, tornadoRows } from "@/lib/results";
import type { DecisionResponse, InsightResponse, TornadoResponse } from "@/lib/api/simulations";
import styles from "./results.module.css";

const WARNINGS: Record<string, string> = {
  correlated_drivers: "Há drivers correlacionados entre si; as participações deixam de ser aditivas.",
  low_rank_linear_fit: "O ajuste monotônico explica pouco da variação; há interações ou efeitos não lineares relevantes.",
  valuation_constant: "O valuation não varia entre os cenários; não há drivers a estimar.",
};

function coefficient(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function Legend() {
  return (
    <div className={styles.legend}>
      <span><i className={`${styles.swatch} ${styles.swatchIncrease}`} aria-hidden="true" />aumenta o valuation</span>
      <span><i className={`${styles.swatch} ${styles.swatchDecrease}`} aria-hidden="true" />reduz o valuation</span>
    </div>
  );
}

export function DriversCard({ decision, insight }: { decision: DecisionResponse; insight: InsightResponse }) {
  return (
    <article className={styles.card} id="drivers" aria-labelledby="drivers-title">
      <p className={styles.eyebrow}>Key valuation drivers</p>
      <h2 className={styles.cardTitle} id="drivers-title">O que mais move o valuation</h2>
      {insight.key_drivers_sentence && <p className={styles.sentence}>{insight.key_drivers_sentence}</p>}
      <Legend />
      <div className={styles.driverHead} aria-hidden="true">
        <span>Fator</span>
        <span><b>-1</b><b>0</b><b>+1</b></span>
        <span>Spearman</span>
        <span>Part.</span>
      </div>
      <div role="list">
        {decision.drivers.map((driver) => {
          const bar = divergingBar(driver.rho);
          const description = driver.rho === null
            ? `${driver.label}: não estimável, a variável não variou nesta simulação`
            : `${driver.label}: Spearman ${coefficient(driver.rho)}, participação ${percent(driver.contribution ?? 0, 0)}`;
          return (
            <div className={styles.driverRow} role="listitem" key={driver.name} title={description} aria-label={description}>
              <span className={styles.driverLabel}>{driver.label}</span>
              <div className={styles.driverTrack} aria-hidden="true">
                {bar && (
                  <i
                    className={`${styles.bar} ${bar.direction === "positive" ? `${styles.increase} ${styles.barPositive}` : `${styles.decrease} ${styles.barNegative}`}`}
                    style={{ left: `${bar.left}%`, width: `${Math.max(bar.width, 0.6)}%` }}
                  />
                )}
              </div>
              <span className={styles.driverValue}>{driver.rho === null ? "—" : coefficient(driver.rho)}</span>
              <span className={styles.driverShare}>{driver.contribution === null ? "—" : percent(driver.contribution, 0)}</span>
            </div>
          );
        })}
      </div>
      <p className={styles.note}>
        Barras: correlação de postos (Spearman) com o valuation, de -1 a +1. Participação: parcela da variância
        explicada atribuída a cada fator (SRRC²){decision.r_squared !== null ? `; o conjunto explica ${percent(decision.r_squared, 0)} da variação` : ""}.
        Associação no modelo, não causalidade.
        {decision.warnings.map((warning) => ` ${WARNINGS[warning] ?? ""}`)}
      </p>
    </article>
  );
}

export function TailsCard({ insight }: { insight: InsightResponse }) {
  return (
    <article className={`${styles.card} ${styles.tails}`} aria-label="Upside e downside drivers">
      <div>
        <p className={styles.eyebrow}>Upside drivers</p>
        <h3 className={styles.tailTitle}>O que diferencia os 10% melhores cenários</h3>
        {insight.upside.length ? (
          <ul className={styles.tailList}>
            {insight.upside.map((item) => (
              <li key={item.name}><span className={`${styles.arrow} ${styles.arrowUp}`} aria-hidden="true">↑</span><span>{item.text}</span></li>
            ))}
          </ul>
        ) : <p className={styles.note}>Nenhum fator se desloca de forma relevante nos melhores cenários.</p>}
      </div>
      <div>
        <p className={styles.eyebrow}>Downside drivers</p>
        <h3 className={styles.tailTitle}>O que diferencia os 10% piores cenários</h3>
        {insight.downside.length ? (
          <ul className={styles.tailList}>
            {insight.downside.map((item) => (
              <li key={item.name}><span className={`${styles.arrow} ${styles.arrowDown}`} aria-hidden="true">↓</span><span>{item.text}</span></li>
            ))}
          </ul>
        ) : <p className={styles.note}>Nenhum fator se desloca de forma relevante nos piores cenários.</p>}
      </div>
    </article>
  );
}

export function TornadoCard({ tornado, sentence, currency }: { tornado: TornadoResponse; sentence: string | null; currency: string }) {
  // Bars use 30% of each half so the value label at the tip fits even on a 390px screen.
  const half = 30;
  const rows = tornadoRows(tornado.items, tornado.base_value, half);
  const scale = Math.max(...tornado.items.flatMap((item) => [Math.abs(item.value_at_low - tornado.base_value), Math.abs(item.value_at_high - tornado.base_value)]), 0);
  const level = (unit: TornadoResponse["items"][number]["unit"], value: number) => formatByUnit(unit, value, currency);
  return (
    <article className={styles.card} id="sensibilidade" aria-labelledby="tornado-title">
      <p className={styles.eyebrow}>Sensibilidade · tornado</p>
      <h2 className={styles.cardTitle} id="tornado-title">Quanto cada premissa move o valuation mediano</h2>
      {sentence && <p className={styles.sentence}>{sentence}</p>}
      <Legend />
      {tornado.items.map((item, index) => {
        const row = rows[index];
        const segments = [
          { key: "low", segment: row.low, levelValue: item.low_level, className: styles.tornadoLow },
          { key: "high", segment: row.high, levelValue: item.high_level, className: styles.tornadoHigh },
        ];
        return (
          <div className={styles.tornadoRow} key={item.parameter}>
            <div className={styles.tornadoLabel}>
              <strong>{item.label}{item.clamped ? " *" : ""}</strong>
              <small>{level(item.unit, item.low_level)} → {level(item.unit, item.high_level)}</small>
            </div>
            <div className={styles.tornadoTrack}>
              {segments.map(({ key, segment, levelValue, className }) => {
                const text = `${item.label} em ${level(item.unit, levelValue)}: P50 ${compactMoney(tornado.base_value + segment.delta, "long", currency)} (${signedMoney(segment.delta, currency)})`;
                const positive = segment.direction === "positive";
                // Delta at the bar tip; the assumption level on the empty side of the axis.
                const deltaStyle = positive ? { left: `calc(${segment.start + segment.width}% + 6px)` } : { right: `calc(${100 - segment.start}% + 6px)` };
                const levelStyle = positive ? { right: "calc(50% + 6px)" } : { left: "calc(50% + 6px)" };
                return (
                  <span key={key}>
                    <i
                      className={`${styles.tornadoBar} ${className} ${segment.direction === "positive" ? `${styles.increase} ${styles.barPositive}` : `${styles.decrease} ${styles.barNegative}`}`}
                      style={{ left: `${segment.start}%`, width: `${Math.max(segment.width, 0.4)}%` }}
                      title={text}
                      role="img"
                      aria-label={text}
                    />
                    <span className={`${styles.tornadoValue} ${className}`} style={deltaStyle} aria-hidden="true">
                      {signedMoney(segment.delta, currency)}
                    </span>
                    <span className={`${styles.tornadoLevel} ${className}`} style={levelStyle} aria-hidden="true">
                      {level(item.unit, levelValue)}
                    </span>
                  </span>
                );
              })}
            </div>
          </div>
        );
      })}
      <div className={styles.tornadoAxis} aria-hidden="true">
        <span />
        <div className={styles.tornadoTicks}>
          <span style={{ left: `${50 - half}%` }}>{signedMoney(-scale, currency)}</span>
          <span style={{ left: "50%" }}>P50 base {compactMoney(tornado.base_value, "short", currency)}</span>
          <span style={{ left: `${50 + half}%` }}>{signedMoney(scale, currency)}</span>
        </div>
      </div>
      <p className={styles.note}>
        Uma premissa por vez, demais mantidas, sobre os mesmos cenários simulados. Barra superior: premissa no nível
        baixo; inferior: no nível alto (o nível aparece junto ao eixo). Níveis: P10/P90 da faixa informada ou base ±
        delta publicado.
        {tornado.items.some((item) => item.clamped) ? " * Nível ajustado para manter o crescimento na perpetuidade abaixo do WACC." : ""}
      </p>
      <details className={styles.tableView}>
        <summary>Ver tabela do tornado</summary>
        <table>
          <thead><tr><th>Premissa</th><th>Nível baixo</th><th>P50</th><th>Nível alto</th><th>P50</th></tr></thead>
          <tbody>
            {tornado.items.map((item) => (
              <tr key={item.parameter}>
                <td>{item.label}</td>
                <td>{level(item.unit, item.low_level)}</td>
                <td>{compactMoney(item.value_at_low, "short", currency)}</td>
                <td>{level(item.unit, item.high_level)}</td>
                <td>{compactMoney(item.value_at_high, "short", currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </article>
  );
}

export function RisksCard({ insight }: { insight: InsightResponse }) {
  return (
    <article className={styles.card} aria-labelledby="risks-title">
      <p className={styles.eyebrow}>Principais riscos</p>
      <h2 className={styles.cardTitle} id="risks-title">O que pode derrubar o valuation</h2>
      {insight.risks.length ? (
        <ol className={styles.risks}>{insight.risks.map((risk) => <li key={risk}>{risk}</li>)}</ol>
      ) : <p className={styles.note}>Nenhum risco material identificado nos cenários simulados.</p>}
    </article>
  );
}
