import { echarts, ReactEChartsCore } from "./EChartsCore";
import type { TimeSeriesPoint } from "../data/types";

type UnderwaterChartProps = {
  series: TimeSeriesPoint[];
};

export function UnderwaterChart({ series }: UnderwaterChartProps) {
  const names = Object.keys(series[0]?.values ?? {});
  const sampled = series.filter((_, index) => index % 8 === 0 || index === series.length - 1);

  return (
    <section className="border border-ink/15 bg-paper p-5">
      <div className="mb-4">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-ink/45">Drawdown</p>
        <h2 className="mt-2 text-xl font-semibold tracking-tight">水下曲线</h2>
      </div>
      <ReactEChartsCore
        echarts={echarts}
        notMerge
        style={{ height: 320, width: "100%" }}
        option={{
          color: ["#141412", "#2f6f63", "#8a6f2a", "#9b3f35"],
          grid: { left: 44, right: 18, top: 20, bottom: 42 },
          legend: { bottom: 0, type: "scroll" },
          tooltip: { trigger: "axis", valueFormatter: (value: number) => `${(value * 100).toFixed(2)}%` },
          xAxis: { type: "category", data: sampled.map((point) => point.date), axisLabel: { color: "#5e5a52" } },
          yAxis: {
            type: "value",
            axisLabel: { color: "#5e5a52", formatter: (value: number) => `${(value * 100).toFixed(0)}%` },
            splitLine: { lineStyle: { color: "#e3ded2" } }
          },
          series: names.map((name) => ({
            name,
            type: "line",
            showSymbol: false,
            areaStyle: { opacity: 0.08 },
            lineStyle: { width: 2 },
            data: sampled.map((point) => point.values[name])
          }))
        }}
      />
    </section>
  );
}
