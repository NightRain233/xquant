import { describe, expect, it } from "vitest";
import { formatInteger, formatPercent, formatRatio, formatSignalState } from "./formatters";

describe("dashboard formatters", () => {
  it("formats decimal percentages with two decimals by default", () => {
    expect(formatPercent(0.1570815707)).toBe("15.71%");
  });

  it("formats negative drawdowns as percentages", () => {
    expect(formatPercent(-0.135314577)).toBe("-13.53%");
  });

  it("formats ratios with two decimals", () => {
    expect(formatRatio(1.35607555)).toBe("1.36");
  });

  it("formats integer-like values without decimals", () => {
    expect(formatInteger(653.0)).toBe("653");
  });

  it("translates boolean signal state into display text", () => {
    expect(formatSignalState(false)).toBe("Off");
    expect(formatSignalState(true)).toBe("On");
  });
});
