"""Four frozen index strategies (dividend low-vol and S&P 500) against holding, with pass criteria set in advance.

Run (from repo root): .venv/bin/python scripts/research_index_enhance_strategies.py
Reads existing caches of ``dividend-lowvol-csi2000-2026-10-18`` and ``weinstein-us-sector-2026-10-18``.
CSI 2000 is left out at the user's request. All parameters and criteria are in CONFIG before any result was seen.
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
from xquant import position_rules as pr  # noqa: E402
from xquant import style_combo as sc  # noqa: E402
from xquant.weinstein_stage import load_yfinance_csv  # noqa: E402

SLUG = "index-enhance-strategies-2026-11-05"
OUT = ROOT / "outputs" / SLUG
DIV_SOURCE = ROOT / "outputs" / "dividend-lowvol-csi2000-2026-10-18"
US_SOURCE = ROOT / "outputs" / "weinstein-us-sector-2026-10-18"
CONFIG = {
    "execution": "weekly-close signal, trade at next close, 10bp per side on traded amount",
    "dividend_lowvol": {"asset": "H20269 total return", "window": ["2014-08-01", "2026-10-16"], "cash_annual": 0.02,
                        "segments": {"2014-08~2019": ["2014-08-01", "2019-12-31"], "2020~2026-10": ["2020-01-01", "2026-10-16"]}},
    "sp500": {"asset": "SPY auto-adjusted (dividends reinvested)", "window": ["1999-10-01", "2026-10-16"],
              "cash": "13-week T-bill yield (^IRX), previous close", "borrow_spread": 0.015,
              "segments": {"1999-10~2012": ["1999-10-01", "2012-12-31"], "2013~2026-10": ["2013-01-01", "2026-10-16"]},
              "window_note": "start set by the 200-day warm-up on data from 1998-12"},
    "R1_more_return": "dividend low-vol: 85% base, 100% within 2% of the 20-week 2-sigma lower band, back to 85% at the middle band, no selling at the upper band",
    "R2_less_drawdown": "dividend low-vol: weekly weight 12% / 20-day annualized vol, within 20%-100%, ignore changes under 10 points",
    "S1_more_return": "S&P 500: weekly close above 200-day mean 1.5x (re-levered at month ends), else cash; research only",
    "S2_less_drawdown": "S&P 500: 100% when above a rising 30-week mean, 50% after a weekly close below it",
    "not_tested": "S&P 500 default of plain low-cost holding equals the holding benchmark; premium filter has no reliable data",
    "pass_more_return": ["annualized >= holding in the full window", "annualized >= holding in both segments",
                         "max drawdown no more than 5 points deeper than holding"],
    "pass_less_drawdown": ["abs(max drawdown) <= 70% of holding's", "annualized at most 2 points below holding",
                           "return/drawdown above a fixed position at the rule's average weight"],
    "sensitivity_only_not_for_param_selection": True,
}
PERIODS = {
    "红利低波": {"2015股灾(6-9月)": ("2015-06-01", "2015-09-30"), "2018全年": ("2018-01-01", "2018-12-31"),
             "2021全年": ("2021-01-01", "2021-12-31"), "2024全年": ("2024-01-01", "2024-12-31"),
             "2025至今": ("2025-01-01", "2026-10-16")},
    "标普500": {"2000-03~2002-10": ("2000-03-24", "2002-10-09"), "2007-10~2009-03": ("2007-10-09", "2009-03-09"),
              "2020-02~03": ("2020-02-19", "2020-03-23"), "2022全年": ("2022-01-01", "2022-12-31"),
              "2023至今": ("2023-01-01", "2026-10-16")},
}
NAMES = {"R1": "R1 红利低波 高底仓+下轨加仓", "R2": "R2 红利低波 波动率目标", "S1": "S1 标普 1.5倍趋势杠杆",
         "S2": "S2 标普 半仓持有+半仓趋势"}
GOAL = {"R1": "more_return", "R2": "less_drawdown", "S1": "more_return", "S2": "less_drawdown"}


def verify_sha(path: Path, expected: str) -> None:
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, path


def load_dividend_lowvol() -> pd.Series:
    path = DIV_SOURCE / "cache" / "csindex_H20269.csv"
    verify_sha(path, json.loads((DIV_SOURCE / "data_manifest.json").read_text())["files"][path.name]["sha256"])
    series = pd.read_csv(path, parse_dates=["日期"]).set_index("日期")["收盘"]
    assert series.index.is_unique and series.notna().all()
    return series[series.index <= CONFIG["dividend_lowvol"]["window"][1]]


def load_sp500() -> tuple[pd.Series, pd.Series]:
    manifest = json.loads((US_SOURCE / "fetch_manifest.json").read_text())["files"]
    for name in ("yf_SPY.csv", "yf_IRX.csv"):
        verify_sha(US_SOURCE / "cache" / name, manifest[name]["sha256"])
    close = load_yfinance_csv(US_SOURCE / "cache" / "yf_SPY.csv")["close"]
    bill = load_yfinance_csv(US_SOURCE / "cache" / "yf_IRX.csv")["close"]
    bill = bill.reindex(close.index.union(bill.index)).ffill().reindex(close.index) / 100.0
    assert bill.notna().all()
    return close, bill


class Market:
    """One asset, its cash rate and the common backtest settings."""

    def __init__(self, name, close, cash, window, segments, borrow_spread=0.0):
        self.name, self.close, self.cash, self.segments, self.borrow_spread = name, close, cash, segments, borrow_spread
        self.dates = close.index
        self.prices = pd.DataFrame({"a": close, "b": close})
        self.start_i = int(self.dates.searchsorted(pd.Timestamp(window[0])))

    def run(self, signal, cost=0.001, cash=None, borrow_spread=None, start_i=None):
        return sc.run_backtest(self.prices, signal, self.start_i if start_i is None else start_i, cost,
                               self.cash if cash is None else cash,
                               self.borrow_spread if borrow_spread is None else borrow_spread)

    def hold(self, cost=0.001, cash=None, start_i=None):
        i = self.start_i if start_i is None else start_i
        return self.run(sc.rule_buy_hold({"a": 1.0, "b": 0.0}, i), cost, cash, start_i=i)

    def fixed(self, weight, cash=None, start_i=None):
        i = self.start_i if start_i is None else start_i
        return self.run(bt.rule_fixed_weight(weight, self.dates, i), cash=cash, start_i=i)


def average_weight(result) -> float:
    return float(result.weights["a"].iloc[1:].mean())


def segment_nav(nav, start, end):
    prior = nav[nav.index < pd.Timestamp(start)]
    seg = nav[(nav.index >= pd.Timestamp(start)) & (nav.index <= pd.Timestamp(end))]
    return pd.concat([prior.iloc[-1:], seg]) if len(prior) else seg


def yearly_returns(nav):
    last = nav.groupby(nav.index.year).last()
    prev = last.shift(1)
    prev.iloc[0] = nav.iloc[0]
    return last / prev - 1


def evaluate(key, market, result):
    """Apply the frozen criteria of the rule's goal; returns one row with every check."""
    hold = market.hold()
    m, h = sc.summary_metrics(result.nav, result.trades), sc.summary_metrics(hold.nav, hold.trades)
    weight = average_weight(result)
    fixed = sc.summary_metrics(market.fixed(weight).nav)
    row = {"rule": NAMES[key], "goal": GOAL[key], "annualized": m["annualized"], "hold_annualized": h["annualized"],
           "max_drawdown": m["max_drawdown"], "hold_max_drawdown": h["max_drawdown"], "calmar": m["calmar"],
           "hold_calmar": h["calmar"], "annual_vol": m["annual_vol"], "hold_vol": h["annual_vol"],
           "longest_recovery_days": m["longest_recovery_days"], "hold_longest_recovery_days": h["longest_recovery_days"],
           "rolling3y_worst": m["rolling3y_worst_annualized"], "hold_rolling3y_worst": h["rolling3y_worst_annualized"],
           "avg_weight": weight, "fixed_annualized": fixed["annualized"], "fixed_max_drawdown": fixed["max_drawdown"],
           "fixed_calmar": fixed["calmar"], "n_trades": m["n_trades"], "turnover_per_year": m["turnover_per_year"]}
    seg_ok = True
    for label, (s, e) in market.segments.items():
        rule_seg, hold_seg = segment_nav(result.nav, s, e), segment_nav(hold.nav, s, e)
        row[f"seg {label}"] = sc.annualized(rule_seg)
        row[f"seg hold {label}"] = sc.annualized(hold_seg)
        row[f"seg dd {label}"] = float(sc.drawdown(rule_seg).min())
        row[f"seg hold dd {label}"] = float(sc.drawdown(hold_seg).min())
        seg_ok = seg_ok and row[f"seg {label}"] >= row[f"seg hold {label}"]
    if GOAL[key] == "more_return":
        checks = {"beats_hold_full": m["annualized"] >= h["annualized"], "beats_hold_segments": seg_ok,
                  "drawdown_within_5pts": m["max_drawdown"] >= h["max_drawdown"] - 0.05}
    else:
        checks = {"drawdown_30pct_smaller": abs(m["max_drawdown"]) <= 0.7 * abs(h["max_drawdown"]),
                  "gives_up_at_most_2pts": m["annualized"] >= h["annualized"] - 0.02,
                  "calmar_above_fixed": m["calmar"] > fixed["calmar"]}
    row["checks"] = json.dumps({k: bool(v) for k, v in checks.items()})
    row["passed"] = all(checks.values())
    return row


def rolling_starts(market, build, key):
    """The rule from each year's first trading day with at least 3 years left, against same-window holding."""
    rows = []
    years = sorted(set(market.dates[market.start_i:].year))
    for year in years:
        i = int(market.dates.searchsorted(pd.Timestamp(f"{year}-01-01")))
        i = max(i, market.start_i)
        if len(market.dates) - i < 756:
            continue
        res, hold = market.run(build(i), start_i=i), market.hold(start_i=i)
        m, h = sc.summary_metrics(res.nav), sc.summary_metrics(hold.nav)
        rows.append({"rule": NAMES[key], "start": market.dates[i], "annualized": m["annualized"], "hold_annualized": h["annualized"],
                     "max_drawdown": m["max_drawdown"], "hold_max_drawdown": h["max_drawdown"]})
    return rows


def sensitivity_rows(div, spx):
    rows = []

    def add(key, market, label, result):
        m = sc.summary_metrics(result.nav, result.trades)
        rows.append({"rule": NAMES[key], "variant": label, "annualized": m["annualized"], "max_drawdown": m["max_drawdown"],
                     "calmar": m["calmar"], "avg_weight": average_weight(result), "n_trades": m["n_trades"]})

    i, dates = div.start_i, div.dates
    base_levels = bt.weekly_band_levels(div.close)
    for window, k in [(10, 2.0), (30, 2.0), (20, 1.5), (20, 2.5)]:
        lv = bt.weekly_band_levels(div.close, window, k)
        add("R1", div, f"布林 {window}周 {k}倍", div.run(bt.rule_core_tilt(lv, dates, i, 0.02, 0.85, 1.0, 0.85)))
    for near in (0.01, 0.03):
        add("R1", div, f"接近 {near:.0%}", div.run(bt.rule_core_tilt(base_levels, dates, i, near, 0.85, 1.0, 0.85)))
    for base in (0.8, 0.9):
        add("R1", div, f"底仓 {base:.0%}", div.run(bt.rule_core_tilt(base_levels, dates, i, 0.02, base, 1.0, base)))
    r1 = lambda: bt.rule_core_tilt(base_levels, dates, i, 0.02, 0.85, 1.0, 0.85)  # noqa: E731
    for cash in (0.0, 0.03):
        add("R1", div, f"现金 {cash:.0%}", div.run(r1(), cash=cash))
    for cost in (0.0005, 0.003):
        add("R1", div, f"单边成本 {cost * 1e4:.0f}bp", div.run(r1(), cost=cost))

    for target in (0.10, 0.15):
        add("R2", div, f"目标波动 {target:.0%}", div.run(pr.rule_vol_target(div.close, i, target=target)))
    for window in (10, 60):
        add("R2", div, f"波动窗口 {window}日", div.run(pr.rule_vol_target(div.close, i, window=window)))
    for change in (0.05, 0.20):
        add("R2", div, f"最小调仓 {change:.0%}", div.run(pr.rule_vol_target(div.close, i, min_change=change)))
    add("R2", div, "下限 0%", div.run(pr.rule_vol_target(div.close, i, floor=0.0)))
    for cash in (0.0, 0.03):
        add("R2", div, f"现金 {cash:.0%}", div.run(pr.rule_vol_target(div.close, i), cash=cash))
    for cost in (0.0005, 0.003):
        add("R2", div, f"单边成本 {cost * 1e4:.0f}bp", div.run(pr.rule_vol_target(div.close, i), cost=cost))

    j = spx.start_i
    for leverage in (1.0, 1.25, 2.0):
        add("S1", spx, f"杠杆 {leverage}倍", spx.run(pr.rule_trend_leverage(spx.close, j, leverage=leverage)))
    for days in (150, 250):
        if not np.isnan(spx.close.rolling(days).mean().iloc[j]):
            add("S1", spx, f"{days}日均线", spx.run(pr.rule_trend_leverage(spx.close, j, ma_days=days)))
    add("S1", spx, "每日检查", spx.run(pr.rule_trend_leverage(spx.close, j, check="day")))
    for spread in (0.01, 0.025):
        add("S1", spx, f"融资利差 {spread:.1%}", spx.run(pr.rule_trend_leverage(spx.close, j), borrow_spread=spread))
    for cost in (0.0005, 0.003):
        add("S1", spx, f"单边成本 {cost * 1e4:.0f}bp", spx.run(pr.rule_trend_leverage(spx.close, j), cost=cost))

    states = pr.stage_states(spx.close)
    for off in (0.0, 0.25, 0.75):
        add("S2", spx, f"趋势破位后仓位 {off:.0%}", spx.run(pr.rule_stage_blend(states, spx.dates, j, off=off)))
    for weeks in (20, 40):
        add("S2", spx, f"{weeks}周均线", spx.run(pr.rule_stage_blend(pr.stage_states(spx.close, weeks), spx.dates, j)))
    add("S2", spx, "现金 0%", spx.run(pr.rule_stage_blend(states, spx.dates, j), cash=0.0))
    for cost in (0.0005, 0.003):
        add("S2", spx, f"单边成本 {cost * 1e4:.0f}bp", spx.run(pr.rule_stage_blend(states, spx.dates, j), cost=cost))
    return pd.DataFrame(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    div_cfg, spx_cfg = CONFIG["dividend_lowvol"], CONFIG["sp500"]
    div = Market("红利低波", load_dividend_lowvol(), div_cfg["cash_annual"], div_cfg["window"], div_cfg["segments"])
    close, bill = load_sp500()
    spx = Market("标普500", close, bill, spx_cfg["window"], spx_cfg["segments"], spx_cfg["borrow_spread"])

    levels = bt.weekly_band_levels(div.close)
    states = pr.stage_states(spx.close)
    builders = {
        "R1": (div, lambda i: bt.rule_core_tilt(levels, div.dates, i, 0.02, 0.85, 1.0, 0.85)),
        "R2": (div, lambda i: pr.rule_vol_target(div.close, i)),
        "S1": (spx, lambda i: pr.rule_trend_leverage(spx.close, i)),
        "S2": (spx, lambda i: pr.rule_stage_blend(states, spx.dates, i)),
    }
    results = {k: m.run(build(m.start_i)) for k, (m, build) in builders.items()}
    verdicts = pd.DataFrame([evaluate(k, builders[k][0], r) for k, r in results.items()])
    verdicts.to_csv(OUT / "verdicts.csv", index=False)

    frames = {"红利低波": (div, ["R1", "R2"]), "标普500": (spx, ["S1", "S2"])}
    yearly, periods = [], []
    for label, (market, keys) in frames.items():
        hold, navs = market.hold(), {}
        navs[f"{label}买入持有"] = hold.nav
        for key in keys:
            navs[NAMES[key]] = results[key].nav
        pd.DataFrame(navs).to_csv(OUT / f"nav_daily_{label}.csv", index_label="date")
        yearly.append(pd.DataFrame({n: yearly_returns(v) for n, v in navs.items()}).assign(market=label))
        for period, (s, e) in PERIODS[label].items():
            for n, v in navs.items():
                periods.append({"market": label, "period": period, "name": n, **sc.period_stats(v, s, e)})
    pd.concat(yearly).to_csv(OUT / "yearly_returns.csv", index_label="year")
    pd.DataFrame(periods).to_csv(OUT / "key_periods.csv", index=False)
    pd.DataFrame({NAMES[k]: r.weights["a"] for k, r in results.items()}).to_csv(OUT / "weights_daily.csv", index_label="date")

    rolling = [row for k, (m, build) in builders.items() for row in rolling_starts(m, build, k)]
    pd.DataFrame(rolling).to_csv(OUT / "rolling_starts.csv", index=False)

    placebo = []
    for key in ("R1", "R2", "S2"):
        market = builders[key][0]
        cash = market.cash if isinstance(market.cash, float) else float(market.cash.iloc[market.start_i:].mean())
        placebo.append({"rule": NAMES[key], "constant_cash_rate": cash,
                        **bt.timing_placebo(results[key].weights["a"], market.close.pct_change(), cash)})
    pd.DataFrame(placebo).to_csv(OUT / "timing_placebo.csv", index=False)
    sensitivity_rows(div, spx).to_csv(OUT / "sensitivity.csv", index=False)

    previous = pd.read_csv(DIV_SOURCE / "summary.csv").set_index("name")
    div_hold = sc.annualized(div.hold().nav)
    us_prior = pd.read_csv(ROOT / "outputs" / "weinstein-quick-checks-2026-10-18" / "research_summary.csv")
    prior_spy = us_prior[(us_prior.instrument == "SPY") & (us_prior.strategy == "买入持有")]["cagr"].iloc[0]
    i_prior = int(spx.dates.searchsorted(pd.Timestamp("1999-08-02")))
    spy_prior_window = sc.annualized(spx.hold(start_i=i_prior).nav)
    selfcheck = {"dividend_hold_annualized": div_hold,
                 "dividend_hold_in_prior_note": float(previous.loc["红利低波买入持有", "annualized"]),
                 "spy_hold_same_window_as_prior": spy_prior_window, "spy_hold_in_prior_note": float(prior_spy),
                 "all_execute_after_signal": all(r.checks["exec_after_signal"] for r in results.values()),
                 "max_ledger_residual": max(r.checks["max_cash_plus_holdings_residual"] for r in results.values())}
    assert abs(selfcheck["dividend_hold_annualized"] - selfcheck["dividend_hold_in_prior_note"]) < 1e-3
    assert abs(spy_prior_window - float(prior_spy)) < 2e-3
    (OUT / "selfcheck.json").write_text(json.dumps(selfcheck, indent=2, ensure_ascii=False))
    (OUT / "config.json").write_text(json.dumps(CONFIG, indent=2, ensure_ascii=False))

    pd.set_option("display.width", 240, "display.max_columns", 40, "display.max_rows", 200, "display.float_format", lambda x: f"{x:.3f}")
    print(verdicts.T)
    print(json.dumps(selfcheck, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
