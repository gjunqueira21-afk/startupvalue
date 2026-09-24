"use client";

const compact = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });

export function ValuationHistogram({ histogram, p10, p50, p90 }: {
  histogram: { edges: number[]; counts: number[] };
  p10: number;
  p50: number;
  p90: number;
}) {
  const { edges, counts } = histogram;
  if (edges.length !== counts.length + 1 || counts.length === 0) return null;
  const maxCount = Math.max(...counts, 1);
  const min = edges[0];
  const max = edges[edges.length - 1];
  const position = (value: number) => `${Math.max(0, Math.min(100, ((value - min) / (max - min || 1)) * 100))}%`;
  return (
    <div className="real-histogram" role="img" aria-label={`Histograma dos valuations; P10 ${compact.format(p10)}, mediana ${compact.format(p50)}, P90 ${compact.format(p90)}`}>
      <div className="real-histogram-bars">{counts.map((count, index) => <i key={index} style={{ height: `${Math.max(1, count / maxCount * 100)}%` }} />)}</div>
      <span className="histogram-marker histogram-p10" style={{ left: position(p10) }}><b>P10</b></span>
      <span className="histogram-marker histogram-p50" style={{ left: position(p50) }}><b>P50</b></span>
      <span className="histogram-marker histogram-p90" style={{ left: position(p90) }}><b>P90</b></span>
      <div className="histogram-axis"><span>{compact.format(min)}</span><span>{compact.format(max)}</span></div>
    </div>
  );
}
