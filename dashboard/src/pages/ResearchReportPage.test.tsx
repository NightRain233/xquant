import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import strategy from "../../public/data/strategies/btc-supertrend-satellite/strategy.json";
import type { StrategyPackage } from "../data/types";
import { ResearchReportPage } from "./ResearchReportPage";

vi.mock("echarts-for-react", () => ({
  default: () => <div data-testid="chart" />
}));

describe("ResearchReportPage", () => {
  it("renders candidate metrics and implementation stress evidence", () => {
    render(<ResearchReportPage strategy={strategy as StrategyPackage} />);

    expect(screen.getByText("候选对比")).toBeInTheDocument();
    expect(screen.getAllByText("BTC7.5%ST卫星").length).toBeGreaterThan(0);
    expect(screen.getByText("19.49%")).toBeInTheDocument();
    expect(screen.getByText("-12.75%")).toBeInTheDocument();
    expect(screen.getByText("1.67")).toBeInTheDocument();
    expect(screen.getByText("1.53")).toBeInTheDocument();
    expect(screen.getAllByText("100%").length).toBeGreaterThan(0);
    expect(screen.getByText("年度收益")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "热力图" })).toBeInTheDocument();
    expect(screen.getByText("年度收益热力图")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "表格" })[0]);
    expect(screen.getByText("年份")).toBeInTheDocument();

    expect(screen.getByText("月度统计")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "体验概览" })).toBeInTheDocument();
    expect(screen.getByText("月度体验概览")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "表格" })[1]);
    expect(screen.getByText("盈亏因子")).toBeInTheDocument();
    expect(screen.getAllByText("BTC7.5%ST卫星").length).toBeGreaterThan(1);
  });
});
