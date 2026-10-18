"""Frozen three-ETF attribution and robustness study. No parameter selection."""
from __future__ import annotations

import argparse
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
from xquant.three_asset_research import (drawdown_events, entry_recovery, performance,
                                        replay, rolling_windows)

SLUG = "three-asset-core-2026-10-03"
SYMBOLS = ["510300.SS", "513100.SS", "518880.SS"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=ROOT / "outputs/strategy-healthcheck-2026-10-02/market_data")
    parser.add_argument("--reference", type=Path, default=ROOT / "outputs/strategy-healthcheck-2026-10-02/next_open")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / SLUG)
    parser.add_argument("--benchmark-only", action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    frames = {s: pd.read_parquet(args.snapshot / f"{s}.parquet") for s in SYMBOLS}
    for frame in frames.values():
        assert frame.index.is_unique and frame.index.is_monotonic_increasing
        assert (frame[["Open", "Close"]] > 0).all().all()
    common = frames[SYMBOLS[0]].index
    union = common
    for frame in frames.values():
        common = common.intersection(frame.index)
        union = union.union(frame.index)
    close_common = pd.DataFrame({s: f.Close.reindex(common) for s, f in frames.items()})
    returns = close_common.pct_change(fill_method=None)
    # Reproduce activation and calendar of native replay, including Jan 1 valuation.
    dates = union[(union >= "2015-01-01") & (union <= "2026-09-30")]
    dates = dates.union(pd.DatetimeIndex(["2014-12-31", "2015-01-01"]))
    close = pd.DataFrame({s: f.Close.reindex(f.index.union(dates)).ffill().reindex(dates)
                          for s, f in frames.items()})
    opening = pd.DataFrame({s: f.Open.reindex(dates) for s, f in frames.items()})
    signal_dates = common[(common >= "2015-01-01") & (common <= "2026-09-30")][::10]
    positions = common.get_indexer(signal_dates) + 1
    valid = positions < len(common)
    signal_dates, execution_dates = signal_dates[valid], common[positions[valid]]

    def inverse(window):
        vol = returns.rolling(window).std(ddof=1).loc[signal_dates]
        inv = 1 / vol
        result = inv.div(inv.sum(axis=1), axis=0)
        result.index = execution_dates
        assert result.notna().all().all()
        return result

    def fixed(weight):
        return pd.DataFrame(np.tile(weight, (len(execution_dates), 1)), index=execution_dates, columns=SYMBOLS)

    base_targets = inverse(20)
    t0 = time.perf_counter()
    base = replay(opening, close, base_targets)
    kernel_seconds = time.perf_counter() - t0
    old = pd.read_csv(args.reference / "nav_RP_native.csv", index_col=0, parse_dates=True)
    assert old.index.equals(base[0].index), "Native valuation calendar differs"
    nav_error = float((base[0].nav - old.nav).abs().max())
    old_fills = pd.read_csv(args.reference / "fills_RP_native.csv", parse_dates=["actual_execution_date", "signal_date"])
    actual = base[2].set_index(["date", "symbol"]).sort_index()
    archived = old_fills.set_index(["actual_execution_date", "symbol"]).sort_index()
    assert actual.index.equals(archived.index)
    quantity_error = float(np.abs(actual.quantity_delta.to_numpy() - archived.quantity_delta.to_numpy()).max())
    cost_error = float(np.abs(base[0].cost.reindex(execution_dates).to_numpy() -
                              old_fills.groupby("actual_execution_date").commission.sum().reindex(execution_dates).to_numpy()).max())
    assert nav_error < 1e-5 and quantity_error < 1e-5 and cost_error < 1e-5
    assert (old_fills.signal_date < old_fills.actual_execution_date).all()
    audit = {"nav_max_abs_error": nav_error, "quantity_delta_max_abs_error": quantity_error,
             "group_cost_max_abs_error": cost_error, "kernel_seconds": kernel_seconds,
             "estimated_20_variants_seconds": 20 * kernel_seconds,
             "calendar_rows": len(dates), "common_rows": len(common), "signal_count": len(signal_dates),
             "max_daily_attribution_residual": float(base[0].pnl_residual.abs().max())}
    print(json.dumps(audit, indent=2), flush=True)
    (out / "preflight.json").write_text(json.dumps(audit, indent=2))
    if args.benchmark_only:
        return
    # Predeclared simple contrasts, never a search for optimal weights.
    targets = {"IV20": base_targets, "Equal": fixed([1/3]*3),
               "Fixed40_30_30": fixed([.4, .3, .3]), "Fixed30_40_30": fixed([.3, .4, .3]),
               "Fixed25_25_50": fixed([.25, .25, .5])}
    pre = (1 / returns.loc["2014"].std(ddof=1))
    targets["Fixed_pre2015"] = fixed((pre / pre.sum()).to_numpy())
    targets["Fixed_fullsample_mean_DIAGNOSTIC"] = fixed(base_targets.mean().to_numpy())
    for window in [10, 40, 60]:
        targets[f"IV{window}_sensitivity"] = inverse(window)
    # Phase shift keeps the original first activation, shifts only later signals.
    phase_signals = common[(common >= "2015-01-01") & (common <= "2026-09-30")][5::10]
    phase_pos = common.get_indexer(phase_signals) + 1
    phase_signals = phase_signals[phase_pos < len(common)]
    phase_exec = common[phase_pos[phase_pos < len(common)]]
    phase_vol = 1 / returns.rolling(20).std(ddof=1).loc[phase_signals]
    phase = phase_vol.div(phase_vol.sum(axis=1), axis=0)
    phase.index = phase_exec
    targets["IV20_phase5"] = pd.concat([base_targets.iloc[:1], phase]).sort_index()
    runs = {"IV20": base}
    for label, target in targets.items():
        if label not in runs:
            runs[label] = replay(opening, close, target)
        print(f"Completed {label}", flush=True)
    for label in ["IV20", "Equal", "Fixed25_25_50"]:
        for bps in [0, 20, 30]:
            key = f"{label}_cost{bps}"
            runs[key] = replay(opening, close, targets[label], cost_bps=bps)
        runs[f"{label}_gross10bps"] = replay(opening, close, targets[label], cost_mode="gross")
    # Buy-and-hold is a separate rebalancing hypothesis.
    runs["Equal_buy_hold"] = replay(opening, close, targets["Equal"].iloc[:1])
    runs["IV20_initial_buy_hold"] = replay(opening, close, base_targets.iloc[:1])
    summaries, months, years, rolling, event_rows, attribution, weight_rows, recoveries = [], [], [], [], [], [], [], []
    navs = pd.DataFrame({label: run[0].nav for label, run in runs.items()})
    for label, (daily, weights, trades) in runs.items():
        nav = daily.nav
        metrics = performance(nav)
        monthly = nav.resample("ME").last().pct_change().dropna()
        winners, losers = monthly[monthly > 0], monthly[monthly < 0]
        metrics.update({"strategy": label, "turnover_annual": daily.turnover.sum() / ((dates[-1]-dates[0]).days/365.25),
                        "fees_currency": daily.cost.sum(), "monthly_win_rate": (monthly > 0).mean(),
                        "average_winning_month": winners.mean(), "average_losing_month": losers.mean(),
                        "payoff_ratio": winners.mean()/abs(losers.mean()), "profit_factor": winners.sum()/abs(losers.sum()),
                        "best_month": monthly.max(), "worst_month": monthly.min()})
        events = drawdown_events(nav)
        metrics["average_drawdown_event_depth"] = events.depth.mean()
        metrics["longest_observed_underwater_days"] = events.underwater_calendar_days.max()
        summaries.append(metrics)
        event_rows.append(events.assign(strategy=label))
        months.extend({"strategy": label, "month": str(day.date()), "return": value} for day, value in monthly.items())
        ret = nav.pct_change().fillna(0)
        years.extend({"strategy": label, "year": year, "return": (1+group).prod()-1,
                      "partial": year in [2014, 2026]} for year, group in ret.groupby(ret.index.year) if year != 2014)
        for length in [3, 5]:
            table = rolling_windows(nav, length)
            table.to_csv(out / f"rolling_{label}_{length}y.csv", index=False)
            worst = table.loc[table.total_return.idxmin()].to_dict()
            rolling.append({"strategy": label, "years": length, "windows": len(table),
                            "negative_share": (table.total_return < 0).mean(), **worst})
        for symbol in SYMBOLS:
            weight_rows.append({"strategy": label, "symbol": symbol,
                                "average_close_weight_invested": weights.loc[execution_dates[0]:, symbol].mean(),
                                "latest_close_weight": weights[symbol].iloc[-1],
                                "minimum": weights.loc[execution_dates[0]:, symbol].min(), "maximum": weights[symbol].max()})
        if label in targets or label.endswith("buy_hold"):
            daily.to_csv(out / f"daily_{label}.csv")
            weights.to_csv(out / f"weights_{label}.csv")
            recovery = entry_recovery(nav)
            recovery.to_csv(out / f"entry_recovery_{label}.csv", index=False)
            completed = recovery.loc[~recovery.censored]
            recoveries.append({"strategy": label, "longest_completed_days": completed.calendar_days.max(),
                               "longest_unrecovered_observation_days": recovery.loc[recovery.censored, "calendar_days"].max(),
                               "censored_entries": int(recovery.censored.sum()),
                               "completed_median_days": completed.calendar_days.median()})
        if label == "IV20":
            trades.to_csv(out / "trades_IV20.csv", index=False)
        # Exact P&L attribution in original capital percentage points, including costs.
        for period, mask in [("full", daily.index > dates[0])] + [(str(y), daily.index.year == y) for y in range(2015, 2027)]:
            selected = daily.loc[mask]
            before = daily.nav.shift().loc[selected.index[0]]
            denominator = before if pd.notna(before) else 100000
            pieces = selected[SYMBOLS].sum() / denominator
            fee = -selected.cost.sum() / denominator
            attribution.append({"strategy": label, "period": period, **pieces.to_dict(), "cost": fee,
                                "net": selected.nav.iloc[-1]/denominator-1,
                                "residual": pieces.sum()+fee-(selected.nav.iloc[-1]/denominator-1)})
    navs.to_csv(out / "nav_all.csv")
    tables = {"summary": summaries, "monthly": months, "annual": years, "rolling_worst": rolling,
              "attribution": attribution, "weights_summary": weight_rows, "entry_recovery_summary": recoveries}
    for name, rows in tables.items():
        pd.DataFrame(rows).to_csv(out / f"{name}.csv", index=False)
    pd.concat(event_rows).to_csv(out / "drawdown_events.csv", index=False)
    base_targets.assign(signal_date=signal_dates).to_csv(out / "targets_IV20.csv")
    # Attribution to daily variance uses realized P&L, not inverse-vol labels.
    contributions = base[0][SYMBOLS].div(base[0].nav.shift(), axis=0).fillna(0)
    contributions["cost"] = -base[0].cost.div(base[0].nav.shift()).fillna(0)
    pr = base[0].nav.pct_change().fillna(0)
    pd.Series({s: contributions[s].cov(pr)/pr.var() for s in contributions}, name="variance_share").to_csv(out / "risk_contribution.csv")
    returns.loc["2015":].corr().to_csv(out / "asset_correlation.csv")
    asset_nav = close / close.iloc[0] * 100000
    pd.DataFrame([{"symbol": s, **performance(asset_nav[s])} for s in SYMBOLS]).to_csv(out / "asset_metrics.csv", index=False)
    # Benchmark alpha is descriptive regression versus the equal-weight portfolio.
    benchmark = navs.Equal.pct_change().dropna()
    alpha_rows = []
    scale = len(benchmark) / ((dates[-1]-dates[0]).days/365.25)
    for label in targets:
        r = navs[label].pct_change().dropna()
        beta = r.cov(benchmark)/benchmark.var()
        alpha_rows.append({"strategy": label, "beta_vs_equal": beta,
                           "arithmetic_alpha_zero_rf_annual": (r.mean()-beta*benchmark.mean())*scale,
                           "cagr_difference_vs_equal": performance(navs[label])["cagr"]-performance(navs.Equal)["cagr"]})
    pd.DataFrame(alpha_rows).to_csv(out / "benchmark_alpha.csv", index=False)
    # Deliberately hypothetical simultaneous shocks; no probabilities or forecasts.
    scenario_vectors = {"stocks_down_gold_flat": [-.35, -.45, 0],
                        "all_down": [-.30, -.40, -.20], "gold_down": [0, 0, -.30],
                        "nasdaq_premium_20_to_0": [0, 1/1.2-1, 0],
                        "cny_up10_nasdaq_usd_flat": [0, -.10, 0]}
    scenario_rows = []
    for label in ["IV20", "Equal", "Fixed25_25_50"]:
        for basis, weight in [("latest", runs[label][1].iloc[-1]),
                               ("historical_average", runs[label][1].loc[execution_dates[0]:].mean())]:
            for scenario, shock in scenario_vectors.items():
                loss = float(weight @ np.array(shock))
                row = {"strategy": label, "weight_basis": basis, "scenario": scenario,
                       "instant_return_before_cost": loss, "gain_needed_to_recover": 1/(1+loss)-1}
                for assumed in [.03, .05, .08]:
                    row[f"years_if_constant_{int(assumed*100)}pct"] = -np.log1p(loss)/np.log1p(assumed)
                scenario_rows.append(row)
    pd.DataFrame(scenario_rows).to_csv(out / "hypothetical_shocks.csv", index=False)
    stress = []
    for period, begin, end in [("2015_crash", "2015-06-12", "2015-08-26"),
                               ("2018", "2017-12-29", "2018-12-28"),
                               ("2020_covid", "2020-01-20", "2020-03-23"),
                               ("2022", "2021-12-31", "2022-12-30"),
                               ("2026_ytd", "2025-12-31", "2026-09-30"),
                               ("2026_q3", "2026-06-30", "2026-09-30")]:
        for label in ["IV20", "Equal", "Fixed25_25_50"]:
            selected = navs[label].loc[navs.index[navs.index <= begin][-1]:end]
            stress.append({"strategy": label, "period": period, "start": selected.index[0],
                           "end": selected.index[-1], "return": selected.iloc[-1]/selected.iloc[0]-1,
                           "within_window_mdd": (selected/selected.cummax()-1).min()})
    pd.DataFrame(stress).to_csv(out / "historical_stress.csv", index=False)
    subperiods = []
    for begin, end in [("2014-12-31", "2020-12-31"), ("2020-12-31", "2026-09-30"),
                       ("2015-12-31", "2026-09-30"), ("2014-12-31", "2023-12-29")]:
        for label in ["IV20", "Equal", "Fixed25_25_50", "Fixed_pre2015"]:
            selected = navs[label].loc[navs.index[navs.index <= begin][-1]:end]
            subperiods.append({"strategy": label, "start": selected.index[0], "end": selected.index[-1],
                               **performance(selected)})
    pd.DataFrame(subperiods).to_csv(out / "subperiods.csv", index=False)
    # Recovery in purchasing power is a scenario, not a downloaded CPI series.
    elapsed_years = (navs.index-navs.index[0]).days/365.25
    inflation_nav = navs.IV20 / np.power(1.02, elapsed_years)
    drawdown_events(inflation_nav).to_csv(out / "drawdowns_assumed_inflation2pct.csv", index=False)
    future_rows = []
    # Fixed beginning weights, annual resetting, zero costs: simple prolonged adverse arithmetic.
    # Even the optimistic no-cost version can lose for five years; these are not forecasts.
    for scenario, asset_rates in {"weak_all_assets": [-.02, -.05, -.03],
                                   "stocks_stagnant_gold_down": [0, 0, -.05],
                                   "zero_nominal": [0, 0, 0]}.items():
        weight = base[1].iloc[-1].to_numpy()
        annual_rate = float(weight @ np.array(asset_rates))
        future_rows.append({"scenario": scenario, "csi300_annual_assumed": asset_rates[0],
                            "nasdaq_annual_assumed": asset_rates[1], "gold_annual_assumed": asset_rates[2],
                            "portfolio_annual_before_cost": annual_rate,
                            "five_year_nominal": (1+annual_rate)**5-1,
                            "five_year_real_if_inflation2pct": ((1+annual_rate)/1.02)**5-1})
    pd.DataFrame(future_rows).to_csv(out / "hypothetical_five_year.csv", index=False)
    os.environ.setdefault("MPLCONFIGDIR", str(out / "mpl-cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
    for label in ["IV20", "Equal", "Fixed25_25_50", "Fixed_pre2015"]:
        axes[0].plot(navs.index, navs[label]/100000, label=label)
        axes[1].plot(navs.index, navs[label]/navs[label].cummax()-1, label=label)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("Growth (log scale)")
    axes[0].legend()
    axes[1].set_ylabel("Drawdown")
    axes[2].stackplot(base[1].index, base[1].to_numpy().T, labels=SYMBOLS)
    axes[2].set_ylabel("IV20 close weights")
    axes[2].legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(out / "comparison.png", dpi=150)
    plt.close(fig)
    inputs = [args.snapshot / f"{s}.parquet" for s in SYMBOLS] + [args.reference / f for f in
                ["nav_RP_native.csv", "fills_RP_native.csv", "config_RP_native.json"]]
    # Check these three frozen files against the previous coverage manifest.
    coverage_path = args.snapshot.parent / "data_coverage_and_revisions.csv"
    if coverage_path.exists():
        coverage = pd.read_csv(coverage_path).set_index("symbol")
        assert all(sha(args.snapshot/f"{s}.parquet") == coverage.loc[s, "sha256"] for s in SYMBOLS)
    sources = [Path(__file__), ROOT / "scripts/render_three_asset_review.py", ROOT / "scripts/verify_three_asset_delivery.py", ROOT / "src/xquant/three_asset_research.py",
               ROOT / "tests/test_three_asset_research.py", ROOT / "pyproject.toml", ROOT / "uv.lock"]
    with zipfile.ZipFile(out / "reproduction_bundle.zip", "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sources:
            bundle.write(path, str(path.relative_to(ROOT)))
        for path in inputs:
            folder = "market_data" if path.suffix == ".parquet" else "reference"
            bundle.write(path, f"inputs/{folder}/{path.name}")
    audit["total_seconds"] = time.perf_counter()-started
    audit["processes"] = 1
    audit["reason_single_process"] = "Array kernel is fast; process startup and duplicated data outweigh parallel benefit"
    (out / "validation.json").write_text(json.dumps(audit, indent=2))
    manifest = {"python": platform.python_version(), "packages": {p: importlib.metadata.version(p) for p in
                ["numpy", "pandas", "pyarrow", "matplotlib", "pytest"]},
                "inputs": {str(p): sha(p) for p in inputs}, "source": {str(p.relative_to(ROOT)): sha(p) for p in sources},
                "outputs": {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != "manifest.json"},
                "fixed_weights_pre2015": targets["Fixed_pre2015"].iloc[0].to_dict(),
                "fixed_fullsample_DIAGNOSTIC": base_targets.mean().to_dict(),
                "assumptions": {"signal_window": 20, "rebalance_sessions": 10, "cost": "half L1 including cash x10bps",
                                "valuation": "union of frozen ETF dates; missing close carried forward for valuation only",
                                "signal": "intersection of frozen ETF dates; next common open execution",
                                "start": "2014-12-31 cash 100000", "end": "2026-09-30"}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Finished in {audit['total_seconds']:.2f}s; saved {out}", flush=True)


if __name__ == "__main__":
    main()
