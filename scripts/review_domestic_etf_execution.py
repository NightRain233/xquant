"""Offline, frozen-input ETF product/execution and accounting diagnostics."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from xquant.cashflow_research import PreparedDcaMarket, account_summary, replay_dca
from xquant.etf_execution_research import lot_orders, premium_shock, replay_lot_account
from xquant.three_asset_research import drawdown_events, performance

SLUG = "domestic-etf-small-account-2026-10-04"
CORE = ["510300", "513100", "518880"]


def load_provider(path):
    payload = json.loads(path.read_text())
    frames = {}
    for symbol, data in payload["data"].items():
        dates = pd.to_datetime(data["timestamp"], unit="ms", utc=True).tz_convert("Asia/Shanghai").tz_localize(None).normalize()
        frame = pd.DataFrame({field.capitalize(): data[field] for field in ["open", "high", "low", "close", "volume"]}, index=dates)
        if "amount" in data:
            frame["Amount"] = data["amount"]
        frame.Volume *= 100  # provider hands; independently checked against Sina shares
        assert frame.index.is_unique and frame.index.is_monotonic_increasing
        assert frame.index.max() <= pd.Timestamp("2026-09-30")
        frames[symbol[:6]] = frame
    return frames


def expand(frame, dates):
    return frame.reindex(frame.index.union(dates)).sort_index().ffill().reindex(dates)


def target_series(prices, common, reference, dates, original=False):
    closes = pd.DataFrame({c: prices[c].Close.reindex(common) for c in CORE})
    vol = closes.pct_change(fill_method=None).rolling(20).std(ddof=1)
    frozen = reference.copy()
    signals = pd.DatetimeIndex(pd.to_datetime(frozen.signal_date))
    inverse = 1/vol.loc[signals]
    targets = inverse.div(inverse.sum(axis=1), axis=0)
    targets.index = frozen.index
    if original:
        targets = frozen[[c+".SS" for c in CORE]].rename(columns=lambda s:s[:6])
    previous = common[common < dates[0]][-1]
    startup = 1/vol.loc[previous]
    startup /= startup.sum()
    targets = pd.concat([pd.DataFrame([startup], index=[dates[0]]), targets])
    return expand(targets, dates)


def prepared(prices, targets, dates, reference, deposits):
    opening = pd.DataFrame({c: prices[c].Open.reindex(dates) for c in CORE})
    closing = pd.DataFrame({c: expand(prices[c], dates).Close for c in CORE})
    pair = targets[CORE[1:]].div(targets[CORE[1:]].sum(axis=1), axis=0)
    n = len(dates)
    return PreparedDcaMarket(dates, opening.to_numpy(), closing.to_numpy(), targets.to_numpy(),
                             pair.to_numpy(), dates.isin(reference.index), np.ones(n),
                             deposits, deposits.copy(), np.ones(len(deposits)), [])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT/"outputs"/SLUG)
    parser.add_argument("--evidence", type=Path, default=ROOT/"outputs"/SLUG/"evidence")
    parser.add_argument("--frozen", type=Path, default=ROOT/"outputs/strategy-healthcheck-2026-10-02/market_data")
    parser.add_argument("--reference", type=Path, default=ROOT/"outputs/three-asset-core-2026-10-03")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    out, ev = args.output, args.evidence
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    raw = {}
    for name in ["raw_510300.SH.json", "raw_510310.SH.json", "raw_sz.json"]:
        raw.update(load_provider(ev/name))
    forward = load_provider(ev/"forward_core.json")
    old = {c:pd.read_parquet(args.frozen/(c+".SS.parquet")) for c in CORE}
    reference = pd.read_csv(args.reference/"targets_IV20.csv", index_col=0, parse_dates=True)
    common = old[CORE[0]].index
    for c in CORE[1:]:
        common = common.intersection(old[c].index)
    dates = pd.date_range("2015-01-05", "2026-09-30")
    tradable = dates.isin(common)
    deposits = np.asarray([np.flatnonzero((dates.to_period("M")==p)&tradable)[0] for p in dates.to_period("M").unique()])
    old_targets = target_series(old, common, reference, dates, original=True)
    # Exact share splits; the provider's proportional series applies slightly
    # different historical multipliers. 510300 remains a dividend-return proxy.
    proxy = {c:forward[c].copy() for c in CORE}
    for c, split_date, ratio in [("513100", "2022-01-14", 5), ("513500", "2022-03-30", 2)]:
        frame = raw[c].copy()
        frame.loc[frame.index < split_date, ["Open", "High", "Low", "Close"]] /= ratio
        proxy[c] = frame
    new_targets = target_series(proxy, common, reference, dates)
    market = prepared(proxy, new_targets, dates, reference, deposits)
    tick = time.perf_counter()
    sample, _ = replay_dca(market, "Three", contribution=10000, fee_bps=1)
    measured = time.perf_counter()-tick
    preflight = {"prepare_seconds":tick-started, "one_full_account_seconds":measured,
                 "estimated_full_job_seconds":measured*180+5,
                 "network_required_for_calculation":False, "workers":1,
                 "note":"reuse frozen calendar/targets; no BTC/multi replay; small job stays serial"}
    (out/"preflight.json").write_text(json.dumps(preflight, indent=2)+"\n")
    print(json.dumps(preflight), flush=True)
    if args.preflight_only:
        return
    # Raw vs prior adjustment, including inferred affine shifts (not NAVs).
    audit = []
    for c in CORE:
        join = old[c].join(raw[c], lsuffix="_old", rsuffix="_raw", how="inner")
        assert len(join) == len(old[c])
        differences=(old[c].Close.pct_change()-proxy[c].Close.pct_change()).abs().loc["2015-01-05":]
        audit.append({"symbol":c,"rows":len(join),"raw_close_20150105":raw[c].Close.loc["2015-01-05"],
                      "old_close_20150105":old[c].Close.loc["2015-01-05"],
                      "proxy_close_20150105":proxy[c].Close.loc["2015-01-05"],
                      "raw_close_terminal":raw[c].Close.iloc[-1],
                      "max_daily_return_difference":(old[c].Close.pct_change()-proxy[c].Close.pct_change()).abs().max(),
                      "max_daily_return_difference_since2015":differences.max(),
                      "max_daily_return_difference_since2015_date":differences.idxmax(),
                      "old_price_return_20150105_to_terminal":old[c].Close.iloc[-1]/old[c].Close.loc["2015-01-05"]-1,
                      "proxy_return_20150105_to_terminal":proxy[c].Close.iloc[-1]/proxy[c].Close.loc["2015-01-05"]-1})
    pd.DataFrame(audit).to_csv(out/"adjustment_audit.csv", index=False)
    delta = pd.DataFrame({"old_weight_300":old_targets["510300"],"proxy_weight_300":new_targets["510300"]})
    delta["difference"] = delta.proxy_weight_300-delta.old_weight_300
    delta.to_csv(out/"weight_adjustment_diagnostic.csv")
    summaries, qmetrics, annual, monthly, recoveries = [], [], [], [], []
    variants = [("old_additive_cost10",old,old_targets,10), ("old_additive_cost1",old,old_targets,1),
                ("price_proxy_old_weights_cost1",proxy,old_targets,1), ("price_proxy_recalculated_cost1",proxy,new_targets,1)]
    for label, prices, targets, fee in variants:
        m = prepared(prices, targets, dates, reference, deposits)
        for strategy in ["Three", "Two"]:
            daily, _ = replay_dca(m, strategy, contribution=10000, fee_bps=fee)
            summaries.append({"variant":label,"strategy":strategy,**account_summary(daily)})
            if label == "price_proxy_recalculated_cost1":
                daily.to_csv(out/("diagnostic_account_"+strategy+".csv"))
                qmetrics.append({"strategy":strategy,**performance(daily.unit_nav)})
                events = drawdown_events(daily.unit_nav);events["strategy"]=strategy;recoveries.append(events)
                mon = daily.unit_nav.resample("ME").last().pct_change();mon.iloc[0]=daily.unit_nav.resample("ME").last().iloc[0]-1
                yr = daily.unit_nav.resample("YE").last().pct_change();yr.iloc[0]=daily.unit_nav.resample("YE").last().iloc[0]-1
                monthly.append(pd.DataFrame({"strategy":strategy,"return":mon}))
                annual.append(pd.DataFrame({"strategy":strategy,"return":yr}))
    sp_prices = {c:proxy["513500"] for c in CORE}
    sp_targets = pd.DataFrame(np.tile([1.,0,0], (len(dates),1)), index=dates, columns=CORE)
    sp = prepared(sp_prices, sp_targets, dates, reference.iloc[:0], deposits)
    sp_daily, _ = replay_dca(sp, "Three", contribution=10000, fee_bps=1)
    sp_daily.to_csv(out/"diagnostic_account_513500.csv")
    summaries.append({"variant":"mainland_actual_price_exact_split_cost1","strategy":"513500",**account_summary(sp_daily)})
    qmetrics.append({"strategy":"513500",**performance(sp_daily.unit_nav)})
    events=drawdown_events(sp_daily.unit_nav);events["strategy"]="513500";recoveries.append(events)
    mon=sp_daily.unit_nav.resample("ME").last().pct_change();mon.iloc[0]=sp_daily.unit_nav.resample("ME").last().iloc[0]-1
    yr=sp_daily.unit_nav.resample("YE").last().pct_change();yr.iloc[0]=sp_daily.unit_nav.resample("YE").last().iloc[0]-1
    monthly.append(pd.DataFrame({"strategy":"513500","return":mon}));annual.append(pd.DataFrame({"strategy":"513500","return":yr}))
    pd.DataFrame(summaries).to_csv(out/"accounting_diagnostics.csv",index=False)
    pd.DataFrame(qmetrics).to_csv(out/"diagnostic_q3_q5.csv",index=False)
    pd.concat(monthly).to_csv(out/"diagnostic_monthly.csv");pd.concat(annual).to_csv(out/"diagnostic_annual.csv")
    pd.concat(recoveries).to_csv(out/"diagnostic_drawdown_events.csv",index=False)
    month_stats=[]
    for group in monthly:
        values=group["return"].dropna();wins=values[values>0];losses=values[values<0]
        month_stats.append({"strategy":group.strategy.iloc[0],"months":len(values),"winning_month_share":(values>0).mean(),
                            "mean_win":wins.mean(),"mean_loss":losses.mean(),"payoff_ratio":wins.mean()/abs(losses.mean()),
                            "profit_factor":wins.sum()/abs(losses.sum()),"best_month":values.max(),"worst_month":values.min()})
    pd.DataFrame(month_stats).to_csv(out/"diagnostic_month_statistics.csv",index=False)
    # Mainland S&P rolling cash-flow risk only; neither substitutes for old SPY
    # series nor proves the price proxy's complete cash-dividend accounting.
    rolling=[]
    for months in [36,60]:
        for start in range(len(deposits)-months+1):
            daily,_=replay_dca(sp,"Three",start_month=start,stop_after=months,contribution=10000,fee_bps=1)
            endpoint=(dates[deposits[start+months-1]]+pd.offsets.MonthEnd(0))
            row=daily.loc[endpoint]
            rolling.append({"months":months,"start":daily.index[0],"end":endpoint,
                            "principal":row.principal,"liquidation":row.liquidation_wealth,
                            "profit_ratio":row.profit_ratio})
    pd.DataFrame(rolling).to_csv(out/"513500_rolling_cashflow.csv",index=False)
    # Product snapshots are retrospective references, not decision-time IOPVs.
    quotes={}
    for line in (ev/"sina_quotes.txt").read_text(encoding="gb18030").splitlines():
        found=re.search(r"(?:sh|sz)(\d{6})=\"([^\"]+)\"",line)
        if found:
            quotes[found[1]]=found[2].split(",")
    products=[]
    for c, frame in raw.items():
        q=quotes[c]; bid,ask=float(q[11]),float(q[21]);mid=(bid+ask)/2
        navdata=json.loads((ev/("nav_recent_"+c+".json")).read_text())["Data"]["LSJZList"]
        nav=navdata[0];lastnav=float(nav["DWJZ"])
        last=frame.iloc[-1];trailing=frame.tail(60)
        products.append({"symbol":c,"price_date":q[30],"quote_time":q[31],"close":float(q[3]),
                         "bid":bid,"ask":ask,"bid_shares":float(q[10]),"ask_shares":float(q[20]),
                         "snapshot_full_spread_bps":(ask-bid)/mid*10000,"actual_day_turnover_cny":float(q[9]),
                         "tickflow_day_shares":last.Volume,"sina_day_shares":float(q[8]),
                         "tickflow_day_turnover_cny":last.Amount,
                         "median_60day_actual_turnover_cny":trailing.Amount.median(),
                         "min_60day_actual_turnover_cny":trailing.Amount.min(),
                         "median_60day_close_times_volume_proxy":(trailing.Close*trailing.Volume).median(),
                         "min_60day_close_times_volume_proxy":(trailing.Close*trailing.Volume).min(),
                         "one_lot_cny":ask*100,"last_nav_date":nav["FSRQ"],"last_nav":lastnav,
                         "close_last_nav_ratio_minus1":float(q[3])/lastnav-1,
                         "nav_publication_timestamp":"UNKNOWN","premium_is_decision_time_truth":False})
        assert abs(float(q[3])-last.Close)<1e-9
        assert abs(float(q[8])-last.Volume)<100  # provider rounds volume to hands
    pd.DataFrame(products).to_csv(out/"product_market_snapshot.csv",index=False)
    # 2026 trial simulation: raw shares and a verified 510300 cash dividend.
    pilotdates=pd.date_range("2026-01-05","2026-09-30")
    pilotcommon=common.intersection(pilotdates)
    firstmonths=pd.DatetimeIndex(pd.Series(pilotcommon,index=pilotcommon).groupby(pilotcommon.to_period("M")).first().to_numpy())
    pilotrows=[]
    for strategy, columns in [("Three",CORE),("Two",CORE[1:]),("513500",["513500"])]:
        op=pd.DataFrame({c:raw[c].Open.reindex(pilotdates) for c in columns})
        cl=pd.DataFrame({c:expand(raw[c],pilotdates).Close for c in columns})
        if strategy=="513500":
            targets=pd.DataFrame(1.,index=pilotdates,columns=columns)
        else:
            targets=new_targets.loc[pilotdates,columns]
            targets=targets.div(targets.sum(axis=1),axis=0)
        dividend={"column":0,"ex_date":"2026-01-19","pay_date":"2026-01-27","per_share":.123} if strategy=="Three" else None
        for monthly_flow in [1000,3000,5000]:
            flows={d:float(monthly_flow) for d in firstmonths};flows[firstmonths[0]]=50000.
            for cadence in (["10sessions","monthly"] if strategy!="513500" else ["monthly"]):
                rebalances=set(reference.index.intersection(pilotdates)) if cadence=="10sessions" else set(firstmonths)
                rebalances.add(pilotdates[0])
                for spread in [0,5,20]:
                    daily,fills=replay_lot_account(op,cl,targets,rebalances,flows,dividend=dividend,spread_bps=spread)
                    pilotrows.append({"strategy":strategy,"monthly":monthly_flow,"cadence":cadence,"full_spread_bps":spread,
                                      "principal":daily.principal.iloc[-1],"wealth":daily.wealth.iloc[-1],"profit":daily.profit.iloc[-1],
                                      "commission":daily.commission.iloc[-1],"spread_cost":daily.spread_cost.iloc[-1],
                                      "orders":len(fills),"unit_max_drawdown":daily.unit_drawdown.min(),
                                      "max_cash":daily.cash.max(),"mean_cash_fraction":(daily.cash/daily.wealth).mean(),
                                      "mean_max_weight_error":daily.max_weight_error.mean(),"max_weight_error":daily.max_weight_error.max()})
                    if monthly_flow==3000 and spread==5:
                        daily.to_csv(out/f"pilot_{strategy}_{cadence}.csv")
                        fills.to_csv(out/f"pilot_fills_{strategy}_{cadence}.csv",index=False)
    pd.DataFrame(pilotrows).to_csv(out/"pilot_execution_sensitivity.csv",index=False)
    # Frozen last-known target, not a recommendation or a fresh trading signal.
    last_targets=new_targets.iloc[-1]
    plans=[]
    gated_plans=[]
    for strategy,columns in [("Three",CORE),("Two",CORE[1:]),("513500",["513500"])]:
        target=last_targets[columns].to_numpy(copy=True) if strategy!="513500" else np.ones(1)
        target/=target.sum()
        prices=np.array([float(quotes[c][21]) for c in columns])
        q,cash,records=lot_orders(np.zeros(len(columns)),50000.,prices,target)
        for c,w,qty,price in zip(columns,target,q,prices):
            plans.append({"strategy":strategy,"symbol":c,"reference_target":w,"shares":qty,"reference_ask":price,
                          "notional":qty*price,"commission":qty*price*.0001,"cash_after_all":cash})
        allowed=np.array([c not in ["513100","513500"] for c in columns])
        gated_q,gated_cash,_=lot_orders(np.zeros(len(columns)),50000.,prices,target,buy_allowed=allowed)
        for c,w,qty,price in zip(columns,target,gated_q,prices):
            gated_plans.append({"strategy":strategy,"symbol":c,"reference_target":w,"shares":qty,"reference_ask":price,
                                "notional":qty*price,"commission":qty*price*.0001,"cash_after_all":gated_cash,
                                "scenario":"foreign_new_buy_blocked; other ETFs assumed eligible, not an actual order"})
    pd.DataFrame(plans).to_csv(out/"50000_reference_lot_plan.csv",index=False)
    pd.DataFrame(gated_plans).to_csv(out/"50000_reference_lot_plan_gated.csv",index=False)
    scenarios=[]
    # Latest target weights; deterministic surprises, not probabilities.
    for p in [.01,.05,.10,.20]:
        for navret in [0,-.30]:
            shock=premium_shock(navret,p,0)
            for name,w in [("Three",last_targets["513100"]),("Two",last_targets["513100"]/last_targets[CORE[1:]].sum()),("SP500",1.)]:
                scenarios.append({"strategy":name,"premium_before":p,"premium_after":0,"nav_return":navret,
                                  "foreign_weight":w,"etf_price_return":shock,"portfolio_loss_cny":50000*w*shock})
    pd.DataFrame(scenarios).to_csv(out/"premium_shock_scenarios.csv",index=False)
    costs=[]
    for wait_return in [-.20,0,.20]:
        for p0 in [.01,.10,.20]:
            for end_premium in [0,p0]:
                end_price=premium_shock(wait_return,p0,end_premium)
                costs.append({"skipped_buy_budget":10000,"nav_return_while_waiting":wait_return,
                              "initial_premium":p0,"terminal_premium":end_premium,"buy_now_wealth":10000*(1+end_price),
                              "wait_cash_wealth":10000,"cash_minus_buy_now":-10000*end_price})
    pd.DataFrame(costs).to_csv(out/"cash_wait_opportunity_scenarios.csv",index=False)
    inputpaths=[*ev.glob("*.json"),ev/"sina_quotes.txt",args.reference/"targets_IV20.csv",*[args.frozen/(c+".SS.parquet") for c in CORE]]
    sources=[Path(__file__).resolve(),ROOT/"src/xquant/etf_execution_research.py",ROOT/"src/xquant/cashflow_research.py",ROOT/"src/xquant/three_asset_research.py"]
    manifest={"inputs":{str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputpaths},
              "sources":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
              "outputs":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob("*.csv")},
              "elapsed_seconds":time.perf_counter()-started,"pandas":pd.__version__,"numpy":np.__version__,
              "python":sys.version,"scope":"diagnostics, not certified investment returns or timestamped premium backtest"}
    (out/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    print("Completed diagnostic and 45 small-account cases in",round(manifest["elapsed_seconds"],2),"seconds",flush=True)


if __name__=="__main__":
    main()
