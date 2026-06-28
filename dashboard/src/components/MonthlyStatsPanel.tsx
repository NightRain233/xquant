import { useState } from "react";
import { formatInteger, formatPercent, formatRatio } from "../data/formatters";
import type { MonthlyStat, RecentMonthlyRecord } from "../data/types";

type MonthlyStatsPanelProps = {
  rows: MonthlyStat[];
  recentMonthlyRecords: RecentMonthlyRecord[];
};

type MonthlyView = "overview" | "table" | "recent";

export function MonthlyStatsPanel({ rows, recentMonthlyRecords }: MonthlyStatsPanelProps) {
  const [view, setView] = useState<MonthlyView>("overview");
  const maxProfitFactor = Math.max(...rows.map((row) => row.profitFactor), 1);

  return (
    <section className="min-w-0 overflow-hidden border border-ink/15 bg-paper">
      <div className="flex flex-col gap-4 border-b border-ink/10 p-5 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Monthly diagnostics</p>
          <h2 className="mt-2 text-xl font-semibold tracking-tight">月度统计</h2>
        </div>
        <div className="inline-grid w-fit grid-cols-3 gap-1 border border-ink/15 bg-paper p-1">
          {[
            ["overview", "体验概览"],
            ["table", "汇总表"],
            ["recent", "近期 6 个月"]
          ].map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`min-h-9 px-3 text-sm font-medium transition active:translate-y-px ${
                view === id ? "bg-ink text-paper" : "text-ink/65 hover:bg-ink/5"
              }`}
              onClick={() => setView(id as MonthlyView)}
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
      ) : view === "table" ? (
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
      ) : (
        <RecentMonthlyView records={recentMonthlyRecords} />
      )}
    </section>
  );
}

function RecentMonthlyView({ records }: { records: RecentMonthlyRecord[] }) {
  if (records.length === 0) {
    return (
      <div className="p-5">
        <h3 className="text-sm font-semibold text-ink">近期 6 个月</h3>
        <p className="mt-2 text-sm leading-6 text-ink/62">近期月度数据暂不可用。</p>
      </div>
    );
  }

  return (
    <div className="p-5">
      <div className="flex flex-col gap-2 border-b border-ink/10 pb-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h3 className="text-sm font-semibold text-ink">近期 6 个月</h3>
          <p className="mt-2 text-sm leading-6 text-ink/62">展示默认纸面候选的月度收益与月末已执行持仓。</p>
        </div>
        <p className="font-mono text-xs text-ink/55">{records[0].strategy}</p>
      </div>
      <div className="divide-y divide-ink/10">
        {records.map((record) => {
          const visibleHoldings = Object.entries(record.holdings).filter(
            ([, weight]) => Number.isFinite(weight) && Math.abs(weight) > 1e-10
          );
          const returnTone = record.monthlyReturn >= 0 ? "text-accent" : "text-red-900";

          return (
            <article key={`${record.strategy}-${record.month}`} className="py-5">
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="flex items-center gap-3">
                  <p className="font-mono text-base font-semibold text-ink">{record.month}</p>
                  {record.isPartial ? (
                    <span className="border border-amber-800/20 bg-amber-700/10 px-2 py-1 text-xs font-medium text-amber-800">
                      截至 {formatMonthDay(record.monthEndDate)}
                    </span>
                  ) : null}
                </div>
                <div className="md:text-right">
                  <p className={`font-mono text-xl font-semibold ${returnTone}`}>
                    {formatPercent(record.monthlyReturn)}
                  </p>
                  <p className="mt-1 font-mono text-xs text-ink/48">月末 {record.monthEndDate}</p>
                </div>
              </div>
              {visibleHoldings.length > 0 ? (
                <div className="mt-4 grid grid-cols-1 gap-px border border-ink/10 bg-ink/10 md:grid-cols-2 xl:grid-cols-3">
                  {visibleHoldings.map(([asset, weight]) => (
                    <div key={asset} className="flex items-center justify-between gap-4 bg-paper px-3 py-2.5">
                      <span className="truncate text-sm text-ink/70" title={asset}>
                        {asset}
                      </span>
                      <span className="shrink-0 font-mono text-sm font-semibold">{formatPercent(weight)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-4 text-sm text-ink/55">暂无有效持仓。</p>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}

function formatMonthDay(date: string): string {
  const [, month, day] = date.split("-");
  return `${Number(month)}/${Number(day)}`;
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
