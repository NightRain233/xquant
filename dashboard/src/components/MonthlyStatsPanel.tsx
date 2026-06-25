import { formatInteger, formatPercent, formatRatio } from "../data/formatters";
import type { MonthlyStat } from "../data/types";

type MonthlyStatsPanelProps = {
  rows: MonthlyStat[];
};

export function MonthlyStatsPanel({ rows }: MonthlyStatsPanelProps) {
  return (
    <section className="min-w-0 overflow-hidden border border-ink/15 bg-paper">
      <div className="border-b border-ink/10 p-5">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Monthly diagnostics</p>
        <h2 className="mt-2 text-xl font-semibold tracking-tight">月度统计</h2>
      </div>
      <div className="w-full overflow-x-auto">
        <table className="min-w-[860px] border-collapse text-left text-sm">
          <thead className="bg-ink/[0.04] text-xs uppercase tracking-[0.12em] text-ink/48">
            <tr>
              <th className="px-5 py-3 font-medium">策略</th>
              <th className="px-4 py-3 font-medium">总月数</th>
              <th className="px-4 py-3 font-medium">胜率</th>
              <th className="px-4 py-3 font-medium">盈利月</th>
              <th className="px-4 py-3 font-medium">亏损月</th>
              <th className="px-4 py-3 font-medium">平均盈利月</th>
              <th className="px-4 py-3 font-medium">平均亏损月</th>
              <th className="px-4 py-3 font-medium">盈亏因子</th>
              <th className="px-4 py-3 font-medium">最好月</th>
              <th className="px-4 py-3 font-medium">最差月</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink/10">
            {rows.map((row) => (
              <tr key={row.id} className="transition hover:bg-ink/[0.03]">
                <td className="px-5 py-4 font-medium">{row.name}</td>
                <td className="px-4 py-4 font-mono">{formatInteger(row.totalMonths)}</td>
                <td className="px-4 py-4 font-mono">{formatPercent(row.monthlyWinRate)}</td>
                <td className="px-4 py-4 font-mono">{formatInteger(row.winningMonths)}</td>
                <td className="px-4 py-4 font-mono">{formatInteger(row.losingMonths)}</td>
                <td className="px-4 py-4 font-mono">{formatPercent(row.averageWinningMonth)}</td>
                <td className="px-4 py-4 font-mono">{formatPercent(row.averageLosingMonth)}</td>
                <td className="px-4 py-4 font-mono">{formatRatio(row.profitFactor)}</td>
                <td className="px-4 py-4 font-mono">{formatPercent(row.bestMonth)}</td>
                <td className="px-4 py-4 font-mono">{formatPercent(row.worstMonth)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
