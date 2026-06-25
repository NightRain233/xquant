import { existsSync } from "node:fs";
import { mkdir, readFile, rm } from "node:fs/promises";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  buildBtcStrategyPackage,
  buildThemeAlphaStrategyPackage,
  writeAllStrategyPackages,
  writeBtcStrategyPackage
} from "./build-data";

const repoRoot = resolve("..");

describe("BTC strategy data builder", () => {
  it("normalizes Q10 research outputs into a strategy package", async () => {
    const strategy = await buildBtcStrategyPackage(repoRoot);

    expect(strategy.id).toBe("btc-supertrend-satellite");
    expect(strategy.name).toBe("BTC SuperTrend Satellite");
    expect(strategy.status.paperTracking).toBe("recommended");
    expect(strategy.status.liveTrading).toBe("not-yet");
    expect(strategy.recommendation.preferredPaperCaps).toEqual(["5%", "7.5%"]);
    expect(strategy.recommendation.growthCandidateCap).toBe("10%");
    expect(strategy.candidateMetrics).toHaveLength(4);
    expect(strategy.candidateMetrics.map((candidate) => candidate.name)).toEqual([
      "原三资产RiskParity",
      "BTC5%ST卫星",
      "BTC7.5%ST卫星",
      "BTC10%ST卫星"
    ]);
    expect(strategy.latestSignal.btcSupertrendOn).toBe(false);
    expect(strategy.latestSignal.latestDate).toBe("2026-06-23");
    expect(strategy.targetWeights).toHaveLength(3);
    expect(strategy.navSeries.length).toBeGreaterThan(1000);
    expect(strategy.underwaterSeries.length).toBeGreaterThan(1000);
    expect(strategy.annualReturns.length).toBeGreaterThan(8);
    expect(strategy.monthlyStats).toHaveLength(4);
    expect(strategy.recommendation.headline).toContain("建议进入纸面跟踪");
    expect(strategy.strategyBrief?.plainLanguage).toContain("三资产 RiskParity");
    expect(strategy.strategyBrief?.glossary.map((item) => item.term)).toContain("SuperTrend");
    expect(strategy.benchmarkScorecard?.title).toBe("评价坐标系");
    expect(strategy.benchmarkScorecard?.period).toEqual({
      startDate: "2016-06-21",
      endDate: "2026-06-23"
    });
    expect(strategy.benchmarkScorecard?.rows.map((row) => row.role)).toContain("内部基准");
    expect(strategy.benchmarkScorecard?.rows.map((row) => row.role)).toContain("主动权益基金参考线");
    expect(strategy.benchmarkScorecard?.rows.map((row) => row.name)).toEqual(
      expect.arrayContaining(["中证主动偏股型基金指数", "沪深300全收益指数", "纳斯达克100全收益指数"])
    );
    const btcActiveEquityReference = strategy.benchmarkScorecard?.rows.find(
      (row) => row.name === "中证主动偏股型基金指数"
    );
    expect(btcActiveEquityReference?.annualReturn).toBeCloseTo(0.083);
    expect(btcActiveEquityReference?.note).toContain("2016-06-21 至 2026-06-23");
    const btcCsi300Reference = strategy.benchmarkScorecard?.rows.find((row) => row.name === "沪深300全收益指数");
    expect(btcCsi300Reference?.note).toContain("2016-06-21 至 2026-06-23");
    expect(btcCsi300Reference?.note).toContain("全收益口径");
    const btcNasdaqReference = strategy.benchmarkScorecard?.rows.find((row) => row.name === "纳斯达克100全收益指数");
    expect(btcNasdaqReference?.note).toContain("2016-06-21 至 2026-06-23");
    expect(btcNasdaqReference?.note).toContain("全收益美元口径");
    expect(strategy.benchmarkScorecard?.conclusion).toContain("跑赢主动偏股和沪深300全收益");
    expect(strategy.benchmarkScorecard?.conclusion).toContain("没有跑赢纳指100全收益");
    expect(strategy.benchmarkScorecard?.conclusion).toContain("回撤明显更浅");
    expect(strategy.riskNotes[0].title).toBe("BTC 趋势收益可能消失");
    expect(strategy.stressSummaries.map((summary) => summary.id)).toContain("implementation");
  });

  it("writes the strategy JSON to the requested output directory", async () => {
    const outputRoot = resolve("tmp-test-data");
    await rm(outputRoot, { force: true, recursive: true });
    await mkdir(outputRoot, { recursive: true });

    const outputPath = await writeBtcStrategyPackage(repoRoot, outputRoot);

    expect(outputPath.endsWith("strategies/btc-supertrend-satellite/strategy.json")).toBe(true);
    expect(existsSync(outputPath)).toBe(true);

    await rm(outputRoot, { force: true, recursive: true });
  });
});

describe("Theme Alpha strategy data builder", () => {
  it("normalizes Q8 and Q12 research outputs into a strategy package", async () => {
    const strategy = await buildThemeAlphaStrategyPackage(repoRoot);

    expect(strategy.id).toBe("theme-alpha-core80-lvt20-def200-cash");
    expect(strategy.name).toBe("Theme Alpha / Core80 LVT20 Def200 Cash");
    expect(strategy.asOfDate).toBe("2026-06-24");
    expect(strategy.status.paperTracking).toBe("recommended");
    expect(strategy.status.liveTrading).toBe("not-yet");
    expect(strategy.recommendation.preferredPaperCaps).toEqual(["Def200_Cash / BIMONTHLY"]);
    expect(strategy.recommendation.growthCandidateCap).toBe("Core60_LVT40_Def200_Cash");
    expect(strategy.strategyBrief?.plainLanguage).toContain("三资产核心仓位");
    expect(strategy.strategyBrief?.mechanism).toEqual(
      expect.arrayContaining(["20% 卫星仓位在扩展主题 ETF 池内做低波趋势选择。"])
    );
    expect(strategy.strategyBrief?.methodology?.map((item) => item.value).join(" ")).toContain("MA60");
    expect(strategy.strategyBrief?.methodology?.map((item) => item.value).join(" ")).toContain("63 日动量");
    expect(strategy.strategyBrief?.methodology?.map((item) => item.value).join(" ")).toContain("60 日波动率最低的 3 个");
    expect(strategy.strategyBrief?.glossary.map((item) => item.term)).toEqual(
      expect.arrayContaining(["Core80", "LVT20", "Def200 Cash", "BIMONTHLY"])
    );
    expect(strategy.benchmarkScorecard?.rows.map((row) => row.name)).toEqual(
      expect.arrayContaining([
        "Original_RiskParity_3Asset",
        "中证主动偏股型基金指数",
        "沪深300全收益指数",
        "纳斯达克100全收益指数"
      ])
    );
    expect(strategy.benchmarkScorecard?.period).toEqual({
      startDate: "2021-01-04",
      endDate: "2026-06-23"
    });
    const activeEquityReference = strategy.benchmarkScorecard?.rows.find(
      (row) => row.name === "中证主动偏股型基金指数"
    );
    expect(activeEquityReference?.annualReturn).toBeCloseTo(0.0158);
    expect(activeEquityReference?.note).toContain("2021-01-04 至 2026-06-23");
    expect(activeEquityReference?.note).toContain("同周期");
    const csi300Reference = strategy.benchmarkScorecard?.rows.find((row) => row.name === "沪深300全收益指数");
    expect(csi300Reference?.note).toContain("2021-01-04 至 2026-06-23");
    expect(csi300Reference?.note).toContain("全收益口径");
    const nasdaqReference = strategy.benchmarkScorecard?.rows.find((row) => row.name === "纳斯达克100全收益指数");
    expect(nasdaqReference?.note).toContain("2021-01-04 至 2026-06-23");
    expect(nasdaqReference?.note).toContain("全收益美元口径");
    expect(strategy.benchmarkScorecard?.conclusion).toContain("Core80_LVT20_Def200_Cash");
    expect(strategy.benchmarkScorecard?.conclusion).toContain("明显跑赢主动偏股和沪深300全收益");
    expect(strategy.benchmarkScorecard?.conclusion).toContain("年化低于纳指100全收益");
    expect(strategy.benchmarkScorecard?.conclusion).toContain("Calmar");
    expect(strategy.candidateMetrics.map((candidate) => candidate.name)).toEqual([
      "Original_RiskParity_3Asset",
      "Expanded_LVT_100",
      "Core80_LVT20_Def200_Cash",
      "Core60_LVT40_Def200_Cash",
      "Core80_LVT20_STEntry_Def200_Cash",
      "Core80_LVT20_STHalf_Def200_Cash"
    ]);
    expect(strategy.navSeries.length).toBeGreaterThan(1000);
    expect(Object.keys(strategy.navSeries[0].values)).toContain("Def200 Bimonthly");
    expect(strategy.underwaterSeries.length).toBe(strategy.navSeries.length);
    expect(strategy.annualReturns.length).toBeGreaterThanOrEqual(6);
    expect(strategy.monthlyStats).toHaveLength(6);
    expect(strategy.targetWeights.find((row) => row.candidate === "Def200_Cash / BIMONTHLY")?.weights["现金"]).toBe(0);
    expect(strategy.latestSignal.title).toBe("Theme Alpha 信号状态");
    const signalRows = strategy.latestSignal.rows ?? [];
    expect(signalRows.map((row) => row.label)).toContain("调仓频率");
    expect(strategy.stressSummaries.map((summary) => summary.id)).toEqual(
      expect.arrayContaining(["schedule", "friction", "liquidity"])
    );
    expect(strategy.sourceFiles).toContain("outputs/theme-alpha-q8-signal-live-readiness/research_summary.csv");
    expect(strategy.sourceFiles).toContain("outputs/theme-alpha-q12-long-sample-proxy-validation/summary_real_etf.csv");
  });

  it("writes both strategy packages and the catalog", async () => {
    const outputRoot = resolve("tmp-test-data");
    await rm(outputRoot, { force: true, recursive: true });
    await mkdir(outputRoot, { recursive: true });

    const outputPaths = await writeAllStrategyPackages(repoRoot, outputRoot);
    const catalogPath = resolve(outputRoot, "strategies", "index.json");
    const catalog = JSON.parse(await readFile(catalogPath, "utf8")) as {
      defaultStrategyId: string;
      strategies: Array<{ id: string; name: string }>;
    };

    expect(outputPaths).toContain(resolve(outputRoot, "strategies", "btc-supertrend-satellite", "strategy.json"));
    expect(outputPaths).toContain(
      resolve(outputRoot, "strategies", "theme-alpha-core80-lvt20-def200-cash", "strategy.json")
    );
    expect(existsSync(catalogPath)).toBe(true);
    expect(catalog.defaultStrategyId).toBe("btc-supertrend-satellite");
    expect(catalog.strategies.map((strategy) => strategy.id)).toEqual([
      "btc-supertrend-satellite",
      "theme-alpha-core80-lvt20-def200-cash"
    ]);

    await rm(outputRoot, { force: true, recursive: true });
  });
});
