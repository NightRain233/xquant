import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import strategy from "../public/data/strategies/btc-supertrend-satellite/strategy.json";
import App from "./App";

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => strategy
      }))
    );
  });

  it("renders the strategy shell and decision state", async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("BTC SuperTrend Satellite")).toBeInTheDocument();
    });

    expect(screen.getByText("建议纸面跟踪")).toBeInTheDocument();
    expect(screen.getByText("暂不实盘")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "研究汇报" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "纸面跟踪" })).toBeInTheDocument();
  });
});
