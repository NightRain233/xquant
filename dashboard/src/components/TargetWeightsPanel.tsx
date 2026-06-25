import { formatPercent } from "../data/formatters";
import type { TargetWeightRow } from "../data/types";

type TargetWeightsPanelProps = {
  rows: TargetWeightRow[];
};

export function TargetWeightsPanel({ rows }: TargetWeightsPanelProps) {
  const assets = Object.keys(rows[0]?.weights ?? {});

  return (
    <section className="min-w-0 overflow-hidden border border-ink/15 bg-paper">
      <div className="border-b border-ink/10 p-5">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Target weights</p>
        <h2 className="mt-2 text-xl font-semibold tracking-tight">当前目标权重</h2>
      </div>
      <div className="w-full overflow-x-auto">
        <table className="min-w-[760px] border-collapse text-left text-sm">
          <thead className="bg-ink/[0.04] text-xs uppercase tracking-[0.12em] text-ink/48">
            <tr>
              <th className="px-5 py-3 font-medium">候选</th>
              {assets.map((asset) => (
                <th key={asset} className="px-4 py-3 font-medium">
                  {asset}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-ink/10">
            {rows.map((row) => (
              <tr key={row.candidate} className="transition hover:bg-ink/[0.03]">
                <td className="px-5 py-4 font-medium">{row.candidate}</td>
                {assets.map((asset) => (
                  <td key={asset} className="px-4 py-4 font-mono">
                    {formatPercent(row.weights[asset])}
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
