import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import Papa from "papaparse";
import type {
  AnnualReturnRow,
  CandidateMetric,
  LatestSignal,
  MonthlyStat,
  PaperTradingRule,
  StrategyPackage,
  StressSummary,
  TargetWeightRow,
  TimeSeriesPoint
} from "../src/data/types";

type CsvRow = Record<string, string>;

const BTC_OUTPUT_DIR = "outputs/q10-live-readiness-stress";
const STRATEGY_ID = "btc-supertrend-satellite";

const sourceFiles = [
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

function numeric(value: string | undefined): number {
  if (value === undefined || value === "") {
    return 0;
  }

  return Number(value);
}

function boolish(value: string | undefined): boolean {
  return value === "True" || value === "true";
}

function keyedValue(rows: CsvRow[]): Record<string, string> {
  return Object.fromEntries(rows.map((row) => [row[""], row["0"]]));
}

function normalizeMetric(row: CsvRow): CandidateMetric {
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

function normalizeSeries(rows: CsvRow[]): TimeSeriesPoint[] {
  return rows.map((row) => {
    const { Date: date, ...values } = row;

    return {
      date,
      values: Object.fromEntries(
        Object.entries(values)
          .filter(([key]) => key.length > 0)
          .map(([key, value]) => [key, numeric(value)])
      )
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
    const wins = returns.filter((value) => value > 0);
    const losses = returns.filter((value) => value < 0);
    const winSum = wins.reduce((sum, value) => sum + value, 0);
    const lossSum = losses.reduce((sum, value) => sum + value, 0);

    return {
      id: metric.id,
      name: metric.name,
      totalMonths: returns.length,
      winningMonths: wins.length,
      losingMonths: losses.length,
      monthlyWinRate: returns.length > 0 ? wins.length / returns.length : 0,
      averageWinningMonth: wins.length > 0 ? winSum / wins.length : 0,
      averageLosingMonth: losses.length > 0 ? lossSum / losses.length : 0,
      profitFactor: lossSum < 0 ? winSum / Math.abs(lossSum) : 0,
      bestMonth: Math.max(...returns),
      worstMonth: Math.min(...returns)
    };
  });
}

function normalizeLatestSignal(rows: CsvRow[]): LatestSignal {
  const values = keyedValue(rows);

  return {
    latestDate: values.latest_date,
    btcClose: numeric(values.btc_close),
    btcSupertrendLine: numeric(values.btc_supertrend_line),
    btcSupertrendOn: boolish(values.btc_supertrend_on)
  };
}

function normalizeTargetWeights(rows: CsvRow[]): TargetWeightRow[] {
  return rows.map((row) => {
    const { "": candidate, ...weights } = row;

    return {
      candidate,
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

function buildStressSummaries(
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

export async function buildBtcStrategyPackage(repoRoot: string): Promise<StrategyPackage> {
  const [
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
  ] = await Promise.all(sourceFiles.map((file) => parseCsv(repoRoot, file)));

  const researchSummary = keyedValue(researchSummaryRows);
  const latestSignal = normalizeLatestSignal(latestSignalRows);
  const candidateMetrics = metricRows.map(normalizeMetric);
  const navSeries = normalizeSeries(navRows);

  return {
    id: STRATEGY_ID,
    name: "BTC SuperTrend Satellite",
    asOfDate: latestSignal.latestDate,
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
    candidateMetrics,
    navSeries,
    underwaterSeries: normalizeSeries(underwaterRows),
    annualReturns: calculateAnnualReturns(navSeries),
    monthlyStats: calculateMonthlyStats(navSeries, candidateMetrics),
    stressSummaries: buildStressSummaries(implementationRows, btcHaircutRows, coreHaircutRows),
    latestSignal,
    targetWeights: normalizeTargetWeights(targetWeightRows),
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
    sourceFiles
  };
}

export async function writeBtcStrategyPackage(repoRoot: string, outputRoot: string): Promise<string> {
  const strategy = await buildBtcStrategyPackage(repoRoot);
  const outputPath = join(outputRoot, "strategies", STRATEGY_ID, "strategy.json");
  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(outputPath, `${JSON.stringify(strategy, null, 2)}\n`, "utf8");
  return outputPath;
}

async function main() {
  const repoRoot = join(process.cwd(), "..");
  const outputRoot = join(process.cwd(), "public", "data");
  await writeBtcStrategyPackage(repoRoot, outputRoot);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  await main();
}
