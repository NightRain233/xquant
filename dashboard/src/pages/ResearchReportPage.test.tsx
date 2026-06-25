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

    expect(screen.getByText("策略说明")).toBeInTheDocument();
    expect(screen.getByText("评价坐标系")).toBeInTheDocument();
    expect(screen.getByText("回测窗口 2016-06-21 - 2026-06-23")).toBeInTheDocument();
    expect(screen.getByText("中证主动偏股型基金指数")).toBeInTheDocument();
    expect(screen.getByText("沪深300全收益指数")).toBeInTheDocument();
    expect(screen.getByText("纳斯达克100全收益指数")).toBeInTheDocument();
    expect(screen.getAllByText("8.30%").length).toBeGreaterThan(0);
    expect(screen.getByText("结论")).toBeInTheDocument();
    expect(screen.getByText("核心判断")).toBeInTheDocument();
    expect(screen.getByText("关键理由")).toBeInTheDocument();
    expect(screen.getByText("SuperTrend")).toBeInTheDocument();
    expect(screen.getByText("候选对比")).toBeInTheDocument();
    expect(screen.getAllByText("BTC7.5%ST卫星").length).toBeGreaterThan(0);
    expect(screen.getAllByText("19.49%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("-12.75%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("1.67").length).toBeGreaterThan(0);
    expect(screen.getAllByText("1.53").length).toBeGreaterThan(0);
    expect(screen.getByText("Execution friction stress")).toBeInTheDocument();
    expect(screen.getByText("年度收益")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "热力图" })).toBeInTheDocument();
    expect(screen.getByText("年度收益热力图")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "表格" })[0]);
    expect(screen.getByText("年份")).toBeInTheDocument();

    expect(screen.getByText("月度统计")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "体验概览" })).toBeInTheDocument();
    expect(screen.getByText("月度体验概览")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "表格" })[1]);
    expect(screen.getAllByText("盈亏因子").length).toBeGreaterThan(0);
    expect(screen.getAllByText("BTC7.5%ST卫星").length).toBeGreaterThan(1);
  });
});
