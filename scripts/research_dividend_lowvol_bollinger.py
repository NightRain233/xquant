"""Dividend low-vol: weekly Bollinger timing and dividend-yield tilt versus holding (run once).

Run (from repo root): .venv/bin/python scripts/research_dividend_lowvol_bollinger.py
Reads the index cache of ``dividend-lowvol-csi2000-2026-10-18`` (see its fetch script).
All parameters are fixed in CONFIG below before any result was seen.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from xquant import band_timing as bt  # noqa: E402
from xquant import style_combo as sc  # noqa: E402

SLUG = "dividend-lowvol-bollinger-2026-11-05"
SOURCE_SLUG = "dividend-lowvol-csi2000-2026-10-18"
OUT = ROOT / "outputs" / SLUG
SOURCE = ROOT / "outputs" / SOURCE_SLUG
CONFIG = {
    "start_after": "2014-08-01", "end": "2026-10-16", "cost_one_way": 0.001, "cash_annual": 0.02,
    "execution": "signal at close t, trade at close t+1, cost on traded amount, cash earns cash_annual",
    "assets": {"traded_and_signal": "H20269 total return", "yield_only": "H30269 price"},
    "bands": {"window_weeks": 20, "k": 2.0, "std": "population", "check": "weekly close", "near": 0.02,
              "near_definition": "close <= lower*(1+near) or close >= upper*(1-near); both at once = no action"},
    "V1": "100% near lower, 0% near upper, otherwise keep; reported from both start states (flat, held)",
    "V2": "70% base, 100% near lower, 50% near upper, back to 70% on crossing middle band",
    "V3": {"yield": "trailing 252-day TR growth / price growth - 1", "percentile": "expanding, min 756 days",
           "weights": "pct>=70: 100%, pct<=30: 50%, else or no history: 70%", "check": "weekly close"},
    "comparators": ["buy and hold", "fixed exposure at each rule's average position, quarterly rebalance"],
    "added_after_seeing_results": "timing placebo: every circular shift of each rule's position path, full window, 2014-08~2019 and 2020+",
    "sensitivity_only_not_for_param_selection": [
        "window 10/20/30 x k 1.5/2/2.5 x near 0/1/2/3%", "signal on price index", "daily monitoring",
        "cash 0%/3%", "cost 5bp/30bp", "V2 80/100/60 and 50/100/25", "V3 thresholds 20/80, rolling 5y percentile"],
}
PERIODS = {
    "2015股灾 2015-06-01~09-30": ("2015-06-01", "2015-09-30"),
    "2018全年": ("2018-01-01", "2018-12-31"),
    "2021全年": ("2021-01-01", "2021-12-31"),
    "2024全年": ("2024-01-01", "2024-12-31"),
    "2024-09-24~10-08行情": ("2024-09-24", "2024-10-08"),
    "2025全年": ("2025-01-01", "2025-12-31"),
}
SUBSAMPLES = {"2014-08~2019": ("2014-08-01", "2019-12-31"), "2020~2026-10": ("2020-01-01", "2026-12-31"),
              "2017~2026-10(股息率规则有完整历史后)": ("2017-08-01", "2026-12-31")}
NAMES = {"V1a": "V1a 全进全出(空仓起步)", "V1b": "V1b 全进全出(持仓起步)", "V2": "V2 布林底仓70%加减",
         "V3": "V3 股息率底仓70%加减", "BH": "红利低波买入持有", "F70": "固定70%(季调)"}
FORWARD_WEEKS = [4, 13, 26, 52]
FORWARD_START = "2014-08-01"


def load_index(code: str) -> pd.Series:
    path = SOURCE / "cache" / f"csindex_{code}.csv"
    manifest = json.loads((SOURCE / "data_manifest.json").read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest["files"][path.name]["sha256"], path
    series = pd.read_csv(path, parse_dates=["日期"]).set_index("日期")["收盘"]
    assert series.index.is_unique and series.notna().all()
    return series.rename(code)


def backtest(prices, signal, start_i, cost=None, cash=None):
    return sc.run_backtest(prices, signal, start_i, CONFIG["cost_one_way"] if cost is None else cost,
                           CONFIG["cash_annual"] if cash is None else cash)


def build_rules(dates, start_i, levels, near, percentile):
    return {
        "V1a": bt.rule_all_in_out(levels, dates, start_i, near, start_held=False),
        "V1b": bt.rule_all_in_out(levels, dates, start_i, near, start_held=True),
        "V2": bt.rule_core_tilt(levels, dates, start_i, near),
        "V3": bt.rule_yield_tilt(percentile, dates, start_i),
    }


def average_exposure(result) -> float:
    return float(result.weights["a"].iloc[1:].mean())


def row(name, result) -> dict:
    return {"name": name, **sc.summary_metrics(result.nav, result.trades), "avg_exposure": average_exposure(result)}


def segment(nav, start, end):
    prior = nav[nav.index < pd.Timestamp(start)]
    seg = nav[(nav.index >= pd.Timestamp(start)) & (nav.index <= pd.Timestamp(end))]
    return pd.concat([prior.iloc[-1:], seg]) if len(prior) else seg


def yearly_returns(nav):
    last = nav.groupby(nav.index.year).last()
    prev = last.shift(1)
    prev.iloc[0] = nav.iloc[0]
    return last / prev - 1


def forward_table(levels, close, near, start):
    """What the index did after each zone: the hypothesis behind the rule, independent of any position sizing."""
    frame = levels[levels.index >= start].copy()
    weekly = bt.weekly_band_levels(close, 20, 2.0)["close"]
    frame["zone"] = [bt.band_zone(r.close, r.upper, r.lower, near) or "between" for r in frame.itertuples()]
    frame["episode"] = (frame["zone"] != frame["zone"].shift()).cumsum()
    rows = []
    for zone, group_name in [("all", "全部周"), ("lower", "接近下轨"), ("between", "两轨之间"), ("upper", "接近上轨")]:
        part = frame if zone == "all" else frame[frame["zone"] == zone]
        episodes = part["episode"].nunique() if zone != "all" else np.nan
        for weeks in FORWARD_WEEKS:
            fwd = (weekly.shift(-weeks) / weekly - 1).reindex(part.index).dropna()
            rows.append({"zone": group_name, "weeks": len(part), "episodes": episodes, "forward_weeks": weeks,
                         "n": len(fwd), "mean": fwd.mean(), "median": fwd.median(), "win_rate": (fwd > 0).mean()})
    return pd.DataFrame(rows), frame["zone"].value_counts().to_dict()


def round_trips(result, close):
    trades = result.trades
    trades = trades[trades["traded_amount"] > 0]
    rows, entry = [], None
    for t in trades.itertuples():
        if t.w_a == 1.0:
            entry = pd.Timestamp(t.exec_date)
        elif entry is not None:
            exit_ = pd.Timestamp(t.exec_date)
            rows.append({"buy": entry, "sell": exit_, "days_held": (exit_ - entry).days,
                         "index_return": close[exit_] / close[entry] - 1})
            entry = None
    table = pd.DataFrame(rows)
    next_buy = table["buy"].shift(-1).fillna(close.index[-1])
    table["days_out_after"] = (next_buy - table["sell"]).dt.days
    table["index_return_while_out"] = [close[b] / close[s] - 1 for s, b in zip(table["sell"], next_buy)]
    if entry is not None:
        table.attrs["still_held_since"] = str(entry.date())
    return table


def rolling_starts(prices, dates, levels, near, percentile, first_i):
    """Same rules from every quarter start with at least three years left, each against its own same-window holding."""
    rows = []
    starts = [i for i in range(first_i, len(dates) - 756) if i == first_i or sc.is_period_end(dates, i - 1, "Q")]
    for i in starts:
        hold = backtest(prices, sc.rule_buy_hold({"a": 1.0, "b": 0.0}, i), i)
        hm = sc.summary_metrics(hold.nav)
        for key, signal in build_rules(dates, i, levels, near, percentile).items():
            res = backtest(prices, signal, i)
            m = sc.summary_metrics(res.nav)
            matched = backtest(prices, bt.rule_fixed_weight(average_exposure(res), dates, i), i)
            mm = sc.summary_metrics(matched.nav)
            rows.append({"start": dates[i], "rule": NAMES[key], "annualized": m["annualized"], "max_drawdown": m["max_drawdown"],
                         "calmar": m["calmar"], "hold_annualized": hm["annualized"], "hold_max_drawdown": hm["max_drawdown"],
                         "hold_calmar": hm["calmar"], "matched_annualized": mm["annualized"]})
    return pd.DataFrame(rows)


def sensitivity(prices, price_index, dates, start_i, levels, percentile, close, yld):
    rows = []

    def add(label, key, result):
        m = sc.summary_metrics(result.nav, result.trades)
        rows.append({"variant": label, "rule": NAMES[key], "annualized": m["annualized"], "max_drawdown": m["max_drawdown"],
                     "calmar": m["calmar"], "avg_exposure": average_exposure(result), "n_trades": m["n_trades"]})

    near = CONFIG["bands"]["near"]
    for window in [10, 20, 30]:
        for k in [1.5, 2.0, 2.5]:
            grid_levels = bt.weekly_band_levels(close, window, k)
            for near_v in [0.0, 0.01, 0.02, 0.03]:
                rules = build_rules(dates, start_i, grid_levels, near_v, percentile)
                for key in ["V1a", "V1b", "V2"]:
                    add(f"grid w{window} k{k} near{near_v:.0%}", key, backtest(prices, rules[key], start_i))
    variants = {"信号用价格指数": bt.weekly_band_levels(price_index), "每日盯盘(含未走完的本周)": bt.daily_band_levels(close)}
    for label, lv in variants.items():
        rules = build_rules(dates, start_i, lv, near, percentile)
        for key in ["V1a", "V1b", "V2"]:
            add(label, key, backtest(prices, rules[key], start_i))
    for cash in [0.0, 0.03]:
        rules = build_rules(dates, start_i, levels, near, percentile)
        for key, signal in rules.items():
            add(f"现金年化{cash:.0%}", key, backtest(prices, signal, start_i, cash=cash))
    for cost in [0.0005, 0.003]:
        rules = build_rules(dates, start_i, levels, near, percentile)
        for key, signal in rules.items():
            add(f"单边成本{cost * 1e4:.0f}bp", key, backtest(prices, signal, start_i, cost=cost))
    for base, high, low in [(0.8, 1.0, 0.6), (0.5, 1.0, 0.25)]:
        add(f"V2仓位{base:.0%}/{high:.0%}/{low:.0%}", "V2",
            backtest(prices, bt.rule_core_tilt(levels, dates, start_i, near, base, high, low), start_i))
    add("V3阈值20/80", "V3", backtest(prices, bt.rule_yield_tilt(percentile, dates, start_i, 0.8, 0.2), start_i))
    add("V3滚动5年分位", "V3", backtest(prices, bt.rule_yield_tilt(bt.rolling_percentile(yld), dates, start_i), start_i))
    return pd.DataFrame(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    close, price_index = load_index("H20269"), load_index("H30269")
    assert close.index.equals(price_index.index), "calendars differ"
    close = close[close.index <= CONFIG["end"]]
    price_index = price_index.reindex(close.index)
    dates = close.index
    prices = pd.DataFrame({"a": close, "b": close})
    start_i = int(dates.searchsorted(pd.Timestamp(CONFIG["start_after"])))
    near = CONFIG["bands"]["near"]
    levels = bt.weekly_band_levels(close, CONFIG["bands"]["window_weeks"], CONFIG["bands"]["k"])
    assert levels.index[0] < dates[start_i], "bands not warmed up at start"
    yld = bt.trailing_dividend_yield(close, price_index)
    percentile = bt.expanding_percentile(yld)
    print("start", dates[start_i].date(), "end", dates[-1].date(), "yield rank from", percentile.first_valid_index().date())

    results = {k: backtest(prices, s, start_i) for k, s in build_rules(dates, start_i, levels, near, percentile).items()}
    results["BH"] = backtest(prices, sc.rule_buy_hold({"a": 1.0, "b": 0.0}, start_i), start_i)
    results["F70"] = backtest(prices, bt.rule_fixed_weight(0.7, dates, start_i), start_i)

    rows = []
    matched_rows = []
    for key, res in results.items():
        rows.append(row(NAMES[key], res))
        if key in ("V1a", "V1b", "V2", "V3"):
            exposure = average_exposure(res)
            matched = backtest(prices, bt.rule_fixed_weight(exposure, dates, start_i), start_i)
            mm, m = sc.summary_metrics(matched.nav, matched.trades), sc.summary_metrics(res.nav, res.trades)
            matched_rows.append({"rule": NAMES[key], "avg_exposure": exposure, "rule_annualized": m["annualized"],
                                 "matched_annualized": mm["annualized"], "excess_annualized": m["annualized"] - mm["annualized"],
                                 "rule_max_drawdown": m["max_drawdown"], "matched_max_drawdown": mm["max_drawdown"],
                                 "rule_vol": m["annual_vol"], "matched_vol": mm["annual_vol"]})
    pd.DataFrame(rows).to_csv(OUT / "summary.csv", index=False)
    pd.DataFrame(matched_rows).to_csv(OUT / "vs_matched_exposure.csv", index=False)

    navs = {NAMES[k]: r.nav for k, r in results.items()}
    pd.DataFrame(navs).to_csv(OUT / "nav_daily.csv", index_label="date")
    pd.DataFrame({n: yearly_returns(v) for n, v in navs.items()}).to_csv(OUT / "yearly_returns.csv", index_label="year")
    pd.DataFrame({NAMES[k]: results[k].weights["a"] for k in ("V1a", "V1b", "V2", "V3")}).to_csv(OUT / "weights_daily.csv", index_label="date")
    pd.DataFrame([{"period": p, "name": n, **sc.period_stats(v, *w)} for p, w in PERIODS.items() for n, v in navs.items()]
                 ).to_csv(OUT / "key_periods.csv", index=False)
    sub_rows = []
    for label, (s, e) in SUBSAMPLES.items():
        for n, v in navs.items():
            seg = segment(v, s, e)
            sub_rows.append({"subsample": label, "name": n, "annualized": sc.annualized(seg),
                             "max_drawdown": float(sc.drawdown(seg).min())})
    pd.DataFrame(sub_rows).to_csv(OUT / "subsamples.csv", index=False)

    forward, zone_counts = forward_table(levels, close, near, FORWARD_START)
    forward.to_csv(OUT / "forward_returns_by_zone.csv", index=False)
    trips = round_trips(results["V1a"], close)
    trips.to_csv(OUT / "round_trips_V1a.csv", index=False)
    rolling = rolling_starts(prices, dates, levels, near, percentile, start_i)
    rolling.to_csv(OUT / "rolling_starts.csv", index=False)
    pd.DataFrame({"trailing_yield": yld, "expanding_percentile": percentile}).dropna(how="all").to_csv(OUT / "dividend_yield.csv", index_label="date")
    sensitivity(prices, price_index, dates, start_i, levels, percentile, close, yld).to_csv(OUT / "sensitivity.csv", index=False)

    rows_placebo = []
    asset_returns = close.pct_change()
    placebo_windows = {"全区间": (dates[start_i], dates[-1]), "2014-08~2019": (dates[start_i], pd.Timestamp("2019-12-31")),
                       "2020年起": (pd.Timestamp("2020-01-01"), dates[-1])}
    for label, (begin, finish) in placebo_windows.items():
        for key in ("V1a", "V2", "V3"):
            path = results[key].weights["a"]
            rows_placebo.append({"window": label, "rule": NAMES[key], **bt.timing_placebo(
                path[(path.index >= begin) & (path.index <= finish)], asset_returns, CONFIG["cash_annual"])})
    pd.DataFrame(rows_placebo).to_csv(OUT / "timing_placebo.csv", index=False)

    source_summary = pd.read_csv(SOURCE / "summary.csv").set_index("name")
    no_cash_hold = backtest(prices, sc.rule_buy_hold({"a": 1.0, "b": 0.0}, start_i), start_i, cash=0.0)
    selfcheck = {
        "buy_hold_annualized": sc.annualized(no_cash_hold.nav),
        "buy_hold_annualized_in_2026_10_18_note": float(source_summary.loc["红利低波买入持有", "annualized"]),
        "all_execute_after_signal": all(r.checks["exec_after_signal"] for r in results.values()),
        "max_ledger_residual": max(r.checks["max_cash_plus_holdings_residual"] for r in results.values()),
        "min_cash": min(r.checks["min_cash"] for r in results.values()),
        "zone_counts_weeks": zone_counts,
        "yield_rank_first_valid": str(percentile.first_valid_index().date()),
        "still_held_since_V1a": trips.attrs.get("still_held_since"),
    }
    assert abs(selfcheck["buy_hold_annualized"] - selfcheck["buy_hold_annualized_in_2026_10_18_note"]) < 1e-3
    (OUT / "selfcheck.json").write_text(json.dumps(selfcheck, indent=2, ensure_ascii=False))
    (OUT / "config.json").write_text(json.dumps(CONFIG, indent=2, ensure_ascii=False))

    pd.set_option("display.width", 220, "display.max_columns", 30, "display.float_format", lambda x: f"{x:.4f}")
    print(pd.DataFrame(rows)[["name", "annualized", "max_drawdown", "annual_vol", "calmar", "longest_recovery_days", "rolling3y_worst_annualized", "avg_exposure", "n_trades", "turnover_per_year"]])
    print(json.dumps(selfcheck, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
