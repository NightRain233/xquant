import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AnnualReturnRow,
  MonthlyStat,
  RecentMonthlyRecord,
  StrategyReportData
} from "../data/types";
import { ResearchReportPage } from "./ResearchReportPage";

vi.mock("echarts-for-react", () => ({
  default: () => <div data-testid="chart" />
}));

vi.mock("../components/EChartsCore", () => ({
  echarts: {},
  ReactEChartsCore: () => <div data-testid="chart" />
}));

const reportData: StrategyReportData = {
  highlightCards: [],
  strategyBrief: {
    plainLanguage: "这是一个以三资产 RiskParity 为核心、用 BTC SuperTrend 趋势信号做小比例卫星增强的组合策略。",
    objective: "观察 BTC 趋势收益是否能改善核心组合。",
    mechanism: ["BTC 只作为 5% / 7.5% / 10% 上限的卫星仓位。"],
    investorUse: "适合用来观察小比例 BTC 趋势增强是否值得进入纸面跟踪。",
    watchOut: "如果未来 BTC 趋势收益消失，卫星层可能只增加复杂度和执行摩擦。",
    glossary: [{ term: "SuperTrend", definition: "趋势线。" }]
  },
  benchmarkScorecard: {
    title: "评价坐标系",
    summary: "同窗口机会成本坐标。",
    conclusion:
      "本报告结论基于 2026-06-23 研究快照形成，不随后续 benchmark 刷新自动改变。若判断发生变化，应生成新的研究快照。",
    period: { startDate: "2016-06-21", endDate: "2026-06-23" },
    rows: [
      {
        role: "主动权益基金参考线",
        name: "中证主动偏股型基金指数",
        annualReturn: 0.083,
        maxDrawdown: -0.2,
        sharpe: 0.8,
        calmar: 0.4,
        note: "2016-06-21 至 2026-06-23 同周期计算。",
        verdict: "同周期参考"
      },
      {
        role: "宽基指数参考线",
        name: "沪深300全收益指数",
        annualReturn: 0.03,
        maxDrawdown: -0.3,
        sharpe: 0.4,
        calmar: 0.1,
        note: "全收益口径。",
        verdict: "A股Beta参考"
      },
      {
        role: "海外成长参考线",
        name: "纳斯达克100全收益指数",
        annualReturn: 0.12,
        maxDrawdown: -0.35,
        sharpe: 0.7,
        calmar: 0.34,
        note: "全收益美元口径。",
        verdict: "海外成长参考"
      }
    ]
  },
  candidateMetrics: [
    {
      id: "btc-75",
      name: "BTC7.5%ST卫星",
      annualReturn: 0.1949,
      annualVolatility: 0.11,
      maxDrawdown: -0.1275,
      sharpe: 1.67,
      calmar: 1.53
    }
  ],
  candidateComparisonGroups: {
    primary: ["btc-75"],
    research: []
  },
  stressSummaries: [{ id: "implementation", title: "Execution friction stress", rows: [{ scenario: "base" }] }]
};

const navSeries = [
  { date: "2026-06-22", values: { "BTC7.5%ST卫星": 1 } },
  { date: "2026-06-23", values: { "BTC7.5%ST卫星": 1.01 } }
];

const underwaterSeries = [
  { date: "2026-06-22", values: { "BTC7.5%ST卫星": 0 } },
  { date: "2026-06-23", values: { "BTC7.5%ST卫星": -0.01 } }
];

const annualReturns: AnnualReturnRow[] = [{ year: "2026", values: { "BTC7.5%ST卫星": 0.12 } }];

const monthlyStats: MonthlyStat[] = [
  {
    id: "btc-75",
    name: "BTC7.5%ST卫星",
    totalMonths: 2,
    winningMonths: 1,
    losingMonths: 1,
    monthlyWinRate: 0.5,
    averageWinningMonth: 0.03,
    averageLosingMonth: -0.01,
    profitFactor: 3,
    bestMonth: 0.03,
    worstMonth: -0.01
  }
];

const recentMonthlyRecords: RecentMonthlyRecord[] = [
  {
    strategy: "BTC7.5%ST卫星",
    month: "2026-06",
    monthEndDate: "2026-06-26",
    isPartial: true,
    monthlyReturn: 0.01,
    holdings: { BTC: 0, 现金: 1 }
  }
];

const themeCandidateNames = {
  baseline: "Original_RiskParity_3Asset",
  current: "Core80_LVT20_Def200_Cash",
  boundary: "Expanded_LVT_100",
  core60: "Core60_LVT40_Def200_Cash",
  entry: "Core80_LVT20_STEntry_Def200_Cash",
  half: "Core80_LVT20_STHalf_Def200_Cash"
};

const themeCandidateMetrics = Object.values(themeCandidateNames).map((name, index) => ({
  id: name.replace(/_/g, "-"),
  name,
  annualReturn: 0.1 + index / 100,
  annualVolatility: 0.12,
  maxDrawdown: -0.1,
  sharpe: 1,
  calmar: 1
}));

const themeReportData: StrategyReportData = {
  ...reportData,
  candidateMetrics: themeCandidateMetrics,
  candidateComparisonGroups: {
    primary: [
      "Original-RiskParity-3Asset",
      "Core80-LVT20-Def200-Cash",
      "Expanded-LVT-100"
    ],
    research: [
      "Core60-LVT40-Def200-Cash",
      "Core80-LVT20-STEntry-Def200-Cash",
      "Core80-LVT20-STHalf-Def200-Cash"
    ]
  }
};

const themeAnnualReturns: AnnualReturnRow[] = [
  {
    year: "2026",
    values: Object.fromEntries(Object.values(themeCandidateNames).map((name, index) => [name, 0.1 + index / 100]))
  }
];

const themeMonthlyStats: MonthlyStat[] = themeCandidateMetrics.map((candidate) => ({
  id: candidate.id,
  name: candidate.name,
  totalMonths: 60,
  winningMonths: 36,
  losingMonths: 24,
  monthlyWinRate: 0.6,
  averageWinningMonth: 0.02,
  averageLosingMonth: -0.01,
  profitFactor: 2,
  bestMonth: 0.08,
  worstMonth: -0.05
}));

function stubReportFetch(
  report = reportData,
  annual = annualReturns,
  monthly = monthlyStats,
  recent = recentMonthlyRecords
) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/report.json")) {
        return { ok: true, json: async () => report };
      }

      if (url.endsWith("/nav-series.json")) {
        return { ok: true, json: async () => navSeries };
      }

      if (url.endsWith("/underwater-series.json")) {
        return { ok: true, json: async () => underwaterSeries };
      }

      if (url.endsWith("/annual-returns.json")) {
        return { ok: true, json: async () => annual };
      }

      if (url.endsWith("/monthly-stats.json")) {
        return { ok: true, json: async () => monthly };
      }

      if (url.endsWith("/recent-monthly-records.json")) {
        return { ok: true, json: async () => recent };
      }

      return { ok: false, status: 404, json: async () => ({}) };
    })
  );
}

describe("ResearchReportPage", () => {
  beforeEach(() => {
    stubReportFetch();
  });

  it("loads report and chart data only when the research report page is entered", async () => {
    render(<ResearchReportPage strategyId="btc-supertrend-satellite" />);

    expect(await screen.findByText("策略说明")).toBeInTheDocument();
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
    fireEvent.click(screen.getByRole("button", { name: "汇总表" }));
    expect(screen.getAllByText("盈亏因子").length).toBeGreaterThan(0);
    expect(screen.getAllByText("BTC7.5%ST卫星").length).toBeGreaterThan(1);

    const requestedUrls = vi.mocked(fetch).mock.calls.map(([input]) => String(input));
    expect(requestedUrls).toEqual([
      "/data/strategies/btc-supertrend-satellite/report.json",
      "/data/strategies/btc-supertrend-satellite/nav-series.json",
      "/data/strategies/btc-supertrend-satellite/underwater-series.json",
      "/data/strategies/btc-supertrend-satellite/annual-returns.json",
      "/data/strategies/btc-supertrend-satellite/monthly-stats.json",
      "/data/strategies/btc-supertrend-satellite/recent-monthly-records.json"
    ]);
  });

  it("keeps candidate, annual, and monthly comparisons in one Theme Alpha scope", async () => {
    stubReportFetch(themeReportData, themeAnnualReturns, themeMonthlyStats, []);
    render(<ResearchReportPage strategyId="theme-alpha-core80-lvt20-def200-cash" />);

    expect(await screen.findByRole("button", { name: "核心对比" })).toBeInTheDocument();
    expect(screen.queryByText(themeCandidateNames.core60)).not.toBeInTheDocument();
    expect(screen.queryByText(themeCandidateNames.entry)).not.toBeInTheDocument();
    expect(screen.queryByText(themeCandidateNames.half)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "研究候选" }));

    const candidateSection = screen.getByRole("heading", { name: "候选对比" }).closest("section");
    const annualSection = screen.getByRole("heading", { name: "年度收益" }).closest("section");
    const monthlySection = screen.getByRole("heading", { name: "月度统计" }).closest("section");
    expect(candidateSection).not.toBeNull();
    expect(annualSection).not.toBeNull();
    expect(monthlySection).not.toBeNull();

    for (const name of [
      themeCandidateNames.current,
      themeCandidateNames.core60,
      themeCandidateNames.entry,
      themeCandidateNames.half
    ]) {
      expect(within(candidateSection!).getByText(name)).toBeInTheDocument();
      expect(within(annualSection!).getByText(name)).toBeInTheDocument();
      expect(within(monthlySection!).getByText(name)).toBeInTheDocument();
    }

    expect(screen.queryByText(themeCandidateNames.baseline)).not.toBeInTheDocument();
    expect(screen.queryByText(themeCandidateNames.boundary)).not.toBeInTheDocument();
  });
});
