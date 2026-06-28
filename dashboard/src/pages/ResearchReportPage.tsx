import { lazy, Suspense, useEffect, useState } from "react";
import { AnnualReturnsPanel } from "../components/AnnualReturnsPanel";
import { BenchmarkScorecardPanel } from "../components/BenchmarkScorecardPanel";
import { CandidateTable } from "../components/CandidateTable";
import { MetricCardGrid } from "../components/MetricCardGrid";
import { MonthlyStatsPanel } from "../components/MonthlyStatsPanel";
import { StressSummaryPanel } from "../components/StressSummaryPanel";
import { StrategyBriefPanel } from "../components/StrategyBriefPanel";
import { useStrategyReportData } from "../data/useStrategyData";

const NavChart = lazy(() => import("../components/NavChart").then((module) => ({ default: module.NavChart })));
const UnderwaterChart = lazy(() =>
  import("../components/UnderwaterChart").then((module) => ({ default: module.UnderwaterChart }))
);

type ResearchReportPageProps = {
  strategyId: string;
};

type ComparisonScope = "primary" | "research";

function DataLoadingPanel({ label }: { label: string }) {
  return (
    <section className="border border-ink/15 bg-paper p-5">
      <div className="h-3 w-32 animate-pulse bg-ink/15" />
      <div className="mt-4 h-6 w-64 max-w-full animate-pulse bg-ink/10" />
      <div className="mt-4 h-28 animate-pulse bg-ink/10" />
      <p className="sr-only">{label}</p>
    </section>
  );
}

export function ResearchReportPage({ strategyId }: ResearchReportPageProps) {
  const [comparisonScope, setComparisonScope] = useState<ComparisonScope>("primary");
  const reportData = useStrategyReportData(strategyId);

  useEffect(() => {
    setComparisonScope("primary");
  }, [strategyId]);

  if (reportData.status === "loading" || reportData.status === "idle") {
    return (
      <div className="min-w-0 space-y-5">
        <DataLoadingPanel label="研究数据加载中" />
        <div className="grid min-w-0 gap-5 xl:grid-cols-2">
          <DataLoadingPanel label="净值图加载中" />
          <DataLoadingPanel label="水下曲线加载中" />
        </div>
      </div>
    );
  }

  if (reportData.status === "error") {
    return (
      <section className="border border-red-900/20 bg-paper p-5">
        <p className="font-semibold text-red-900">研究数据加载失败</p>
        <p className="mt-2 text-sm text-ink/65">{reportData.error}</p>
      </section>
    );
  }

  const strategy = reportData.data;
  const hasResearchCandidates = strategy.candidateComparisonGroups.research.length > 0;
  const currentCandidateId =
    strategy.candidateComparisonGroups.primary.find((id) => strategyId.endsWith(id.toLowerCase())) ??
    strategy.candidateComparisonGroups.primary[0];
  const selectedCandidateIds =
    comparisonScope === "research" && hasResearchCandidates
      ? [currentCandidateId, ...strategy.candidateComparisonGroups.research]
      : strategy.candidateComparisonGroups.primary;
  const selectedIdSet = new Set(selectedCandidateIds);
  const candidateMetrics = strategy.candidateMetrics.filter((candidate) => selectedIdSet.has(candidate.id));
  const candidateNames = candidateMetrics.map((candidate) => candidate.name);
  const monthlyStats = strategy.monthlyStats.filter((row) => selectedIdSet.has(row.id));

  return (
    <div className="min-w-0 space-y-5">
      {strategy.strategyBrief ? <StrategyBriefPanel brief={strategy.strategyBrief} /> : null}
      {strategy.benchmarkScorecard ? <BenchmarkScorecardPanel scorecard={strategy.benchmarkScorecard} /> : null}
      <MetricCardGrid metrics={candidateMetrics} cards={strategy.highlightCards} />
      <CandidateTable
        metrics={candidateMetrics}
        comparisonScope={hasResearchCandidates ? comparisonScope : undefined}
        onComparisonScopeChange={hasResearchCandidates ? setComparisonScope : undefined}
      />
      <div className="grid min-w-0 gap-5 xl:grid-cols-2">
        <Suspense
          fallback={
            <>
              <DataLoadingPanel label="净值图加载中" />
              <DataLoadingPanel label="水下曲线加载中" />
            </>
          }
        >
          <NavChart series={strategy.navSeries} />
          <UnderwaterChart series={strategy.underwaterSeries} />
        </Suspense>
      </div>
      <AnnualReturnsPanel rows={strategy.annualReturns} candidateNames={candidateNames} />
      <MonthlyStatsPanel rows={monthlyStats} recentMonthlyRecords={strategy.recentMonthlyRecords} />
      <StressSummaryPanel summaries={strategy.stressSummaries} />
    </div>
  );
}
