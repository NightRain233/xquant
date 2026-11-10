"""QQQ under the two S&P 500 rules, unchanged, scored against both frozen goals.

Run (from repo root): .venv/bin/python scripts/research_qqq_trend_strategies.py
Reads existing caches of ``weinstein-quick-checks-2026-10-18`` and ``weinstein-us-sector-2026-10-18``.
Rules, parameters and criteria come from ``research_index_enhance_strategies.py``; nothing is tuned for QQQ.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from research_index_enhance_strategies import Market, average_weight, load_sp500, segment_nav, yearly_returns  # noqa: E402
from xquant import band_timing as bt  # noqa: E402
from xquant import position_rules as pr  # noqa: E402
from xquant import style_combo as sc  # noqa: E402
from xquant.weinstein_stage import load_yfinance_csv  # noqa: E402

SLUG = "qqq-trend-strategies-2026-11-05"
OUT = ROOT / "outputs" / SLUG
QQQ_SOURCE = ROOT / "outputs" / "weinstein-quick-checks-2026-10-18"
BORROW_SPREAD = 0.015
CONFIG = {
    "asset": "QQQ auto-adjusted (dividends reinvested)", "cash": "13-week T-bill yield (^IRX), previous close",
    "execution": "weekly-close signal, trade at next close, 10bp per side", "borrow_spread": BORROW_SPREAD,
    "start_rule": "first trading day of the first month with a full 200-day mean", "end": "2026-10-16",
    "segments": ["start~2012", "2013~2026-10"],
    "L": "weekly close above 200-day mean 1.5x (re-levered at month ends), else cash",
    "H": "100% above a rising 30-week mean, 50% after a weekly close below it",
    "scored_against": "both the more-return and the less-drawdown criteria of the S&P 500 test",
    "same_window_comparison": "SPY over the QQQ window, same rules",
    "after_bust_view": "2003-01-02 start, to remove the benefit of starting at the 2000 peak",
}
PERIODS = {"2000-03~2002-10": ("2000-03-27", "2002-10-09"), "2007-10~2009-03": ("2007-10-31", "2009-03-09"),
           "2020-02~03": ("2020-02-19", "2020-03-23"), "2022全年": ("2022-01-01", "2022-12-31"),
           "2023至今": ("2023-01-01", "2026-10-16")}
RULE_NAMES = {"L": "1.5倍趋势杠杆", "H": "半仓持有+半仓趋势"}


def load_qqq() -> pd.Series:
    path = QQQ_SOURCE / "cache" / "yf_QQQ.csv"
    close = load_yfinance_csv(path)["close"]
    return close[close.index <= CONFIG["end"]]


def make_market(name, close, bill, start):
    segments = {"起点~2012": (start, "2012-12-31"), "2013~2026-10": ("2013-01-01", CONFIG["end"])}
    return Market(name, close, bill.reindex(close.index).ffill(), (start, CONFIG["end"]), segments, BORROW_SPREAD)


def builders(market):
    states = pr.stage_states(market.close)
    return {"L": lambda i: pr.rule_trend_leverage(market.close, i),
            "H": lambda i: pr.rule_stage_blend(states, market.dates, i)}


def score(market, key, result, start_i=None):
    hold = market.hold(start_i=start_i)
    m, h = sc.summary_metrics(result.nav, result.trades), sc.summary_metrics(hold.nav, hold.trades)
    weight = average_weight(result)
    fixed = sc.summary_metrics(market.fixed(weight, start_i=start_i).nav)
    dd_share = sc.drawdown(result.nav)
    hold_share = sc.drawdown(hold.nav)
    row = {"market": market.name, "rule": RULE_NAMES[key], "start": result.nav.index[0].date(),
           "annualized": m["annualized"], "hold_annualized": h["annualized"],
           "multiple": result.nav.iloc[-1] / result.nav.iloc[0], "hold_multiple": hold.nav.iloc[-1] / hold.nav.iloc[0],
           "max_drawdown": m["max_drawdown"], "hold_max_drawdown": h["max_drawdown"], "calmar": m["calmar"],
           "hold_calmar": h["calmar"], "fixed_calmar": fixed["calmar"], "annual_vol": m["annual_vol"], "hold_vol": h["annual_vol"],
           "time_below_minus20": float((dd_share < -0.2).mean()), "hold_time_below_minus20": float((hold_share < -0.2).mean()),
           "longest_recovery_days": m["longest_recovery_days"], "hold_longest_recovery_days": h["longest_recovery_days"],
           "avg_weight": weight, "n_trades": m["n_trades"], "turnover_per_year": m["turnover_per_year"]}
    seg_ok = True
    for label, (s, e) in market.segments.items():
        rule_seg, hold_seg = segment_nav(result.nav, s, e), segment_nav(hold.nav, s, e)
        if len(rule_seg) < 2:
            continue
        row[f"seg {label}"], row[f"seg hold {label}"] = sc.annualized(rule_seg), sc.annualized(hold_seg)
        row[f"seg dd {label}"], row[f"seg hold dd {label}"] = float(sc.drawdown(rule_seg).min()), float(sc.drawdown(hold_seg).min())
        seg_ok = seg_ok and row[f"seg {label}"] >= row[f"seg hold {label}"]
    more = {"beats_hold_full": m["annualized"] >= h["annualized"], "beats_hold_segments": seg_ok,
            "drawdown_within_5pts": m["max_drawdown"] >= h["max_drawdown"] - 0.05}
    less = {"drawdown_30pct_smaller": abs(m["max_drawdown"]) <= 0.7 * abs(h["max_drawdown"]),
            "gives_up_at_most_2pts": m["annualized"] >= h["annualized"] - 0.02,
            "calmar_above_fixed": m["calmar"] > fixed["calmar"]}
    row["more_return_checks"], row["passed_more_return"] = json.dumps({k: bool(v) for k, v in more.items()}), all(more.values())
    row["less_drawdown_checks"], row["passed_less_drawdown"] = json.dumps({k: bool(v) for k, v in less.items()}), all(less.values())
    return row


def rolling_rows(market, build):
    rows = []
    for year in sorted(set(market.dates[market.start_i:].year)):
        i = max(int(market.dates.searchsorted(pd.Timestamp(f"{year}-01-01"))), market.start_i)
        if len(market.dates) - i < 756:
            continue
        hold = sc.summary_metrics(market.hold(start_i=i).nav)
        for key, b in build.items():
            m = sc.summary_metrics(market.run(b(i), start_i=i).nav)
            rows.append({"market": market.name, "rule": RULE_NAMES[key], "start": market.dates[i], "annualized": m["annualized"],
                         "hold_annualized": hold["annualized"], "max_drawdown": m["max_drawdown"], "hold_max_drawdown": hold["max_drawdown"]})
    return rows


def sensitivity(market):
    rows, j = [], market.start_i

    def add(key, label, result):
        m = sc.summary_metrics(result.nav, result.trades)
        rows.append({"rule": RULE_NAMES[key], "variant": label, "annualized": m["annualized"], "max_drawdown": m["max_drawdown"],
                     "calmar": m["calmar"], "avg_weight": average_weight(result), "n_trades": m["n_trades"]})

    close, dates = market.close, market.dates
    for leverage in (1.0, 1.25, 2.0):
        add("L", f"杠杆 {leverage}倍", market.run(pr.rule_trend_leverage(close, j, leverage=leverage)))
    add("L", "150日均线", market.run(pr.rule_trend_leverage(close, j, ma_days=150)))
    add("L", "每日检查", market.run(pr.rule_trend_leverage(close, j, check="day")))
    for spread in (0.01, 0.025):
        add("L", f"融资利差 {spread:.1%}", market.run(pr.rule_trend_leverage(close, j), borrow_spread=spread))
    for cost in (0.0005, 0.003):
        add("L", f"单边成本 {cost * 1e4:.0f}bp", market.run(pr.rule_trend_leverage(close, j), cost=cost))
    states = pr.stage_states(close)
    for off in (0.0, 0.25, 0.75):
        add("H", f"趋势破位后仓位 {off:.0%}", market.run(pr.rule_stage_blend(states, dates, j, off=off)))
    for weeks in (20, 40):
        add("H", f"{weeks}周均线", market.run(pr.rule_stage_blend(pr.stage_states(close, weeks), dates, j)))
    add("H", "现金 0%", market.run(pr.rule_stage_blend(states, dates, j), cash=0.0))
    for cost in (0.0005, 0.003):
        add("H", f"单边成本 {cost * 1e4:.0f}bp", market.run(pr.rule_stage_blend(states, dates, j), cost=cost))
    return pd.DataFrame(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    qqq = load_qqq()
    spy, bill = load_sp500()
    mean_ready = qqq.rolling(200).mean().first_valid_index()
    start = str((mean_ready + pd.offsets.MonthBegin(1)).date())
    print("QQQ first", qqq.index[0].date(), "200-day ready", mean_ready.date(), "start", start)
    full_bill = bill.reindex(bill.index.union(qqq.index)).ffill()
    markets = {"QQQ": make_market("QQQ", qqq, full_bill, start), "SPY": make_market("SPY", spy, bill, start),
               "QQQ 2003起": make_market("QQQ 2003起", qqq, full_bill, "2003-01-02"),
               "SPY 2003起": make_market("SPY 2003起", spy, bill, "2003-01-02")}
    rows, rolling, yearly, periods = [], [], {}, []
    for label, market in markets.items():
        build = builders(market)
        hold = market.hold()
        navs = {f"{label} 持有": hold.nav}
        for key, b in build.items():
            result = market.run(b(market.start_i))
            assert result.checks["exec_after_signal"]
            rows.append(score(market, key, result))
            navs[f"{label} {RULE_NAMES[key]}"] = result.nav
        if label in ("QQQ", "SPY"):
            rolling += rolling_rows(market, build)
            pd.DataFrame(navs).to_csv(OUT / f"nav_daily_{label}.csv", index_label="date")
            yearly.update({n: yearly_returns(v) for n, v in navs.items()})
            for period, (s, e) in PERIODS.items():
                periods += [{"period": period, "name": n, **sc.period_stats(v, s, e)} for n, v in navs.items()]
    pd.DataFrame(rows).to_csv(OUT / "verdicts.csv", index=False)
    pd.DataFrame(rolling).to_csv(OUT / "rolling_starts.csv", index=False)
    pd.DataFrame(yearly).to_csv(OUT / "yearly_returns.csv", index_label="year")
    pd.DataFrame(periods).to_csv(OUT / "key_periods.csv", index=False)
    sensitivity(markets["QQQ"]).to_csv(OUT / "sensitivity.csv", index=False)
    placebo = []
    market = markets["QQQ"]
    cash = float(market.cash.iloc[market.start_i:].mean())
    h = market.run(builders(market)["H"](market.start_i))
    placebo.append({"rule": RULE_NAMES["H"], "constant_cash_rate": cash,
                    **bt.timing_placebo(h.weights["a"], market.close.pct_change(), cash)})
    pd.DataFrame(placebo).to_csv(OUT / "timing_placebo.csv", index=False)
    (OUT / "config.json").write_text(json.dumps({**CONFIG, "start": start}, indent=2, ensure_ascii=False))

    pd.set_option("display.width", 240, "display.max_columns", 40, "display.max_rows", 200, "display.float_format", lambda x: f"{x:.3f}")
    table = pd.DataFrame(rows)
    print(table.drop(columns=["more_return_checks", "less_drawdown_checks"]).T)
    print(table[["market", "rule", "more_return_checks", "less_drawdown_checks"]].to_string())
    print(pd.DataFrame(placebo).T)
    print(sensitivity(markets["QQQ"]).to_string())
    kp = pd.DataFrame(periods)
    print(kp.pivot(index="period", columns="name", values="return"))
    print(kp.pivot(index="period", columns="name", values="max_drawdown"))
    print(pd.DataFrame(yearly).filter(like="QQQ"))
    r = pd.DataFrame(rolling)
    r["ex"] = r.annualized - r.hold_annualized
    r["ddr"] = r.max_drawdown.abs() / r.hold_max_drawdown.abs()
    print(r.groupby(["market", "rule"]).agg(n=("ex", "size"), beat=("ex", lambda s: int((s > 0).sum())), ex_med=("ex", "median"), ex_min=("ex", "min"),
                                            ex_max=("ex", "max"), dd30=("ddr", lambda s: int((s <= .7).sum())), give2=("ex", lambda s: int((s >= -.02).sum())), ddr_max=("ddr", "max")))
    print(r[r.market == "QQQ"].pivot(index="start", columns="rule", values="ex"))


if __name__ == "__main__":
    main()
