export type StrategyStatus = {
  paperTracking: "recommended" | "watch" | "not-ready";
  liveTrading: "ready" | "not-yet" | "not-ready";
};

export type CandidateMetric = {
  id: string;
  name: string;
  annualReturn: number;
  annualVolatility: number;
  maxDrawdown: number;
  sharpe: number;
  calmar: number;
  sortino?: number;
  annualTurnover?: number;
  averageBtcWeight?: number;
  currentBtcWeight?: number;
  averageCash?: number;
  monthlyWinRate?: number;
  longestUnderwaterDays?: number;
  daysBelowTenDrawdown?: number;
  daysBelowTwentyDrawdown?: number;
  currentCash?: number;
  annualCostDrag?: number;
};

export type TimeSeriesPoint = {
  date: string;
  values: Record<string, number>;
};

export type StressSummary = {
  id: string;
  title: string;
  rows: Array<Record<string, string | number | boolean>>;
};

export type AnnualReturnRow = {
  year: string;
  values: Record<string, number>;
};

export type MonthlyStat = {
  id: string;
  name: string;
  totalMonths: number;
  winningMonths: number;
  losingMonths: number;
  monthlyWinRate: number;
  averageWinningMonth: number;
  averageLosingMonth: number;
  profitFactor: number;
  bestMonth: number;
  worstMonth: number;
};

export type LatestSignal = {
  latestDate?: string;
  btcClose?: number;
  btcSupertrendLine?: number;
  btcSupertrendOn?: boolean;
  title?: string;
  stateLabel?: string;
  stateTone?: "positive" | "warning" | "neutral";
  rows?: Array<{
    label: string;
    value: string | number | boolean;
    detail?: string;
  }>;
};

export type TargetWeightRow = {
  candidate: string;
  weights: Record<string, number>;
};

export type PaperTradingRule = {
  item: string;
  rule: string;
};

export type RiskNote = {
  title: string;
  body: string;
};

export type HighlightCard = {
  label: string;
  value: string;
  detail: string;
};

export type StrategyBrief = {
  plainLanguage: string;
  objective: string;
  mechanism: string[];
  methodology?: Array<{
    label: string;
    value: string;
  }>;
  investorUse: string;
  watchOut: string;
  glossary: Array<{
    term: string;
    definition: string;
  }>;
};

export type BenchmarkScorecardRow = {
  role: string;
  name: string;
  annualReturn?: number;
  maxDrawdown?: number;
  sharpe?: number;
  calmar?: number;
  note: string;
  verdict: string;
};

export type BenchmarkScorecard = {
  title: string;
  summary: string;
  conclusion: string;
  period?: {
    startDate: string;
    endDate: string;
  };
  rows: BenchmarkScorecardRow[];
};

export type StrategyCatalogItem = {
  id: string;
  name: string;
  asOfDate: string;
  headline: string;
  summary: string;
  paperTracking: StrategyStatus["paperTracking"];
  liveTrading: StrategyStatus["liveTrading"];
};

export type StrategyCatalog = {
  defaultStrategyId: string;
  strategies: StrategyCatalogItem[];
};

export type StrategyPackage = {
  id: string;
  name: string;
  asOfDate: string;
  status: StrategyStatus;
  recommendation: {
    headline: string;
    summary: string;
    preferredPaperCaps: string[];
    growthCandidateCap: string;
  };
  highlightCards?: HighlightCard[];
  strategyBrief?: StrategyBrief;
  benchmarkScorecard?: BenchmarkScorecard;
  candidateMetrics: CandidateMetric[];
  navSeries: TimeSeriesPoint[];
  underwaterSeries: TimeSeriesPoint[];
  annualReturns: AnnualReturnRow[];
  monthlyStats: MonthlyStat[];
  stressSummaries: StressSummary[];
  latestSignal: LatestSignal;
  targetWeights: TargetWeightRow[];
  paperTradingRules: PaperTradingRule[];
  riskNotes: RiskNote[];
  sourceFiles: string[];
};
