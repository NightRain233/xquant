"""Half-trend rule on the mainland ETFs 513500 (S&P 500) and 513100 (Nasdaq 100), traded at their own RMB prices.

Run (from repo root): .venv/bin/python scripts/research_domestic_us_etf_trend.py
Prices: unadjusted TickFlow closes from ``domestic-etf-small-account-2026-10-04`` with the official unit splits
(513100 1:5 effective 2022-01-14, 513500 1:2 effective 2022-03-30); neither fund paid cash in the checked records.
The ETF price already contains premium/discount, RMB moves and fund fees, so none of them is modelled separately.
Rules and criteria are unchanged from the S&P 500 test; everything below is fixed before any result was seen.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from research_index_enhance_strategies import load_sp500  # noqa: E402
from research_qqq_trend_strategies import load_qqq  # noqa: E402
from xquant import band_timing as bt  # noqa: E402
from xquant import position_rules as pr  # noqa: E402
from xquant import style_combo as sc  # noqa: E402

SLUG = "domestic-us-etf-trend-2026-11-10"
OUT = ROOT / "outputs" / SLUG
SOURCE = ROOT / "outputs" / "domestic-etf-small-account-2026-10-04"
RAW_FILE = SOURCE / "evidence" / "raw_510300.SH.json"
FORWARD_FILE = SOURCE / "evidence" / "forward_core.json"
SPLITS = {"513100": ("2022-01-14", 5), "513500": ("2022-03-30", 2)}
US_PAIR = {"513500": "SPY", "513100": "QQQ"}
CONFIG = {
    "window": ["2014-10-08", "2026-09-30"], "cost_one_way": 0.001, "cash_annual": 0.02,
    "rule": "100% above a rising 30-week mean, 50% after a weekly close below it",
    "signal_main": "US ETF (SPY/QQQ) weekly close; traded at the close of the first mainland trading day after that US date",
    "signal_alt": "the mainland ETF's own weekly close; traded at the next mainland close",
    "prices": "unadjusted closes with official unit splits; forward-adjusted series only as a check",
    "pass_less_drawdown": ["abs(max drawdown) <= 70% of holding's", "annualized at most 2 points below holding",
                           "return/drawdown above a fixed position at the rule's average weight"],
    "also_reported": ["US ETF in USD with the same rule over the same window", "monthly entries held 3 and 5 years"],
    "sensitivity_only": ["cash 0%/3%", "cost 30bp", "signal lag one extra mainland day"],
}
EXPECTED_SHA = {RAW_FILE.name: "ace18b4e70d3029e959b7c72e77c6c6300a90ecd673fa1dcaf3c085c8d1ca8b6",
                FORWARD_FILE.name: "9b5670f70c451c2640af5bd9ef9f629df44b05e49dd26921a3070fb614556b2a"}


def load_provider(path: Path, symbol: str) -> pd.Series:
    assert hashlib.sha256(path.read_bytes()).hexdigest() == EXPECTED_SHA[path.name], path
    data = json.loads(path.read_text())["data"][f"{symbol}.SH"]
    dates = (pd.to_datetime(data["timestamp"], unit="ms", utc=True).tz_convert("Asia/Shanghai").tz_localize(None).normalize())
    close = pd.Series(np.asarray(data["close"], float), index=dates).sort_index()
    return close[~close.index.duplicated()]


def domestic_close(symbol: str) -> pd.Series:
    close = load_provider(RAW_FILE, symbol)
    date, ratio = SPLITS[symbol]
    close.loc[close.index < date] /= ratio
    return close[close.index <= CONFIG["window"][1]]


def us_state_signal(us_close: pd.Series, dates: pd.DatetimeIndex, start_i: int, lag: int = 0, on=1.0, off=0.5):
    """Mainland execution of a US weekly state: the trade on mainland day i+1 uses US weeks dated before day i+1 (minus lag)."""
    states = pr.stage_states(us_close)
    week_dates = states.index.to_numpy()
    values = states.to_numpy()
    state = {"weight": None}

    def known_weight(j):
        k = int(np.searchsorted(week_dates, dates[j].to_datetime64(), side="left")) - 1
        if k < 0:
            raise ValueError("US state not warmed up")
        return on if values[k] else off

    def sig(i):
        j = min(i + 1 + lag, len(dates) - 1)
        wanted = known_weight(j)
        if i == start_i or wanted != state["weight"]:
            state["weight"] = wanted
            return {"a": wanted, "b": 0.0}
        return None
    return sig


def run(prices, signal, start_i, cost=None, cash=None):
    return sc.run_backtest(prices, signal, start_i, CONFIG["cost_one_way"] if cost is None else cost,
                           CONFIG["cash_annual"] if cash is None else cash)


def score(name, result, hold, prices, dates, start_i):
    m, h = sc.summary_metrics(result.nav, result.trades), sc.summary_metrics(hold.nav)
    weight = float(result.weights["a"].iloc[1:].mean())
    fixed = sc.summary_metrics(run(prices, bt.rule_fixed_weight(weight, dates, start_i), start_i).nav)
    checks = {"drawdown_30pct_smaller": abs(m["max_drawdown"]) <= 0.7 * abs(h["max_drawdown"]),
              "gives_up_at_most_2pts": m["annualized"] >= h["annualized"] - 0.02,
              "calmar_above_fixed": m["calmar"] > fixed["calmar"]}
    return {"name": name, "annualized": m["annualized"], "hold_annualized": h["annualized"], "max_drawdown": m["max_drawdown"],
            "hold_max_drawdown": h["max_drawdown"], "calmar": m["calmar"], "hold_calmar": h["calmar"], "fixed_calmar": fixed["calmar"],
            "annual_vol": m["annual_vol"], "hold_vol": h["annual_vol"], "time_below_minus20": float((sc.drawdown(result.nav) < -0.2).mean()),
            "hold_time_below_minus20": float((sc.drawdown(hold.nav) < -0.2).mean()), "avg_weight": weight,
            "n_trades": m["n_trades"], "checks": json.dumps({k: bool(v) for k, v in checks.items()}), "passed": all(checks.values())}


def entry_rows(name, prices, dates, build, years_list=(3, 5)):
    rows = []
    months = dates.to_period("M")
    starts = np.flatnonzero(np.r_[True, months[1:] != months[:-1]] & (dates >= CONFIG["window"][0]))
    for i in starts:
        navs = {"一直持有": run(prices, sc.rule_buy_hold({"a": 1.0, "b": 0.0}, i), i).nav, "半仓趋势": run(prices, build(i), i).nav}
        for years in years_list:
            end = dates[i] + pd.DateOffset(years=years)
            if end > dates[-1]:
                continue
            for rule, nav in navs.items():
                seg = nav[nav.index <= end]
                rows.append({"name": name, "rule": rule, "entry": dates[i], "years": years, "annualized": sc.annualized(seg),
                             "max_drawdown": float(sc.drawdown(seg).min()), "lost_money": bool(seg.iloc[-1] < seg.iloc[0])})
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    spy, _ = load_sp500()
    us = {"SPY": spy, "QQQ": load_qqq()}
    rows, sens, entries, yearly, periods, gaps = [], [], [], {}, [], []
    for symbol, us_name in US_PAIR.items():
        close = domestic_close(symbol)
        dates = close.index
        prices = pd.DataFrame({"a": close, "b": close})
        start_i = int(dates.searchsorted(pd.Timestamp(CONFIG["window"][0])))
        hold = run(prices, sc.rule_buy_hold({"a": 1.0, "b": 0.0}, start_i), start_i)
        main_sig = lambda i, c=us[us_name], d=dates: us_state_signal(c, d, i)  # noqa: E731
        own_states = pr.stage_states(close)
        alt_sig = lambda i, s=own_states, d=dates: pr.rule_stage_blend(s, d, i)  # noqa: E731
        results = {"美股信号": run(prices, main_sig(start_i), start_i), "境内自身信号": run(prices, alt_sig(start_i), start_i)}
        for label, res in results.items():
            assert res.checks["exec_after_signal"]
            rows.append({"etf": symbol, **score(f"{symbol} 半仓趋势({label})", res, hold, prices, dates, start_i)})
        navs = {f"{symbol} 持有": hold.nav, **{f"{symbol} 半仓趋势({k})": r.nav for k, r in results.items()}}

        # same rule on the US ETF in USD over the same calendar window (T-bill cash as in the US test)
        us_close = us[us_name]
        us_close = us_close[us_close.index <= CONFIG["window"][1]]
        _, bill = load_sp500()
        us_prices = pd.DataFrame({"a": us_close, "b": us_close})
        us_i = int(us_close.index.searchsorted(pd.Timestamp(CONFIG["window"][0])))
        us_hold = sc.run_backtest(us_prices, sc.rule_buy_hold({"a": 1.0, "b": 0.0}, us_i), us_i, 0.001, bill)
        us_rule = sc.run_backtest(us_prices, pr.rule_stage_blend(pr.stage_states(us[us_name]), us_close.index, us_i), us_i, 0.001, bill)
        rows.append({"etf": symbol, **score(f"{us_name}(美元) 半仓趋势", us_rule, us_hold, us_prices, us_close.index, us_i)})
        navs[f"{us_name}(美元) 持有"], navs[f"{us_name}(美元) 半仓趋势"] = us_hold.nav, us_rule.nav
        pd.DataFrame(navs).to_csv(OUT / f"nav_daily_{symbol}.csv", index_label="date")
        for n, v in navs.items():
            last = v.groupby(v.index.year).last()
            prev = last.shift(1)
            prev.iloc[0] = v.iloc[0]
            yearly[n] = last / prev - 1
        for period, (s, e) in {"2018年10-12月": ("2018-10-01", "2018-12-31"), "2020年2-3月": ("2020-02-19", "2020-03-23"),
                               "2022全年": ("2022-01-01", "2022-12-31"), "2025年2-4月": ("2025-02-19", "2025-04-30"),
                               "2023至今": ("2023-01-01", CONFIG["window"][1])}.items():
            periods += [{"period": period, "name": n, **sc.period_stats(v, s, e)} for n, v in navs.items()]
        forward = load_provider(FORWARD_FILE, symbol)
        forward = forward[(forward.index >= CONFIG["window"][0]) & (forward.index <= CONFIG["window"][1])]
        gaps.append({"etf": symbol, "split_adjusted_annualized": sc.annualized(close[close.index >= CONFIG["window"][0]]),
                     "forward_adjusted_annualized": sc.annualized(forward),
                     "domestic_hold_annualized": sc.annualized(hold.nav), "us_hold_annualized_usd": sc.annualized(us_hold.nav)})

        for cash in (0.0, 0.03):
            r = run(prices, main_sig(start_i), start_i, cash=cash)
            sens.append({"etf": symbol, "variant": f"现金 {cash:.0%}", **{k: v for k, v in score("", r, run(prices, sc.rule_buy_hold({"a": 1.0, "b": 0.0}, start_i), start_i, cash=cash), prices, dates, start_i).items() if k != "name"}})
        r = run(prices, main_sig(start_i), start_i, cost=0.003)
        sens.append({"etf": symbol, "variant": "单边成本 30bp", **{k: v for k, v in score("", r, run(prices, sc.rule_buy_hold({"a": 1.0, "b": 0.0}, start_i), start_i, cost=0.003), prices, dates, start_i).items() if k != "name"}})
        r = run(prices, us_state_signal(us[us_name], dates, start_i, lag=1), start_i)
        sens.append({"etf": symbol, "variant": "晚一天成交", **{k: v for k, v in score("", r, hold, prices, dates, start_i).items() if k != "name"}})
        entries += entry_rows(symbol, prices, dates, main_sig)

    verdicts = pd.DataFrame(rows)
    verdicts.to_csv(OUT / "verdicts.csv", index=False)
    pd.DataFrame(sens).to_csv(OUT / "sensitivity.csv", index=False)
    pd.DataFrame(yearly).to_csv(OUT / "yearly_returns.csv", index_label="year")
    pd.DataFrame(periods).to_csv(OUT / "key_periods.csv", index=False)
    pd.DataFrame(gaps).to_csv(OUT / "price_checks.csv", index=False)
    entry = pd.DataFrame(entries)
    entry.to_csv(OUT / "entry_windows.csv", index=False)
    entry_summary = entry.groupby(["name", "years", "rule"]).agg(
        n=("annualized", "size"), median=("annualized", "median"), p10=("annualized", lambda s: s.quantile(0.1)),
        worst=("annualized", "min"), lost_money=("lost_money", "mean"), dd_median=("max_drawdown", "median"),
        dd_worst=("max_drawdown", "min")).reset_index()
    entry_summary.to_csv(OUT / "entry_summary.csv", index=False)
    (OUT / "config.json").write_text(json.dumps(CONFIG, indent=2, ensure_ascii=False))

    pd.set_option("display.width", 240, "display.max_columns", 30, "display.max_rows", 200, "display.float_format", lambda x: f"{x:.3f}")
    print(verdicts.T)
    print(pd.DataFrame(sens).T)
    print(pd.DataFrame(gaps))
    print(pd.DataFrame(yearly))
    kp = pd.DataFrame(periods)
    print(kp.pivot(index="period", columns="name", values="return").T)
    print(kp.pivot(index="period", columns="name", values="max_drawdown").T)
    print(entry_summary)


if __name__ == "__main__":
    main()
