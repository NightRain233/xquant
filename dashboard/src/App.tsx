import { AppShell } from "./components/AppShell";
import { useStrategyData } from "./data/useStrategyData";

export default function App() {
  const data = useStrategyData();

  if (data.status === "loading") {
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

  if (data.status === "error") {
    return (
      <main className="min-h-[100dvh] px-4 py-5 text-ink md:px-8">
        <div className="mx-auto max-w-[720px] border border-red-900/20 bg-paper p-6">
          <p className="font-semibold text-red-900">数据加载失败</p>
          <p className="mt-2 text-sm text-ink/65">{data.error}</p>
        </div>
      </main>
    );
  }

  return <AppShell strategy={data.strategy} />;
}
