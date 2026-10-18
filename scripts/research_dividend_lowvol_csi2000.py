"""Dividend low-vol + CSI 2000: four pre-registered combination rules (run once).

Run (from repo root):
  PYTHONPATH=src ../trading/backend/.venv/bin/python scripts/research_dividend_lowvol_csi2000.py
Needs ``scripts/fetch_dividend_lowvol_csi2000_data.py`` to have filled the cache.
All parameters are fixed in CONFIG below before any result was seen.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from xquant import style_combo as sc  # noqa: E402

SLUG = "dividend-lowvol-csi2000-2026-10-18"
OUT = ROOT / "outputs" / SLUG
CACHE = OUT / "cache"
CONFIG = {
    "cost_one_way": 0.001, "start_after": "2014-08-01", "end": "2026-10-16",
    "A": {"weights": "50/50", "rebalance": "quarter-end close"},
    "B": {"vol_window": 20, "rebalance_every_trading_days": 10},
    "C": {"ma_weeks": 30, "check": "weekly close", "quarter_rebalance_only_when_unfiltered": True},
    "D": {"momentum_calendar_days": 182, "rebalance": "month-end close", "hold": "100% stronger"},
    "execution": "signal at close t, trade at close t+1, 10bp per side on traded amount",
    "assets": {"a": "H20269 dividend low-vol total return", "b": "932000 CSI 2000 PRICE index (no TR available)",
               "benchmark": "H00300 CSI 300 total return"},
    "sensitivity_only_not_for_param_selection": ["B window 20/60", "A freq M/Q/Y", "subsamples",
                                                 "a=price index", "b + 1%/yr assumed dividend"],
}
PERIODS = {
    "2015股灾 2015-06-01~09-30": ("2015-06-01", "2015-09-30"),
    "2016-2020": ("2016-01-01", "2020-12-31"),
    "2018全年": ("2018-01-01", "2018-12-31"),
    "2021全年": ("2021-01-01", "2021-12-31"),
    "2024年1-2月小盘暴跌": ("2024-01-01", "2024-02-29"),
    "2024-09-24~10-08行情": ("2024-09-24", "2024-10-08"),
}
RULES = ["A", "B", "C", "D"]
BENCH = {"红利低波买入持有": {"a": 1.0, "b": 0.0}, "中证2000买入持有": {"a": 0.0, "b": 1.0}}
NAMES = {"A": "A 基准50/50季调", "B": "B 逆波动", "C": "C 趋势过滤", "D": "D 风格轮动"}


def load_index(code):
    d = pd.read_csv(CACHE / f"csindex_{code}.csv", parse_dates=["日期"]).set_index("日期")["收盘"]
    d = d[d.index >= "2014-01-01"]
    assert d.index.is_unique and d.notna().all()
    return d.rename(code)


def run_all(prices, start_i, window=20, freq="Q", with_bench=True):
    rets = prices.pct_change()
    sigs = {"A": sc.rule_a(prices.index, start_i, freq), "B": sc.rule_b(rets, start_i, window),
            "C": sc.rule_c(prices, start_i), "D": sc.rule_d(prices, start_i)}
    res = {k: sc.run_backtest(prices, s, start_i, CONFIG["cost_one_way"]) for k, s in sigs.items()}
    if with_bench:
        for n, w in BENCH.items():
            res[n] = sc.run_backtest(prices, sc.rule_buy_hold(w, start_i), start_i, CONFIG["cost_one_way"])
    return res


def metrics_table(res, extra=None):
    rows = []
    for k, r in res.items():
        m = sc.summary_metrics(r.nav, r.trades)
        rows.append({"name": NAMES.get(k, k), **m})
    if extra is not None:
        rows.append({"name": "沪深300全收益买入持有", **sc.summary_metrics(extra)})
    return pd.DataFrame(rows)


def sub_metrics(nav, start, end):
    s = nav[(nav.index >= start) & (nav.index <= end)]
    # include the prior close so the first day's return counts
    prev = nav[nav.index < s.index[0]]
    s = pd.concat([prev.iloc[-1:], s]) if len(prev) else s
    ret = s.pct_change().dropna()
    return {"annualized": sc.annualized(s), "max_drawdown": float(sc.drawdown(s).min()),
            "annual_vol": float(ret.std() * np.sqrt(252))}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    idx = {c: load_index(c) for c in ["H20269", "H30269", "932000", "H00300", "000300"]}
    cal = idx["H20269"].index.intersection(idx["932000"].index).intersection(idx["H00300"].index)
    assert cal.equals(idx["932000"].index), "calendars differ"
    for c in idx:
        idx[c] = idx[c].reindex(cal)
        assert idx[c].notna().all(), f"missing values in {c}"  # no interpolation
    px = pd.DataFrame({"a": idx["H20269"], "b": idx["932000"]})
    csi300 = idx["H00300"]
    start_i = int(px.index.searchsorted(pd.Timestamp(CONFIG["start_after"])))
    print("backtest start (signal day):", px.index[start_i].date(), "end:", px.index[-1].date(), "days:", len(px) - start_i)

    res = run_all(px, start_i)
    bench300 = sc.run_backtest(pd.DataFrame({"a": csi300, "b": csi300}), sc.rule_buy_hold({"a": 1.0, "b": 0.0}, start_i),
                               start_i, CONFIG["cost_one_way"])
    allnav = {NAMES.get(k, k): r.nav for k, r in res.items()}
    allnav["沪深300全收益买入持有"] = bench300.nav
    nav_df = pd.DataFrame(allnav)

    # ---- main summary
    summ = metrics_table(res, extra=None)
    m300 = {"name": "沪深300全收益买入持有", **sc.summary_metrics(bench300.nav, bench300.trades)}
    summ = pd.concat([summ, pd.DataFrame([m300])], ignore_index=True)
    summ.to_csv(OUT / "summary.csv", index=False)

    # ---- yearly returns
    yearly = {}
    for n, nav in allnav.items():
        y = nav.groupby(nav.index.year).last()
        first = nav.iloc[0]
        prev = y.shift(1)
        prev.iloc[0] = first
        yearly[n] = y / prev - 1
    pd.DataFrame(yearly).to_csv(OUT / "yearly_returns.csv", index_label="year")

    # ---- key periods
    rows = []
    for pn, (s, e) in PERIODS.items():
        for n, nav in allnav.items():
            rows.append({"period": pn, "name": n, **sc.period_stats(nav, s, e)})
    kp = pd.DataFrame(rows)
    kp.to_csv(OUT / "key_periods.csv", index=False)
    # underlying index context for same periods
    ctx = []
    for pn, (s, e) in PERIODS.items():
        for n, ser in [("红利低波全收益(指数)", px["a"]), ("中证2000(指数)", px["b"]), ("沪深300全收益(指数)", csi300)]:
            ctx.append({"period": pn, "name": n, **sc.period_stats(ser, s, e)})
    pd.DataFrame(ctx).to_csv(OUT / "key_periods_index_context.csv", index=False)

    # ---- correlations (daily returns, full index history from 2014 and backtest window)
    r = px.pct_change().dropna()
    corr = [{"scope": "2014全期(含倒推)", "corr": float(r["a"].corr(r["b"]))}]
    for y, g in r.groupby(r.index.year):
        corr.append({"scope": str(y), "corr": float(g["a"].corr(g["b"]))})
    corr.append({"scope": "回测区间", "corr": float(r.loc[px.index[start_i]:, "a"].corr(r.loc[px.index[start_i]:, "b"]))})
    r23 = r[r.index >= "2023-08-11"]
    corr.append({"scope": "2023-08-11起(真实发布后)", "corr": float(r23["a"].corr(r23["b"]))})
    pd.DataFrame(corr).to_csv(OUT / "correlations.csv", index=False)

    # ---- subsamples
    sub = []
    for lab, (s, e) in {"2014-08~2019": ("2014-08-01", "2019-12-31"), "2020~2026-10": ("2020-01-01", "2026-12-31")}.items():
        for n, nav in allnav.items():
            sub.append({"sample": lab, "name": n, **sub_metrics(nav, s, e)})
    sub = pd.DataFrame(sub)
    sub["rank_annualized_ABCD"] = np.nan
    sub["rank_calmar_ABCD"] = np.nan
    sub["calmar"] = sub["annualized"] / sub["max_drawdown"].abs()
    for lab, g in sub.groupby("sample"):
        abcd = g[g["name"].isin(NAMES.values())]
        sub.loc[abcd.index, "rank_annualized_ABCD"] = abcd["annualized"].rank(ascending=False)
        sub.loc[abcd.index, "rank_calmar_ABCD"] = abcd["calmar"].rank(ascending=False)
    sub.to_csv(OUT / "subsamples.csv", index=False)

    # ---- sensitivities (not used to pick parameters)
    sens = []

    def add(label, rs, only=RULES):
        for k in only:
            m = sc.summary_metrics(rs[k].nav, rs[k].trades)
            sens.append({"variant": label, "rule": NAMES[k], "annualized": m["annualized"], "max_drawdown": m["max_drawdown"],
                         "annual_vol": m["annual_vol"], "calmar": m["calmar"], "turnover_per_year": m["turnover_per_year"],
                         "longest_recovery_days": m["longest_recovery_days"]})
    add("基准设定(B=20日, A=季)", res)
    add("B窗口60日", run_all(px, start_i, window=60, with_bench=False), ["B"])
    add("A月度再平衡", run_all(px, start_i, freq="M", with_bench=False), ["A"])
    add("A年度再平衡", run_all(px, start_i, freq="Y", with_bench=False), ["A"])
    px_div = px.copy()
    px_div["a"] = idx["H30269"]
    add("红利低波改用价格指数(无分红)", run_all(px_div, start_i, with_bench=False))
    px_b = px.copy()
    rb = px["b"].pct_change().fillna(0) + 0.01 / 252
    px_b["b"] = px["b"].iloc[0] * (1 + rb).cumprod()
    add("中证2000假设每年多1%分红(假设值)", run_all(px_b, start_i, with_bench=False))
    sens = pd.DataFrame(sens)
    sens.to_csv(OUT / "sensitivity.csv", index=False)

    # ---- trades / orders
    tr = pd.concat([r_.trades.assign(rule=NAMES.get(k, k)) for k, r_ in res.items()], ignore_index=True)
    tr.to_csv(OUT / "trades.csv", index=False)
    nav_df.to_csv(OUT / "nav_daily.csv", index_label="date")
    res["C"].weights.to_csv(OUT / "weights_daily_C.csv", index_label="date")

    # ---- ETF vs index
    etf_rows = []
    for sym, code, label in [("512890", "H20269", "红利低波ETF vs 全收益指数"), ("512890", "H30269", "红利低波ETF vs 价格指数"),
                             ("563300", "932000", "中证2000ETF vs 价格指数")]:
        d = json.loads((CACHE / f"tickflow_forward_{sym}.json").read_text())["data"][f"{sym}.SH"]
        ts = pd.to_datetime(d["timestamp"], unit="ms", utc=True).tz_convert("Asia/Shanghai").tz_localize(None).normalize()
        etf = pd.Series(d["close"], index=ts).astype(float)
        ref = idx[code]
        j = pd.concat([etf, ref], axis=1, keys=["etf", "idx"]).dropna()
        rr = j.pct_change().dropna()
        yrs = (j.index[-1] - j.index[0]).days / 365.25
        ann = lambda s: (s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1
        te = (rr["etf"] - rr["idx"]).std() * np.sqrt(252)
        etf_rows.append({"pair": label, "start": j.index[0].date(), "end": j.index[-1].date(), "n_days": len(j),
                         "etf_annualized": ann(j["etf"]), "index_annualized": ann(j["idx"]),
                         "gap_per_year": ann(j["etf"]) - ann(j["idx"]), "daily_corr": rr["etf"].corr(rr["idx"]),
                         "tracking_error_annual": te, "etf_total_return": j["etf"].iloc[-1] / j["etf"].iloc[0] - 1,
                         "index_total_return": j["idx"].iloc[-1] / j["idx"].iloc[0] - 1,
                         "etf_max_dd": sc.drawdown(j["etf"]).min(), "index_max_dd": sc.drawdown(j["idx"]).min()})
    pd.DataFrame(etf_rows).to_csv(OUT / "etf_vs_index.csv", index=False)

    # dividend gaps (TR vs price) for context
    gap = []
    for tr_c, px_c, lab in [("H20269", "H30269", "红利低波"), ("H00300", "000300", "沪深300")]:
        s = pd.concat([idx[tr_c], idx[px_c]], axis=1).loc[px.index[start_i]:]
        yrs = (s.index[-1] - s.index[0]).days / 365.25
        a1 = (s.iloc[-1, 0] / s.iloc[0, 0]) ** (1 / yrs) - 1
        a2 = (s.iloc[-1, 1] / s.iloc[0, 1]) ** (1 / yrs) - 1
        gap.append({"index": lab, "tr_annualized": a1, "price_annualized": a2, "dividend_gap_per_year": a1 - a2})
    pd.DataFrame(gap).to_csv(OUT / "dividend_gap.csv", index=False)

    # ---- self checks
    checks = {k: v.checks for k, v in res.items()}
    nav_ok = all(abs(r_.weights.sum(axis=1).max() - 1) < 1e-6 or r_.weights.sum(axis=1).max() < 1 + 1e-9 for r_ in res.values())
    selfcheck = {
        "backtest_signal_start": str(px.index[start_i].date()), "end": str(px.index[-1].date()),
        "first_trade_date_all_rules": {k: str(v.trades["exec_date"].iloc[0].date()) for k, v in res.items()},
        "per_rule_checks": checks, "weights_never_exceed_1": nav_ok,
        "orders_signal_before_exec": all((v.orders["exec_date"] > v.orders["signal_date"]).all() for v in res.values() if len(v.orders)),
        "calendar_equal_across_indexes": True, "no_missing_values_no_interpolation": True,
        "max_abs_daily_return": {c: float(idx[c].pct_change().abs().max()) for c in idx},
        "csi2000_first_real_publication_note": "932000 published ~2023-08; earlier values are back-cast",
        "uv_lock_untouched_check": "see git status at delivery",
    }
    (OUT / "selfcheck.json").write_text(json.dumps(selfcheck, ensure_ascii=False, indent=2, default=str) + "\n")
    (OUT / "config.json").write_text(json.dumps(CONFIG, ensure_ascii=False, indent=2) + "\n")

    pd.set_option("display.width", 250, "display.max_columns", 30, "display.float_format", lambda x: f"{x:.4f}")
    print(summ.drop(columns=["rolling3y_worst_end"]).to_string())
    print(pd.DataFrame(yearly).to_string())
    print(kp.pivot(index="name", columns="period", values="return").to_string())
    print(kp.pivot(index="name", columns="period", values="max_drawdown").to_string())
    print(pd.DataFrame(ctx).pivot(index="name", columns="period", values="return").to_string())
    print(pd.DataFrame(corr).to_string())
    print(sub.to_string())
    print(sens.to_string())
    print(pd.DataFrame(etf_rows).T.to_string())
    print(pd.DataFrame(gap).to_string())
    print(json.dumps(selfcheck, ensure_ascii=False, default=str)[:900])
    print(summ[["name", "rolling3y_worst_end"]])


if __name__ == "__main__":
    main()
