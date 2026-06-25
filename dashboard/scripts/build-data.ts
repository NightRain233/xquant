import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import Papa from "papaparse";
import type {
  CandidateMetric,
  LatestSignal,
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
      headline: "Paper tracking recommended; live capital waits.",
      summary:
        "BTC 5% and 7.5% SuperTrend satellite caps are the preferred first paper-tracking candidates. BTC 10% remains the historical winner and growth observation candidate, but it depends more visibly on future BTC trend contribution.",
      preferredPaperCaps: researchSummary.preferred_paper_caps
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      growthCandidateCap: researchSummary.growth_candidate_cap
    },
    candidateMetrics: metricRows.map(normalizeMetric),
    navSeries: normalizeSeries(navRows),
    underwaterSeries: normalizeSeries(underwaterRows),
    stressSummaries: buildStressSummaries(implementationRows, btcHaircutRows, coreHaircutRows),
    latestSignal,
    targetWeights: normalizeTargetWeights(targetWeightRows),
    paperTradingRules: normalizeRules(ruleRows),
    riskNotes: [
      {
        title: "BTC trend contribution can disappear",
        body: "The satellite does not require BTC to repeat the last decade, but it still needs some future positive trend return."
      },
      {
        title: "Core assets still drive the portfolio",
        body: "The BTC sleeve is an enhancement layer. If the three-asset RiskParity core weakens sharply, the satellite cannot rescue the whole portfolio."
      },
      {
        title: "Execution assumptions are incomplete",
        body: "Actual BTC access, tax, spread, premium or discount, trading-hour mismatch, and account constraints still need paper-trading evidence."
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
