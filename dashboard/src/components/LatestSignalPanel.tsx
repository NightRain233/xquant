import { RadioTower } from "lucide-react";
import { formatNumber, formatSignalState } from "../data/formatters";
import type { LatestSignal } from "../data/types";

type LatestSignalPanelProps = {
  signal: LatestSignal;
};

export function LatestSignalPanel({ signal }: LatestSignalPanelProps) {
  const signalOn = signal.btcSupertrendOn;

  return (
    <section className="border border-ink/15 bg-paper p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Latest signal</p>
          <h2 className="mt-2 text-xl font-semibold tracking-tight">最新 BTC 信号</h2>
        </div>
        <div
          className={`flex min-w-24 items-center justify-center gap-2 border px-3 py-2 text-sm font-semibold ${
            signalOn ? "border-accent/30 bg-accent/10 text-accent" : "border-amber-800/20 bg-amber-700/10 text-amber-800"
          }`}
        >
          <RadioTower size={16} strokeWidth={1.8} />
          {formatSignalState(signalOn)}
        </div>
      </div>

      <dl className="mt-6 grid gap-px overflow-hidden border border-ink/10 bg-ink/10 sm:grid-cols-3">
        <div className="bg-paper p-4">
          <dt className="font-mono text-xs uppercase tracking-[0.14em] text-ink/45">Date</dt>
          <dd className="mt-2 font-mono text-lg">{signal.latestDate}</dd>
        </div>
        <div className="bg-paper p-4">
          <dt className="font-mono text-xs uppercase tracking-[0.14em] text-ink/45">BTC close</dt>
          <dd className="mt-2 font-mono text-lg">{formatNumber(signal.btcClose)}</dd>
        </div>
        <div className="bg-paper p-4">
          <dt className="font-mono text-xs uppercase tracking-[0.14em] text-ink/45">SuperTrend line</dt>
          <dd className="mt-2 font-mono text-lg">{formatNumber(signal.btcSupertrendLine)}</dd>
        </div>
      </dl>
    </section>
  );
}
