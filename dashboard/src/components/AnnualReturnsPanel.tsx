import { useState } from "react";
import { formatPercent } from "../data/formatters";
import type { AnnualReturnRow } from "../data/types";

type AnnualReturnsPanelProps = {
  rows: AnnualReturnRow[];
};

export function AnnualReturnsPanel({ rows }: AnnualReturnsPanelProps) {
  const [view, setView] = useState<"heatmap" | "table">("heatmap");
  const strategyNames = Object.keys(rows[0]?.values ?? {});
  const recentRows = rows.slice(-10);
  const values = recentRows.flatMap((row) => Object.values(row.values));
  const maxAbs = Math.max(...values.map((value) => Math.abs(value)), 0.01);

  function heatColor(value: number): string {
    const intensity = Math.min(Math.abs(value) / maxAbs, 1);

    if (value >= 0) {
      return `rgba(47, 111, 99, ${0.12 + intensity * 0.62})`;
    }

    return `rgba(155, 63, 53, ${0.12 + intensity * 0.62})`;
  }

  return (
    <section className="min-w-0 overflow-hidden border border-ink/15 bg-paper">
      <div className="flex flex-col gap-4 border-b border-ink/10 p-5 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Annual returns</p>
          <h2 className="mt-2 text-xl font-semibold tracking-tight">年度收益</h2>
        </div>
        <div className="inline-grid w-fit grid-cols-2 gap-1 border border-ink/15 bg-paper p-1">
          {[
            ["heatmap", "热力图"],
            ["table", "表格"]
          ].map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`min-h-9 px-3 text-sm font-medium transition active:translate-y-px ${
                view === id ? "bg-ink text-paper" : "text-ink/65 hover:bg-ink/5"
              }`}
              onClick={() => setView(id as "heatmap" | "table")}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {view === "heatmap" ? (
        <div className="p-5">
          <h3 className="text-sm font-semibold text-ink">年度收益热力图</h3>
          <p className="mt-2 text-sm leading-6 text-ink/62">绿色代表正收益，红色代表负收益，颜色越深代表幅度越大。</p>
          <div className="mt-5 w-full overflow-x-auto">
            <div className="grid min-w-[720px] gap-px bg-ink/10" style={{ gridTemplateColumns: `92px repeat(${strategyNames.length}, minmax(132px, 1fr))` }}>
              <div className="bg-paper p-3 font-mono text-xs uppercase tracking-[0.12em] text-ink/45">Year</div>
              {strategyNames.map((name) => (
                <div key={name} className="bg-paper p-3 text-xs font-semibold text-ink/70">
                  {name}
                </div>
              ))}
              {recentRows.map((row) => (
                <div key={row.year} className="contents">
                  <div className="bg-paper p-3 font-mono text-sm font-semibold">{row.year}</div>
                  {strategyNames.map((name) => (
                    <div
                      key={`${row.year}-${name}`}
                      className="p-3 font-mono text-sm font-semibold text-ink"
                      style={{ backgroundColor: heatColor(row.values[name]) }}
                    >
                      {formatPercent(row.values[name])}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="w-full overflow-x-auto">
          <table className="min-w-[720px] border-collapse text-left text-sm">
            <thead className="bg-ink/[0.04] text-xs uppercase tracking-[0.12em] text-ink/48">
              <tr>
                <th className="px-5 py-3 font-medium">年份</th>
                {strategyNames.map((name) => (
                  <th key={name} className="px-4 py-3 font-medium">
                    {name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-ink/10">
              {recentRows.map((row) => (
                <tr key={row.year} className="transition hover:bg-ink/[0.03]">
                  <td className="px-5 py-4 font-mono font-medium">{row.year}</td>
                  {strategyNames.map((name) => (
                    <td key={name} className="px-4 py-4 font-mono">
                      {formatPercent(row.values[name])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
