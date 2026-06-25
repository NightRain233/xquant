import { LatestSignalPanel } from "../components/LatestSignalPanel";
import { PaperRulesPanel } from "../components/PaperRulesPanel";
import { RiskReviewPanel } from "../components/RiskReviewPanel";
import { TargetWeightsPanel } from "../components/TargetWeightsPanel";
import type { StrategyPackage } from "../data/types";

type PaperTrackingPageProps = {
  strategy: StrategyPackage;
};

export function PaperTrackingPage({ strategy }: PaperTrackingPageProps) {
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
