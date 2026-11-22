"""Compare 513500 self-signals with the earlier SPY-signal replay.

The traded asset is always the actual RMB 513500 close.  Signal variants are:
``SPY`` (the diagnostic transfer experiment), ``SELF`` (513500 itself), and
``B0`` buy and hold.  MTF-3 and TVT-50 retain their frozen parameters.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
import research_513500_mtf_tvt_real_2026_11_14 as old  # noqa: E402
from xquant import style_combo as sc  # noqa: E402

SLUG = "sp500-513500-direct-signal-2026-11-15"
OUT = ROOT / "outputs" / SLUG
START, END = old.START, old.END
COSTS = {"10bp": 0.001, "30bp": 0.003}


def signal_mtf_self(close, dates, start_i, week_ma=30, month_ma=10, slope_weeks=4):
    weekly, monthly = old.stage_states(close, week_ma, slope_weeks), old.month_state(close, month_ma)
    state = {"last": None}
    def sig(i):
        d = dates[i]; w = old.latest_before(weekly.astype(float), d, 0.0); m = old.latest_before(monthly, d, 0.0)
        wanted = 1.0 if w > .5 and m > .5 else (.5 if w > .5 or m > .5 else 0.0)
        if i == start_i or wanted != state["last"]:
            state["last"] = wanted; return {"a": wanted, "b": 0.0}
        return None
    return sig


def signal_tvt_self(close, dates, start_i, target=.15, window=21, off_cap=.50):
    vol = np.log(close).diff().rolling(window).std(ddof=1) * np.sqrt(252.0)
    weekly = old.stage_states(close); state = {"last": None}
    def sig(i):
        d = dates[i]; v = old.latest_before(vol, d, np.nan)
        if not np.isfinite(v) or v <= 0: return None
        trend = old.latest_before(weekly.astype(float), d, 0.0) > .5
        wanted = min(1.0 if trend else off_cap, target / v)
        if i == start_i or state["last"] is None or abs(wanted - state["last"]) > .10:
            state["last"] = wanted; return {"a": wanted, "b": 0.0}
        return None
    return sig


def metrics(res):
    m = sc.summary_metrics(res.nav, res.trades); ret = res.nav.pct_change().dropna()
    days = ret.index.to_series().diff().dt.days.fillna(1).to_numpy() / 365.25
    rf = pd.Series(1.02 ** days - 1, index=ret.index); ex = ret - rf
    sh = float(ex.mean() / ex.std(ddof=1) * np.sqrt(252))
    return {"cagr": m["annualized"], "vol": m["annual_vol"], "sharpe": sh,
            "max_dd": m["max_drawdown"], "calmar": m["calmar"], "trades": m["n_trades"],
            "avg_weight": float(res.weights["a"].iloc[1:].mean()),
            "time_below_20": float((sc.drawdown(res.nav) < -.20).mean())}


def q5(nav):
    x = nav.resample("ME").last().pct_change().dropna(); w, l = x[x > 0], x[x < 0]
    return {"monthly_win_rate": float((x > 0).mean()), "avg_win_month": float(w.mean()),
            "avg_loss_month": float(l.mean()), "payoff_ratio": float(w.mean() / abs(l.mean())),
            "profit_factor": float(w.sum() / abs(l.sum())), "best_month": float(x.max()), "worst_month": float(x.min())}


def dca(nav, dates):
    from xquant.cashflow_research import xirr
    c = pd.DatetimeIndex(dates[~dates.to_period("M").duplicated()]).intersection(nav.index)
    buys = pd.Series(0., index=nav.index); buys.loc[c] = 1 / nav.loc[c]
    units = buys.cumsum(); principal = pd.Series(0., index=nav.index); principal.loc[c] = 1; principal = principal.cumsum()
    value = units * nav; fr = value / principal.replace(0, np.nan) - 1
    return {"xirr": float(xirr(pd.Series(1., index=c), float(value.iloc[-1]), nav.index[-1])),
            "terminal_per_contribution": float(value.iloc[-1] / len(c)), "max_float_loss": float(fr.dropna().min()), "n": len(c)}


def dca_windows(nav, dates):
    rows = []
    for day in dates[~dates.to_period("M").duplicated()]:
        for months in (60, 120):
            endp = day.to_period("M") + months - 1
            part = nav[(nav.index >= day) & (nav.index.to_period("M") <= endp)]
            if part.empty or part.index[-1].to_period("M") != endp: continue
            rows.append({"start": str(day.date()), "months": months, **dca(part, part.index[~part.index.to_period("M").duplicated()])})
    return pd.DataFrame(rows)


def dd_events(nav):
    dd = nav / nav.cummax() - 1; rows=[]; active=False
    for d,v in dd.items():
        if v < 0 and not active: active=True; st=d; tr=d
        if active and v < dd.loc[tr]: tr=d
        if active and v >= 0:
            rows.append({"start":st,"trough":tr,"recovery":d,"depth":float(dd.loc[tr]),"days_to_recovery":(d-tr).days}); active=False
    if active: rows.append({"start":st,"trough":tr,"recovery":pd.NaT,"depth":float(dd.loc[tr]),"days_to_recovery":np.nan})
    return pd.DataFrame(rows).sort_values("depth").head(8)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    domestic = old.domestic_close(); spy, _ = old.load_sp500(); spy = spy[spy.index <= END]
    dates = domestic.index; prices = pd.DataFrame({"a": domestic, "b": domestic}, index=dates)
    builders = {
        "B0": lambda: sc.rule_buy_hold({"a":1.,"b":0.}, 0),
        "MTF-3_SPY": lambda: old.signal_mtf(spy, dates, 0),
        "MTF-3_SELF": lambda: signal_mtf_self(domestic, dates, 0),
        "TVT-50_SPY": lambda: old.signal_tvt(spy, dates, 0),
        "TVT-50_SELF": lambda: signal_tvt_self(domestic, dates, 0),
    }
    results={}; summary=[]
    for cl,cost in COSTS.items():
        for name,build in builders.items():
            r=old.run(prices, build(), cost=cost); results[(cl,name)] = r
            summary.append({"cost":cl,"strategy":name,**metrics(r),**q5(r.nav)})
    pd.DataFrame(summary).to_csv(OUT/"summary_q3_q5.csv",index=False)
    pd.DataFrame({f"{c}_{n}":r.nav for (c,n),r in results.items()}).to_csv(OUT/"nav_daily.csv",index_label="date")
    pd.DataFrame({f"{c}_{n}":r.weights.a for (c,n),r in results.items()}).to_csv(OUT/"weights_daily.csv",index_label="date")
    pd.concat([dd_events(r.nav).assign(cost=c,strategy=n) for (c,n),r in results.items()],ignore_index=True).to_csv(OUT/"drawdown_events.csv",index=False)
    seg=[]
    for (c,n),r in results.items():
        for lab,(a,b) in {"2014-2020":("2014-10-08","2020-12-31"),"2021-2026":("2021-01-01",str(END.date()))}.items():
            nav=r.nav[(r.nav.index>=a)&(r.nav.index<=b)]
            rr=type("R",(),{"nav":nav,"trades":r.trades,"weights":r.weights})()
            seg.append({"cost":c,"strategy":n,"segment":lab,**metrics(rr)})
    pd.DataFrame(seg).to_csv(OUT/"segments.csv",index=False)
    dca_rows=[]
    for (c,n),r in results.items(): dca_rows.append({"cost":c,"strategy":n,**dca(r.nav,dates)})
    pd.DataFrame(dca_rows).to_csv(OUT/"dca_summary.csv",index=False)
    win=[]; base=dca_windows(results[("10bp","B0")].nav,dates)
    for (c,n),r in results.items():
        if c != "10bp": continue
        cur=dca_windows(r.nav,dates).set_index(["start","months"]); b=base.set_index(["start","months"])
        for (st,mo),row in cur.iterrows():
            br=b.loc[(st,mo)]; ratio=row.xirr/abs(row.max_float_loss) if row.max_float_loss<0 else np.nan; bratio=br.xirr/abs(br.max_float_loss) if br.max_float_loss<0 else np.nan
            win.append({"strategy":n,"start":st,"months":mo,"xirr":row.xirr,"max_float_loss":row.max_float_loss,"ratio":ratio,"ratio_gt_b0":bool(ratio>bratio),"xirr_gt_b0":bool(row.xirr>br.xirr)})
    wf=pd.DataFrame(win); wf.to_csv(OUT/"dca_windows.csv",index=False)
    wf.groupby(["months","strategy"]).agg(n=("xirr","size"),median_xirr=("xirr","median"),median_ratio=("ratio","median"),share_ratio_gt_b0=("ratio_gt_b0","mean"),share_xirr_gt_b0=("xirr_gt_b0","mean")).reset_index().to_csv(OUT/"dca_windows_summary.csv",index=False)
    sens=[]
    for source,close in [("SELF",domestic),("SPY",spy)]:
        for weeks,months in ((20,8),(30,10),(40,12)):
            sig=signal_mtf_self(close,dates,0,week_ma=weeks,month_ma=months) if source=="SELF" else old.signal_mtf(close,dates,0)
            r=old.run(prices,sig,cost=COSTS["10bp"]); sens.append({"family":f"MTF-3_{source}","variant":f"week{weeks}_month{months}",**metrics(r)})
    for source,close in [("SELF",domestic),("SPY",spy)]:
        for target,cap in ((.12,.25),(.15,.50),(.18,.75)):
            sig=signal_tvt_self(close,dates,0,target=target,off_cap=cap) if source=="SELF" else old.signal_tvt(close,dates,0,target=target,off_cap=cap)
            r=old.run(prices,sig,cost=COSTS["10bp"]); sens.append({"family":f"TVT-50_{source}","variant":f"target{target:.2f}_offcap{cap:.2f}",**metrics(r)})
    pd.DataFrame(sens).to_csv(OUT/"sensitivity.csv",index=False)
    cfg={"slug":SLUG,"window":[str(START.date()),str(END.date())],"trade_price":"real 513500 RMB close","signal_variants":{"SPY":"SPY closes, next mainland close","SELF":"513500 close, next mainland close"},"costs":COSTS,"cash":"2% RMB proxy","note":"SELF is the production-like signal; SPY is retained only as transfer diagnostic"}
    (OUT/"config.json").write_text(json.dumps(cfg,ensure_ascii=False,indent=2))
    (OUT/"selfcheck.json").write_text(json.dumps({"weights_in_range":all((r.weights.a.between(0,1)).all() for r in results.values()),"positive_nav":all((r.nav>0).all() for r in results.values())},indent=2))
    (OUT/"README.md").write_text("""# 513500 自身信号与 SPY 信号对照\n\n交易价格统一为真实 513500 人民币收盘价。SELF 使用 513500 自身价格发信号，SPY 使用 SPY 仅作迁移诊断；最终可执行规则应优先看 SELF。\n\n复现：`uv run python -I scripts/research_513500_direct_signal_2026_11_15.py`。\n""",encoding="utf-8")

if __name__ == "__main__": main()
