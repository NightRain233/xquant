import { useState } from "react";
import type { StrategyPackage } from "../data/types";
import { PaperTrackingPage } from "../pages/PaperTrackingPage";
import { ResearchReportPage } from "../pages/ResearchReportPage";
import { DecisionStrip } from "./DecisionStrip";
import { type DashboardMode, ModeTabs } from "./ModeTabs";

type AppShellProps = {
  strategy: StrategyPackage;
};

export function AppShell({ strategy }: AppShellProps) {
  const [mode, setMode] = useState<DashboardMode>("report");

  return (
    <div className="min-h-[100dvh] px-4 py-5 text-ink md:px-8 lg:px-10">
      <div className="mx-auto grid max-w-[1440px] gap-5 lg:grid-cols-[260px_1fr]">
        <aside className="border border-ink/15 bg-paper/85 p-5 lg:sticky lg:top-5 lg:h-[calc(100dvh-2.5rem)]">
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-ink/50">XQuant</p>
          <h1 className="mt-4 text-2xl font-semibold tracking-tight">{strategy.name}</h1>
          <p className="mt-3 text-sm leading-6 text-ink/62">策略研究驾驶舱</p>
          <div className="mt-6">
            <ModeTabs mode={mode} onModeChange={setMode} />
          </div>
          <div className="mt-8 border-t border-ink/10 pt-5">
            <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">As of</p>
            <p className="mt-2 font-mono text-sm text-ink/75">{strategy.asOfDate}</p>
          </div>
        </aside>

        <main className="space-y-5">
          <DecisionStrip strategy={strategy} />
          {mode === "report" ? (
            <ResearchReportPage strategy={strategy} />
          ) : (
            <PaperTrackingPage strategy={strategy} />
          )}
        </main>
      </div>
    </div>
  );
}
