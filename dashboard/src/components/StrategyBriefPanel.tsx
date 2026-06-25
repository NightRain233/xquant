import { AlertTriangle, BookOpen, Crosshair, Route } from "lucide-react";
import type { ReactNode } from "react";
import type { StrategyBrief } from "../data/types";

type StrategyBriefPanelProps = {
  brief: StrategyBrief;
};

export function StrategyBriefPanel({ brief }: StrategyBriefPanelProps) {
  return (
    <section className="min-w-0 overflow-hidden border border-ink/15 bg-paper">
      <div className="grid gap-px bg-ink/10 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="bg-paper p-5">
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Strategy brief</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight">策略说明</h2>
          <p className="mt-4 max-w-4xl text-base leading-7 text-ink/78">{brief.plainLanguage}</p>
          <div className="mt-5 grid gap-3 md:grid-cols-2">
            <BriefFact icon={<Crosshair className="size-4" />} label="目标" value={brief.objective} />
            <BriefFact icon={<AlertTriangle className="size-4" />} label="注意" value={brief.watchOut} />
          </div>
        </div>

        <div className="bg-paper p-5">
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Reader use</p>
          <div className="mt-3 flex items-start gap-3">
            <BookOpen className="mt-1 size-4 shrink-0 text-ink/55" />
            <p className="text-sm leading-6 text-ink/70">{brief.investorUse}</p>
          </div>
          <div className="mt-5 flex items-start gap-3">
            <Route className="mt-1 size-4 shrink-0 text-ink/55" />
            <ol className="space-y-2 text-sm leading-6 text-ink/72">
              {brief.mechanism.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>
          </div>
        </div>
      </div>

      {brief.methodology ? (
        <div className="border-t border-ink/10 p-5">
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Methodology</p>
          <div className="mt-3 grid gap-px overflow-hidden border border-ink/10 bg-ink/10 md:grid-cols-2 xl:grid-cols-4">
            {brief.methodology.map((item) => (
              <div key={item.label} className="bg-paper p-4">
                <p className="font-mono text-xs uppercase tracking-[0.12em] text-ink/45">{item.label}</p>
                <p className="mt-2 text-sm leading-6 text-ink/72">{item.value}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="border-t border-ink/10 p-5">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Glossary</p>
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-[repeat(auto-fit,minmax(180px,1fr))]">
          {brief.glossary.map((item) => (
            <div key={item.term} className="border border-ink/10 bg-paper p-4">
              <p className="font-semibold tracking-tight">{item.term}</p>
              <p className="mt-2 text-sm leading-6 text-ink/64">{item.definition}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

type BriefFactProps = {
  icon: ReactNode;
  label: string;
  value: string;
};

function BriefFact({ icon, label, value }: BriefFactProps) {
  return (
    <div className="border border-ink/10 p-4">
      <div className="flex items-center gap-2 font-mono text-xs uppercase tracking-[0.14em] text-ink/45">
        {icon}
        <span>{label}</span>
      </div>
      <p className="mt-3 text-sm leading-6 text-ink/72">{value}</p>
    </div>
  );
}
