import { describe, expect, it } from "vitest";
import { basisLabel, compactMoney, formatByUnit, signedMoney } from "./format";

describe("compactMoney", () => {
  it("uses long pt-BR scale words for prose", () => {
    expect(compactMoney(8_400_000)).toBe("R$ 8,4 milhões");
    expect(compactMoney(1_040_000)).toBe("R$ 1,0 milhão");
    expect(compactMoney(960_000_000)).toBe("R$ 960 milhões");
    expect(compactMoney(919_272)).toBe("R$ 919 mil");
    expect(compactMoney(-1_230_000)).toBe("-R$ 1,2 milhão");
  });

  it("uses short scale words for charts and tiles", () => {
    expect(compactMoney(8_400_000, "short")).toBe("R$ 8,4 mi");
    expect(compactMoney(2_400_000_000, "short")).toBe("R$ 2,4 bi");
    expect(compactMoney(919_272, "short")).toBe("R$ 919 mil");
    expect(compactMoney(512, "short")).toBe("R$ 512");
  });
});

describe("signedMoney", () => {
  it("always shows the sign of a change", () => {
    expect(signedMoney(3_300_000)).toBe("+R$ 3,3 mi");
    expect(signedMoney(-2_400_000)).toBe("-R$ 2,4 mi");
    expect(signedMoney(0)).toBe("R$ 0");
  });
});

describe("formatByUnit", () => {
  it("formats each catalog unit", () => {
    expect(formatByUnit("currency", 10_300_000)).toBe("R$ 10,3 mi");
    expect(formatByUnit("ratio", 0.588)).toBe("58,8%");
    expect(formatByUnit("multiplier", 1.333)).toBe("1,33x");
    expect(formatByUnit("binary", 0.231)).toBe("23,1%");
    expect(formatByUnit(null, 3.14159)).toBe("3,14");
  });
});

describe("basisLabel", () => {
  it("translates the persisted valuation basis", () => {
    expect(basisLabel("DCF equity value (signed)")).toBe("Equity via DCF · inclui valores negativos");
    expect(basisLabel("Something new")).toBe("Something new");
  });
});
