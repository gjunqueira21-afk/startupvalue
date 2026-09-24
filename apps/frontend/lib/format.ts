/**
 * pt-BR number formatting for the results UI. The long style mirrors the backend
 * insight formatter (app/insights/formatting.py) so prose reads the same on
 * screen and in the PDF; the short style ("R$ 8,4 mi") is for tiles and charts.
 */

export type ValueUnit = "currency" | "ratio" | "multiplier" | "binary" | null;

const SYMBOLS: Record<string, string> = { BRL: "R$", USD: "US$", EUR: "EUR" };

function decimal(value: number, digits: number): string {
  return value.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function scaled(value: number, singular: string, plural: string, style: "long" | "short"): string {
  const digits = value >= 99.95 ? 0 : 1;
  const rounded = Number(value.toFixed(digits));
  const unit = style === "short" ? singular : rounded < 2 ? singular : plural;
  return `${decimal(rounded, digits)} ${unit}`;
}

export function compactMoney(value: number, style: "long" | "short" = "long", currency = "BRL"): string {
  const symbol = SYMBOLS[currency] ?? currency;
  const sign = value < 0 ? "-" : "";
  const absolute = Math.abs(value);
  let amount: string;
  // Move to the next scale when the smaller one would round to 1.000 or more.
  if (Math.round(absolute / 1e6) >= 1000) {
    amount = style === "short" ? scaled(absolute / 1e9, "bi", "bi", style) : scaled(absolute / 1e9, "bilhão", "bilhões", style);
  } else if (Math.round(absolute / 1e3) >= 1000) {
    amount = style === "short" ? scaled(absolute / 1e6, "mi", "mi", style) : scaled(absolute / 1e6, "milhão", "milhões", style);
  } else if (Math.round(absolute) >= 1000) {
    amount = `${decimal(Math.round(absolute / 1e3), 0)} mil`;
  } else {
    amount = decimal(Math.round(absolute), 0);
  }
  return `${sign}${symbol} ${amount}`;
}

export function signedMoney(value: number, currency = "BRL"): string {
  if (value === 0) return compactMoney(0, "short", currency);
  return `${value > 0 ? "+" : ""}${compactMoney(value, "short", currency)}`;
}

export function percent(value: number, digits = 1): string {
  if (value === 0 || value === 1) return `${Math.round(value * 100)}%`;
  return `${decimal(value * 100, digits)}%`;
}

export function formatByUnit(unit: ValueUnit, value: number, currency = "BRL"): string {
  if (unit === "currency") return compactMoney(value, "short", currency);
  if (unit === "ratio" || unit === "binary") return percent(value);
  if (unit === "multiplier") return `${decimal(value, 2)}x`;
  return decimal(value, 2);
}

const BASIS_LABELS: Record<string, string> = {
  "DCF equity value (signed)": "Equity via DCF · inclui valores negativos",
};

export function basisLabel(basis: string): string {
  return BASIS_LABELS[basis] ?? basis;
}
