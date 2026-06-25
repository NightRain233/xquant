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
    expect(strategy.benchmarkScorecard?.conclusion).toContain("基于 2026-06-23 研究快照");
    expect(strategy.benchmarkScorecard?.conclusion).toContain("BTC7.5%ST卫星年化 19.49%");
    expect(strategy.benchmarkScorecard?.conclusion).toContain("没有跑赢纳指100全收益 22.01%");
    expect(strategy.benchmarkScorecard?.conclusion).toContain("默认仍应先纸面跟踪 5% / 7.5%");
    expect(strategy.riskNotes[0].title).toBe("BTC 趋势收益可能消失");
    expect(strategy.stressSummaries.map((summary) => summary.id)).toContain("implementation");
  });

  it("writes the strategy JSON to the requested output directory", async () => {
    const outputRoot = resolve("tmp-test-data");
    await rm(outputRoot, { force: true, recursive: true });
    await mkdir(outputRoot, { recursive: true });

    const outputPath = await writeBtcStrategyPackage(repoRoot, outputRoot);
    const strategyJson = JSON.parse(await readFile(outputPath, "utf8")) as Record<string, unknown>;
    const reportPath = resolve(outputRoot, "strategies", "btc-supertrend-satellite", "report.json");
    const paperPath = resolve(outputRoot, "strategies", "btc-supertrend-satellite", "paper.json");
    const navPath = resolve(outputRoot, "strategies", "btc-supertrend-satellite", "nav-series.json");
    const underwaterPath = resolve(outputRoot, "strategies", "btc-supertrend-satellite", "underwater-series.json");
    const annualPath = resolve(outputRoot, "strategies", "btc-supertrend-satellite", "annual-returns.json");
    const monthlyPath = resolve(outputRoot, "strategies", "btc-supertrend-satellite", "monthly-stats.json");

    expect(outputPath.endsWith("strategies/btc-supertrend-satellite/strategy.json")).toBe(true);
    expect(existsSync(outputPath)).toBe(true);
    expect(strategyJson.navSeries).toBeUndefined();
    expect(strategyJson.underwaterSeries).toBeUndefined();
    expect(strategyJson.annualReturns).toBeUndefined();
    expect(strategyJson.monthlyStats).toBeUndefined();
    expect(strategyJson.latestSignal).toBeUndefined();
    expect(strategyJson.targetWeights).toBeUndefined();
    expect(strategyJson.recommendation).toMatchObject({
      headline: "建议进入纸面跟踪，暂不直接实盘。"
    });
    expect(existsSync(reportPath)).toBe(true);
    expect(existsSync(paperPath)).toBe(true);
    expect(existsSync(navPath)).toBe(true);
    expect(existsSync(underwaterPath)).toBe(true);
    expect(existsSync(annualPath)).toBe(true);
    expect(existsSync(monthlyPath)).toBe(true);

    const reportJson = JSON.parse(await readFile(reportPath, "utf8")) as Record<string, unknown>;
    const paperJson = JSON.parse(await readFile(paperPath, "utf8")) as Record<string, unknown>;
    const navJson = JSON.parse(await readFile(navPath, "utf8")) as unknown[];
    expect(reportJson.benchmarkScorecard).toBeDefined();
    expect(reportJson.candidateMetrics).toBeDefined();
    expect(paperJson.latestSignal).toBeDefined();
    expect(paperJson.riskNotes).toBeDefined();
    expect(navJson.length).toBeGreaterThan(1000);

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
    expect(strategy.benchmarkScorecard?.conclusion).toContain("基于 2026-06-24 研究快照");
    expect(strategy.benchmarkScorecard?.conclusion).toContain("Core80_LVT20_Def200_Cash 年化 14.48%");
    expect(strategy.benchmarkScorecard?.conclusion).toContain("年化低于纳指100全收益 17.55%");
    expect(strategy.benchmarkScorecard?.conclusion).toContain("纳指100全收益约 -35.04% 回撤");
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
    expect(strategy.sourceFiles).not.toContain("docs/notes/theme-alpha-q8-signal-live-readiness-review.md");
    expect(strategy.sourceFiles).not.toContain("outputs/theme-alpha-q12-long-sample-proxy-validation/latest_weights_real_etf.csv");
  });

  it("writes both strategy packages and the catalog", async () => {
    const outputRoot = resolve("tmp-test-data");
    await rm(outputRoot, { force: true, recursive: true });
    await mkdir(outputRoot, { recursive: true });

    const outputPaths = await writeAllStrategyPackages(repoRoot, outputRoot);
    const catalogPath = resolve(outputRoot, "strategies", "index.json");
    const btcStrategyPath = resolve(outputRoot, "strategies", "btc-supertrend-satellite", "strategy.json");
    const themeAlphaStrategyPath = resolve(
      outputRoot,
      "strategies",
      "theme-alpha-core80-lvt20-def200-cash",
      "strategy.json"
    );
    const themeAlphaNavPath = resolve(
      outputRoot,
      "strategies",
      "theme-alpha-core80-lvt20-def200-cash",
      "nav-series.json"
    );
    const catalog = JSON.parse(await readFile(catalogPath, "utf8")) as {
      defaultStrategyId: string;
      strategies: Array<{ id: string; name: string }>;
    };
    const btcStrategyJson = JSON.parse(await readFile(btcStrategyPath, "utf8")) as Record<string, unknown>;
    const themeAlphaStrategyJson = JSON.parse(await readFile(themeAlphaStrategyPath, "utf8")) as Record<string, unknown>;

    expect(outputPaths).toContain(btcStrategyPath);
    expect(outputPaths).toContain(themeAlphaStrategyPath);
    expect(outputPaths).toContain(themeAlphaNavPath);
    expect(existsSync(catalogPath)).toBe(true);
    expect(catalog.defaultStrategyId).toBe("btc-supertrend-satellite");
    expect(catalog.strategies.map((strategy) => strategy.id)).toEqual([
      "btc-supertrend-satellite",
      "theme-alpha-core80-lvt20-def200-cash"
    ]);
    expect(btcStrategyJson.navSeries).toBeUndefined();
    expect(themeAlphaStrategyJson.navSeries).toBeUndefined();
    expect(themeAlphaStrategyJson.sourceFiles).toContain(
      "outputs/theme-alpha-q8-signal-live-readiness/research_summary.csv"
    );

    await rm(outputRoot, { force: true, recursive: true });
  });
});
