import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import Papa from "papaparse";
import type {
  AnnualReturnRow,
  CandidateMetric,
  LatestSignal,
  MonthlyStat,
  PaperTradingRule,
  BenchmarkScorecardRow,
  StrategyCatalog,
  StrategyCatalogItem,
  StrategyChartData,
  StrategyPackage,
  StrategyPaperData,
  StrategyReportData,
  StrategySummaryPackage,
  StressSummary,
  TargetWeightRow,
  TimeSeriesPoint
} from "../src/data/types";

type CsvRow = Record<string, string>;

const BTC_OUTPUT_DIR = "outputs/q10-live-readiness-stress";
const BTC_STRATEGY_ID = "btc-supertrend-satellite";
const THEME_ALPHA_Q8_DIR = "outputs/theme-alpha-q8-signal-live-readiness";
const THEME_ALPHA_Q12_DIR = "outputs/theme-alpha-q12-long-sample-proxy-validation";
const THEME_ALPHA_STRATEGY_ID = "theme-alpha-core80-lvt20-def200-cash";
const ACTIVE_EQUITY_BENCHMARK_FILE = "outputs/benchmarks/csi932055_active_partial_equity_fund.csv";
const CSI300_BENCHMARK_FILE = "outputs/benchmarks/csi_h00300_csi300_total_return.csv";
const NASDAQ100_BENCHMARK_FILE = "outputs/benchmarks/fred_nasdaqxndx_nasdaq100_total_return.csv";

const btcSourceFiles = [
  ACTIVE_EQUITY_BENCHMARK_FILE,
  CSI300_BENCHMARK_FILE,
  NASDAQ100_BENCHMARK_FILE,
  `${BTC_OUTPUT_DIR}/research_summary.csv`,
  `${BTC_OUTPUT_DIR}/base_candidate_metrics.csv`,
  `${BTC_OUTPUT_DIR}/base_candidate_nav.csv`,
  `${BTC_OUTPUT_DIR}/base_candidate_underwater.csv`,
  `${BTC_OUTPUT_DIR}/implementation_stress_summary.csv`,
  `${BTC_OUTPUT_DIR}/btc_return_haircut_stress.csv`,
  `${BTC_OUTPUT_DIR}/core_return_haircut_stress.csv`,
  `${BTC_OUTPUT_DIR}/latest_signal_summary.csv`,
  `${BTC_OUTPUT_DIR}/latest_target_weights.csv`,
  `${BTC_OUTPUT_DIR}/paper_trading_rule_draft.csv`
];

const themeAlphaSourceFiles = [
  ACTIVE_EQUITY_BENCHMARK_FILE,
  CSI300_BENCHMARK_FILE,
  NASDAQ100_BENCHMARK_FILE,
  `${THEME_ALPHA_Q8_DIR}/research_summary.csv`,
  `${THEME_ALPHA_Q8_DIR}/signal_schedule_comparison.csv`,
  `${THEME_ALPHA_Q8_DIR}/friction_stress_comparison.csv`,
  `${THEME_ALPHA_Q8_DIR}/liquidity_participation_summary.csv`,
  `${THEME_ALPHA_Q8_DIR}/latest_target_weights.csv`,
  `${THEME_ALPHA_Q8_DIR}/nav_q8_selected_2021_to_date.csv`,
  `${THEME_ALPHA_Q8_DIR}/underwater_q8_selected_2021_to_date.csv`,
  `${THEME_ALPHA_Q12_DIR}/summary_real_etf.csv`,
  `${THEME_ALPHA_Q12_DIR}/scorecard_selected_metrics.csv`,
  `${THEME_ALPHA_Q12_DIR}/annual_returns.csv`,
  `${THEME_ALPHA_Q12_DIR}/monthly_returns.csv`
];

async function parseCsv(repoRoot: string, relativePath: string): Promise<CsvRow[]> {
  const raw = await readFile(join(repoRoot, relativePath), "utf8");
  const parsed = Papa.parse<CsvRow>(raw.replace(/^\uFEFF/, ""), {
    header: true,
    skipEmptyLines: true
  });

  if (parsed.errors.length > 0) {
    const [firstError] = parsed.errors;
    throw new Error(`Failed to parse ${relativePath}: ${firstError.message}`);
  }

  return parsed.data;
}

function numeric(value: string | number | undefined): number {
  if (value === undefined || value === "") {
    return 0;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function boolish(value: string | undefined): boolean {
  return value === "True" || value === "true";
}

function slug(value: string): string {
  return value.replace(/\s+/g, "-").replace(/[/%]/g, "").replace(/_+/g, "-");
}

function keyedValue(rows: CsvRow[]): Record<string, string> {
  return Object.fromEntries(rows.map((row) => [row[""], row["0"]]));
}

function normalizeBtcMetric(row: CsvRow): CandidateMetric {
  return {
    id: row[""].replace(/\s+/g, "-"),
    name: row[""],
    annualReturn: numeric(row["年化收益"]),
    annualVolatility: numeric(row["年化波动"]),
    maxDrawdown: numeric(row["最大回撤"]),
    sharpe: numeric(row["夏普"]),
    calmar: numeric(row["卡玛"]),
    sortino: numeric(row["索提诺"]),
    annualTurnover: numeric(row["年化换手"]),
    averageBtcWeight: numeric(row["平均BTC权重"]),
    currentBtcWeight: numeric(row["当前BTC权重"]),
    averageCash: numeric(row["平均现金"]),
    monthlyWinRate: numeric(row["月度胜率"]),
    longestUnderwaterDays: numeric(row["最长水下天数"]),
    daysBelowTenDrawdown: numeric(row["超过-10%天数"])
  };
}

function normalizeThemeAlphaMetric(row: CsvRow): CandidateMetric {
  return {
    id: slug(row.strategy),
    name: row.strategy,
    annualReturn: numeric(row["年化收益"]),
    annualVolatility: numeric(row["年化波动"]),
    maxDrawdown: numeric(row["最大回撤"]),
    sharpe: numeric(row.Sharpe),
    calmar: numeric(row.Calmar),
    sortino: numeric(row.Sortino),
    annualTurnover: numeric(row["年化换手"]),
    averageCash: numeric(row["平均现金"]),
    currentCash: numeric(row["当前现金"]),
    monthlyWinRate: numeric(row["月胜率"]),
    daysBelowTenDrawdown: numeric(row["超过-10%回撤天数"]),
    daysBelowTwentyDrawdown: numeric(row["超过-20%回撤天数"]),
    annualCostDrag: numeric(row["年化成本拖累"]),
    longestUnderwaterDays: numeric(row["最长修复天数"])
  };
}

function findMetric(metrics: CandidateMetric[], name: string): CandidateMetric {
  const metric = metrics.find((item) => item.name === name);
  if (!metric) {
    throw new Error(`Missing candidate metric: ${name}`);
  }

  return metric;
}

function benchmarkRowFromMetric(
  role: string,
  metric: CandidateMetric,
  note: string,
  verdict: string
): BenchmarkScorecardRow {
  return {
    role,
    name: metric.name,
    annualReturn: metric.annualReturn,
    maxDrawdown: metric.maxDrawdown,
    sharpe: metric.sharpe,
    calmar: metric.calmar,
    note,
    verdict
  };
}

function benchmarkRowFromSeries(
  role: string,
  rows: CsvRow[],
  startDate: string,
  endDate: string,
  options: {
    name: string;
    sourceNote: string;
    verdict?: string;
  }
): BenchmarkScorecardRow {
  const points = rows
    .map((row) => ({
      date: row.date,
      close: numeric(row.close)
    }))
    .filter((row) => row.date >= startDate && row.date <= endDate && row.close > 0)
    .sort((a, b) => a.date.localeCompare(b.date));

  if (points.length < 2) {
    throw new Error(`Insufficient benchmark data for ${startDate} to ${endDate}`);
  }

  const first = points[0];
  const last = points[points.length - 1];
  const returns = points.slice(1).map((point, index) => point.close / points[index].close - 1);
  const totalReturn = last.close / first.close - 1;
  const annualReturn = Math.pow(last.close / first.close, 252 / (points.length - 1)) - 1;
  const meanReturn = returns.reduce((sum, value) => sum + value, 0) / returns.length;
  const variance =
    returns.length > 1
      ? returns.reduce((sum, value) => sum + Math.pow(value - meanReturn, 2), 0) / (returns.length - 1)
      : 0;
  const annualVolatility = Math.sqrt(variance) * Math.sqrt(252);

  let peak = first.close;
  let maxDrawdown = 0;
  for (const point of points) {
    peak = Math.max(peak, point.close);
    maxDrawdown = Math.min(maxDrawdown, point.close / peak - 1);
  }

  return {
    role,
    name: options.name,
    annualReturn,
    maxDrawdown,
    sharpe: annualVolatility > 0 ? (meanReturn * 252) / annualVolatility : 0,
    calmar: maxDrawdown < 0 ? annualReturn / Math.abs(maxDrawdown) : 0,
    note: `${first.date} 至 ${last.date} 同周期计算，累计收益 ${(totalReturn * 100).toFixed(
      2
    )}%。${options.sourceNote}`,
    verdict: options.verdict ?? "同周期参考"
  };
}

function benchmarkRowsFromExternalSeries(
  activeEquityRows: CsvRow[],
  csi300Rows: CsvRow[],
  nasdaq100Rows: CsvRow[],
  startDate: string,
  endDate: string
): BenchmarkScorecardRow[] {
  return [
    benchmarkRowFromSeries("主动权益基金参考线", activeEquityRows, startDate, endDate, {
      name: "中证主动偏股型基金指数",
      sourceNote: "数据源：中证指数 932055，用作主动权益基金机会成本 proxy。",
      verdict: "同周期参考"
    }),
    benchmarkRowFromSeries("宽基指数参考线", csi300Rows, startDate, endDate, {
      name: "沪深300全收益指数",
      sourceNote: "数据源：中证指数 H00300，全收益口径，用作 A 股大盘含分红再投资参考。",
      verdict: "A股Beta参考"
    }),
    benchmarkRowFromSeries("海外成长参考线", nasdaq100Rows, startDate, endDate, {
      name: "纳斯达克100全收益指数",
      sourceNote: "数据源：FRED NASDAQXNDX / Nasdaq，全收益美元口径，不含境内 QDII 汇率、溢价和申赎约束。",
      verdict: "海外成长参考"
    })
  ];
}

function normalizeSeries(rows: CsvRow[]): TimeSeriesPoint[] {
  return rows.map((row) => {
    const date = row.Date ?? row[""] ?? row.date;
    const values = Object.entries(row).filter(([key]) => key !== "Date" && key !== "" && key !== "date");

    return {
      date,
      values: Object.fromEntries(values.map(([key, value]) => [key, numeric(value)]))
    };
  });
}

function calculateAnnualReturns(series: TimeSeriesPoint[]): AnnualReturnRow[] {
  const byYear = new Map<string, TimeSeriesPoint[]>();

  for (const point of series) {
    const year = point.date.slice(0, 4);
    byYear.set(year, [...(byYear.get(year) ?? []), point]);
  }

  return [...byYear.entries()].map(([year, points]) => {
    const first = points[0];
    const last = points[points.length - 1];

    return {
      year,
      values: Object.fromEntries(
        Object.keys(last.values).map((name) => [name, last.values[name] / first.values[name] - 1])
      )
    };
  });
}

function annualReturnsFromRows(rows: CsvRow[], layer = "real_etf"): AnnualReturnRow[] {
  const byYear = new Map<string, Record<string, number>>();

  for (const row of rows.filter((item) => item.layer === layer)) {
    const values = byYear.get(row.year) ?? {};
    values[row.strategy] = numeric(row.return);
    byYear.set(row.year, values);
  }

  return [...byYear.entries()].map(([year, values]) => ({ year, values }));
}

function calculateMonthlyStats(series: TimeSeriesPoint[], metrics: CandidateMetric[]): MonthlyStat[] {
  const byMonth = new Map<string, TimeSeriesPoint[]>();

  for (const point of series) {
    const month = point.date.slice(0, 7);
    byMonth.set(month, [...(byMonth.get(month) ?? []), point]);
  }

  const monthlyReturns = [...byMonth.values()].map((points) => {
    const first = points[0];
    const last = points[points.length - 1];

    return Object.fromEntries(Object.keys(last.values).map((name) => [name, last.values[name] / first.values[name] - 1]));
  });

  return metrics.map((metric) => {
    const returns = monthlyReturns.map((row) => row[metric.name]).filter((value) => Number.isFinite(value));
    return summarizeMonthlyReturns(metric.id, metric.name, returns);
  });
}

function monthlyStatsFromRows(rows: CsvRow[], metrics: CandidateMetric[], layer = "real_etf"): MonthlyStat[] {
  return metrics.map((metric) => {
    const returns = rows
      .filter((row) => row.layer === layer && row.strategy === metric.name)
      .map((row) => numeric(row.return));

    return summarizeMonthlyReturns(metric.id, metric.name, returns);
  });
}

function summarizeMonthlyReturns(id: string, name: string, returns: number[]): MonthlyStat {
  const wins = returns.filter((value) => value > 0);
  const losses = returns.filter((value) => value < 0);
  const winSum = wins.reduce((sum, value) => sum + value, 0);
  const lossSum = losses.reduce((sum, value) => sum + value, 0);

  return {
    id,
    name,
    totalMonths: returns.length,
    winningMonths: wins.length,
    losingMonths: losses.length,
    monthlyWinRate: returns.length > 0 ? wins.length / returns.length : 0,
    averageWinningMonth: wins.length > 0 ? winSum / wins.length : 0,
    averageLosingMonth: losses.length > 0 ? lossSum / losses.length : 0,
    profitFactor: lossSum < 0 ? winSum / Math.abs(lossSum) : 0,
    bestMonth: returns.length > 0 ? Math.max(...returns) : 0,
    worstMonth: returns.length > 0 ? Math.min(...returns) : 0
  };
}

function normalizeBtcLatestSignal(rows: CsvRow[]): LatestSignal {
  const values = keyedValue(rows);

  return {
    latestDate: values.latest_date,
    btcClose: numeric(values.btc_close),
    btcSupertrendLine: numeric(values.btc_supertrend_line),
    btcSupertrendOn: boolish(values.btc_supertrend_on)
  };
}

function normalizeBtcTargetWeights(rows: CsvRow[]): TargetWeightRow[] {
  return rows.map((row) => {
    const { "": candidate, ...weights } = row;

    return {
      candidate,
      weights: Object.fromEntries(Object.entries(weights).map(([asset, value]) => [asset, numeric(value)]))
    };
  });
}

function normalizeThemeTargetWeights(rows: CsvRow[]): TargetWeightRow[] {
  return rows
    .filter((row) => row.schedule === "BIMONTHLY")
    .map((row) => {
      const { candidate, schedule, ...weights } = row;

      return {
        candidate: `${candidate} / ${schedule}`,
        weights: Object.fromEntries(Object.entries(weights).map(([asset, value]) => [asset, numeric(value)]))
      };
    });
}

function normalizeRules(rows: CsvRow[]): PaperTradingRule[] {
  return rows.map((row) => ({
    item: row["项目"],
    rule: row["规则"]
  }));
}

function takeStressRows(rows: CsvRow[], count = 24): Array<Record<string, string | number | boolean>> {
  return rows.slice(0, count).map((row) =>
    Object.fromEntries(
      Object.entries(row).map(([key, value]) => {
        if (value === "True" || value === "False") {
          return [key, boolish(value)];
        }

        const parsed = Number(value);
        return [key, Number.isFinite(parsed) && value.trim() !== "" ? parsed : value];
      })
    )
  );
}

function buildBtcStressSummaries(
  implementationRows: CsvRow[],
  btcHaircutRows: CsvRow[],
  coreHaircutRows: CsvRow[]
): StressSummary[] {
  return [
    {
      id: "implementation",
      title: "Execution friction stress",
      rows: takeStressRows(implementationRows)
    },
    {
      id: "btc-haircut",
      title: "BTC return haircut stress",
      rows: takeStressRows(btcHaircutRows)
    },
    {
      id: "core-haircut",
      title: "Core return haircut stress",
      rows: takeStressRows(coreHaircutRows)
    }
  ];
}

function buildThemeAlphaStressSummaries(scheduleRows: CsvRow[], frictionRows: CsvRow[], liquidityRows: CsvRow[]): StressSummary[] {
  const schedule = scheduleRows
    .filter((row) => row.window === "2021_to_date" && row.candidate === "Def200_Cash" && row.execution_mode === "next_close")
    .filter((row) => ["10D", "BIMONTHLY", "M"].includes(row.schedule) && row.friction_mode === "base20_plus_asset")
    .map((row) => ({
      schedule: row.schedule,
      "累计收益": numeric(row["累计收益"]),
      "年化收益": numeric(row["年化收益"]),
      "最大回撤": numeric(row["最大回撤"]),
      Sharpe: numeric(row["夏普"]),
      Calmar: numeric(row["卡玛"]),
      "超过-10%天数": numeric(row["超过-10%天数"]),
      "平均现金": numeric(row["平均现金"])
    }));

  const friction = frictionRows
    .filter(
      (row) =>
        row.window === "2021_to_date" &&
        row.candidate === "Def200_Cash" &&
        row.schedule === "BIMONTHLY" &&
        row.execution_mode === "next_close"
    )
    .map((row) => ({
      friction: row.friction_mode,
      "年化收益": numeric(row["年化收益"]),
      "最大回撤": numeric(row["最大回撤"]),
      "年化成本拖累": numeric(row["年化成本拖累"]),
      "总成本拖累": numeric(row["总成本拖累"])
    }));

  const byAum = new Map<number, CsvRow[]>();
  for (const row of liquidityRows.filter((item) => item.portfolio === "Def200_Cash_BIMONTHLY_next_close_base20_plus_asset")) {
    const aum = numeric(row.aum);
    byAum.set(aum, [...(byAum.get(aum) ?? []), row]);
  }

  const liquidity = [...byAum.entries()].map(([aum, rows]) => {
    const bottleneck = rows.reduce((worst, row) =>
      numeric(row.max_participation_adv20) > numeric(worst.max_participation_adv20) ? row : worst
    );

    return {
      aum,
      bottleneck: `${bottleneck.name} ${bottleneck.symbol}`,
      maxParticipationAdv20: numeric(bottleneck.max_participation_adv20),
      tradesGt5pctAdv20: numeric(bottleneck.trades_gt_5pct_adv20),
      tradesGt10pctAdv20: numeric(bottleneck.trades_gt_10pct_adv20)
    };
  });

  return [
    {
      id: "schedule",
      title: "Signal schedule comparison",
      rows: schedule
    },
    {
      id: "friction",
      title: "Execution friction comparison",
      rows: friction
    },
    {
      id: "liquidity",
      title: "Liquidity participation check",
      rows: liquidity
    }
  ];
}

function buildCatalogItem(strategy: StrategyPackage): StrategyCatalogItem {
  return {
    id: strategy.id,
    name: strategy.name,
    asOfDate: strategy.asOfDate,
    headline: strategy.recommendation.headline,
    summary: strategy.recommendation.summary,
    paperTracking: strategy.status.paperTracking,
    liveTrading: strategy.status.liveTrading
  };
}

export function buildStrategyCatalog(strategies: StrategyPackage[]): StrategyCatalog {
  return {
    defaultStrategyId: BTC_STRATEGY_ID,
    strategies: strategies.map(buildCatalogItem)
  };
}

function splitStrategyPackage(strategy: StrategyPackage): {
  summary: StrategySummaryPackage;
  report: StrategyReportData;
  charts: StrategyChartData;
  paper: StrategyPaperData;
} {
  const {
    id,
    name,
    asOfDate,
    status,
    recommendation,
    sourceFiles,
    highlightCards,
    strategyBrief,
    benchmarkScorecard,
    candidateMetrics,
    stressSummaries,
    navSeries,
    underwaterSeries,
    annualReturns,
    monthlyStats,
    latestSignal,
    targetWeights,
    paperTradingRules,
    riskNotes
  } = strategy;

  return {
    summary: {
      id,
      name,
      asOfDate,
      status,
      recommendation,
      sourceFiles
    },
    report: {
      highlightCards,
      strategyBrief,
      benchmarkScorecard,
      candidateMetrics,
      stressSummaries
    },
    charts: {
      navSeries,
      underwaterSeries,
      annualReturns,
      monthlyStats
    },
    paper: {
      latestSignal,
      targetWeights,
      paperTradingRules,
      riskNotes
    }
  };
}

async function writeJsonFile(outputPath: string, value: unknown): Promise<string> {
  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(outputPath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  return outputPath;
}

async function writeSplitStrategyPackage(outputRoot: string, strategy: StrategyPackage): Promise<string[]> {
  const strategyDir = join(outputRoot, "strategies", strategy.id);
  const { summary, report, charts, paper } = splitStrategyPackage(strategy);

  return Promise.all([
    writeJsonFile(join(strategyDir, "strategy.json"), summary),
    writeJsonFile(join(strategyDir, "report.json"), report),
    writeJsonFile(join(strategyDir, "paper.json"), paper),
    writeJsonFile(join(strategyDir, "nav-series.json"), charts.navSeries),
    writeJsonFile(join(strategyDir, "underwater-series.json"), charts.underwaterSeries),
    writeJsonFile(join(strategyDir, "annual-returns.json"), charts.annualReturns),
    writeJsonFile(join(strategyDir, "monthly-stats.json"), charts.monthlyStats)
  ]);
}

function btcSnapshotConclusion(asOfDate: string): string {
  return `本报告结论基于 ${asOfDate} 研究快照形成，为静态研究判断；后续 benchmark 刷新不会自动改写本段结论，需要手动生成新的研究快照。结论：BTC7.5%ST卫星年化 19.49%，明显跑赢主动偏股和沪深300全收益，且最大回撤约 -12.75%，相对两条权益参考线回撤明显更浅；但它没有跑赢纳指100全收益 22.01% 的年化。评价上更像是用多资产和 BTC 趋势过滤换取更平滑路径，而不是追求最高进攻收益；BTC10%ST卫星只作进攻观察，默认仍应先纸面跟踪 5% / 7.5%。`;
}

function themeAlphaSnapshotConclusion(asOfDate: string): string {
  return `本报告结论基于 ${asOfDate} 研究快照形成，为静态研究判断；后续 benchmark 刷新不会自动改写本段结论，需要手动生成新的研究快照。结论：Core80_LVT20_Def200_Cash 年化 14.48%，明显跑赢主动偏股和沪深300全收益，但年化低于纳指100全收益 17.55%。它的优势在路径：最大回撤约 -11.29%、Calmar 约 1.28，显著好于纳指100全收益约 -35.04% 回撤和 0.50 Calmar。因此默认候选不是最高收益选择，而是更均衡的可跟踪组合；若投资者只接受纳指成长 Beta，Theme Alpha 的吸引力主要来自回撤控制而非收益领先。`;
}

export async function buildBtcStrategyPackage(repoRoot: string): Promise<StrategyPackage> {
  const [
    activeEquityBenchmarkRows,
    csi300BenchmarkRows,
    nasdaq100BenchmarkRows,
    researchSummaryRows,
    metricRows,
    navRows,
    underwaterRows,
    implementationRows,
    btcHaircutRows,
    coreHaircutRows,
    latestSignalRows,
    targetWeightRows,
    ruleRows
  ] = await Promise.all(btcSourceFiles.map((file) => parseCsv(repoRoot, file)));

  const researchSummary = keyedValue(researchSummaryRows);
  const latestSignal = normalizeBtcLatestSignal(latestSignalRows);
  const candidateMetrics = metricRows.map(normalizeBtcMetric);
  const navSeries = normalizeSeries(navRows);
  const btcBaseline = findMetric(candidateMetrics, "原三资产RiskParity");
  const btcPaperCandidate = findMetric(candidateMetrics, "BTC7.5%ST卫星");
  const btcGrowthCandidate = findMetric(candidateMetrics, "BTC10%ST卫星");
  const benchmarkStartDate = navSeries[0].date;
  const benchmarkEndDate = navSeries[navSeries.length - 1].date;
  const asOfDate = latestSignal.latestDate ?? "";

  return {
    id: BTC_STRATEGY_ID,
    name: "BTC SuperTrend Satellite",
    asOfDate,
    status: {
      paperTracking: researchSummary.paper_tracking_recommendation === "yes" ? "recommended" : "watch",
      liveTrading:
        researchSummary.small_capital_trial_recommendation === "not_yet_before_paper_tracking"
          ? "not-yet"
          : "ready"
    },
    recommendation: {
      headline: "建议进入纸面跟踪，暂不直接实盘。",
      summary:
        "BTC 5% 和 7.5% SuperTrend 卫星更适合作为第一批纸面跟踪对象；BTC 10% 仍是历史表现最强的进攻观察候选，但对未来 BTC 趋势收益的依赖更明显。",
      preferredPaperCaps: researchSummary.preferred_paper_caps
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      growthCandidateCap: researchSummary.growth_candidate_cap
    },
    strategyBrief: {
      plainLanguage: "这是一个以三资产 RiskParity 为核心、用 BTC SuperTrend 趋势信号做小比例卫星增强的组合策略。",
      objective: "观察 BTC 趋势收益是否能在可控回撤和可执行成本下改善核心组合。",
      mechanism: [
        "核心仓位仍由沪深300、纳指100、黄金的 RiskParity 结构承担。",
        "BTC 只作为 5% / 7.5% / 10% 上限的卫星仓位，不是组合主引擎。",
        "当 BTC close 高于 SuperTrend line 时卫星开启，否则卫星仓位进入现金。"
      ],
      investorUse: "适合用来观察小比例 BTC 趋势增强是否值得进入纸面跟踪，而不是作为单独押注 BTC 的展示页。",
      watchOut: "如果未来 BTC 趋势收益消失，卫星层可能只增加复杂度和执行摩擦。",
      glossary: [
        {
          term: "RiskParity",
          definition: "按风险贡献而非资金比例来配置沪深300、纳指100和黄金的核心组合。"
        },
        {
          term: "BTC 卫星",
          definition: "核心组合之外的小比例增强仓位，用来测试 BTC 趋势收益是否值得承担。"
        },
        {
          term: "SuperTrend",
          definition: "以价格和波动率构造的趋势线，价格站上线视为趋势打开，跌破则降低或关闭 BTC 暴露。"
        },
        {
          term: "纸面跟踪",
          definition: "先按实盘规则记录信号、成本和成交可行性，但不直接投入真实资金。"
        }
      ]
    },
    benchmarkScorecard: {
      title: "评价坐标系",
      summary:
        "先用三资产 RiskParity 判断卫星层是否真的增厚组合，再把主动偏股基金、沪深300全收益和纳指100全收益放到同一回测窗口里，帮助投资者理解机会成本、A股Beta和海外成长Beta。",
      conclusion: btcSnapshotConclusion(asOfDate),
      period: {
        startDate: benchmarkStartDate,
        endDate: benchmarkEndDate
      },
      rows: [
        benchmarkRowFromMetric(
          "内部基准",
          btcBaseline,
          "不含 BTC 卫星的原始三资产组合，用来判断新增复杂度是否值得。",
          "必须跑赢或改善路径"
        ),
        benchmarkRowFromMetric(
          "默认观察候选",
          btcPaperCandidate,
          "纸面跟踪优先候选之一，收益、回撤和 BTC 依赖之间较均衡。",
          "进入纸面跟踪"
        ),
        benchmarkRowFromMetric(
          "进攻观察",
          btcGrowthCandidate,
          "历史表现更强，但对 BTC 趋势持续性的依赖更高。",
          "只作观察"
        ),
        ...benchmarkRowsFromExternalSeries(
          activeEquityBenchmarkRows,
          csi300BenchmarkRows,
          nasdaq100BenchmarkRows,
          benchmarkStartDate,
          benchmarkEndDate
        )
      ]
    },
    candidateMetrics,
    navSeries,
    underwaterSeries: normalizeSeries(underwaterRows),
    annualReturns: calculateAnnualReturns(navSeries),
    monthlyStats: calculateMonthlyStats(navSeries, candidateMetrics),
    stressSummaries: buildBtcStressSummaries(implementationRows, btcHaircutRows, coreHaircutRows),
    latestSignal,
    targetWeights: normalizeBtcTargetWeights(targetWeightRows),
    paperTradingRules: normalizeRules(ruleRows),
    riskNotes: [
      {
        title: "BTC 趋势收益可能消失",
        body: "卫星仓位不要求 BTC 重演过去十年的完整涨幅，但仍然需要未来存在一部分正向趋势收益。"
      },
      {
        title: "核心资产仍是组合主体",
        body: "BTC 卫星是增强层，不是独立发动机。如果三资产 RiskParity 核心明显走弱，卫星仓位无法单独拯救组合。"
      },
      {
        title: "执行假设仍需纸面验证",
        body: "实际 BTC 工具、税费、点差、溢价折价、交易时段差异和账户限制，都需要通过纸面跟踪继续记录。"
      }
    ],
    sourceFiles: btcSourceFiles
  };
}

export async function buildThemeAlphaStrategyPackage(repoRoot: string): Promise<StrategyPackage> {
  const [
    activeEquityBenchmarkRows,
    csi300BenchmarkRows,
    nasdaq100BenchmarkRows,
    _researchSummaryRows,
    scheduleRows,
    frictionRows,
    liquidityRows,
    targetWeightRows,
    navRows,
    underwaterRows,
    realEtfRows,
    _scorecardRows,
    annualReturnRows,
    monthlyReturnRows
  ] = await Promise.all(themeAlphaSourceFiles.map((file) => parseCsv(repoRoot, file)));

  const fullSampleRows = realEtfRows.filter((row) => row.window === "full_sample");
  const candidateMetrics = fullSampleRows.map(normalizeThemeAlphaMetric);
  const themeBaseline = findMetric(candidateMetrics, "Original_RiskParity_3Asset");
  const themeLvt100 = findMetric(candidateMetrics, "Expanded_LVT_100");
  const themeDefault = findMetric(candidateMetrics, "Core80_LVT20_Def200_Cash");
  const themeGrowth = findMetric(candidateMetrics, "Core60_LVT40_Def200_Cash");
  const preferredRow = fullSampleRows.find((row) => row.strategy === "Core80_LVT20_Def200_Cash") ?? fullSampleRows[0];
  const targetWeights = normalizeThemeTargetWeights(targetWeightRows);
  const preferredWeights = targetWeights.find((row) => row.candidate === "Def200_Cash / BIMONTHLY");
  const currentCash = preferredWeights?.weights["现金"] ?? 0;
  const asOfDate = preferredRow?.end ?? "2026-06-24";
  const navSeries = normalizeSeries(navRows);
  const benchmarkStartDate = navSeries[0].date;
  const benchmarkEndDate = navSeries[navSeries.length - 1].date;

  return {
    id: THEME_ALPHA_STRATEGY_ID,
    name: "Theme Alpha / Core80 LVT20 Def200 Cash",
    asOfDate,
    status: {
      paperTracking: "recommended",
      liveTrading: "not-yet"
    },
    recommendation: {
      headline: "建议进入纸面跟踪，暂不直接实盘。",
      summary:
        "默认候选保持 Core80 / Expanded LVT20 / Def200 Cash，并采用固定半月信号、收盘信号下一交易日执行和资产级摩擦假设。Q12 支持它作为稳健实盘候选，但 proxy 长样本提醒 LVT 只能做卫星，不能升级为主引擎。",
      preferredPaperCaps: ["Def200_Cash / BIMONTHLY"],
      growthCandidateCap: "Core60_LVT40_Def200_Cash"
    },
    strategyBrief: {
      plainLanguage:
        "这是一个以三资产核心仓位为底座、用 20% 低波趋势主题 ETF 做卫星增强，并在核心风险恶化时转入现金防御的半月调仓策略。",
      objective: "观察主题 ETF 增强和 Def200 Cash 防御规则能否在近实盘成本下改善组合路径。",
      mechanism: [
        "80% 核心仓位由沪深300、纳指100和黄金承担主要资产配置。",
        "20% 卫星仓位在扩展主题 ETF 池内做低波趋势选择。",
        "核心风险恶化时，Def200 Cash 将防御袖转入现金。",
        "固定每月 10 日和 25 日附近生成信号，收盘信号下一交易日执行。"
      ],
      methodology: [
        {
          label: "趋势门槛",
          value: "候选 ETF 价格需要站上 MA60，避免在中期下行趋势里强行买入。"
        },
        {
          label: "动量门槛",
          value: "候选 ETF 的 63 日动量需要为正，过滤只低波但没有上涨惯性的资产。"
        },
        {
          label: "低波筛选",
          value: "通过趋势和动量门槛后，选择 60 日波动率最低的 3 个资产进入卫星池。"
        },
        {
          label: "权重约束",
          value: "入选卫星资产使用 RiskParity 分配，并设置单资产 cap50，避免主题仓位过度集中。"
        }
      ],
      investorUse: "适合观察多资产配置加主题卫星是否能比单纯买指数或全仓主题轮动更稳。",
      watchOut: "全仓 LVT 在长样本 proxy 中并不稳定，主题卫星不能升级为主引擎。",
      glossary: [
        {
          term: "Core80",
          definition: "80% 核心仓位，主要承担长期资产配置和组合稳定性。"
        },
        {
          term: "LVT20",
          definition: "20% 低波趋势主题卫星，在扩展主题 ETF 池中选择更平滑的趋势暴露。"
        },
        {
          term: "Def200 Cash",
          definition: "防御规则；当核心风险状态变差时，将防御袖转入现金。"
        },
        {
          term: "BIMONTHLY",
          definition: "固定半月调仓节奏，每月 10 日和 25 日附近生成信号。"
        },
        {
          term: "proxy",
          definition: "用于延长样本的代理资产数据，能提供压力测试线索，但不能等同于真实 ETF 历史。"
        }
      ]
    },
    benchmarkScorecard: {
      title: "评价坐标系",
      summary:
        "Theme Alpha 先和原始三资产核心比较，确认主题卫星和现金防御是否改善路径；再用全仓 LVT 作为风险上限提醒，并把主动偏股基金、沪深300全收益和纳指100全收益放进同一回测窗口里，形成投资者更直观的外部坐标。",
      conclusion: themeAlphaSnapshotConclusion(asOfDate),
      period: {
        startDate: benchmarkStartDate,
        endDate: benchmarkEndDate
      },
      rows: [
        benchmarkRowFromMetric(
          "内部基准",
          themeBaseline,
          "原始三资产 RiskParity，用来判断 Theme Alpha 增加主题卫星和现金防御后是否真的更好。",
          "核心参照"
        ),
        benchmarkRowFromMetric(
          "风险上限",
          themeLvt100,
          "全仓扩展主题 LVT 用来提醒主题轮动的波动和样本不稳定性，不是默认实盘候选。",
          "只作风险镜子"
        ),
        benchmarkRowFromMetric(
          "当前策略",
          themeDefault,
          "Core80 / LVT20 / Def200 Cash 是当前建议进入纸面跟踪的默认候选。",
          "进入纸面跟踪"
        ),
        benchmarkRowFromMetric(
          "进攻观察",
          themeGrowth,
          "Core60 / LVT40 提高主题暴露，适合观察上行弹性和压力期代价。",
          "只作观察"
        ),
        ...benchmarkRowsFromExternalSeries(
          activeEquityBenchmarkRows,
          csi300BenchmarkRows,
          nasdaq100BenchmarkRows,
          benchmarkStartDate,
          benchmarkEndDate
        )
      ]
    },
    highlightCards: [
      {
        label: "默认纸面候选",
        value: "Def200 Cash / 半月",
        detail: `真实 ETF 全样本年化 ${(numeric(preferredRow?.["年化收益"]) * 100).toFixed(2)}% / 最大回撤 ${(
          numeric(preferredRow?.["最大回撤"]) * 100
        ).toFixed(2)}%`
      },
      {
        label: "防御规则",
        value: currentCash > 0 ? "现金防御开启" : "现金防御未触发",
        detail: `当前现金 ${(currentCash * 100).toFixed(2)}% / 平均现金 ${(
          numeric(preferredRow?.["平均现金"]) * 100
        ).toFixed(2)}%`
      },
      {
        label: "进攻观察",
        value: "Core60 / LVT40",
        detail: "更高主题暴露仅作观察，不替代 Core80 / LVT20 默认候选"
      }
    ],
    candidateMetrics,
    navSeries,
    underwaterSeries: normalizeSeries(underwaterRows),
    annualReturns: annualReturnsFromRows(annualReturnRows),
    monthlyStats: monthlyStatsFromRows(monthlyReturnRows, candidateMetrics),
    stressSummaries: buildThemeAlphaStressSummaries(scheduleRows, frictionRows, liquidityRows),
    latestSignal: {
      title: "Theme Alpha 信号状态",
      latestDate: asOfDate,
      stateLabel: currentCash > 0 ? "Def200 Cash 已触发" : "Def200 Cash 未触发",
      stateTone: currentCash > 0 ? "warning" : "positive",
      rows: [
        { label: "调仓频率", value: "固定半月：10 日 / 25 日附近" },
        { label: "执行口径", value: "收盘信号，下一交易日执行" },
        { label: "候选", value: "Def200_Cash / BIMONTHLY" },
        { label: "当前现金", value: `${(currentCash * 100).toFixed(2)}%` }
      ]
    },
    targetWeights,
    paperTradingRules: [
      {
        item: "候选策略",
        rule: "Core80 / Expanded LVT20 / Def200 Cash，默认采用固定半月信号。"
      },
      {
        item: "调仓频率",
        rule: "每月 10 日和 25 日附近生成信号，若非交易日则顺延到下一个可交易日。"
      },
      {
        item: "执行口径",
        rule: "使用收盘数据计算信号，下一交易日执行；展示包不做自动行情刷新。"
      },
      {
        item: "Def200 Cash",
        rule: "核心风险较差时，防御袖从风险资产转入现金；当前状态由生成的目标权重文件决定。"
      },
      {
        item: "LVT 卫星",
        rule: "20% 卫星在扩展主题 ETF 池内做低波趋势选择；Core60/LVT40 仅作为进攻观察。"
      },
      {
        item: "流动性约束",
        rule: "纸面跟踪必须记录 AUM、最大 ADV20 参与率和能源 ETF 等瓶颈资产。"
      }
    ],
    riskNotes: [
      {
        title: "LVT 不能作为主引擎",
        body: "Q12 proxy 长样本没有证明全仓 LVT 是跨周期赢家，Theme Alpha 应保持 Core/Satellite 结构。"
      },
      {
        title: "现金防御是结构核心",
        body: "Def200 Cash 的价值在于压力期降低核心权益暴露，而不是追求最高历史收益。"
      },
      {
        title: "半月信号不是魔法日期",
        body: "Q8 显示固定半月没有破坏策略，但不能解释为 10 日和 25 日本身具有稳定 alpha。"
      },
      {
        title: "流动性瓶颈需要继续纸面记录",
        body: "能源 ETF 159930.SZ 是主要流动性瓶颈；账户规模扩大时需要仓位上限、ADV 过滤或分日执行。"
      }
    ],
    sourceFiles: themeAlphaSourceFiles
  };
}

export async function writeBtcStrategyPackage(repoRoot: string, outputRoot: string): Promise<string> {
  const strategy = await buildBtcStrategyPackage(repoRoot);
  const outputPaths = await writeSplitStrategyPackage(outputRoot, strategy);
  return outputPaths[0];
}

export async function writeAllStrategyPackages(repoRoot: string, outputRoot: string): Promise<string[]> {
  const strategies = await Promise.all([buildBtcStrategyPackage(repoRoot), buildThemeAlphaStrategyPackage(repoRoot)]);
  const outputPaths = (await Promise.all(strategies.map((strategy) => writeSplitStrategyPackage(outputRoot, strategy)))).flat();

  const catalogPath = join(outputRoot, "strategies", "index.json");
  await writeJsonFile(catalogPath, buildStrategyCatalog(strategies));

  return [...outputPaths, catalogPath];
}

async function main() {
  const repoRoot = join(process.cwd(), "..");
  const outputRoot = join(process.cwd(), "public", "data");
  await writeAllStrategyPackages(repoRoot, outputRoot);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  await main();
}
