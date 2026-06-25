import { RadioTower } from "lucide-react";
import { formatNumber, formatSignalState } from "../data/formatters";
import type { LatestSignal } from "../data/types";

type LatestSignalPanelProps = {
  signal: LatestSignal;
};

export function LatestSignalPanel({ signal }: LatestSignalPanelProps) {
  const signalOn = signal.btcSupertrendOn ?? signal.stateTone === "positive";
  const rows =
    signal.rows ??
    [
      { label: "Date", value: signal.latestDate ?? "" },
      { label: "BTC close", value: formatNumber(signal.btcClose ?? 0) },
      { label: "SuperTrend line", value: formatNumber(signal.btcSupertrendLine ?? 0) }
    ];

  return (
    <section className="border border-ink/15 bg-paper p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Latest signal</p>
          <h2 className="mt-2 text-xl font-semibold tracking-tight">{signal.title ?? "最新 BTC 信号"}</h2>
        </div>
        <div
          className={`flex min-w-24 items-center justify-center gap-2 border px-3 py-2 text-sm font-semibold ${
            signalOn ? "border-accent/30 bg-accent/10 text-accent" : "border-amber-800/20 bg-amber-700/10 text-amber-800"
          }`}
        >
          <RadioTower size={16} strokeWidth={1.8} />
          {signal.stateLabel ?? formatSignalState(signalOn)}
        </div>
      </div>

      <dl className="mt-6 grid gap-px overflow-hidden border border-ink/10 bg-ink/10 sm:grid-cols-3">
        {rows.map((row) => (
          <div key={row.label} className="bg-paper p-4">
            <dt className="font-mono text-xs uppercase tracking-[0.14em] text-ink/45">{row.label}</dt>
            <dd className="mt-2 font-mono text-lg">{String(row.value)}</dd>
            {row.detail ? <dd className="mt-1 text-xs leading-5 text-ink/55">{row.detail}</dd> : null}
          </div>
        ))}
      </dl>
      <div className="mt-4 border border-ink/10 bg-ink/[0.03] p-4">
        <p className="text-sm font-semibold text-ink">不会自动实时更新</p>
        <p className="mt-2 text-sm leading-6 text-ink/62">
          当前面板读取的是已生成的研究输出文件。更新信号和权重需要先刷新研究产物，再运行{" "}
          <span className="font-mono text-ink">npm run build:data</span> 重新生成前端数据。
        </p>
      </div>
    </section>
  );
}
