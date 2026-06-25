import { formatPercent } from "../data/formatters";
import type { AnnualReturnRow } from "../data/types";

type AnnualReturnsPanelProps = {
  rows: AnnualReturnRow[];
};

export function AnnualReturnsPanel({ rows }: AnnualReturnsPanelProps) {
  const strategyNames = Object.keys(rows[0]?.values ?? {});
  const recentRows = rows.slice(-10);

  return (
    <section className="min-w-0 overflow-hidden border border-ink/15 bg-paper">
      <div className="border-b border-ink/10 p-5">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Annual returns</p>
        <h2 className="mt-2 text-xl font-semibold tracking-tight">年度收益</h2>
      </div>
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
    </section>
  );
}
