import { CandidateTable } from "../components/CandidateTable";
import { MetricCardGrid } from "../components/MetricCardGrid";
import { NavChart } from "../components/NavChart";
import { StressSummaryPanel } from "../components/StressSummaryPanel";
import { UnderwaterChart } from "../components/UnderwaterChart";
import type { StrategyPackage } from "../data/types";

type ResearchReportPageProps = {
  strategy: StrategyPackage;
};

export function ResearchReportPage({ strategy }: ResearchReportPageProps) {
  return (
    <div className="min-w-0 space-y-5">
      <MetricCardGrid metrics={strategy.candidateMetrics} />
      <CandidateTable metrics={strategy.candidateMetrics} />
      <div className="grid min-w-0 gap-5 xl:grid-cols-2">
        <NavChart series={strategy.navSeries} />
        <UnderwaterChart series={strategy.underwaterSeries} />
      </div>
      <StressSummaryPanel summaries={strategy.stressSummaries} />
    </div>
  );
}
