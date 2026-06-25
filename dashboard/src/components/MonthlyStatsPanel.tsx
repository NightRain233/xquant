import { useState } from "react";
import { formatInteger, formatPercent, formatRatio } from "../data/formatters";
import type { MonthlyStat } from "../data/types";

type MonthlyStatsPanelProps = {
  rows: MonthlyStat[];
};

export function MonthlyStatsPanel({ rows }: MonthlyStatsPanelProps) {
  const [view, setView] = useState<"overview" | "table">("overview");
  const maxProfitFactor = Math.max(...rows.map((row) => row.profitFactor), 1);

  return (
    <section className="min-w-0 overflow-hidden border border-ink/15 bg-paper">
      <div className="flex flex-col gap-4 border-b border-ink/10 p-5 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Monthly diagnostics</p>
          <h2 className="mt-2 text-xl font-semibold tracking-tight">月度统计</h2>
        </div>
        <div className="inline-grid w-fit grid-cols-2 gap-1 border border-ink/15 bg-paper p-1">
          {[
            ["overview", "体验概览"],
            ["table", "表格"]
          ].map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`min-h-9 px-3 text-sm font-medium transition active:translate-y-px ${
                view === id ? "bg-ink text-paper" : "text-ink/65 hover:bg-ink/5"
              }`}
              onClick={() => setView(id as "overview" | "table")}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {view === "overview" ? (
        <div className="p-5">
          <h3 className="text-sm font-semibold text-ink">月度体验概览</h3>
          <p className="mt-2 text-sm leading-6 text-ink/62">每行压缩展示胜率、盈亏因子和月度极值，用来快速判断路径是否拿得住。</p>
          <div className="mt-5 space-y-4">
            {rows.map((row) => (
              <article key={row.id} className="border border-ink/10 bg-ink/[0.02] p-4">
                <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                  <h3 className="text-sm font-semibold">{row.name}</h3>
                  <p className="font-mono text-xs text-ink/55">
                    {formatInteger(row.winningMonths)} 盈利月 / {formatInteger(row.losingMonths)} 亏损月
                  </p>
                </div>
                <div className="mt-4 grid gap-4 md:grid-cols-[1fr_1fr_1fr]">
                  <MetricBar label="月度胜率" value={formatPercent(row.monthlyWinRate)} width={row.monthlyWinRate * 100} tone="green" />
                  <MetricBar label="盈亏因子" value={formatRatio(row.profitFactor)} width={(row.profitFactor / maxProfitFactor) * 100} tone="green" />
                  <div className="grid grid-cols-2 gap-px overflow-hidden border border-ink/10 bg-ink/10">
                    <div className="bg-paper p-3">
                      <p className="text-xs text-ink/45">最好月</p>
                      <p className="mt-1 font-mono text-sm font-semibold">{formatPercent(row.bestMonth)}</p>
                    </div>
                    <div className="bg-paper p-3">
                      <p className="text-xs text-ink/45">最差月</p>
                      <p className="mt-1 font-mono text-sm font-semibold">{formatPercent(row.worstMonth)}</p>
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </div>
      ) : (
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
      )}
    </section>
  );
}

type MetricBarProps = {
  label: string;
  value: string;
  width: number;
  tone: "green";
};

function MetricBar({ label, value, width }: MetricBarProps) {
  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-ink/45">{label}</p>
        <p className="font-mono text-sm font-semibold">{value}</p>
      </div>
      <div className="mt-2 h-2 overflow-hidden bg-ink/10">
        <div className="h-full bg-accent" style={{ width: `${Math.max(4, Math.min(width, 100))}%` }} />
      </div>
    </div>
  );
}
