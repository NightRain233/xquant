import { LatestSignalPanel } from "../components/LatestSignalPanel";
import { PaperRulesPanel } from "../components/PaperRulesPanel";
import { RiskReviewPanel } from "../components/RiskReviewPanel";
import { TargetWeightsPanel } from "../components/TargetWeightsPanel";
import { useStrategyPaperData } from "../data/useStrategyData";

type PaperTrackingPageProps = {
  strategyId: string;
};

function PaperLoadingPanel() {
  return (
    <section className="border border-ink/15 bg-paper p-5">
      <div className="h-3 w-32 animate-pulse bg-ink/15" />
      <div className="mt-4 h-6 w-56 max-w-full animate-pulse bg-ink/10" />
      <div className="mt-4 h-28 animate-pulse bg-ink/10" />
    </section>
  );
}

export function PaperTrackingPage({ strategyId }: PaperTrackingPageProps) {
  const paperData = useStrategyPaperData(strategyId);

  if (paperData.status === "loading" || paperData.status === "idle") {
    return (
      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <div className="min-w-0 space-y-5">
          <PaperLoadingPanel />
          <PaperLoadingPanel />
        </div>
        <PaperLoadingPanel />
      </div>
    );
  }

  if (paperData.status === "error") {
    return (
      <section className="border border-red-900/20 bg-paper p-5">
        <p className="font-semibold text-red-900">纸面跟踪数据加载失败</p>
        <p className="mt-2 text-sm text-ink/65">{paperData.error}</p>
      </section>
    );
  }

  const strategy = paperData.data;

  return (
    <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
      <div className="min-w-0 space-y-5">
        <LatestSignalPanel signal={strategy.latestSignal} />
        <TargetWeightsPanel rows={strategy.targetWeights} />
        <PaperRulesPanel rules={strategy.paperTradingRules} />
      </div>
      <RiskReviewPanel notes={strategy.riskNotes} />
    </div>
  );
}
