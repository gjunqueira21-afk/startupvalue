"use client";

import { useEffect, useRef, useState } from "react";

type Dot = { x: number; y: number; depth: number; phase: number; size: number };

function seededDots(count: number): Dot[] {
  let seed = 471829;
  const random = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  return Array.from({ length: count }, () => ({
    x: random(),
    y: random(),
    depth: random(),
    phase: random() * Math.PI * 2,
    size: 0.6 + random() * 1.5,
  }));
}

const percentiles = [
  { label: "P10", value: "R$ 4,3M", x: 15 },
  { label: "P25", value: "R$ 6,1M", x: 29 },
  { label: "P50", value: "R$ 8,4M", x: 50 },
  { label: "P75", value: "R$ 11,7M", x: 71 },
  { label: "P90", value: "R$ 15,2M", x: 86 },
];

export function MonteCarloVisual() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;

    const context = canvas.getContext("2d");
    if (!context) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dots = seededDots(window.innerWidth < 640 ? 150 : 380);
    let frame = 0;
    let start = performance.now();
    let visible = true;

    const resize = () => {
      const rect = wrap.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(rect.width * dpr);
      canvas.height = Math.floor(rect.height * dpr);
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (now: number) => {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      context.clearRect(0, 0, width, height);
      const elapsed = reduced ? 8000 : now - start;
      const settle = Math.min(1, elapsed / 2600);
      const mouseX = Number(wrap.dataset.pointerX || 0);
      const mouseY = Number(wrap.dataset.pointerY || 0);

      context.save();
      context.strokeStyle = "rgba(166, 177, 189, 0.12)";
      context.lineWidth = 1;
      for (let row = 1; row < 5; row += 1) {
        const y = (height / 5) * row;
        context.beginPath(); context.moveTo(0, y); context.lineTo(width, y); context.stroke();
      }
      context.restore();

      for (const dot of dots) {
        const gaussian = Math.exp(-Math.pow((dot.x - 0.5) * 3.5, 2));
        const targetY = height * (0.79 - gaussian * 0.55 * dot.y);
        const dispersedY = height * (0.1 + dot.y * 0.78);
        const idle = reduced ? 0 : Math.sin(now / 1100 + dot.phase) * 2.5;
        const parallaxX = mouseX * (dot.depth - 0.5) * 8;
        const parallaxY = mouseY * (dot.depth - 0.5) * 5;
        const x = width * (0.05 + dot.x * 0.9) + parallaxX;
        const y = dispersedY * (1 - settle) + targetY * settle + idle + parallaxY;
        context.beginPath();
        context.fillStyle = dot.x > 0.76
          ? `rgba(92,167,255,${0.25 + dot.depth * 0.6})`
          : `rgba(53,230,161,${0.2 + dot.depth * 0.65})`;
        context.arc(x, y, dot.size, 0, Math.PI * 2);
        context.fill();
      }

      if (!reduced && visible) frame = requestAnimationFrame(draw);
    };

    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (visible && !reduced) {
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(draw);
      }
    });
    const resizeObserver = new ResizeObserver(() => { resize(); draw(performance.now()); });
    observer.observe(wrap);
    resizeObserver.observe(wrap);
    resize();
    setReady(true);
    frame = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      resizeObserver.disconnect();
    };
  }, []);

  const handlePointer = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!wrapRef.current) return;
    const bounds = wrapRef.current.getBoundingClientRect();
    wrapRef.current.dataset.pointerX = String((event.clientX - bounds.left) / bounds.width - 0.5);
    wrapRef.current.dataset.pointerY = String((event.clientY - bounds.top) / bounds.height - 0.5);
  };

  return (
    <div className="simulation-shell" ref={wrapRef} onPointerMove={handlePointer} onPointerLeave={() => {
      if (wrapRef.current) { wrapRef.current.dataset.pointerX = "0"; wrapRef.current.dataset.pointerY = "0"; }
    }}>
      <div className="simulation-topline">
        <span className="live-dot" />
        <span>MONTE CARLO MODEL</span>
        <span className="mono">SEED 471829</span>
      </div>
      <div className="simulation-title">
        <span>10.000 futuros simulados</span>
        <strong>Distribuição de valuation</strong>
      </div>
      <div className="canvas-wrap" aria-hidden="true">
        <canvas className={ready ? "is-ready" : ""} ref={canvasRef} />
        <svg className="canvas-fallback" viewBox="0 0 600 310" preserveAspectRatio="none">
          <path d="M22 264C124 260 156 239 215 205c48-28 62-131 92-131 35 0 47 107 99 137 50 29 93 48 170 53" />
        </svg>
      </div>
      <div className="percentile-row" aria-label="Exemplo ilustrativo de percentis">
        {percentiles.map((item) => (
          <div className={item.label === "P50" ? "percentile active" : "percentile"} key={item.label} style={{ left: `${item.x}%` }}>
            <span>{item.label}</span><strong>{item.value}</strong>
          </div>
        ))}
      </div>
      <p className="visual-caption">Dados ilustrativos · DCF equity value · BRL</p>
    </div>
  );
}
