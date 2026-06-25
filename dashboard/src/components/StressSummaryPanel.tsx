import { formatInteger, formatPercent, formatRatio } from "../data/formatters";
import type { StressSummary } from "../data/types";

type StressSummaryPanelProps = {
  summaries: StressSummary[];
};

export function StressSummaryPanel({ summaries }: StressSummaryPanelProps) {
  return (
    <section className="space-y-5">
      {summaries.map((summary) => (
        <StressSummaryBlock key={summary.id} summary={summary} />
      ))}
    </section>
  );
}

function StressSummaryBlock({ summary }: { summary: StressSummary }) {
  const rows = summary.rows;
  const columns = Object.keys(rows[0] ?? {});

  return (
    <section className="min-w-0 overflow-hidden border border-ink/15 bg-paper">
      <div className="border-b border-ink/10 p-5">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Stress evidence</p>
        <h2 className="mt-2 text-xl font-semibold tracking-tight">{summary.title}</h2>
      </div>
      <div className="w-full overflow-x-auto">
        <table className="min-w-[760px] border-collapse text-left text-sm">
          <thead className="bg-ink/[0.04] text-xs uppercase tracking-[0.12em] text-ink/48">
            <tr>
              {columns.map((column) => (
                <th key={column} className="px-5 py-3 font-medium">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-ink/10">
            {rows.map((row, index) => (
              <tr key={`${summary.id}-${index}`} className="transition hover:bg-ink/[0.03]">
                {columns.map((column) => (
                  <td key={column} className="px-5 py-4 font-mono">
                    {formatCellValue(column, row[column])}
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

function formatCellValue(key: string, value: string | number | boolean): string {
  if (typeof value === "boolean") {
    return value ? "True" : "False";
  }

  if (typeof value === "string") {
    return value;
  }

  if (key.toLowerCase().includes("days") || key.includes("天数") || key.includes("aum") || key.includes("trades")) {
    return formatInteger(value);
  }

  if (
    key.includes("收益") ||
    key.includes("回撤") ||
    key.includes("现金") ||
    key.includes("成本") ||
    key.toLowerCase().includes("participation") ||
    key.toLowerCase().includes("drag") ||
    key === "cap"
  ) {
    return formatPercent(value);
  }

  return formatRatio(value);
}
