import { formatInteger, formatPercent, formatRatio } from "../data/formatters";
import type { CandidateMetric } from "../data/types";

type CandidateTableProps = {
  metrics: CandidateMetric[];
};

export function CandidateTable({ metrics }: CandidateTableProps) {
  const showCash = metrics.some((metric) => metric.averageCash !== undefined || metric.currentCash !== undefined);
  const showCost = metrics.some((metric) => metric.annualCostDrag !== undefined || metric.annualTurnover !== undefined);

  return (
    <section className="min-w-0 overflow-hidden border border-ink/15 bg-paper">
      <div className="border-b border-ink/10 p-5">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Candidate metrics</p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight">候选对比</h2>
      </div>
      <div className="w-full overflow-x-auto">
        <table className="min-w-[900px] border-collapse text-left text-sm">
          <thead className="bg-ink/[0.04] text-xs uppercase tracking-[0.12em] text-ink/48">
            <tr>
              <th className="px-5 py-3 font-medium">策略</th>
              <th className="px-4 py-3 font-medium">年化</th>
              <th className="px-4 py-3 font-medium">波动</th>
              <th className="px-4 py-3 font-medium">最大回撤</th>
              <th className="px-4 py-3 font-medium">Sharpe</th>
              <th className="px-4 py-3 font-medium">Calmar</th>
              <th className="px-4 py-3 font-medium">最长水下</th>
              <th className="px-4 py-3 font-medium">-10% 天数</th>
              {showCash ? <th className="px-4 py-3 font-medium">平均现金</th> : null}
              {showCost ? <th className="px-4 py-3 font-medium">成本/换手</th> : null}
            </tr>
          </thead>
          <tbody className="divide-y divide-ink/10">
            {metrics.map((metric) => (
              <tr key={metric.id} className="transition hover:bg-ink/[0.03]">
                <td className="px-5 py-4 font-medium text-ink">{metric.name}</td>
                <td className="px-4 py-4 font-mono">{formatPercent(metric.annualReturn)}</td>
                <td className="px-4 py-4 font-mono">{formatPercent(metric.annualVolatility)}</td>
                <td className="px-4 py-4 font-mono">{formatPercent(metric.maxDrawdown)}</td>
                <td className="px-4 py-4 font-mono">{formatRatio(metric.sharpe)}</td>
                <td className="px-4 py-4 font-mono">{formatRatio(metric.calmar)}</td>
                <td className="px-4 py-4 font-mono">{formatInteger(metric.longestUnderwaterDays ?? 0)}</td>
                <td className="px-4 py-4 font-mono">{formatInteger(metric.daysBelowTenDrawdown ?? 0)}</td>
                {showCash ? (
                  <td className="px-4 py-4 font-mono">{formatPercent(metric.averageCash ?? metric.currentCash ?? 0)}</td>
                ) : null}
                {showCost ? (
                  <td className="px-4 py-4 font-mono">
                    {metric.annualCostDrag !== undefined
                      ? formatPercent(metric.annualCostDrag)
                      : formatRatio(metric.annualTurnover ?? 0)}
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
