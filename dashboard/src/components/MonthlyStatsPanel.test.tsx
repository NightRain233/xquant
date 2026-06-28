import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MonthlyStatsPanel } from "./MonthlyStatsPanel";

const rows = [
  {
    id: "Core80-LVT20-Def200-Cash",
    name: "Core80_LVT20_Def200_Cash",
    totalMonths: 60,
    winningMonths: 36,
    losingMonths: 24,
    monthlyWinRate: 0.6,
    averageWinningMonth: 0.025,
    averageLosingMonth: -0.012,
    profitFactor: 2.1,
    bestMonth: 0.08,
    worstMonth: -0.05
  }
];

const recentMonthlyRecords = [
  {
    strategy: "Def200_Cash / BIMONTHLY",
    month: "2026-01",
    monthEndDate: "2026-01-30",
    isPartial: false,
    monthlyReturn: 0.025,
    holdings: { 沪深300ETF: 0.45, 零仓位: 0, 现金: 0.55 }
  },
  {
    strategy: "Def200_Cash / BIMONTHLY",
    month: "2026-02",
    monthEndDate: "2026-02-27",
    isPartial: false,
    monthlyReturn: -0.012,
    holdings: { 沪深300ETF: 0.4, 零仓位: 0, 现金: 0.6 }
  },
  {
    strategy: "Def200_Cash / BIMONTHLY",
    month: "2026-03",
    monthEndDate: "2026-03-31",
    isPartial: false,
    monthlyReturn: 0.01,
    holdings: { 沪深300ETF: 0.5, 零仓位: 0, 现金: 0.5 }
  },
  {
    strategy: "Def200_Cash / BIMONTHLY",
    month: "2026-04",
    monthEndDate: "2026-04-30",
    isPartial: false,
    monthlyReturn: -0.005,
    holdings: { 沪深300ETF: 0.35, 零仓位: 0, 现金: 0.65 }
  },
  {
    strategy: "Def200_Cash / BIMONTHLY",
    month: "2026-05",
    monthEndDate: "2026-05-29",
    isPartial: false,
    monthlyReturn: 0.018,
    holdings: { 沪深300ETF: 0.6, 零仓位: 0, 现金: 0.4 }
  },
  {
    strategy: "Def200_Cash / BIMONTHLY",
    month: "2026-06",
    monthEndDate: "2026-06-26",
    isPartial: true,
    monthlyReturn: -0.007,
    holdings: { 沪深300ETF: 0.52, 零仓位: 0, 现金: 0.48 }
  }
];

describe("MonthlyStatsPanel", () => {
  it("shows recent monthly returns and non-zero month-end holdings", () => {
    render(<MonthlyStatsPanel rows={rows} recentMonthlyRecords={recentMonthlyRecords} />);

    fireEvent.click(screen.getByRole("button", { name: "近期 6 个月" }));

    expect(screen.getAllByText("Def200_Cash / BIMONTHLY").length).toBeGreaterThan(0);
    expect(screen.getByText("截至 6/26")).toBeInTheDocument();
    expect(screen.getByText("2.50%")).toBeInTheDocument();
    expect(screen.getByText("-1.20%")).toBeInTheDocument();
    expect(screen.queryByText("零仓位")).not.toBeInTheDocument();
    expect(screen.getAllByText("沪深300ETF").length).toBeGreaterThan(0);
    expect(screen.getAllByText("现金").length).toBeGreaterThan(0);
    expect(screen.getByText("月末 2026-05-29")).toBeInTheDocument();
  });
});
