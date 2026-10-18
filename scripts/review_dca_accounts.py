"""Monthly cash-flow comparison: three ETFs, two ETFs, and CNY SPY proxy.

Frozen prices, common contribution schedule, causal asynchronous SPY execution.
Account cohorts and stopping contributions are independent, not parameter fitting.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import importlib.metadata
import json
import multiprocessing
import os
from pathlib import Path
import platform
import sys
import time
import zipfile

import exchange_calendars as xcals
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from xquant.cashflow_research import PreparedDcaMarket, account_summary, principal_loss_events, replay_dca
from xquant.three_asset_research import drawdown_events, performance

SLUG = "dca-comparison-2026-10-04"
CORE = ["510300.SS", "513100.SS", "518880.SS"]
STRATEGIES = ["Three", "Two", "SP500"]
UV = "uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 --with exchange-calendars==4.13.2"
WORK_MARKET = None
WORK_MONTHLY = None


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(snapshot, reference, timing="first", fx_lag_days=0, constant_fx=False, window=20):
    frames = {s: pd.read_parquet(snapshot/f"{s}.parquet") for s in [*CORE, "SPY", "CNY=X"]}
    old = pd.read_csv(reference/"nav_all.csv", index_col=0, parse_dates=True)
    # Value on calendar days too: a US drawdown during a Chinese holiday must
    # not disappear just because the domestic exchanges are closed.
    trading_dates = old.index[old.index >= "2015-01-05"]
    dates = pd.date_range(trading_dates[0], trading_dates[-1], freq="D")
    assert dates[-1] == pd.Timestamp("2026-09-30")
    common = frames[CORE[0]].index
    for s in CORE[1:]:
        common = common.intersection(frames[s].index)
    closes = pd.DataFrame({s: frames[s].Close.reindex(common) for s in CORE})
    returns = closes.pct_change(fill_method=None)
    frozen = pd.read_csv(reference/"targets_IV20.csv", index_col=0, parse_dates=True)
    signals = pd.DatetimeIndex(pd.to_datetime(frozen.signal_date))
    inv = 1/returns.rolling(20).std(ddof=1).loc[signals]
    calculated = inv.div(inv.sum(axis=1), axis=0)
    assert np.allclose(calculated, frozen[CORE], atol=1e-12)
    assert common[common.get_indexer(signals)+1].equals(frozen.index)
    if window != 20:
        inv = 1/returns.rolling(window).std(ddof=1).loc[signals]
        calculated = inv.div(inv.sum(axis=1), axis=0)
        calculated.index = frozen.index
    else:
        calculated = frozen[CORE]
    # Startup portfolio uses only Dec 31 visible history; later cohorts share
    # the frozen signal phase, not a newly chosen anchor for each account.
    previous = common[common < dates[0]][-1]
    bootstrap = 1/returns.loc[:previous].tail(window).std(ddof=1)
    bootstrap /= bootstrap.sum()
    target_series = pd.concat([pd.DataFrame([bootstrap.to_numpy()], index=[dates[0]], columns=CORE), calculated])
    three = target_series.reindex(target_series.index.union(dates)).sort_index().ffill().reindex(dates)
    two = three[CORE[1:]].div(three[CORE[1:]].sum(axis=1), axis=0)
    opening = pd.DataFrame({s: frames[s].Open.reindex(dates) for s in CORE})
    valuation_close = pd.DataFrame({s: frames[s].Close.reindex(frames[s].index.union(dates)).ffill().reindex(dates) for s in CORE})
    tradable = opening.notna().all(axis=1) & (opening>0).all(axis=1)
    month_indices, month_labels = [], []
    for period, values in pd.Series(np.arange(len(dates)), index=dates).loc[tradable].groupby(dates[tradable].to_period("M")):
        if timing == "middle":
            selected = values.loc[values.index.day>=15]
            position = int(selected.iloc[0])
        elif timing == "last":
            position = int(values.iloc[-1])
        else:
            position = int(values.iloc[0])
        month_indices.append(position)
        month_labels.append(str(period))
    month_indices = np.asarray(month_indices, dtype=int)
    # Exchange schedule includes daylight saving and early closes, built once.
    calendar = xcals.get_calendar("XNYS", start="2013-01-01", end="2026-10-02")
    spy = frames["SPY"]
    spy_schedule = calendar.schedule.reindex(spy.index)
    assert spy_schedule.open.notna().all() and spy_schedule.close.notna().all()
    us_open = pd.DatetimeIndex(spy_schedule.open).as_unit("ns").asi8
    us_close = pd.DatetimeIndex(spy_schedule.close).as_unit("ns").asi8+10**9
    fx = frames["CNY=X"]
    # Explicit inherited assumption, not a verified vendor bar cutoff.
    fx_available = (fx.index.tz_localize("UTC")+pd.Timedelta(days=1+fx_lag_days, seconds=1)).as_unit("ns").asi8
    valuation = (dates+pd.Timedelta(hours=15, seconds=2)).tz_localize("Asia/Shanghai").tz_convert("UTC").as_unit("ns").asi8
    release = (dates[month_indices]+pd.Timedelta(hours=9, minutes=29, seconds=59)).tz_localize("Asia/Shanghai").tz_convert("UTC").as_unit("ns").asi8
    spy_position = np.searchsorted(us_close, valuation, side="right")-1
    fx_position = np.searchsorted(fx_available, valuation, side="right")-1
    assert (spy_position>=0).all() and (fx_position>=0).all()
    entry_position = np.searchsorted(us_open, release, side="right")
    assert (entry_position<len(spy)).all()
    entry_at = us_open[entry_position]
    entry_fx_position = np.searchsorted(fx_available, entry_at, side="right")-1
    assert (entry_at>release).all()
    assert (fx_available[entry_fx_position]<entry_at).all()
    assert (us_close[spy_position]<valuation).all()
    fx_mark = fx.Close.to_numpy(float)[fx_position]
    fx_entry = fx.Close.to_numpy(float)[entry_fx_position]
    if constant_fx:
        constant = float(fx.Close.to_numpy(float)[entry_fx_position[0]])
        fx_mark = np.repeat(constant, len(dates))
        fx_entry = np.repeat(constant, len(month_indices))
    spy_marks = spy.Close.to_numpy(float)[spy_position]*fx_mark
    entry_cny = spy.Open.to_numpy(float)[entry_position]*fx_entry
    visible = np.searchsorted(valuation, entry_at, side="right")
    prepared = PreparedDcaMarket(dates, opening.to_numpy(float), valuation_close.to_numpy(float),
                                 three.to_numpy(float), two.to_numpy(float), dates.isin(frozen.index),
                                 spy_marks, month_indices, visible, entry_cny, month_labels)
    clock = pd.DataFrame({"month": month_labels, "release_at": pd.to_datetime(release, utc=True),
                          "spy_execution_at": pd.to_datetime(entry_at, utc=True), "spy_bar_label": spy.index[entry_position],
                          "fx_label_used": fx.index[entry_fx_position], "fx_available_at": pd.to_datetime(fx_available[entry_fx_position], utc=True),
                          "spy_open_usd_adjusted": spy.Open.to_numpy(float)[entry_position], "fx_used": fx_entry,
                          "first_visible_valuation_index": visible})
    quote_audit = pd.DataFrame({"date": dates, "valuation_at": pd.to_datetime(valuation, utc=True),
                               "spy_close_label": spy.index[spy_position], "spy_close_available_at": pd.to_datetime(us_close[spy_position], utc=True),
                               "fx_label": fx.index[fx_position], "fx_available_at": pd.to_datetime(fx_available[fx_position], utc=True),
                               "spy_close_usd_adjusted": spy.Close.to_numpy(float)[spy_position], "fx": fx_mark,
                               "spy_quote_cny": spy_marks})
    for symbol in CORE:
        position = frames[symbol].index.searchsorted(dates, side="right")-1
        quote_audit[f"{symbol}_close_label"] = frames[symbol].index[position]
    return prepared, clock, quote_audit


def worker_init(market, monthly):
    global WORK_MARKET, WORK_MONTHLY
    WORK_MARKET, WORK_MONTHLY = market, monthly


def calculate_cohort(task):
    strategy, start_month, stop_after = task
    daily, _ = replay_dca(WORK_MARKET, strategy, start_month=start_month, stop_after=stop_after, contribution=WORK_MONTHLY)
    summary = account_summary(daily)
    summary.update(strategy=strategy, start_month=WORK_MARKET.monthly_labels[start_month],
                   policy="continue" if stop_after is None else f"stop_after_{stop_after}")
    rolling = []
    if stop_after is None:
        for periods in [12, 36, 60]:
            last_month = start_month+periods-1
            if last_month >= len(WORK_MARKET.monthly_labels):
                continue
            terminal_period = pd.Period(WORK_MARKET.monthly_labels[last_month])
            selection = daily.loc[daily.index.to_period("M") <= terminal_period]
            row = account_summary(selection)
            row.update(strategy=strategy, start_month=WORK_MARKET.monthly_labels[start_month], months=periods)
            rolling.append(row)
    return summary, rolling


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=ROOT/"outputs/strategy-healthcheck-2026-10-02/market_data")
    parser.add_argument("--reference", type=Path, default=ROOT/"outputs/three-asset-core-2026-10-03")
    parser.add_argument("--output", type=Path, default=ROOT/"outputs"/SLUG)
    parser.add_argument("--monthly", type=float, default=10000.0)
    parser.add_argument("--workers", type=int, choices=[1,2], default=2)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    coverage = pd.read_csv(args.snapshot.parent/"data_coverage_and_revisions.csv").set_index("symbol")
    for symbol in [*CORE,"SPY","CNY=X"]:
        assert sha(args.snapshot/f"{symbol}.parquet") == coverage.loc[symbol,"sha256"]
    prepare_started = time.perf_counter()
    market, clock, quote_audit = prepare(args.snapshot, args.reference)
    preparation_seconds = time.perf_counter()-prepare_started
    clock.to_csv(out/"contribution_clock.csv", index=False)
    quote_audit.to_csv(out/"valuation_quotes.csv", index=False)
    main_runs, summaries, annual, monthly, events, unit_events = {}, [], [], [], [], []
    preflight = []
    for strategy in STRATEGIES:
        t0 = time.perf_counter()
        daily, trades = replay_dca(market, strategy, contribution=args.monthly)
        replay_seconds = time.perf_counter()-t0
        s0 = time.perf_counter()
        summary = account_summary(daily)
        summary_seconds = time.perf_counter()-s0
        summary.update(strategy=strategy, policy="continue", start_month=market.monthly_labels[0])
        preflight.append({"strategy":strategy,"replay_seconds":replay_seconds,"summary_seconds":summary_seconds})
        main_runs[strategy] = daily
        summaries.append(summary)
        daily.to_csv(out/f"account_{strategy}.csv")
        trades.to_csv(out/f"fills_{strategy}.csv", index=False)
        events.append(principal_loss_events(daily).assign(strategy=strategy))
        unit = pd.concat([pd.Series([1.0], index=[daily.index[0]-pd.Timedelta(days=1)]),daily.unit_nav])
        unit_events.append(drawdown_events(unit).assign(strategy=strategy))
        for year, group in daily.groupby(daily.index.year):
            position = daily.index.get_loc(group.index[0])
            beginning = daily.wealth.iloc[position-1] if position else 0.0
            beginning_unit = daily.unit_nav.iloc[position-1] if position else 1.0
            annual.append({"strategy":strategy,"year":year,"partial_year":year==2026,
                           "beginning_balance":beginning,"contribution":group.contribution.sum(),
                           "market_pnl":group.market_pnl.sum(),"trade_cost":group.cost.sum(),
                           "ending_balance":group.wealth.iloc[-1],"ending_profit":group.profit.iloc[-1],
                           "unit_return":group.unit_nav.iloc[-1]/beginning_unit-1})
        for period, group in daily.groupby(daily.index.to_period("M")):
            position = daily.index.get_loc(group.index[0])
            beginning = daily.wealth.iloc[position-1] if position else 0.0
            beginning_unit = daily.unit_nav.iloc[position-1] if position else 1.0
            monthly.append({"strategy":strategy,"month":str(period),"contribution":group.contribution.sum(),
                            "account_market_pnl_net_cost":group.wealth.iloc[-1]-beginning-group.contribution.sum(),
                            "unit_return":group.unit_nav.iloc[-1]/beginning_unit-1,
                            "profit_at_month_end":group.profit.iloc[-1]})
    projected = sum(x["replay_seconds"]+4*x["summary_seconds"] for x in preflight)*len(market.monthly_labels)
    performance_note = {"prepare_seconds":preparation_seconds,"main_preflight":preflight,
                        "estimated_serial_cohort_seconds":projected,"workers":args.workers,
                        "monthly_contribution":args.monthly,"months":len(market.monthly_labels),
                        "valuation_rows":len(market.dates),"data_hashes_passed":5}
    (out/"preflight.json").write_text(json.dumps(performance_note,indent=2))
    print(json.dumps(performance_note,indent=2),flush=True)
    pd.DataFrame(summaries).to_csv(out/"main_summary.csv",index=False)
    if args.preflight_only:
        return
    pd.DataFrame(annual).to_csv(out/"annual_accounts.csv",index=False)
    pd.DataFrame(monthly).to_csv(out/"monthly_accounts.csv",index=False)
    pd.concat(events).to_csv(out/"principal_loss_events.csv",index=False)
    pd.concat(unit_events).to_csv(out/"unit_drawdown_events.csv",index=False)
    tasks = [(s,m,None) for m in range(len(market.monthly_labels)) for s in STRATEGIES]
    tasks += [(s,m,12) for m in range(len(market.monthly_labels)-11) for s in STRATEGIES]
    cohorts, rolling = [], []
    cohort_started = time.perf_counter()
    if args.workers == 1:
        worker_init(market,args.monthly)
        iterator = map(calculate_cohort,tasks)
        for number,(row,windows) in enumerate(iterator,1):
            cohorts.append(row);rolling.extend(windows)
            if number%30==0 or number==len(tasks):
                print(f"Cohorts {number}/{len(tasks)}; {time.perf_counter()-cohort_started:.1f}s",flush=True)
    else:
        with ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context("spawn"),
                                 initializer=worker_init,initargs=(market,args.monthly)) as pool:
            futures=[pool.submit(calculate_cohort,task) for task in tasks]
            for number,future in enumerate(as_completed(futures),1):
                row,windows=future.result();cohorts.append(row);rolling.extend(windows)
                if number%30==0 or number==len(tasks):
                    print(f"Cohorts {number}/{len(tasks)}; {time.perf_counter()-cohort_started:.1f}s",flush=True)
    cohorts_frame=pd.DataFrame(cohorts).sort_values(["policy","start_month","strategy"])
    rolling_frame=pd.DataFrame(rolling).sort_values(["months","start_month","strategy"])
    cohorts_frame.to_csv(out/"cohort_accounts.csv",index=False)
    rolling_frame.to_csv(out/"rolling_dca_accounts.csv",index=False)
    statistics=[]
    for (months,strategy),group in rolling_frame.groupby(["months","strategy"]):
        worst=group.loc[group.profit_on_principal.idxmin()]
        statistics.append({"months":months,"strategy":strategy,"cohorts":len(group),
                           "negative_terminal_share":(group.profit<0).mean(),
                           "median_profit_ratio":group.profit_on_principal.median(),"worst_profit_ratio":worst.profit_on_principal,
                           "worst_start_month":worst.start_month,"worst_end":worst.end,
                           "worst_profit_currency":worst.profit,"worst_anytime_loss_ratio":group.worst_loss_ratio.min(),
                           "worst_anytime_loss_currency":group.worst_loss_amount.min(),
                           "median_xirr":group.xirr.median(),"worst_xirr":group.xirr.min(),
                           "longest_observed_principal_loss_days":max(group.longest_completed_principal_loss_days.max(),group.longest_censored_principal_loss_days.max()),
                           "not_recovered_at_end_share":(group.profit<0).mean()})
    pd.DataFrame(statistics).to_csv(out/"rolling_dca_summary.csv",index=False)
    # Plan sensitivity changes neither pool nor timing signal parameters.
    sensitivity=[]
    for timing in ["middle","last"]:
        alternative,_,_=prepare(args.snapshot,args.reference,timing=timing)
        for strategy in STRATEGIES:
            daily,_=replay_dca(alternative,strategy,contribution=args.monthly)
            sensitivity.append({"case":f"contribution_{timing}","strategy":strategy,**account_summary(daily)})
    for strategy in STRATEGIES:
        daily,_=replay_dca(market,strategy,contribution=args.monthly,fee_bps=30)
        sensitivity.append({"case":"gross_fee30bps","strategy":strategy,**account_summary(daily)})
        daily,_=replay_dca(market,strategy,contribution=args.monthly,stop_after=12)
        daily.to_csv(out/f"stop12_{strategy}.csv")
        sensitivity.append({"case":"stop_after12","strategy":strategy,**account_summary(daily)})
    for case,options in [("fx_cost25bps",{"fx_cost_bps":25}), ("fx_cost50bps",{"fx_cost_bps":50})]:
        daily,_=replay_dca(market,"SP500",contribution=args.monthly,**options)
        sensitivity.append({"case":case,"strategy":"SP500",**account_summary(daily)})
    for case,settings in [("fx_extra1day_lag",{"fx_lag_days":1}), ("fx_constant_currency_DIAGNOSTIC",{"constant_fx":True})]:
        alternative,_,_=prepare(args.snapshot,args.reference,**settings)
        daily,_=replay_dca(alternative,"SP500",contribution=args.monthly)
        sensitivity.append({"case":case,"strategy":"SP500",**account_summary(daily)})
    for window in [10,40,60]:
        alternative,_,_=prepare(args.snapshot,args.reference,window=window)
        for strategy in ["Three","Two"]:
            daily,_=replay_dca(alternative,strategy,contribution=args.monthly)
            sensitivity.append({"case":f"vol_window{window}_DIAGNOSTIC","strategy":strategy,**account_summary(daily)})
    pd.DataFrame(sensitivity).to_csv(out/"cashflow_sensitivity.csv",index=False)
    # Strategy TWR metrics do not mistake contributed principal for return.
    qmetrics=[]
    for strategy,daily in main_runs.items():
        unit=pd.concat([pd.Series([1.0],index=[daily.index[0]-pd.Timedelta(days=1)]),daily.unit_nav])
        metrics=performance(unit)
        monthly_unit=pd.Series([r["unit_return"] for r in monthly if r["strategy"]==strategy])
        wins,losses=monthly_unit[monthly_unit>0],monthly_unit[monthly_unit<0]
        metrics.update(strategy=strategy,monthly_win_rate=(monthly_unit>0).mean(),average_winning_month=wins.mean(),
                       average_losing_month=losses.mean(),payoff_ratio=wins.mean()/abs(losses.mean()),
                       profit_factor=wins.sum()/abs(losses.sum()),best_month=monthly_unit.max(),worst_month=monthly_unit.min())
        qmetrics.append(metrics)
    pd.DataFrame(qmetrics).to_csv(out/"unit_q3_q5_metrics.csv",index=False)
    benchmark=main_runs["SP500"].unit_nav.pct_change().dropna()
    alpha=[]
    annualization=len(benchmark)/((benchmark.index[-1]-benchmark.index[0]).days/365.25)
    for strategy in ["Three","Two"]:
        r=main_runs[strategy].unit_nav.pct_change().dropna()
        beta=r.cov(benchmark)/benchmark.var()
        alpha.append({"strategy":strategy,"beta_vs_cny_spy":beta,
                      "arithmetic_alpha_zero_rf_annual":(r.mean()-beta*benchmark.mean())*annualization})
    pd.DataFrame(alpha).to_csv(out/"benchmark_alpha.csv",index=False)
    # Visuals contrast account gains, invested principal, and flow-neutral losses.
    os.environ.setdefault("MPLCONFIGDIR",str(out/"mpl-cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,1,figsize=(11,10),sharex=True)
    for strategy,daily in main_runs.items():
        axes[0].plot(daily.index,daily.liquidation_wealth/10000,label=strategy)
        axes[1].plot(daily.index,daily.profit/10000,label=strategy)
        axes[2].plot(daily.index,daily.unit_drawdown,label=strategy)
    first=main_runs["Three"]
    axes[0].plot(first.index,first.principal/10000,"k--",label="Contributed principal")
    axes[0].set_ylabel("CNY 10,000; net exit")
    axes[0].legend()
    axes[1].axhline(0,color="black",linewidth=.7)
    axes[1].set_ylabel("Profit, CNY 10,000")
    axes[2].set_ylabel("Unit drawdown")
    fig.tight_layout();fig.savefig(out/"account_comparison.png",dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4),sharey=True)
    for ax,months in zip(axes,[36,60]):
        subset=rolling_frame[rolling_frame.months==months]
        for strategy in STRATEGIES:
            rows=subset[subset.strategy==strategy]
            ax.plot(pd.to_datetime(rows.start_month),rows.profit_on_principal,label=strategy)
        ax.axhline(0,color="black",linewidth=.7);ax.set_title(f"{months} monthly deposits");ax.legend()
    axes[0].set_ylabel("Net exit profit / principal")
    fig.tight_layout();fig.savefig(out/"cohort_comparison.png",dpi=150);plt.close(fig)
    validation={"elapsed_seconds":time.perf_counter()-started,"cohort_seconds":time.perf_counter()-cohort_started,
                "accounts":len(tasks),"rolling_windows":len(rolling_frame),"workers":args.workers,
                "max_main_account_residual":max(d.account_residual.abs().max() for d in main_runs.values()),
                "max_all_cohort_residual":float(cohorts_frame.max_account_residual.max()),
                "identical_main_cashflows":all(main_runs[s].contribution.equals(main_runs["Three"].contribution) for s in STRATEGIES),
                "initial_target_visible":"2014-12-31",
                "final_us_price_label":str(quote_audit.spy_close_label.iloc[-1]),
                "fx_clock_assumption":"D-label available at UTC D+1 00:00:01, vendor cutoff not verified"}
    (out/"validation.json").write_text(json.dumps(validation,indent=2))
    sources=[Path(__file__),ROOT/"src/xquant/cashflow_research.py",ROOT/"src/xquant/three_asset_research.py",
             ROOT/"tests/test_cashflow_research.py"]
    inputs=[args.snapshot/f"{s}.parquet" for s in [*CORE,"SPY","CNY=X"]]
    inputs += [args.snapshot.parent/"data_coverage_and_revisions.csv",args.reference/"targets_IV20.csv",args.reference/"nav_all.csv"]
    with zipfile.ZipFile(out/"reproduction_bundle.zip","w",zipfile.ZIP_DEFLATED) as bundle:
        for path in sources:
            bundle.write(path,str(path.relative_to(ROOT)))
        for path in inputs:
            if path.suffix==".parquet":
                destination=f"inputs/market_data/{path.name}"
            elif path.name=="data_coverage_and_revisions.csv":
                destination=f"inputs/{path.name}"
            else:
                destination=f"inputs/reference/{path.name}"
            bundle.write(path,destination)
    manifest={"python":platform.python_version(),"packages":{p:importlib.metadata.version(p) for p in ["pandas","numpy","pyarrow","matplotlib","exchange-calendars","pytest"]},
              "inputs":{str(p):sha(p) for p in inputs},"source":{str(p.relative_to(ROOT)):sha(p) for p in sources},
              "outputs":{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!="manifest.json"},
              "parameters":{"monthly":args.monthly,"workers":args.workers,"cutoff":"2026-09-30 Shanghai 15:00:02",
                            "trade_cost_bps":10,"fx_cost_bps":0,"settlement":"ideal instant fractional shares",
                            "contribution_rule":"first common domestic valid opening each calendar month, released one second earlier"}}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2))
    print(pd.DataFrame(summaries)[["strategy","principal","terminal_liquidation","profit","xirr","worst_loss_amount","worst_loss_ratio","unit_max_drawdown"]].to_string(index=False),flush=True)
    print(f"Completed {SLUG} in {validation['elapsed_seconds']:.1f}s",flush=True)


if __name__=="__main__":
    main()
