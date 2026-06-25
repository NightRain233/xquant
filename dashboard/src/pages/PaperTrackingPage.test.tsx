import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import strategy from "../../public/data/strategies/btc-supertrend-satellite/strategy.json";
import type { StrategyPackage } from "../data/types";
import { PaperTrackingPage } from "./PaperTrackingPage";

describe("PaperTrackingPage", () => {
  it("renders latest signal, target weights, and paper trading rules", () => {
    render(<PaperTrackingPage strategy={strategy as StrategyPackage} />);

    expect(screen.getByText("2026-06-23")).toBeInTheDocument();
    expect(screen.getByText("Off")).toBeInTheDocument();
    expect(screen.getByText("62,533.97")).toBeInTheDocument();
    expect(screen.getByText("70,231.49")).toBeInTheDocument();
    expect(screen.getByText("BTC5.0%ST卫星")).toBeInTheDocument();
    expect(screen.getByText("43.65%")).toBeInTheDocument();
    expect(screen.getByText("每 10 个 ETF 交易日检查一次")).toBeInTheDocument();
    expect(screen.getByText("不会自动实时更新")).toBeInTheDocument();
    expect(screen.getByText("BTC 趋势收益可能消失")).toBeInTheDocument();
  });
});
