import { existsSync } from "node:fs";
import { mkdir, rm } from "node:fs/promises";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { buildBtcStrategyPackage, writeBtcStrategyPackage } from "./build-data";

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
