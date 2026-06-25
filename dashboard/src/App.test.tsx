import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("echarts-for-react", () => ({
  default: () => <div data-testid="chart" />
}));

vi.mock("./components/EChartsCore", () => ({
  echarts: {},
  ReactEChartsCore: () => <div data-testid="chart" />
}));

const catalog = {
  defaultStrategyId: "btc-supertrend-satellite",
  strategies: [
    {
      id: "btc-supertrend-satellite",
      name: "BTC SuperTrend Satellite",
      asOfDate: "2026-06-23",
      headline: "建议进入纸面跟踪，暂不直接实盘。",
      summary: "BTC satellite dashboard package.",
      paperTracking: "recommended",
      liveTrading: "not-yet"
    },
    {
      id: "theme-alpha-core80-lvt20-def200-cash",
      name: "Theme Alpha / Core80 LVT20 Def200 Cash",
      asOfDate: "2026-06-24",
      headline: "建议进入纸面跟踪，暂不直接实盘。",
      summary: "Theme Alpha dashboard package.",
      paperTracking: "recommended",
      liveTrading: "not-yet"
    }
  ]
};

const btcSummary = {
  id: "btc-supertrend-satellite",
  name: "BTC SuperTrend Satellite",
  asOfDate: "2026-06-23",
  status: {
    paperTracking: "recommended",
    liveTrading: "not-yet"
  },
  recommendation: {
    headline: "建议进入纸面跟踪，暂不直接实盘。",
    summary: "BTC satellite dashboard package.",
    preferredPaperCaps: ["5%", "7.5%"],
    growthCandidateCap: "10%"
  },
  sourceFiles: ["outputs/q10-live-readiness-stress/research_summary.csv"]
};

const themeAlphaSummary = {
  ...btcSummary,
  id: "theme-alpha-core80-lvt20-def200-cash",
  name: "Theme Alpha / Core80 LVT20 Def200 Cash",
  asOfDate: "2026-06-24",
  sourceFiles: ["outputs/theme-alpha-q8-signal-live-readiness/research_summary.csv"]
};

const reportData = {
  highlightCards: [],
  strategyBrief: {
    plainLanguage: "这是一个以三资产 RiskParity 为核心的组合策略。",
    objective: "观察 BTC 趋势收益。",
    mechanism: ["BTC 只作为小比例卫星仓位。"],
    investorUse: "用于纸面跟踪前的研究展示。",
    watchOut: "如果未来 BTC 趋势收益消失，卫星层可能只增加复杂度。",
    glossary: [{ term: "SuperTrend", definition: "趋势线。" }]
  },
  benchmarkScorecard: {
    title: "评价坐标系",
    summary: "同窗口机会成本坐标。",
    conclusion: "本报告结论基于 2026-06-23 研究快照形成，不随后续 benchmark 刷新自动改变。",
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

const annualReturns = [{ year: "2026", values: { "BTC7.5%ST卫星": 0.12 } }];

const monthlyStats = [
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

const paperData = {
  latestSignal: {
    latestDate: "2026-06-23",
    btcClose: 62533.97,
    btcSupertrendLine: 70231.49,
    btcSupertrendOn: false
  },
  targetWeights: [{ candidate: "BTC5.0%ST卫星", weights: { BTC: 0.05, Cash: 0.4365 } }],
  paperTradingRules: [{ item: "调仓频率", rule: "每 10 个 ETF 交易日检查一次" }],
  riskNotes: [{ title: "BTC 趋势收益可能消失", body: "卫星仓位需要继续观察。" }]
};

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url.endsWith("/data/strategies/index.json")) {
          return {
            ok: true,
            json: async () => catalog
          };
        }

        if (url.endsWith("/strategy.json") && url.includes("theme-alpha-core80-lvt20-def200-cash")) {
          return {
            ok: true,
            json: async () => themeAlphaSummary
          };
        }

        if (url.endsWith("/strategy.json")) {
          return {
            ok: true,
            json: async () => btcSummary
          };
        }

        if (url.endsWith("/report.json")) {
          return {
            ok: true,
            json: async () => reportData
          };
        }

        if (url.endsWith("/nav-series.json")) {
          return {
            ok: true,
            json: async () => navSeries
          };
        }

        if (url.endsWith("/underwater-series.json")) {
          return {
            ok: true,
            json: async () => underwaterSeries
          };
        }

        if (url.endsWith("/annual-returns.json")) {
          return {
            ok: true,
            json: async () => annualReturns
          };
        }

        if (url.endsWith("/monthly-stats.json")) {
          return {
            ok: true,
            json: async () => monthlyStats
          };
        }

        if (url.endsWith("/paper.json")) {
          return {
            ok: true,
            json: async () => paperData
          };
        }

        if (url.includes("theme-alpha-core80-lvt20-def200-cash")) {
          return {
            ok: true,
            json: async () => themeAlphaSummary
          };
        }

        return {
          ok: true,
          json: async () => btcSummary
        };
      })
    );
  });

  it("renders the strategy hub before a strategy is selected", async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("BTC SuperTrend Satellite")).toBeInTheDocument();
    });

    expect(screen.getByText("Theme Alpha / Core80 LVT20 Def200 Cash")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /打开 Theme Alpha/ })).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith("/data/strategies/index.json");
  });

  it("opens a selected strategy shell from a lightweight summary and loads report data on demand", async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /打开 BTC SuperTrend Satellite/ }));

    expect(await screen.findByRole("heading", { name: "BTC SuperTrend Satellite" })).toBeInTheDocument();
    expect(screen.getAllByText("建议纸面跟踪").length).toBeGreaterThan(0);
    expect(screen.getAllByText("暂不实盘").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "研究汇报" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "纸面跟踪" })).toBeInTheDocument();
    expect(await screen.findByText("评价坐标系")).toBeInTheDocument();

    const requestedUrls = vi.mocked(fetch).mock.calls.map(([input]) => String(input));
    expect(requestedUrls).toEqual(
      expect.arrayContaining([
        "/data/strategies/index.json",
        "/data/strategies/btc-supertrend-satellite/strategy.json",
        "/data/strategies/btc-supertrend-satellite/report.json",
        "/data/strategies/btc-supertrend-satellite/nav-series.json",
        "/data/strategies/btc-supertrend-satellite/underwater-series.json",
        "/data/strategies/btc-supertrend-satellite/annual-returns.json",
        "/data/strategies/btc-supertrend-satellite/monthly-stats.json"
      ])
    );
  });

  it("opens the Theme Alpha strategy from the hub", async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /打开 Theme Alpha/ }));

    expect(
      await screen.findByRole("heading", { name: "Theme Alpha / Core80 LVT20 Def200 Cash" })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "研究汇报" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "纸面跟踪" })).toBeInTheDocument();
  });
});
