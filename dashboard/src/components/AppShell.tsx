import { useState } from "react";
import type { StrategyCatalogItem, StrategySummaryPackage } from "../data/types";
import { PaperTrackingPage } from "../pages/PaperTrackingPage";
import { ResearchReportPage } from "../pages/ResearchReportPage";
import { DecisionStrip } from "./DecisionStrip";
import { type DashboardMode, ModeTabs } from "./ModeTabs";

type AppShellProps = {
  strategy: StrategySummaryPackage;
  strategies: StrategyCatalogItem[];
  onSelectStrategy: (strategyId: string) => void;
  onBackToHub: () => void;
};

export function AppShell({ strategy, strategies, onSelectStrategy, onBackToHub }: AppShellProps) {
  const [mode, setMode] = useState<DashboardMode>("report");

  return (
    <div className="min-h-[100dvh] px-4 py-5 text-ink md:px-8 lg:px-10">
      <div className="mx-auto grid max-w-[1440px] gap-5 lg:grid-cols-[260px_1fr]">
        <aside className="border border-ink/15 bg-paper/85 p-5 lg:sticky lg:top-5 lg:h-[calc(100dvh-2.5rem)]">
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-ink/50">XQuant</p>
          <h1 className="mt-4 text-2xl font-semibold tracking-tight">{strategy.name}</h1>
          <p className="mt-3 text-sm leading-6 text-ink/62">策略研究驾驶舱</p>
          <div className="mt-6 border-t border-ink/10 pt-5">
            <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Strategies</p>
            <div className="mt-3 space-y-2">
              {strategies.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`w-full border px-3 py-2 text-left text-sm transition active:translate-y-px ${
                    item.id === strategy.id
                      ? "border-ink bg-ink text-paper"
                      : "border-ink/15 text-ink/68 hover:bg-ink/5"
                  }`}
                  onClick={() => onSelectStrategy(item.id)}
                >
                  {item.name}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="mt-3 text-sm font-medium text-ink/60 transition hover:text-ink active:translate-y-px"
              onClick={onBackToHub}
            >
              返回策略台账
            </button>
          </div>
          <div className="mt-6">
            <ModeTabs mode={mode} onModeChange={setMode} />
          </div>
          <div className="mt-8 border-t border-ink/10 pt-5">
            <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">As of</p>
            <p className="mt-2 font-mono text-sm text-ink/75">{strategy.asOfDate}</p>
          </div>
        </aside>

        <main className="min-w-0 space-y-5">
          <DecisionStrip strategy={strategy} />
          {mode === "report" ? (
            <ResearchReportPage strategyId={strategy.id} />
          ) : (
            <PaperTrackingPage strategyId={strategy.id} />
          )}
        </main>
      </div>
    </div>
  );
}
