"""Asset-pool ablation: two ETFs versus the frozen three-asset IV20 baseline."""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import time
import zipfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from xquant.three_asset_research import drawdown_events, performance, replay, rolling_windows

SLUG = "nasdaq-gold-ablation-2026-10-03"
SYMBOLS = ["510300.SS", "513100.SS", "518880.SS"]
PAIR = SYMBOLS[1:]
UV = "uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2"


def markdown(frame):
    data = frame.fillna("").astype(str)
    return "| " + " | ".join(map(str, data.columns)) + " |\n| " + " | ".join(["---"] * len(data.columns)) + " |\n" + "\n".join("| " + " | ".join(map(str, row)) + " |" for row in data.to_numpy())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=ROOT / "outputs/strategy-healthcheck-2026-10-02/market_data")
    parser.add_argument("--reference", type=Path, default=ROOT / "outputs/three-asset-core-2026-10-03")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / SLUG)
    args = parser.parse_args()
    start = time.perf_counter()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    frames = {s: pd.read_parquet(args.snapshot / f"{s}.parquet") for s in SYMBOLS}
    manifest = json.loads((args.reference / "manifest.json").read_text())
    for symbol in SYMBOLS:
        expected = next(h for p, h in manifest["inputs"].items() if Path(p).name == f"{symbol}.parquet")
        assert hashlib.sha256((args.snapshot / f"{symbol}.parquet").read_bytes()).hexdigest() == expected
    reference_nav = pd.read_csv(args.reference / "nav_all.csv", index_col=0, parse_dates=True).IV20
    schedule = pd.read_csv(args.reference / "targets_IV20.csv", index_col=0, parse_dates=True)
    executions = schedule.index
    signals = pd.DatetimeIndex(pd.to_datetime(schedule.signal_date))
    common = frames[SYMBOLS[0]].index
    for frame in frames.values():
        common = common.intersection(frame.index)
    common_closes = pd.DataFrame({s: f.Close.reindex(common) for s, f in frames.items()})
    returns = common_closes.pct_change(fill_method=None)
    dates = reference_nav.index
    closes = pd.DataFrame({s: f.Close.reindex(f.index.union(dates)).ffill().reindex(dates) for s, f in frames.items()})
    opens = pd.DataFrame({s: f.Open.reindex(dates) for s, f in frames.items()})
    assert (signals < executions).all()
    assert common[common.get_indexer(signals)+1].equals(executions)

    def inverse(symbols, window=20):
        inv = 1 / returns[symbols].rolling(window).std(ddof=1).loc[signals]
        result = inv.div(inv.sum(axis=1), axis=0)
        result.index = executions
        return result

    def fixed(values):
        return pd.DataFrame(np.tile(values, (len(executions), 1)), index=executions, columns=PAIR)

    targets = {"Three_IV20": inverse(SYMBOLS), "Two_IV20": inverse(PAIR), "Two_equal": fixed([.5, .5])}
    prior = 1 / returns.loc["2014", PAIR].std(ddof=1)
    targets["Two_fixed_pre2015"] = fixed((prior/prior.sum()).to_numpy())
    for window in [10, 40, 60]:
        targets[f"Two_IV{window}_sensitivity"] = inverse(PAIR, window)
    targets["Two_equal_buy_hold"] = targets["Two_equal"].iloc[:1]
    single_seconds = []
    runs = {}
    for label, target in targets.items():
        t0 = time.perf_counter()
        runs[label] = replay(opens[target.columns], closes[target.columns], target)
        single_seconds.append(time.perf_counter()-t0)
    baseline_error = float((runs["Three_IV20"][0].nav-reference_nav).abs().max())
    assert baseline_error < 1e-5
    assert np.allclose(targets["Two_IV20"], schedule[PAIR].div(schedule[PAIR].sum(axis=1), axis=0), atol=1e-12)
    print(f"Baseline error {baseline_error:.3g}; single replay {np.median(single_seconds):.3f}s", flush=True)
    for label in ["Three_IV20", "Two_IV20", "Two_equal"]:
        target = targets[label]
        runs[label+"_gross10bps"] = replay(opens[target.columns], closes[target.columns], target, cost_mode="gross")
    summary, rolling, annual, monthly, event_rows, weights_rows, attribution, subperiods = [], [], [], [], [], [], [], []
    nav_all = pd.DataFrame({label: run[0].nav for label, run in runs.items()})
    for label, (daily, weights, trades) in runs.items():
        nav = daily.nav
        months = nav.resample("ME").last().pct_change().dropna()
        winners, losers = months[months>0], months[months<0]
        events = drawdown_events(nav)
        completed = events[~events.censored]
        row = {"strategy": label, **performance(nav), "monthly_win_rate": (months>0).mean(),
               "winning_month_mean": winners.mean(), "losing_month_mean": losers.mean(),
               "payoff_ratio": winners.mean()/abs(losers.mean()), "profit_factor": winners.sum()/abs(losers.sum()),
               "best_month": months.max(), "worst_month": months.min(),
               "longest_completed_recovery_days": completed.underwater_calendar_days.max(),
               "longest_censored_days": events.loc[events.censored, "underwater_calendar_days"].max(),
               "average_drawdown_depth": events.depth.mean(),
               "turnover_annual": daily.turnover.sum()/((dates[-1]-dates[0]).days/365.25),
               "current_drawdown": nav.iloc[-1]/nav.max()-1}
        summary.append(row)
        event_rows.append(events.assign(strategy=label))
        daily.to_csv(out / f"daily_{label}.csv")
        weights.to_csv(out / f"weights_{label}.csv")
        for symbol in weights:
            weights_rows.append({"strategy": label, "symbol": symbol,
                                 "average": weights.loc[executions[0]:, symbol].mean(),
                                 "latest": weights[symbol].iloc[-1], "max": weights[symbol].max()})
        for length in [3, 5]:
            table = rolling_windows(nav, length)
            table.to_csv(out/f"rolling_{label}_{length}y.csv", index=False)
            rolling.append({"strategy": label, "years": length, "windows": len(table),
                            "negative_share": (table.total_return<0).mean(), **table.loc[table.total_return.idxmin()].to_dict()})
        r = nav.pct_change().fillna(0)
        for year, group in r.groupby(r.index.year):
            if year == 2014:
                continue
            annual.append({"strategy": label, "year": year, "return": (1+group).prod()-1, "partial": year==2026})
        monthly.extend({"strategy": label, "month": day, "return": value} for day, value in months.items())
        for begin, end in [("2014-12-31", "2020-12-31"), ("2020-12-31", "2026-09-30"),
                           ("2014-12-31", "2023-12-29"), ("2025-12-31", "2026-09-30")]:
            selected = nav.loc[nav.index[nav.index<=begin][-1]:end]
            metrics = performance(selected)
            if (selected.index[-1]-selected.index[0]).days < 365:
                for key in ["cagr", "sharpe_zero_rf", "sortino_zero_target", "calmar"]:
                    metrics[key] = None
            subperiods.append({"strategy": label, "start": selected.index[0], "end": selected.index[-1], **metrics})
        for period, mask in [("full", daily.index>dates[0])] + [(str(y), daily.index.year==y) for y in range(2015, 2027)]:
            selected = daily.loc[mask]
            denominator = daily.nav.shift().loc[selected.index[0]]
            pnl = selected[weights.columns].sum()/denominator
            fee = -selected.cost.sum()/denominator
            net = selected.nav.iloc[-1]/denominator-1
            attribution.append({"strategy": label, "period": period, **pnl.to_dict(), "cost": fee, "net": net,
                                "residual": pnl.sum()+fee-net})
    nav_all.to_csv(out / "nav_all.csv")
    for name, rows in {"summary": summary, "rolling_worst": rolling, "annual": annual, "monthly": monthly,
                       "weights_summary": weights_rows, "attribution": attribution, "subperiods": subperiods}.items():
        pd.DataFrame(rows).to_csv(out/f"{name}.csv", index=False)
    pd.concat(event_rows).to_csv(out / "drawdown_events.csv", index=False)
    targets["Two_IV20"].assign(signal_date=signals).to_csv(out / "targets_Two_IV20.csv")
    # Pair-minus-three attribution is descriptive P&L difference, not causal alpha.
    diff = nav_all.Two_IV20.pct_change().fillna(0)-nav_all.Three_IV20.pct_change().fillna(0)
    monthly_compare = nav_all[["Two_IV20", "Three_IV20"]].resample("ME").last().pct_change().dropna()
    pd.Series({"daily_correlation": nav_all.Two_IV20.pct_change().corr(nav_all.Three_IV20.pct_change()),
               "tracking_error_annual": diff.std(ddof=1)*np.sqrt((len(dates)-1)/((dates[-1]-dates[0]).days/365.25)),
               "positive_month_share": (monthly_compare.Two_IV20 > monthly_compare.Three_IV20).mean()},
              name="diagnostic").to_csv(out / "relative_diagnostics.csv")
    benchmark = nav_all.Three_IV20.pct_change().dropna()
    annual_scale = len(benchmark)/((dates[-1]-dates[0]).days/365.25)
    alpha_rows = []
    for label in ["Two_IV20", "Two_equal", "Two_fixed_pre2015"]:
        r = nav_all[label].pct_change().dropna()
        beta = r.cov(benchmark)/benchmark.var()
        alpha_rows.append({"strategy": label, "beta_vs_three": beta,
                           "arithmetic_alpha_zero_rf_annual": (r.mean()-beta*benchmark.mean())*annual_scale})
    pd.DataFrame(alpha_rows).to_csv(out/"benchmark_alpha.csv", index=False)
    shocks = {"all_down": [-.30, -.40, -.20], "gold_down": [0, 0, -.30],
              "nasdaq_down_gold_flat": [0, -.45, 0], "csi_down_others_flat": [-.40, 0, 0],
              "nasdaq_and_gold_deep_down": [0, -.50, -.35]}
    scenario_rows = []
    for label in ["Three_IV20", "Two_IV20", "Two_equal"]:
        for basis, weight in [("latest", runs[label][1].iloc[-1]), ("average", runs[label][1].loc[executions[0]:].mean())]:
            weight = weight.reindex(SYMBOLS).fillna(0)
            for scenario, vector in shocks.items():
                loss = weight @ np.array(vector)
                scenario_rows.append({"strategy": label, "basis": basis, "scenario": scenario,
                                      "return_before_cost": loss, "gain_to_recover": 1/(1+loss)-1})
    pd.DataFrame(scenario_rows).to_csv(out/"hypothetical_shocks.csv", index=False)
    os.environ.setdefault("MPLCONFIGDIR", str(out/"mpl-cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    for label in ["Three_IV20", "Two_IV20", "Two_equal", "Two_fixed_pre2015"]:
        axes[0].plot(dates, nav_all[label]/100000, label=label)
        axes[1].plot(dates, nav_all[label]/nav_all[label].cummax()-1, label=label)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("Growth (log scale)")
    axes[0].legend()
    axes[1].set_ylabel("Drawdown")
    fig.tight_layout()
    fig.savefig(out/"comparison.png", dpi=150)
    plt.close(fig)
    # Precompute a plain report from outputs; no prose depends on unverified intuition.
    summary_frame = pd.DataFrame(summary).set_index("strategy")
    report_table = summary_frame.loc[["Three_IV20", "Two_IV20", "Two_equal", "Two_fixed_pre2015"],
                                     ["cagr", "max_drawdown", "volatility", "sharpe_zero_rf", "longest_completed_recovery_days"]].copy()
    for col in ["cagr", "max_drawdown", "volatility"]:
        report_table[col] = report_table[col].map(lambda x: f"{x:.2%}")
    report_table.sharpe_zero_rf = report_table.sharpe_zero_rf.map(lambda x: f"{x:.2f}")
    report_table = report_table.reset_index()
    worst = pd.DataFrame(rolling).query("strategy in ['Three_IV20', 'Two_IV20', 'Two_equal']").copy()
    for col in ["total_return", "cagr"]:
        worst[col] = worst[col].map(lambda x: f"{x:.2%}")
    year_table = pd.DataFrame(annual).query("strategy in ['Three_IV20', 'Two_IV20', 'Two_equal']").pivot(index="year", columns="strategy", values="return").map(lambda x: f"{x:.2%}").reset_index()
    data = {"total_seconds": time.perf_counter()-start, "median_single_replay_seconds": float(np.median(single_seconds)),
            "baseline_max_nav_error": baseline_error, "calendar_rows": len(dates), "signal_count": len(signals),
            "max_daily_attribution_residual": max(float(run[0].pnl_residual.abs().max()) for run in runs.values()),
            "processes": 1, "frozen_data_hashes_passed": 3}
    (out/"validation.json").write_text(json.dumps(data, indent=2))
    primary = summary_frame.loc["Two_IV20"]
    base = summary_frame.loc["Three_IV20"]
    pair_latest = runs["Two_IV20"][1].iloc[-1]
    report = f"""# 纳指与黄金两资产：去掉沪深300是否更好（2026-10-03）

**在这段样本里，去掉沪深300提高了收益、Sharpe和最差滚动收益，却加深了最大回撤。两资产是更集中于纳指与黄金的配置取舍，不能据此判断未来一定更好。** 主比较历史年化高{primary.cagr-base.cagr:.2%}（个百分点），最大回撤多损失{abs(primary.max_drawdown)-abs(base.max_drawdown):.2%}（个百分点）；基线仍保留20日，不根据10日敏感性改参数。

只改变资产池，基线是此前冻结三资产20日逆波动；同20日窗口、10共同交易日调仓、信号后共同次日开盘、分数份额、满仓、无杠杆、无趋势退出。复用三资产的信号/估值日历，不因少一个资产改变日期；样本2014-12-31现金起点至2026-09-30。主表沿用native半L1含现金×10bps成本，并列gross10bps实际买卖名义额收费对照。此为归一化复权价格研究，不是真实ETF成交或未来收益保证。

## 公平比较

{markdown(report_table)}

Two_IV20权重就是原三资产目标去掉沪深300后，对纳指/黄金重新归一化。这验证了只改变资产池，未同时调整窗口和时点。Two_equal是纳指/黄金50/50，在相同调仓日恢复比例。Two_fixed_pre2015仅用2014全年波动冻结，纳指/黄金比例{targets['Two_fixed_pre2015'].iloc[0,0]:.2%}/{targets['Two_fixed_pre2015'].iloc[0,1]:.2%}；它是事后指定、但不使用2015以后权重信息的结构对照，不构成事前注册样本外。敏感性只做10/40/60日，未搜固定权重、未选择历史赢家替换20日。

10万元在这段价格研究中，两资产逆波动变成约{runs['Two_IV20'][0].nav.iloc[-1]/10000:.2f}万元，三资产约{runs['Three_IV20'][0].nav.iloc[-1]/10000:.2f}万元。Sharpe从1.31到1.45，但Calmar从1.15到1.13，因此“风险调整表现全面改善”并不成立。两资产等权年化16.70%、回撤−18.16%，体现去掉沪深300本身的历史影响；两资产逆波动再改善了它的收益与回撤。两个层面的差值不能当作可相加的因果拆解。

2015–2020年，两资产逆波动年化16.42%，三资产16.99%；2021年至2026年9月则20.59%与14.43%。截至2023年底两资产也领先（14.51%与12.28%），说明优势不完全来自2024–2025，但后半样本的资产行情仍是主要原因。子区间属于事后稳定性检查，不是独立样本外。

## 最差滚动三年与五年

{markdown(worst[['strategy','years','start','end','total_return','cagr','negative_share']])}

使用实际日历年，终点回溯到三/五年前当日或之前最近估值；2123/1637个高度重叠窗口，不当成独立抽样。最差历史结果不是未来下限。回本按峰值到首次回到前高，日历天计；截至末日未修复区间单列删失，不填0天。全部事件在drawdown_events.csv，完整窗口CSV保留。

两资产最差三年累计+18.74%（年化5.90%），五年累计+72.31%（年化11.49%），分别好于三资产+6.40%/+60.99%；这是不同最差窗口的各自下包络，同时按统一具体日期比较需查看完整滚动CSV。native下最长回本两资产925天、三资产546天；实际买卖金额各收10bps时则928天、989天。**回本长短排名会随小额成本改变，稳妥结论是两种组合都曾需要约两三年等待，而非认定三资产总是更快回本。**

## 年度与归因

{markdown(year_table)}

2026只有前三季度。两资产收益仍来自纳指与黄金上涨，以及两者的历史分散作用；去掉沪深300既去掉其拖累，也去掉它未来反弹或独立行情可能提供的收益。由于是看过历史后提出资产池，不能把历史领先当成选池能力。attribution.csv是旧份额隔夜、新份额日内的金额P&L，除以初始/年度资本；它不是因果归因，不能从ETF序列拆出汇率、溢价与底层资产贡献。

Q3/Q5指标、月度盈亏、窗口敏感性、成本对照、2015–2020/2021–2026/截至2023年的子区间均已输出。对比两资产固定权重能判断逆波动与资产池各自带来的变化，不能仅把Two_IV20对Three_IV20的差值都叫逆波动优势。

## 未来不利情景

hypothetical_shocks.csv按各自当前及历史平均权重，比较相同人工冲击，无概率、无收益预测。纳指与黄金同时下跌时，两资产没有第三条价格路径分担；若沪深300独立下跌，删除它则确实减少损失。黄金不是现金，无趋势退出时两类资产都会继续持有。美元、人民币与黄金人民币报价、ETF溢价还可能削弱表面分散，冻结OHLC无法分解这些风险。两资产是海外股票/黄金倾向更强的配置；失去A股暴露是结构性取舍，而非历史收益排名能解决的偏好。

9月30日两资产实际收盘权重纳指{pair_latest.iloc[0]:.2%}、黄金{pair_latest.iloc[1]:.2%}。假定纳指−50%、黄金−35%、沪深300持平，则两资产约−44.04%，三资产约−24.28%；若三资产都跌（沪深300−30%、纳指−40%、黄金−20%），两资产与三资产约−32.05%与−31.13%，分散保护同样会减弱。假定沪深300单独−40%，三资产约−17.94%，两资产为0。情景只解释不同暴露，不声称任何组合存在可靠亏损上限。

纳指基金确有溢价风险，见[国泰官方风险公告](https://st.gtfund.com/report/2025/04/34b9b9ea1bfbff560811cc81b5f0faf7cdbe45ec/国泰基金管理有限公司关于纳斯达克100交易型开放式指数证券投资基金二级市场交易价格溢价风险提示公告.pdf)；黄金基金风险见[华安原始公告](https://www.huaan.com.cn/upload2010/2013/06/21/082816905_0_b7ca7b32-4cab-30a2-879c-37d153eefc3a.pdf)。这些文件支持风险种类，未用于假定未来冲击幅度。

## 验证与复现

三份冻结行情哈希与上轮manifest一致，重算Three_IV20最大NAV差{baseline_error:.3g}元；全部现金/盈亏加总残差最大{data['max_daily_attribution_residual']:.3g}元。单个核约{np.median(single_seconds):.2f}秒，全流程{data['total_seconds']:.1f}秒，复用已验证日历，单进程够用。使用uv固定包版本，未重新下载行情、未重跑BTC/multi。其两项交付缺口仍保留，不能称整体交付完成。

运行命令见 [README](../../outputs/{SLUG}/README.md)，图见[净值与回撤](../../outputs/{SLUG}/comparison.png)，[notebook](../../research/notebooks/{SLUG}-practice.ipynb)。自包含reproduction_bundle.zip含三份行情、上轮日历/目标/NAV/manifest、新脚本和共享核；可独立重算，避免ignored行情丢失。

历史收益最高的是两资产逆波动（预定主比较中），Sharpe也最高；三资产最大回撤更浅，Calmar略高。结构上两资产更简单，三资产保留不同地区股票暴露，没有一个选择同时在所有维度占优。样本优势主要来自删除表现较弱的A股、提高纳指与黄金暴露；未来失败模式是纳指与黄金同步长期低迷，或A股独立强势导致两资产错过收益。下一步以固定20日规则做前瞻对照，保留两资产和三资产基线，不继续按历史收益淘汰资产。
"""
    note = ROOT / "docs/notes" / f"{SLUG}-review.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(report)
    readme = f"""# 纳指/黄金资产池对照复现

完整报告：[研究note](../../docs/notes/{SLUG}-review.md)。先阅读原三组合报告理解费用与数据限制。

仓库根目录运行：

```sh
{UV} python scripts/review_nasdaq_gold.py
```

解压reproduction_bundle.zip到空目录后运行：

```sh
{UV} python scripts/review_nasdaq_gold.py --snapshot inputs/market_data --reference inputs/reference
```

完整输入均在包内，reference包含前轮manifest、targets_IV20、nav_all。参数敏感性只解释形状，无选择最优。summary与rolling_worst是主表；annual/monthly/subperiods解释样本时期，drawdown_events保存完整回本及未回本事件。hypothetical_shocks是人为情景，不是预测。manifest记录输入/源码/产物SHA和环境。notebook可读取已保存CSV，无需重新下载行情。native和gross10bps费用不得混用。
"""
    (out/"README.md").write_text(readme)
    cells = [{"cell_type": "markdown", "metadata": {}, "source": ["# 纳指/黄金与纯三组合\n", "同日历同执行，仅改变资产池。\n"]},
             {"cell_type": "code", "metadata": {"tags": ["repository-root-bootstrap"]}, "execution_count": None,
              "source": ["from pathlib import Path\n", "import pandas as pd\n", "ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / 'src/xquant').exists())\n", f"OUT = ROOT / 'outputs/{SLUG}'\n"], "outputs": []}]
    for file in ["summary.csv", "rolling_worst.csv", "annual.csv", "monthly.csv", "attribution.csv", "weights_summary.csv", "drawdown_events.csv", "subperiods.csv", "hypothetical_shocks.csv"]:
        cells.append({"cell_type": "code", "metadata": {}, "execution_count": None,
                      "source": [f"display(pd.read_csv(OUT / '{file}'))"], "outputs": []})
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None,
                  "source": ["from IPython.display import Image, display\n", "display(Image(filename=str(OUT / 'comparison.png')))"],
                  "outputs": [{"output_type": "display_data", "metadata": {}, "data": {"image/png": base64.b64encode((out/"comparison.png").read_bytes()).decode()}}]})
    for i, cell in enumerate(cells):
        cell["id"] = f"nasdaq-gold-{i:03d}"
    notebook = ROOT / "research/notebooks" / f"{SLUG}-practice.ipynb"
    notebook.parent.mkdir(parents=True, exist_ok=True)
    notebook.write_text(json.dumps({"cells": cells, "metadata": {"kernelspec": {"name": "python3", "language": "python", "display_name": "Python 3"}}, "nbformat": 4, "nbformat_minor": 5}, ensure_ascii=False, indent=1))
    sources = [Path(__file__), ROOT/"src/xquant/three_asset_research.py"]
    inputs = [args.snapshot/f"{s}.parquet" for s in SYMBOLS] + [args.reference/f for f in ["manifest.json", "targets_IV20.csv", "nav_all.csv"]]
    with zipfile.ZipFile(out/"reproduction_bundle.zip", "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sources + [note, notebook]:
            bundle.write(path, str(path.relative_to(ROOT)))
        for path in inputs:
            folder = "market_data" if path.suffix == ".parquet" else "reference"
            bundle.write(path, f"inputs/{folder}/{path.name}")
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    delivery = {"python": platform.python_version(), "packages": {p: importlib.metadata.version(p) for p in ["pandas","numpy","pyarrow","matplotlib"]},
                "inputs": {str(p): digest(p) for p in inputs}, "source": {str(p.relative_to(ROOT)): digest(p) for p in sources},
                "outputs": {p.name: digest(p) for p in out.iterdir() if p.is_file() and p.name != "manifest.json"},
                "report": {str(p.relative_to(ROOT)): digest(p) for p in [note, notebook]},
                "contract": {"asset_pool_only": True, "baseline": "Three_IV20", "signals": "reused three-asset calendar", "window": 20,
                             "rebalance_sessions": 10, "cost": "half-L1 including cash x10bps"}}
    (out/"manifest.json").write_text(json.dumps(delivery, indent=2))
    print(report_table.to_string(index=False))
    print(f"Saved {out}", flush=True)


if __name__ == "__main__":
    main()
