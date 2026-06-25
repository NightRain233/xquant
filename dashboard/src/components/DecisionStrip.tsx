import { Activity, ShieldAlert } from "lucide-react";
import type { StrategyPackage } from "../data/types";

type DecisionStripProps = {
  strategy: StrategyPackage;
};

export function DecisionStrip({ strategy }: DecisionStripProps) {
  return (
    <section className="grid gap-px overflow-hidden border border-ink/15 bg-ink/15 md:grid-cols-[1.4fr_1fr_1fr]">
      <div className="bg-paper p-5">
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-ink/50">Current conclusion</p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-ink">{strategy.recommendation.headline}</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/68">{strategy.recommendation.summary}</p>
      </div>
      <div className="bg-paper p-5">
        <div className="flex items-center gap-2 text-accent">
          <Activity size={18} strokeWidth={1.8} />
          <p className="text-sm font-semibold">建议纸面跟踪</p>
        </div>
        <p className="mt-3 text-sm leading-6 text-ink/65">
          首批观察：{strategy.recommendation.preferredPaperCaps.join(" / ")}
        </p>
      </div>
      <div className="bg-paper p-5">
        <div className="flex items-center gap-2 text-amber-700">
          <ShieldAlert size={18} strokeWidth={1.8} />
          <p className="text-sm font-semibold">暂不实盘</p>
        </div>
        <p className="mt-3 text-sm leading-6 text-ink/65">
          {strategy.recommendation.growthCandidateCap} 是进攻观察，不是默认上仓位。
        </p>
      </div>
    </section>
  );
}
