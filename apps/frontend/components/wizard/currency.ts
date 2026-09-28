/** pt-BR currency-input helpers shared by the wizard money fields. */
const grouper = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const display = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });

/**
 * Formats what the user is typing in a money field: keeps digits and the first
 * comma, regroups thousands live (1500000 -> "1.500.000"), caps decimals at 2.
 */
export function formatCurrencyInput(raw: string): { text: string; value: number | null } {
  const cleaned = raw.replace(/[^\d,]/g, "");
  if (!cleaned) return { text: "", value: null };
  const comma = cleaned.indexOf(",");
  const hasComma = comma >= 0;
  const intDigits = (hasComma ? cleaned.slice(0, comma) : cleaned).replace(/\D/g, "");
  const decimals = hasComma ? cleaned.slice(comma + 1).replace(/\D/g, "").slice(0, 2) : "";
  const intValue = intDigits ? Number(intDigits) : 0;
  const text = grouper.format(intValue) + (hasComma ? `,${decimals}` : "");
  const value = Number(`${intValue}.${decimals || "0"}`);
  return { text, value };
}

/** Formats a stored number for an idle money field ("" when empty). */
export function formatCurrencyValue(value: number | null): string {
  return value === null || Number.isNaN(value) ? "" : display.format(value);
}
