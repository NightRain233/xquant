"""What a new investor gets: every monthly entry, fixed holding horizons, holding versus the two trend rules.

Run (from repo root): .venv/bin/python scripts/research_entry_timing_horizons.py
Rules are unchanged from ``research_index_enhance_strategies.py``. Windows overlap heavily, so counts are descriptive.
"""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from research_index_enhance_strategies import load_sp500  # noqa: E402
from research_qqq_trend_strategies import OUT, builders, load_qqq, make_market  # noqa: E402
from xquant import style_combo as sc  # noqa: E402

FIRST_ENTRY = "2000-01-03"
HORIZONS = [3, 5, 10]
NEAR_HIGH = 0.05
NAMES = {"HOLD": "一直持有", "H": "半仓趋势", "L": "1.5倍杠杆"}


def monthly_entries(market):
    dates = market.dates[market.dates >= FIRST_ENTRY]
    months = dates.to_period("M")
    return [market.dates.get_loc(d) for d in dates[np.r_[True, months[1:] != months[:-1]]]]


def window_rows(market):
    rows, build = [], builders(market)
    peak = market.close.cummax()
    for i in monthly_entries(market):
        entry = market.dates[i]
        navs = {"HOLD": market.hold(start_i=i).nav, **{k: market.run(b(i), start_i=i).nav for k, b in build.items()}}
        near_high = bool(market.close.iloc[i] >= peak.iloc[i] * (1 - NEAR_HIGH))
        for years in HORIZONS:
            end = entry + pd.DateOffset(years=years)
            if end > market.dates[-1]:
                continue
            for key, nav in navs.items():
                seg = nav[nav.index <= end]
                dd = sc.drawdown(seg)
                below_start = seg < seg.iloc[0]
                rows.append({"market": market.name, "rule": NAMES[key], "entry": entry, "years": years,
                             "annualized": sc.annualized(seg), "total_return": seg.iloc[-1] / seg.iloc[0] - 1,
                             "max_drawdown": float(dd.min()), "near_high_at_entry": near_high,
                             "days_below_entry": int(below_start.sum())})
    return pd.DataFrame(rows)


def summarize(frame, label):
    wide_ann = frame.pivot(index="entry", columns="rule", values="annualized")
    rows = []
    for rule, part in frame.groupby("rule", sort=False):
        ex = part.set_index("entry")["annualized"] - wide_ann["一直持有"]
        rows.append({"subset": label, "market": part["market"].iloc[0], "years": part["years"].iloc[0], "rule": rule, "n": len(part),
                     "median": part["annualized"].median(), "p10": part["annualized"].quantile(0.10), "worst": part["annualized"].min(),
                     "lost_money": float((part["total_return"] < 0).mean()), "dd_median": part["max_drawdown"].median(),
                     "dd_worst": part["max_drawdown"].min(), "beat_hold": float((ex > 0).mean()), "excess_median": ex.median()})
    return rows


def current_state(market):
    close = market.close
    grouped = close.iloc[-1] / close.cummax().iloc[-1] - 1
    three = (close.iloc[-1] / close.iloc[-757]) ** (1 / 3) - 1
    return {"market": market.name, "date": close.index[-1].date(), "from_high": grouped, "trailing_3y_annualized": three}


def main():
    qqq = load_qqq()
    spy, bill = load_sp500()
    full_bill = bill.reindex(bill.index.union(qqq.index)).ffill()
    markets = [make_market("QQQ", qqq, full_bill, FIRST_ENTRY), make_market("SPY", spy, bill, FIRST_ENTRY)]
    frames = [window_rows(m) for m in markets]
    windows = pd.concat(frames)
    windows.to_csv(OUT / "entry_windows.csv", index=False)
    summary = []
    for (market, years), part in windows.groupby(["market", "years"], sort=False):
        summary += summarize(part, "全部入场月")
        near = part[part["near_high_at_entry"]]
        summary += summarize(near, "接近历史高点入场")
        bubble = part[part["entry"] < "2001-01-01"]
        summary += summarize(bubble, "2000年入场")
    table = pd.DataFrame(summary)
    table.to_csv(OUT / "entry_summary.csv", index=False)
    state = pd.DataFrame([current_state(m) for m in markets])
    state.to_csv(OUT / "entry_current_state.csv", index=False)
    pd.set_option("display.width", 240, "display.max_columns", 40, "display.max_rows", 300, "display.float_format", lambda x: f"{x:.3f}")
    print(state)
    print(table.to_string())
    print("share of entries near high", windows[windows.rule == "一直持有"].groupby(["market", "years"]).near_high_at_entry.mean())
    worst = windows[(windows.years == 10)].sort_values("annualized").groupby(["market", "rule"], sort=False).head(1)
    print(worst[["market", "rule", "entry", "annualized", "max_drawdown"]])


if __name__ == "__main__":
    main()
