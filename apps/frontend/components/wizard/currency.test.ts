import { describe, expect, it } from "vitest";
import { formatCurrencyInput, formatCurrencyValue } from "./currency";

describe("formatCurrencyInput", () => {
  it("groups thousands while typing", () => {
    expect(formatCurrencyInput("1500000")).toEqual({ text: "1.500.000", value: 1500000 });
  });
  it("accepts values already grouped", () => {
    expect(formatCurrencyInput("1.500.000")).toEqual({ text: "1.500.000", value: 1500000 });
  });
  it("keeps a comma with up to two decimals", () => {
    expect(formatCurrencyInput("1500000,5")).toEqual({ text: "1.500.000,5", value: 1500000.5 });
    expect(formatCurrencyInput("1500000,555")).toEqual({ text: "1.500.000,55", value: 1500000.55 });
  });
  it("treats a leading comma as zero-point", () => {
    expect(formatCurrencyInput(",5")).toEqual({ text: "0,5", value: 0.5 });
  });
  it("ignores everything that is not a digit or comma", () => {
    expect(formatCurrencyInput("R$ 2.000abc")).toEqual({ text: "2.000", value: 2000 });
    expect(formatCurrencyInput("abc")).toEqual({ text: "", value: null });
    expect(formatCurrencyInput("")).toEqual({ text: "", value: null });
  });
});

describe("formatCurrencyValue", () => {
  it("renders pt-BR grouping with up to two decimals", () => {
    expect(formatCurrencyValue(1234567.5)).toBe("1.234.567,5");
    expect(formatCurrencyValue(0)).toBe("0");
    expect(formatCurrencyValue(null)).toBe("");
  });
});
