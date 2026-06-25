import { useState } from "react";
import { AppShell } from "./components/AppShell";
import { StrategyHub } from "./components/StrategyHub";
import { useStrategyCatalog, useStrategyData } from "./data/useStrategyData";

export default function App() {
  const [selectedStrategyId, setSelectedStrategyId] = useState<string | null>(null);
  const catalogData = useStrategyCatalog();
  const strategyData = useStrategyData(selectedStrategyId);

  if (catalogData.status === "loading") {
    return (
      <main className="min-h-[100dvh] px-4 py-5 text-ink md:px-8">
        <div className="mx-auto max-w-[1440px] border border-ink/15 bg-paper p-6">
          <div className="h-3 w-36 animate-pulse bg-ink/15" />
          <div className="mt-5 h-8 w-80 max-w-full animate-pulse bg-ink/10" />
          <div className="mt-4 h-24 animate-pulse bg-ink/10" />
        </div>
      </main>
    );
  }

  if (catalogData.status === "error") {
    return (
      <main className="min-h-[100dvh] px-4 py-5 text-ink md:px-8">
        <div className="mx-auto max-w-[720px] border border-red-900/20 bg-paper p-6">
          <p className="font-semibold text-red-900">数据加载失败</p>
          <p className="mt-2 text-sm text-ink/65">{catalogData.error}</p>
        </div>
      </main>
    );
  }

  if (selectedStrategyId === null) {
    return <StrategyHub catalog={catalogData.catalog} onSelectStrategy={setSelectedStrategyId} />;
  }

  if (strategyData.status === "loading" || strategyData.status === "idle") {
    return (
      <main className="min-h-[100dvh] px-4 py-5 text-ink md:px-8">
        <div className="mx-auto max-w-[1440px] border border-ink/15 bg-paper p-6">
          <div className="h-3 w-36 animate-pulse bg-ink/15" />
          <div className="mt-5 h-8 w-80 max-w-full animate-pulse bg-ink/10" />
          <div className="mt-4 h-24 animate-pulse bg-ink/10" />
        </div>
      </main>
    );
  }

  if (strategyData.status === "error") {
    return (
      <main className="min-h-[100dvh] px-4 py-5 text-ink md:px-8">
        <div className="mx-auto max-w-[720px] border border-red-900/20 bg-paper p-6">
          <p className="font-semibold text-red-900">策略数据加载失败</p>
          <p className="mt-2 text-sm text-ink/65">{strategyData.error}</p>
          <button
            type="button"
            className="mt-5 border border-ink/15 px-3 py-2 text-sm font-medium transition hover:bg-ink/5 active:translate-y-px"
            onClick={() => setSelectedStrategyId(null)}
          >
            返回策略台账
          </button>
        </div>
      </main>
    );
  }

  return (
    <AppShell
      strategy={strategyData.strategy}
      strategies={catalogData.catalog.strategies}
      onSelectStrategy={setSelectedStrategyId}
      onBackToHub={() => setSelectedStrategyId(null)}
    />
  );
}
