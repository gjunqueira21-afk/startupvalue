interface RevenueChartProps {
  values: readonly number[];
  cadence: "annual" | "monthly";
}

const money = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  notation: "compact",
  maximumFractionDigits: 1,
});

export function RevenueChart({ values, cadence }: RevenueChartProps) {
  const maximum = Math.max(...values, 1);

  return (
    <figure className="revenue-preview" aria-label="Prévia da projeção de receita">
      <figcaption>
        <span>PROJEÇÃO EM TEMPO REAL</span>
        <small>{cadence === "annual" ? "Receita anual" : "Receita média mensal"}</small>
      </figcaption>
      <div className="revenue-bars" aria-hidden="true">
        {values.map((value, index) => (
          <div key={index}>
            <span style={{ height: `${Math.max((value / maximum) * 100, value > 0 ? 4 : 0)}%` }} />
            <small>A{index + 1}</small>
          </div>
        ))}
      </div>
      <div className="revenue-values">
        {values.map((value, index) => (
          <span key={index}>{money.format(value)}</span>
        ))}
      </div>
    </figure>
  );
}
