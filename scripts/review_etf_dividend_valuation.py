"""Frozen corporate-action accounting correction, fixed IV20 and calendar."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import sys
import time

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from xquant.etf_dividend_accounting import DividendMarket, distribution_returns, replay_dividend_account
from xquant.cashflow_research import account_summary, principal_loss_events, replay_dca
from xquant.three_asset_research import performance, drawdown_events, rolling_windows, replay
from review_domestic_etf_execution import load_provider, expand, target_series, prepared

SLUG="etf-dividend-valuation-2026-10-04"
CORE=["510300","513100","518880"]
MARKETS={}


def init_worker(markets):
    global MARKETS
    MARKETS=markets


def cohort_job(job):
    strategy,months=job
    market=MARKETS[strategy]
    rows=[]
    for start in range(len(market.deposits)-months+1):
        stop_month=start+months
        endpoint=market.dates[int(market.deposits[stop_month-1])]+pd.offsets.MonthEnd(0)
        stop=market.dates.searchsorted(endpoint,side="right")
        small=DividendMarket(market.dates[:stop],market.symbols,market.opening[:stop],market.closing[:stop],
                             market.targets[:stop],market.rebalance[:stop],market.actions,market.deposits[:stop_month])
        flows={int(i):10000. for i in small.deposits[start:stop_month]}
        daily,_,_=replay_dividend_account(small,flows=flows,start_index=int(market.deposits[start]),export_details=False)
        row=account_summary(daily)
        rows.append({"strategy":strategy,"months":months,"start_month_index":start,**row})
    return rows


def standard_actions(out):
    records=pd.read_csv(out/"dividend_events.csv",dtype={"fund_code":str})
    result=[]
    for row in records.to_dict("records"):
        announced=row.get("announcement_date")
        if not isinstance(announced,str) or not announced:
            match=re.search(r"510300_(\d{8})",row["official_evidence_url"])
            announced=pd.Timestamp(match[1]).date().isoformat() if match else {
                "2015-01-20":"2015-01-14","2016-01-20":"2016-01-14","2017-01-23":"2017-01-17"}[row["ex_date"]]
        result.append({"symbol":row["fund_code"],"action_type":"cash_dividend",
                       "announcement_date":announced,"record_date":row["record_date"],
                       "corporate_action_date":row["ex_date"],"effective_quote_date":row["ex_date"],
                       "pay_date":row["cash_payment_date"],"cash_per_share":float(row["cash_per_unit_cny"]),
                       "split_ratio":1.,"source_url":row["official_evidence_url"],"source_file":row["official_evidence_file"]})
    # Announcement of plans predates conversion; result notices merely confirm
    # exact ratios. Their same-day publication clocks are not invented.
    result.extend([
        {"symbol":"513100","action_type":"split","announcement_date":"2022-01-04","record_date":"2022-01-12",
         "corporate_action_date":"2022-01-13","effective_quote_date":"2022-01-14","pay_date":None,
         "cash_per_share":0.,"split_ratio":5.,"source_url":"https://static.cninfo.com.cn/finalpage/2022-01-14/1212179309.PDF",
         "source_file":"evidence/513100_split_result_2022-01-14.pdf"},
        {"symbol":"513500","action_type":"split","announcement_date":"2022-03-18","record_date":"2022-03-28",
         "corporate_action_date":"2022-03-29","effective_quote_date":"2022-03-30","pay_date":None,
         "cash_per_share":0.,"split_ratio":2.,"source_url":"https://www.sse.com.cn/disclosure/fund/announcement/c/new/2022-03-30/513500_20220330_2_VODYJTry.pdf",
         "source_file":"evidence/513500_split.pdf"}])
    actions=pd.DataFrame(result).sort_values(["corporate_action_date","symbol"]).reset_index(drop=True)
    actions.to_csv(out/"corporate_actions.csv",index=False)
    return actions


def prepare_markets(out,raw,old,reference,actions):
    common=old[CORE[0]].index
    for c in CORE[1:]:common=common.intersection(old[c].index)
    pd.Series(common,name="common_trading_date").to_csv(out/"common_calendar.csv",index=False)
    dates=pd.date_range("2015-01-05","2026-09-30")
    trade_common=common.intersection(dates)
    deposits=np.asarray([np.flatnonzero((dates.to_period("M")==p)&dates.isin(trade_common))[0] for p in dates.to_period("M").unique()])
    signal_levels, native_returns = {},[]
    for c in CORE+["513500"]:
        close=raw[c][["Close"]].rename(columns={"Close":c})
        r=distribution_returns(close,actions)
        signal_levels[c]=(1+r[c].fillna(0)).cumprod()
        native_returns.append(pd.DataFrame({"symbol":c,"raw_close":close[c],"signal_return":r[c],"causal_total_return_index":signal_levels[c]}))
    pd.concat(native_returns).rename_axis("date").to_csv(out/"signal_native_returns.csv")
    levels=pd.DataFrame({c:signal_levels[c].reindex(signal_levels[c].index.union(common)).ffill().reindex(common) for c in CORE})
    common_returns=levels.pct_change(fill_method=None)
    vol=common_returns.rolling(20).std(ddof=1)
    signals=pd.DatetimeIndex(pd.to_datetime(reference.signal_date))
    weights=1/vol.loc[signals]
    weights=weights.div(weights.sum(axis=1),axis=0)
    weights.index=reference.index
    weights["signal_date"]=reference.signal_date
    weights.to_csv(out/"targets_IV20_corrected.csv")
    previous=common[common<dates[0]][-1]
    initial=1/vol.loc[previous];initial/=initial.sum()
    daily_targets=expand(pd.concat([pd.DataFrame([initial],index=[dates[0]]),weights[CORE]]),dates)
    close_daily=pd.DataFrame({c:expand(raw[c],dates).Close for c in CORE+["513500"]})
    # Conversion-day official post-close marks preserve equity while quantities
    # change. The raw ETF has no print on the conversion/one-day halt date.
    for event in actions.loc[actions.action_type=="split"].to_dict("records"):
        date=pd.Timestamp(event["corporate_action_date"])
        if date in dates:
            assert date not in raw[event["symbol"]].index
            close_daily.loc[date,event["symbol"]]/=float(event["split_ratio"])
    markets={}
    for label,columns in [("Three",CORE),("Two",CORE[1:]),("513500",["513500"])]:
        targets=daily_targets[columns].div(daily_targets[columns].sum(axis=1),axis=0) if label!="513500" else pd.DataFrame(1.,index=dates,columns=columns)
        opening=pd.DataFrame({c:raw[c].Open.reindex(dates) for c in columns})
        scheduled=dates.isin(reference.index) if label!="513500" else np.zeros(len(dates),bool)
        markets[label]=DividendMarket(dates,columns,opening.to_numpy(),close_daily[columns].to_numpy(),
                                     targets.to_numpy(),scheduled,actions.to_dict("records"),deposits)
    audit=pd.DataFrame({"signal_date":signals,"execution_date":reference.index,
                        "signal_before_execution":signals<reference.index})
    assert audit.signal_before_execution.all()
    assert np.isfinite(weights[CORE]).all().all()
    audit.to_csv(out/"signal_clock_audit.csv",index=False)
    delta=pd.DataFrame({"old_300_weight":reference["510300.SS"],"corrected_300_weight":weights["510300"]})
    delta["difference"]=delta.corrected_300_weight-delta.old_300_weight
    delta.to_csv(out/"weight_correction.csv")
    return markets,common,daily_targets


def record_run(out,label,strategy,mode,daily,trades,events,summaries,metrics,monthly,annual,dd_rows,loss_rows,rolling):
    tag=f"{label}_{strategy}_{mode}"
    daily.to_csv(out/("account_"+tag+".csv"))
    if trades is not None:trades.to_csv(out/("fills_"+tag+".csv"),index=False)
    if events is not None:events.to_csv(out/("events_"+tag+".csv"),index=False)
    summaries.append({"variant":label,"strategy":strategy,"funding":mode,**account_summary(daily)})
    seed=pd.Series([1.],index=[daily.index[0]-pd.Timedelta(days=1)])
    nav=pd.concat([seed,daily.unit_nav])
    mon=nav.resample("ME").last().pct_change().dropna()
    if len(mon)<len(daily.index.to_period("M").unique()):
        mon=nav.resample("ME").last().pct_change();mon.iloc[0]=nav.resample("ME").last().iloc[0]-1
    wins,losses=mon[mon>0],mon[mon<0]
    dd=drawdown_events(nav)
    metrics.append({"variant":label,"strategy":strategy,"funding":mode,**performance(nav),
                    "monthly_win_rate":(mon>0).mean(),"mean_winning_month":wins.mean(),"mean_losing_month":losses.mean(),
                    "payoff_ratio":wins.mean()/abs(losses.mean()),"profit_factor":wins.sum()/abs(losses.sum()),
                    "best_month":mon.max(),"worst_month":mon.min(),"average_drawdown_depth":dd.depth.mean(),
                    "longest_underwater_days":dd.underwater_calendar_days.max()})
    monthly.append(pd.DataFrame({"variant":label,"strategy":strategy,"funding":mode,"return":mon}))
    yr=daily.unit_nav.resample("YE").last().pct_change();yr.iloc[0]=daily.unit_nav.resample("YE").last().iloc[0]-1
    annual.append(pd.DataFrame({"variant":label,"strategy":strategy,"funding":mode,"return":yr}))
    dd_rows.append(dd.assign(variant=label,strategy=strategy,funding=mode))
    loss_rows.append(principal_loss_events(daily).assign(variant=label,strategy=strategy,funding=mode))
    for years in [3,5]:
        windows=rolling_windows(nav,years)
        worst=windows.loc[windows.total_return.idxmin()]
        rolling.append({"variant":label,"strategy":strategy,"funding":mode,"years":years,
                        "windows":len(windows),"negative_share":(windows.total_return<0).mean(),**worst.to_dict()})


def old_lump(old,reference,dates,strategy):
    columns=CORE if strategy=="Three" else CORE[1:]
    opening=pd.DataFrame({c:old[c].Open.reindex(dates) for c in columns})
    close=pd.DataFrame({c:expand(old[c],dates).Close for c in columns})
    targets=reference[[c+".SS" for c in columns]].rename(columns=lambda x:x[:6])
    targets=targets.div(targets.sum(axis=1),axis=0)
    frame,_,_=replay(opening,close,targets,cost_bps=1,cost_mode="gross")
    wealth=frame.nav*.5
    daily=pd.DataFrame({"wealth":wealth,"liquidation_wealth":wealth-(wealth-frame["cash"]*.5)*.0001,
                        "principal":50000.,"contribution":0.,"cost":frame.cost*.5,"cumulative_cost":frame.cost.cumsum()*.5,
                        "unit_nav":frame.nav/100000.,"market_pnl":frame[columns].sum(axis=1)*.5,
                        "account_residual":frame.pnl_residual*.5})
    daily.loc[dates[0],"contribution"]=50000.
    daily["unit_drawdown"]=daily.unit_nav/daily.unit_nav.cummax().clip(lower=1)-1
    daily["profit"]=daily.liquidation_wealth-daily.principal
    daily["profit_ratio"]=daily.profit/daily.principal
    return daily


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"outputs"/SLUG)
    parser.add_argument("--preflight-only",action="store_true")
    parser.add_argument("--workers",type=int,choices=[1,2],default=2)
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter()
    inputs=out/"inputs";inputs.mkdir(exist_ok=True)
    paths={"raw.json":ROOT/"outputs/domestic-etf-small-account-2026-10-04/evidence/raw_510300.SH.json",
           "targets_IV20.csv":ROOT/"outputs/three-asset-core-2026-10-03/targets_IV20.csv"}
    for c in CORE:paths[c+".parquet"]=ROOT/"outputs/strategy-healthcheck-2026-10-02/market_data"/(c+".SS.parquet")
    for name,path in paths.items():
        if not (inputs/name).exists():shutil.copy2(path,inputs/name)
    for name in ["513500_split.pdf","513500_split.txt"]:
        destination=out/"evidence"/name
        if not destination.exists():shutil.copy2(ROOT/"outputs/domestic-etf-small-account-2026-10-04/evidence"/name,destination)
    raw=load_provider(inputs/"raw.json")
    old={c:pd.read_parquet(inputs/(c+".parquet")) for c in CORE}
    reference=pd.read_csv(inputs/"targets_IV20.csv",index_col=0,parse_dates=True)
    actions=standard_actions(out)
    markets,common,daily_targets=prepare_markets(out,raw,old,reference,actions)
    t0=time.perf_counter()
    sample=replay_dividend_account(markets["Three"],flows={int(i):10000. for i in markets["Three"].deposits},export_details=False)
    kernel=time.perf_counter()-t0
    config={"assets":CORE,"signal":"causal raw ETF total returns, distributions on ex-date; official split ratios",
            "volatility_sessions":20,"std_ddof":1,"signal_calendar":"frozen targets_IV20.signal_date",
            "execution_calendar":"frozen targets_IV20.index; subsequent domestic open",
            "cost_bps":1,"cost_mode":"each gross buy/sell notional","spread_bps_main":0,
            "leverage":False,"trend_exit":False,"premium_filter":False,"fractional_shares":True,
            "dividend_payment":"official investor pay-date AFTER close; no verified intraday broker posting time",
            "reinvestment":"next fixed scheduled rebalance; monthly deposits alone spend only new money",
            "start":"2015-01-05","end":"2026-09-30","lump_cny":50000,"dca_monthly_cny":10000,
            "fixed_calendar_unchanged":True,"parameter_search":False}
    (out/"config.json").write_text(json.dumps(config,ensure_ascii=False,indent=2)+"\n")
    preflight={"preparation_seconds":t0-started,"single_full_account_seconds":kernel,
               "estimated_cohort_seconds":kernel*564*.45/args.workers,"workers":args.workers,
               "network_for_calculation":False,"reuse_calendar":True,"no_BTC_or_multi_replay":True}
    (out/"preflight.json").write_text(json.dumps(preflight,indent=2)+"\n")
    print(json.dumps(preflight),flush=True)
    if args.preflight_only:return
    summaries=[];metrics=[];monthly=[];annual=[];drawdowns=[];losses=[];rolling=[]
    for strategy,m in markets.items():
        for mode in ["lump","dca"]:
            if mode=="lump":
                mm=DividendMarket(m.dates,m.symbols,m.opening,m.closing,m.targets,m.rebalance.copy(),m.actions,m.deposits)
                if strategy=="513500":mm.rebalance[mm.dates.get_loc(reference.index[0])]=True
                daily,trades,events=replay_dividend_account(mm,flows={0:50000.},invest_new_money=False)
            else:
                daily,trades,events=replay_dividend_account(m,flows={int(i):10000. for i in m.deposits})
            record_run(out,"corrected",strategy,mode,daily,trades,events,summaries,metrics,monthly,annual,drawdowns,losses,rolling)
        print("Completed",strategy,flush=True)
    # Controlled same-cost legacy baselines; do not confound the previous 10bp
    # fee with the user's 1bp commission or call a proxy correction exact cash.
    old_targets=target_series(old,common,reference,markets["Three"].dates,original=True)
    for strategy in ["Three","Two"]:
        for mode in ["lump","dca"]:
            if mode=="lump":daily=old_lump(old,reference,markets[strategy].dates,strategy)
            else:
                pm=prepared(old,old_targets,markets[strategy].dates,reference,markets[strategy].deposits)
                daily,_=replay_dca(pm,strategy,contribution=10000,fee_bps=1)
            record_run(out,"legacy_additive",strategy,mode,daily,None,None,summaries,metrics,monthly,annual,drawdowns,losses,rolling)
    # Separate signal/ledger bridge: cash bookkeeping correction with old
    # weights isolates it from the causal return-sequence weight correction.
    m=markets["Three"]
    bridge=DividendMarket(m.dates,m.symbols,m.opening,m.closing,old_targets.to_numpy(),m.rebalance,m.actions,m.deposits)
    for mode in ["lump","dca"]:
        flows={0:50000.} if mode=="lump" else {int(i):10000. for i in m.deposits}
        daily,trades,events=replay_dividend_account(bridge,flows=flows,invest_new_money=mode!="lump")
        record_run(out,"raw_cash_old_weights","Three",mode,daily,trades,events,summaries,metrics,monthly,annual,drawdowns,losses,rolling)
    # Only stated execution-cost sensitivity; do not vary IV20 or phase.
    sensitivity=[]
    for strategy,m in markets.items():
        for fee in [0,1,3]:
            d,_,_=replay_dividend_account(m,flows={int(i):10000. for i in m.deposits},fee_bps=fee,export_details=False)
            sensitivity.append({"strategy":strategy,"gross_cost_bps":fee,**account_summary(d)})
    pd.DataFrame(sensitivity).to_csv(out/"cost_sensitivity.csv",index=False)
    for name,data in [("account_summary",summaries),("q3_q5",metrics),("rolling_unit_summary",rolling)]:
        pd.DataFrame(data).to_csv(out/(name+".csv"),index=False)
    pd.concat(monthly).to_csv(out/"monthly.csv");pd.concat(annual).to_csv(out/"annual.csv")
    pd.concat(drawdowns).to_csv(out/"drawdown_events.csv",index=False)
    pd.concat(losses).to_csv(out/"principal_loss_events.csv",index=False)
    # Actual 2026 small-account deposit scale; still fractional, separate from
    # previously exported board-lot implementation diagnostics.
    pilotrows=[]
    for strategy,m in markets.items():
        start=m.dates.get_loc("2026-01-05")
        deposits=m.deposits[m.deposits>=start]
        for amount in [1000,3000,5000]:
            flows={int(i):float(amount) for i in deposits};flows[start]=50000.
            daily,trades,events=replay_dividend_account(m,flows=flows,start_index=start)
            pilotrows.append({"strategy":strategy,"monthly_cny":amount,**account_summary(daily)})
            if amount==3000:
                daily.to_csv(out/f"pilot_{strategy}_3000.csv")
                events.to_csv(out/f"pilot_events_{strategy}_3000.csv",index=False)
                trades.to_csv(out/f"pilot_fills_{strategy}_3000.csv",index=False)
    pd.DataFrame(pilotrows).to_csv(out/"pilot_summary.csv",index=False)
    # Once prepared, independent rolling accounts can run in two processes.
    cohort_rows=[]
    jobs=[(s,months) for s in markets for months in [36,60]]
    if args.workers==2:
        with ProcessPoolExecutor(max_workers=2,initializer=init_worker,initargs=(markets,)) as pool:
            futures={pool.submit(cohort_job,job):job for job in jobs}
            for future in as_completed(futures):
                cohort_rows.extend(future.result());print("Completed cohorts",futures[future],flush=True)
    else:
        init_worker(markets)
        for job in jobs:cohort_rows.extend(cohort_job(job))
    cohorts=pd.DataFrame(cohort_rows).sort_values(["strategy","months","start_month_index"])
    cohorts.to_csv(out/"rolling_dca_cohorts.csv",index=False)
    worst=[]
    for (strategy,months),group in cohorts.groupby(["strategy","months"]):
        row=group.loc[group.profit_on_principal.idxmin()].to_dict()
        worst.append({"windows":len(group),"negative_terminal_share":(group.profit<0).mean(),**row})
    pd.DataFrame(worst).to_csv(out/"rolling_dca_worst.csv",index=False)
    risks=[]
    for (strategy,months),group in cohorts.groupby(["strategy","months"]):
        worst_loss=group.loc[group.worst_loss_amount.idxmin()]
        longest=group.loc[group.longest_completed_principal_loss_days.idxmax()]
        risks.append({"strategy":strategy,"months":months,"windows":len(group),
                      "worst_intra_account_loss_cny":worst_loss.worst_loss_amount,
                      "worst_loss_cohort_start":worst_loss.start,"worst_loss_date":worst_loss.worst_loss_amount_date,
                      "principal_at_worst_loss":worst_loss.principal_at_worst_amount,
                      "longest_completed_principal_loss_days":longest.longest_completed_principal_loss_days,
                      "longest_loss_cohort_start":longest.start,
                      "max_unrecovered_principal_loss_days":group.longest_censored_principal_loss_days.fillna(0).max(),
                      "any_intra_principal_loss_share":(group.worst_loss_amount < -1e-7).mean()})
    pd.DataFrame(risks).to_csv(out/"rolling_dca_risk_summary.csv",index=False)
    runtime={"total_seconds":time.perf_counter()-started,"python":platform.python_version(),
             "pandas":pd.__version__,"numpy":np.__version__,"workers":args.workers,"cohorts":len(cohorts)}
    (out/"runtime.json").write_text(json.dumps(runtime,indent=2)+"\n")
    print(json.dumps(runtime),flush=True)


if __name__=="__main__":main()
