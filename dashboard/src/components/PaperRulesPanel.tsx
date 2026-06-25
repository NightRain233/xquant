import type { PaperTradingRule } from "../data/types";

type PaperRulesPanelProps = {
  rules: PaperTradingRule[];
};

export function PaperRulesPanel({ rules }: PaperRulesPanelProps) {
  return (
    <section className="border border-ink/15 bg-paper">
      <div className="border-b border-ink/10 p-5">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Operating rules</p>
        <h2 className="mt-2 text-xl font-semibold tracking-tight">纸面跟踪规则</h2>
      </div>
      <div className="divide-y divide-ink/10">
        {rules.map((rule) => (
          <div key={rule.item} className="grid gap-2 p-5 md:grid-cols-[180px_1fr]">
            <p className="text-sm font-semibold text-ink">{rule.item}</p>
            <p className="text-sm leading-6 text-ink/68">{rule.rule}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
