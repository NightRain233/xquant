import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PaperTrackingPage } from "./PaperTrackingPage";

const paperData = {
  latestSignal: {
    latestDate: "2026-06-23",
    btcClose: 62533.97,
    btcSupertrendLine: 70231.49,
    btcSupertrendOn: false
  },
  targetWeights: [
    {
      candidate: "BTC5.0%ST卫星",
      weights: {
        BTC: 0.05,
        Cash: 0.4365
      }
    }
  ],
  paperTradingRules: [
    {
      item: "调仓频率",
      rule: "每 10 个 ETF 交易日检查一次"
    },
    {
      item: "执行口径",
      rule: "不会自动实时更新"
    }
  ],
  riskNotes: [
    {
      title: "BTC 趋势收益可能消失",
      body: "卫星仓位需要继续观察。"
    }
  ]
};

describe("PaperTrackingPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url.endsWith("/paper.json")) {
          return { ok: true, json: async () => paperData };
        }

        return { ok: false, status: 404, json: async () => ({}) };
      })
    );
  });

  it("loads only paper tracking data for the selected strategy", async () => {
    render(<PaperTrackingPage strategyId="btc-supertrend-satellite" />);

    expect(await screen.findByText("2026-06-23")).toBeInTheDocument();
    expect(screen.getByText("Off")).toBeInTheDocument();
    expect(screen.getByText("62,533.97")).toBeInTheDocument();
    expect(screen.getByText("70,231.49")).toBeInTheDocument();
    expect(screen.getByText("BTC5.0%ST卫星")).toBeInTheDocument();
    expect(screen.getByText("43.65%")).toBeInTheDocument();
    expect(screen.getByText("每 10 个 ETF 交易日检查一次")).toBeInTheDocument();
    expect(screen.getAllByText("不会自动实时更新").length).toBeGreaterThan(0);
    expect(screen.getByText("BTC 趋势收益可能消失")).toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.map(([input]) => String(input))).toEqual([
      "/data/strategies/btc-supertrend-satellite/paper.json"
    ]);
  });
});
