"""QDII ETF premium: does a high premium cost money later, and does a premium gate help monthly buyers?

Run (from repo root): .venv/bin/python scripts/fetch_qdii_nav.py && .venv/bin/python scripts/research_qdii_premium.py
Everything below is fixed before any result was seen. Prices: frozen TickFlow unadjusted closes (to 2026-09-30)
with official unit splits; NAV: Eastmoney unit NAV with the same splits.
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
from research_domestic_us_etf_trend import RAW_FILE, SPLITS, load_provider  # noqa: E402
from research_entry_methods import xirr  # noqa: E402
from research_index_enhance_strategies import load_sp500  # noqa: E402
from research_qqq_trend_strategies import load_qqq  # noqa: E402

SLUG = "qdii-premium-2026-11-10"
OUT = ROOT / "outputs" / SLUG
CACHE = OUT / "cache"
US_PAIR = {"513500": "SPY", "513100": "QQQ"}
# NAV is converted on the official split date; the price resumes at the new scale one trading day later
NAV_SPLITS = {"513100": ("2022-01-13", 5), "513500": ("2022-03-29", 2)}
CONFIG = {
    "window": ["2014-10-08", "2026-09-30"],
    "decision_premium": "close_T / estimated NAV_T - 1; estimated NAV_T = latest NAV dated at least two mainland trading days "
                        "before T, moved by the US ETF (SPY/QQQ) from that NAV date to the last US close before date T; "
                        "ignores RMB moves and fees",
    "after_the_fact_premium": "close_T / NAV of the previous NAV date - 1 (description only)",
    "forward_check": {"buckets": [-1.0, 0.0, 0.03, 0.06, 0.10, 1.0], "horizons_days": [20, 60, 120],
                      "measure": "ETF return minus NAV return over the horizon (the premium change paid back)"},
    "gate": {"contribution": "1 unit on the first mainland trading day of each month", "threshold": 0.03,
             "waiting": "pending money earns 2% and is fully invested on the first day the decision premium <= threshold",
             "cap_variant": "pending money is invested anyway after 60 trading days", "cost_one_way": 0.001},
    "gate_sensitivity_only": [0.02, 0.05, 0.08],
    "horizons_years": [3, 5],
}


def adjusted(series: pd.Series, fund: str, splits: dict = SPLITS) -> pd.Series:
    date, ratio = splits[fund]
    out = series.copy()
    out.loc[out.index < date] /= ratio
    return out


def load_nav(fund: str) -> pd.Series:
    path = CACHE / f"nav_{fund}.csv"
    manifest = json.loads((OUT / "data_manifest.json").read_text())["files"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest[path.name]["sha256"], path
    nav = pd.read_csv(path, parse_dates=["净值日期"]).set_index("净值日期")["单位净值"].astype(float)
    nav = adjusted(nav[~nav.index.duplicated()].sort_index(), fund, NAV_SPLITS)
    assert nav.pct_change().abs().max() < 0.2, "split not aligned"
    return nav


def decision_premium(price: pd.Series, nav: pd.Series, us: pd.Series) -> pd.DataFrame:
    dates = price.index
    nav_dates = nav.index.to_numpy()
    us_dates = us.index.to_numpy()
    rows = {}
    for j in range(2, len(dates)):
        cutoff = dates[j - 2].to_datetime64()
        k = int(np.searchsorted(nav_dates, cutoff, side="right")) - 1
        u = int(np.searchsorted(us_dates, dates[j].to_datetime64(), side="left")) - 1
        if k < 0 or u < 0:
            continue
        base_date = nav_dates[k]
        b = int(np.searchsorted(us_dates, base_date, side="right")) - 1
        if b < 0:
            continue
        estimate = nav.iloc[k] * us.iloc[u] / us.iloc[b]
        rows[dates[j]] = {"close": price.iloc[j], "nav_base_date": pd.Timestamp(base_date), "estimated_nav": estimate,
                          "premium": price.iloc[j] / estimate - 1}
    frame = pd.DataFrame.from_dict(rows, orient="index")
    prior_nav = nav.reindex(nav.index.union(dates)).shift(1).reindex(dates)
    frame["premium_after_the_fact"] = (price / prior_nav - 1).reindex(frame.index)
    return frame


def forward_table(frame: pd.DataFrame, price: pd.Series, nav: pd.Series, fund: str) -> pd.DataFrame:
    nav_on = nav.reindex(nav.index.union(price.index)).ffill().reindex(price.index)
    rows = []
    buckets = CONFIG["forward_check"]["buckets"]
    labels = ["<0%", "0-3%", "3-6%", "6-10%", ">=10%"]
    part = frame[(frame.index >= CONFIG["window"][0]) & (frame.index <= CONFIG["window"][1])].copy()
    part["bucket"] = pd.cut(part["premium"], buckets, labels=labels, right=False)
    for h in CONFIG["forward_check"]["horizons_days"]:
        etf = price.shift(-h) / price - 1
        fund_nav = nav_on.shift(-h) / nav_on - 1
        gap = (etf - fund_nav).reindex(part.index)
        for label in labels:
            g = gap[part["bucket"] == label].dropna()
            rows.append({"fund": fund, "horizon_days": h, "bucket": label, "days": len(g), "mean_gap": g.mean(),
                         "median_gap": g.median(), "share_negative": (g < 0).mean() if len(g) else np.nan})
    return pd.DataFrame(rows)


def simulate(price: pd.Series, premium: pd.Series, start: pd.Timestamp, end: pd.Timestamp, threshold: float | None,
             cap: int | None = None, cash_annual: float = 0.02, cost: float = 0.001) -> dict:
    """Monthly contributions with an optional premium gate; returns money-weighted return and costs paid."""
    p = price[(price.index >= start) & (price.index <= end)]
    prem = premium.reindex(p.index)
    months = p.index.to_period("M")
    contribution_days = set(p.index[np.r_[True, months[1:] != months[:-1]]])
    shares = cash = 0.0
    waiting_since = None
    flows_dates, paid_premium, delayed, longest_wait = [], [], 0, 0
    for idx, (date, px) in enumerate(p.items()):
        if idx:
            cash *= (1 + cash_annual) ** ((date - p.index[idx - 1]).days / 365)
        if date in contribution_days and date < end:
            cash += 1.0
            flows_dates.append(date)
            if waiting_since is None:
                waiting_since = idx
        if cash > 0 and waiting_since is not None:
            ok = threshold is None or (not np.isnan(prem[date]) and prem[date] <= threshold)
            forced = cap is not None and idx - waiting_since >= cap
            if ok or forced:
                if idx > waiting_since:
                    delayed += 1
                longest_wait = max(longest_wait, idx - waiting_since)
                shares += cash * (1 - cost) / px
                paid_premium.append((cash, prem[date]))
                cash, waiting_since = 0.0, None
    value = shares * p.iloc[-1] + cash
    n = len(flows_dates)
    weights = np.array([c for c, _ in paid_premium])
    prems = np.array([q for _, q in paid_premium], float)
    mask = ~np.isnan(prems)
    return {"contributions": n, "final_per_unit": value / n, "xirr": xirr(flows_dates + [p.index[-1]], [-1.0] * n + [value]),
            "avg_premium_paid": float(np.average(prems[mask], weights=weights[mask])) if mask.any() else np.nan,
            "buys_after_waiting": delayed, "longest_wait_days": longest_wait, "cash_left_share": cash / value if value else np.nan}


def main():
    spy, _ = load_sp500()
    us_all = {"SPY": spy, "QQQ": load_qqq()}
    forward, full_rows, window_rows, premium_rows, state = [], [], [], [], []
    start, end = (pd.Timestamp(d) for d in CONFIG["window"])
    for fund, us_name in US_PAIR.items():
        price = adjusted(load_provider(RAW_FILE, fund), fund)
        price = price[price.index <= end]
        nav = load_nav(fund)
        frame = decision_premium(price, nav, us_all[us_name])
        frame.to_csv(OUT / f"premium_daily_{fund}.csv", index_label="date")
        inside = frame[(frame.index >= start) & (frame.index <= end)]
        err = (inside["premium"] - inside["premium_after_the_fact"]).abs()
        premium_rows.append({"fund": fund, "days": len(inside), "median": inside["premium"].median(),
                             "share_above_3pct": (inside["premium"] > 0.03).mean(), "share_above_10pct": (inside["premium"] > 0.10).mean(),
                             "max": inside["premium"].max(), "max_date": inside["premium"].idxmax().date(),
                             "median_abs_gap_to_after_the_fact": err.median()})
        for year, g in inside.groupby(inside.index.year):
            premium_rows.append({"fund": fund, "year": year, "median": g["premium"].median(),
                                 "share_above_3pct": (g["premium"] > 0.03).mean(), "max": g["premium"].max()})
        forward.append(forward_table(frame, price, nav, fund))
        prem = frame["premium"]
        variants = {"不检查溢价": (None, None), "溢价<=3%才买": (0.03, None), "溢价<=3%才买,最多等60天": (0.03, 60)}
        variants.update({f"溢价<={t:.0%}才买(敏感性)": (t, None) for t in CONFIG["gate_sensitivity_only"]})
        for label, (thr, cap) in variants.items():
            full_rows.append({"fund": fund, "variant": label, **simulate(price, prem, start, end, thr, cap)})
        months = price.index[(price.index >= start)]
        firsts = months[np.r_[True, months.to_period("M")[1:] != months.to_period("M")[:-1]]]
        for s in firsts:
            for years in CONFIG["horizons_years"]:
                e = s + pd.DateOffset(years=years)
                if e > end:
                    continue
                for label in ("不检查溢价", "溢价<=3%才买", "溢价<=3%才买,最多等60天"):
                    thr, cap = variants[label]
                    window_rows.append({"fund": fund, "start": s, "years": years, "variant": label, **simulate(price, prem, s, e, thr, cap)})
    pd.concat(forward).to_csv(OUT / "forward_gap_by_premium.csv", index=False)
    pd.DataFrame(premium_rows).to_csv(OUT / "premium_summary.csv", index=False)
    full = pd.DataFrame(full_rows)
    full.to_csv(OUT / "gate_full_period.csv", index=False)
    windows = pd.DataFrame(window_rows)
    windows.to_csv(OUT / "gate_windows.csv", index=False)
    base = windows[windows.variant == "不检查溢价"].set_index(["fund", "start", "years"])["xirr"]
    summary = []
    for (fund, years, variant), g in windows.groupby(["fund", "years", "variant"]):
        ex = g.set_index(["fund", "start", "years"])["xirr"] - base.reindex(g.set_index(["fund", "start", "years"]).index)
        summary.append({"fund": fund, "years": years, "variant": variant, "n": len(g), "xirr_median": g.xirr.median(),
                        "xirr_worst": g.xirr.min(), "beat_no_check": (ex > 1e-9).mean(), "excess_median": ex.median(),
                        "excess_worst": ex.min(), "avg_premium_paid_median": g.avg_premium_paid.median(),
                        "cash_left_median": g.cash_left_share.median(), "cash_left_max": g.cash_left_share.max()})
    summary = pd.DataFrame(summary)
    summary.to_csv(OUT / "gate_windows_summary.csv", index=False)
    (OUT / "config.json").write_text(json.dumps(CONFIG, indent=2, ensure_ascii=False))
    pd.set_option("display.width", 240, "display.max_columns", 30, "display.max_rows", 200, "display.float_format", lambda x: f"{x:.4f}")
    print(pd.DataFrame(premium_rows).to_string())
    print(pd.concat(forward).to_string())
    print(full.to_string())
    print(summary.to_string())


if __name__ == "__main__":
    main()
