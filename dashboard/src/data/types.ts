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
  latestDate: string;
  btcClose: number;
  btcSupertrendLine: number;
  btcSupertrendOn: boolean;
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
