import { formatPercent } from "../data/formatters";
import type { TargetWeightRow, TargetWeightSleeve } from "../data/types";

type TargetWeightsPanelProps = {
  rows: TargetWeightRow[];
  sleeves?: TargetWeightSleeve[];
};

export function TargetWeightsPanel({ rows, sleeves = [] }: TargetWeightsPanelProps) {
  const assets = Object.keys(rows[0]?.weights ?? {});
  const lvtSleeve = sleeves.find((row) => row.sleeve === "LVT20");
  const lvtAssets = Object.entries(lvtSleeve?.weights ?? {}).filter(([, weight]) => weight > 1e-10);

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
      {lvtSleeve ? (
        <div className="border-t border-ink/15">
          <div className="p-5">
            <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Sleeve attribution</p>
            <h3 className="mt-2 text-lg font-semibold tracking-tight">LVT20 袖层拆解</h3>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-ink/62">
              同一资产可能同时属于 Core 和 LVT；上方组合总权重会合并同名 ETF，因此这里单独列出 LVT
              内部目标及其折算后的组合贡献。
            </p>
          </div>
          <div className="w-full overflow-x-auto border-t border-ink/10">
            <table className="min-w-[560px] border-collapse text-left text-sm">
              <thead className="bg-ink/[0.04] text-xs uppercase tracking-[0.12em] text-ink/48">
                <tr>
                  <th className="px-5 py-3 font-medium">资产</th>
                  <th className="px-4 py-3 font-medium">LVT 内部目标</th>
                  <th className="px-4 py-3 font-medium">组合贡献</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink/10">
                {lvtAssets.map(([asset, weight]) => (
                  <tr key={asset} className="transition hover:bg-ink/[0.03]">
                    <td className="px-5 py-4 font-medium">{asset}</td>
                    <td className="px-4 py-4 font-mono">{formatPercent(weight)}</td>
                    <td className="px-4 py-4 font-mono">{formatPercent(weight * lvtSleeve.allocation)}</td>
                  </tr>
                ))}
                <tr className="bg-ink/[0.025] font-semibold">
                  <td className="px-5 py-4">合计</td>
                  <td className="px-4 py-4 font-mono">
                    {formatPercent(lvtAssets.reduce((sum, [, weight]) => sum + weight, 0))}
                  </td>
                  <td className="px-4 py-4 font-mono">{formatPercent(lvtSleeve.allocation)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}
