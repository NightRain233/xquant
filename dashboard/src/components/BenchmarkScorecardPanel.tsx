import { Gauge, Scale } from "lucide-react";
import { formatPercent, formatRatio } from "../data/formatters";
import type { BenchmarkScorecard } from "../data/types";

type BenchmarkScorecardPanelProps = {
  scorecard: BenchmarkScorecard;
};

export function BenchmarkScorecardPanel({ scorecard }: BenchmarkScorecardPanelProps) {
  const conclusion = splitConclusion(scorecard.conclusion);

  return (
    <section className="min-w-0 overflow-hidden border border-ink/15 bg-paper">
      <div className="border-b border-ink/10 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Benchmark frame</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight">{scorecard.title}</h2>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            {scorecard.period ? (
              <div className="border border-ink/10 px-3 py-2 font-mono text-xs uppercase tracking-[0.12em] text-ink/55">
                回测窗口 {scorecard.period.startDate} - {scorecard.period.endDate}
              </div>
            ) : null}
            <div className="flex items-center gap-2 border border-ink/10 px-3 py-2 font-mono text-xs uppercase tracking-[0.12em] text-ink/55">
              <Scale className="size-4" />
              <span>Return / drawdown / path</span>
            </div>
          </div>
        </div>
        <p className="mt-4 max-w-4xl text-sm leading-6 text-ink/70">{scorecard.summary}</p>
      </div>

      <div className="w-full overflow-x-auto">
        <table className="min-w-[1120px] border-collapse text-left text-sm">
          <thead className="bg-ink/[0.04] text-xs uppercase tracking-[0.12em] text-ink/48">
            <tr>
              <th className="px-5 py-3 font-medium">角色</th>
              <th className="px-4 py-3 font-medium">对象</th>
              <th className="px-4 py-3 font-medium">年化</th>
              <th className="px-4 py-3 font-medium">最大回撤</th>
              <th className="px-4 py-3 font-medium">Sharpe</th>
              <th className="px-4 py-3 font-medium">Calmar</th>
              <th className="px-4 py-3 font-medium">判断</th>
              <th className="px-4 py-3 font-medium">说明</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink/10">
            {scorecard.rows.map((row) => (
              <tr key={`${row.role}-${row.name}`} className="transition hover:bg-ink/[0.03]">
                <td className="px-5 py-4 align-top">
                  <span className="inline-flex whitespace-nowrap items-center gap-2 border border-ink/10 px-2.5 py-1 font-mono text-xs uppercase tracking-[0.1em] text-ink/58">
                    <Gauge className="size-3.5" />
                    {row.role}
                  </span>
                </td>
                <td className="px-4 py-4 align-top font-medium text-ink">{row.name}</td>
                <td className="px-4 py-4 align-top font-mono">{formatMaybePercent(row.annualReturn)}</td>
                <td className="px-4 py-4 align-top font-mono">{formatMaybePercent(row.maxDrawdown)}</td>
                <td className="px-4 py-4 align-top font-mono">{formatMaybeRatio(row.sharpe)}</td>
                <td className="px-4 py-4 align-top font-mono">{formatMaybeRatio(row.calmar)}</td>
                <td className="px-4 py-4 align-top font-medium">{row.verdict}</td>
                <td className="px-4 py-4 align-top leading-6 text-ink/66">{row.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="border-t border-ink/10 p-5">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Conclusion</p>
        <h3 className="mt-2 text-lg font-semibold tracking-tight">结论</h3>
        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
          <div className="border-l-2 border-accent bg-ink/[0.025] px-4 py-3">
            <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">核心判断</p>
            <p className="mt-2 text-sm font-medium leading-6 text-ink/82">{conclusion.lead}</p>
          </div>

          {conclusion.points.length > 0 ? (
            <div className="border-y border-ink/10 py-3">
              <p className="px-1 font-mono text-xs uppercase tracking-[0.16em] text-ink/45">关键理由</p>
              <ol className="mt-2 divide-y divide-ink/10">
                {conclusion.points.map((point, index) => (
                  <li key={point} className="grid grid-cols-[2.5rem_minmax(0,1fr)] gap-3 py-3">
                    <span className="font-mono text-xs text-ink/42">{String(index + 1).padStart(2, "0")}</span>
                    <span className="text-sm leading-6 text-ink/72">{point}</span>
                  </li>
                ))}
              </ol>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function splitConclusion(conclusion: string): { lead: string; points: string[] } {
  const normalized = conclusion.replace(/^结论[:：]\s*/, "").trim();
  const parts = normalized
    .split(/[；。]/)
    .map((part) => part.trim())
    .filter(Boolean);

  return {
    lead: parts[0] ?? conclusion,
    points: parts.slice(1)
  };
}

function formatMaybePercent(value: number | undefined): string {
  return value === undefined ? "参考线" : formatPercent(value);
}

function formatMaybeRatio(value: number | undefined): string {
  return value === undefined ? "参考线" : formatRatio(value);
}
