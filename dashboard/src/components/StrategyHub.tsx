import { ArrowRight, Activity, ShieldAlert } from "lucide-react";
import type { StrategyCatalog } from "../data/types";

type StrategyHubProps = {
  catalog: StrategyCatalog;
  onSelectStrategy: (strategyId: string) => void;
};

function paperLabel(value: string): string {
  if (value === "recommended") {
    return "建议纸面跟踪";
  }

  if (value === "watch") {
    return "观察";
  }

  return "不适合跟踪";
}

function liveLabel(value: string): string {
  if (value === "ready") {
    return "可试运行";
  }

  if (value === "not-yet") {
    return "暂不实盘";
  }

  return "不适合实盘";
}

export function StrategyHub({ catalog, onSelectStrategy }: StrategyHubProps) {
  return (
    <main className="min-h-[100dvh] px-4 py-5 text-ink md:px-8 lg:px-10">
      <div className="mx-auto max-w-[1440px]">
        <header className="border border-ink/15 bg-paper/85 p-5 md:grid md:grid-cols-[260px_1fr] md:gap-8">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.18em] text-ink/50">XQuant</p>
            <h1 className="mt-4 text-2xl font-semibold tracking-tight">策略展示台账</h1>
          </div>
          <p className="mt-5 max-w-3xl text-sm leading-6 text-ink/65 md:mt-0">
            当前 dashboard 使用静态研究输出生成策略包。这里用于切换研究展示和纸面跟踪视图，不做自动行情刷新和后端调度。
          </p>
        </header>

        <section className="mt-5 grid gap-px overflow-hidden border border-ink/15 bg-ink/15 lg:grid-cols-2">
          {catalog.strategies.map((strategy) => (
            <article key={strategy.id} className="bg-paper p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">{strategy.asOfDate}</p>
                  <h2 className="mt-3 text-xl font-semibold tracking-tight">{strategy.name}</h2>
                </div>
                <button
                  type="button"
                  className="inline-flex min-h-10 items-center gap-2 border border-ink/15 px-3 text-sm font-medium transition hover:bg-ink/5 active:translate-y-px"
                  onClick={() => onSelectStrategy(strategy.id)}
                >
                  打开 {strategy.name}
                  <ArrowRight size={16} strokeWidth={1.8} />
                </button>
              </div>

              <p className="mt-4 text-lg font-semibold tracking-tight">{strategy.headline}</p>
              <p className="mt-3 text-sm leading-6 text-ink/65">{strategy.summary}</p>

              <div className="mt-5 grid gap-px overflow-hidden border border-ink/10 bg-ink/10 sm:grid-cols-2">
                <div className="bg-paper p-4">
                  <div className="flex items-center gap-2 text-accent">
                    <Activity size={17} strokeWidth={1.8} />
                    <p className="text-sm font-semibold">{paperLabel(strategy.paperTracking)}</p>
                  </div>
                </div>
                <div className="bg-paper p-4">
                  <div className="flex items-center gap-2 text-amber-700">
                    <ShieldAlert size={17} strokeWidth={1.8} />
                    <p className="text-sm font-semibold">{liveLabel(strategy.liveTrading)}</p>
                  </div>
                </div>
              </div>
            </article>
          ))}
        </section>
      </div>
    </main>
  );
}
