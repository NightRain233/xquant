"""Entry methods for a new investor: lump sum, 12-month staged entry and monthly contributions,
each with plain holding or the half-trend rule, on SPY and QQQ (rules unchanged, run once).

Run (from repo root): .venv/bin/python scripts/research_entry_methods.py
Every monthly start gets its own backtest; staged entry and monthly contributions are sums of those
sub-accounts, so each tranche follows the rule from the day it is invested. Windows overlap heavily.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from research_index_enhance_strategies import load_sp500  # noqa: E402
from research_qqq_trend_strategies import builders, load_qqq, make_market  # noqa: E402
from xquant import style_combo as sc  # noqa: E402

SLUG = "entry-methods-2026-11-10"
OUT = ROOT / "outputs" / SLUG
CACHE = OUT / "cache"
FIRST_ENTRY = "2000-01-03"
HORIZONS = [3, 5, 10]
TRANCHES = 12
CONFIG = {
    "markets": ["SPY", "QQQ"], "rules": {"hold": "buy and hold", "half": "100% above a rising 30-week mean, 50% after a weekly close below it"},
    "methods": {"lump": "all capital on the entry month's first trading day",
                "staged12": "capital split into 12 equal monthly tranches; waiting money earns the T-bill rate",
                "monthly": "one equal contribution on the first trading day of every month of the horizon"},
    "entries": "first trading day of every month from 2000-01", "horizons_years": HORIZONS,
    "execution": "weekly-close signal, trade at next close, 10bp per side; cash earns 13-week T-bill (^IRX)",
    "metrics": {"lump/staged12": "annualized return on the full capital, max drawdown of account value, share losing money",
                "monthly": "money-weighted annual return (XIRR), final value / contributions, worst floating loss vs money put in"},
    "note": "staged and monthly results are sums of per-tranche sub-accounts that each follow the rule",
}
RULE_NAMES = {"hold": "一直持有", "half": "半仓趋势"}
METHOD_NAMES = {"lump": "一次性买入", "staged12": "12个月分批", "monthly": "每月定投"}


def month_starts(dates: pd.DatetimeIndex) -> np.ndarray:
    months = dates.to_period("M")
    first = np.r_[True, months[1:] != months[:-1]]
    return np.flatnonzero(first & (dates >= FIRST_ENTRY))


def cash_index(market) -> np.ndarray:
    """Growth of 1 in cash with the same accrual as the backtest (previous close's rate)."""
    rates = market.cash.reindex(market.dates).ffill().to_numpy(float)
    days = np.r_[0, np.diff(market.dates.values).astype("timedelta64[D]").astype(float)]
    growth = np.ones(len(rates))
    growth[1:] = (1.0 + rates[:-1]) ** (days[1:] / 365.0)
    return np.cumprod(growth)


def nav_matrix(market, rule: str, starts: np.ndarray) -> np.ndarray:
    path = CACHE / f"nav_{market.name}_{rule}.npy"
    if path.exists():
        return np.load(path)
    matrix = np.full((len(starts), len(market.dates)), np.nan)
    build = builders(market)["H"]
    for row, i in enumerate(starts):
        result = market.hold(start_i=i) if rule == "hold" else market.run(build(i), start_i=i)
        matrix[row, i:] = result.nav.to_numpy(float)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(path, matrix)
    return matrix


def xirr(dates: list[pd.Timestamp], flows: list[float]) -> float:
    t = np.array([(d - dates[0]).days / 365.25 for d in dates])
    f = np.array(flows)
    lo, hi = -0.99, 2.0
    value = lambda r: float((f / (1.0 + r) ** t).sum())  # noqa: E731
    if value(lo) * value(hi) > 0:
        return float("nan")
    for _ in range(200):
        mid = (lo + hi) / 2
        if value(lo) * value(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def max_drawdown(path: np.ndarray) -> float:
    return float((path / np.maximum.accumulate(path) - 1.0).min())


def windows(market, rule, matrix, starts, cash):
    dates = market.dates
    rows = []
    for s, i in enumerate(starts):
        for years in HORIZONS:
            end_date = dates[i] + pd.DateOffset(years=years)
            if end_date > dates[-1]:
                continue
            e = int(dates.searchsorted(end_date, side="right")) - 1
            span = (dates[e] - dates[i]).days / 365.25
            base = {"market": market.name, "rule": RULE_NAMES[rule], "entry": dates[i], "years": years}
            lump = matrix[s, i:e + 1]
            rows.append({**base, "method": METHOD_NAMES["lump"], "annualized": lump[-1] ** (1 / span) - 1,
                         "final_multiple": lump[-1], "max_drawdown": max_drawdown(lump), "lost_money": lump[-1] < 1})
            if s + TRANCHES - 1 < len(starts) and starts[s + TRANCHES - 1] <= e:
                staged = np.zeros(e - i + 1)
                for k in range(s, s + TRANCHES):
                    j = starts[k]
                    waiting = cash[i:e + 1] / cash[i]
                    invested = cash[j] / cash[i] * np.nan_to_num(matrix[k, i:e + 1])
                    staged += np.where(np.arange(i, e + 1) < j, waiting, invested) / TRANCHES
                rows.append({**base, "method": METHOD_NAMES["staged12"], "annualized": staged[-1] ** (1 / span) - 1,
                             "final_multiple": staged[-1], "max_drawdown": max_drawdown(staged), "lost_money": staged[-1] < 1})
            members = [k for k in range(s, len(starts)) if starts[k] < e and dates[starts[k]] < end_date]
            value = np.nansum(matrix[members, i:e + 1], axis=0)
            put_in = np.searchsorted(starts[members], np.arange(i, e + 1), side="right").astype(float)
            floating = (value - put_in) / put_in
            flows_dates = [dates[starts[k]] for k in members] + [dates[e]]
            flows = [-1.0] * len(members) + [float(value[-1])]
            rows.append({**base, "method": METHOD_NAMES["monthly"], "annualized": xirr(flows_dates, flows),
                         "final_multiple": float(value[-1] / len(members)), "max_drawdown": float(floating.min()),
                         "lost_money": value[-1] < len(members)})
    return rows


def summarize(frame):
    rows = []
    keys = ["market", "years", "method", "rule"]
    hold = frame[frame.rule == RULE_NAMES["hold"]].set_index(["market", "years", "method", "entry"])["annualized"]
    for key, part in frame.groupby(keys, sort=False):
        idx = pd.MultiIndex.from_arrays([part.market, part.years, part.method, part.entry])
        excess = part["annualized"].to_numpy() - hold.reindex(idx).to_numpy()
        for subset, mask in [("全部入场月", np.ones(len(part), bool)), ("2000年入场", (part.entry < "2001-01-01").to_numpy())]:
            p = part[mask]
            if p.empty:
                continue
            rows.append({**dict(zip(keys, key)), "subset": subset, "n": len(p), "median": p.annualized.median(),
                         "p10": p.annualized.quantile(0.10), "worst": p.annualized.min(), "lost_money": p.lost_money.mean(),
                         "dd_median": p.max_drawdown.median(), "dd_worst": p.max_drawdown.min(),
                         "excess_vs_hold_median": float(np.median(excess[mask]))})
    return pd.DataFrame(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    qqq = load_qqq()
    spy, bill = load_sp500()
    full_bill = bill.reindex(bill.index.union(qqq.index)).ffill()
    markets = [make_market("SPY", spy, bill, FIRST_ENTRY), make_market("QQQ", qqq, full_bill, FIRST_ENTRY)]
    rows = []
    for market in markets:
        starts = month_starts(market.dates)
        cash = cash_index(market)
        for rule in ("hold", "half"):
            matrix = nav_matrix(market, rule, starts)
            rows += windows(market, rule, matrix, starts, cash)
            print("done", market.name, rule, flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "entry_method_windows.csv", index=False)
    summary = summarize(frame)
    summary.to_csv(OUT / "entry_method_summary.csv", index=False)
    (OUT / "config.json").write_text(json.dumps(CONFIG, indent=2, ensure_ascii=False))
    pd.set_option("display.width", 240, "display.max_columns", 30, "display.max_rows", 300, "display.float_format", lambda x: f"{x:.3f}")
    print(summary.to_string())


if __name__ == "__main__":
    main()
