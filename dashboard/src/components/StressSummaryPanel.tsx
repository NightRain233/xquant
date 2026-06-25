import { formatPercent } from "../data/formatters";
import type { StressSummary } from "../data/types";

type StressSummaryPanelProps = {
  summaries: StressSummary[];
};

export function StressSummaryPanel({ summaries }: StressSummaryPanelProps) {
  const implementation = summaries.find((summary) => summary.id === "implementation");
  const rows = implementation?.rows ?? [];

  return (
    <section className="border border-ink/15 bg-paper">
      <div className="border-b border-ink/10 p-5">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Stress evidence</p>
        <h2 className="mt-2 text-xl font-semibold tracking-tight">执行压力测试</h2>
      </div>
      <div className="grid gap-px bg-ink/10 md:grid-cols-3">
        {rows.map((row) => (
          <div key={String(row.cap)} className="bg-paper p-5">
            <p className="font-mono text-xs uppercase tracking-[0.12em] text-ink/45">
              BTC cap {formatPercent(Number(row.cap), 1)}
            </p>
            <p className="mt-3 text-3xl font-semibold tracking-tight">{formatPercent(Number(row["通过率"]), 0)}</p>
            <p className="mt-2 text-sm leading-6 text-ink/62">
              54 个成本、滑点和执行延迟组合全部通过；最低年化{" "}
              <span className="font-mono text-ink">{formatPercent(Number(row["最低年化收益"]))}</span>
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
