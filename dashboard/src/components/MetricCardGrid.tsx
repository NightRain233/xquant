import { formatInteger, formatPercent, formatRatio } from "../data/formatters";
import type { CandidateMetric } from "../data/types";

type MetricCardGridProps = {
  metrics: CandidateMetric[];
};

export function MetricCardGrid({ metrics }: MetricCardGridProps) {
  const historicalWinner = metrics[metrics.length - 1];
  const balancedCandidate = metrics.find((metric) => metric.name.includes("7.5")) ?? historicalWinner;

  const cards = [
    {
      label: "历史收益最高",
      value: historicalWinner.name,
      detail: `年化 ${formatPercent(historicalWinner.annualReturn)} / Calmar ${formatRatio(historicalWinner.calmar)}`
    },
    {
      label: "首批纸面跟踪",
      value: balancedCandidate.name,
      detail: `最大回撤 ${formatPercent(balancedCandidate.maxDrawdown)} / -10% 天数 ${formatInteger(
        balancedCandidate.daysBelowTenDrawdown ?? 0
      )}`
    },
    {
      label: "基准策略",
      value: metrics[0].name,
      detail: `年化 ${formatPercent(metrics[0].annualReturn)} / 最大回撤 ${formatPercent(metrics[0].maxDrawdown)}`
    }
  ];

  return (
    <section className="grid gap-px overflow-hidden border border-ink/15 bg-ink/15 lg:grid-cols-[1.1fr_1fr_1fr]">
      {cards.map((card) => (
        <div key={card.label} className="bg-paper p-5">
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">{card.label}</p>
          <p className="mt-3 text-xl font-semibold tracking-tight">{card.value}</p>
          <p className="mt-2 font-mono text-sm text-ink/62">{card.detail}</p>
        </div>
      ))}
    </section>
  );
}
