const points = [8, 10, 14, 20, 31, 46, 67, 88, 72, 49, 30, 19, 12, 8, 5];

export function DistributionChart() {
  const max = Math.max(...points);
  return (
    <div className="distribution-chart" role="img" aria-label="Histograma ilustrativo de valuation, com maior concentração em torno de oito milhões e quatrocentos mil reais">
      <div className="chart-bars" aria-hidden="true">
        {points.map((point, index) => <span key={index} style={{ height: `${(point / max) * 100}%` }} />)}
      </div>
      <div className="chart-marker marker-p25"><span>P25</span></div>
      <div className="chart-marker marker-p50"><span>P50 · R$ 8,4M</span></div>
      <div className="chart-marker marker-p75"><span>P75</span></div>
      <div className="chart-axis"><span>R$ 0</span><span>R$ 20M+</span></div>
    </div>
  );
}
