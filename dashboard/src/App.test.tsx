import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import strategy from "../public/data/strategies/btc-supertrend-satellite/strategy.json";
import App from "./App";

vi.mock("echarts-for-react", () => ({
  default: () => <div data-testid="chart" />
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

const themeAlphaStrategy = {
  ...strategy,
  id: "theme-alpha-core80-lvt20-def200-cash",
  name: "Theme Alpha / Core80 LVT20 Def200 Cash",
  asOfDate: "2026-06-24",
  latestSignal: {
    title: "Theme Alpha 信号状态",
    stateLabel: "Def200 Cash 未触发",
    stateTone: "positive",
    rows: [
      { label: "调仓频率", value: "每月 10 日和 25 日附近" },
      { label: "执行口径", value: "收盘信号，下一交易日执行" }
    ]
  }
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

        if (url.includes("theme-alpha-core80-lvt20-def200-cash")) {
          return {
            ok: true,
            json: async () => themeAlphaStrategy
          };
        }

        return {
          ok: true,
          json: async () => strategy
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
  });

  it("opens a selected strategy shell and decision state", async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /打开 BTC SuperTrend Satellite/ }));

    expect(await screen.findByRole("heading", { name: "BTC SuperTrend Satellite" })).toBeInTheDocument();
    expect(screen.getAllByText("建议纸面跟踪").length).toBeGreaterThan(0);
    expect(screen.getAllByText("暂不实盘").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "研究汇报" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "纸面跟踪" })).toBeInTheDocument();
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
