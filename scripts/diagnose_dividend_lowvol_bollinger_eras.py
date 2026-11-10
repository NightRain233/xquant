"""Why the all-in/out Bollinger rule differs before and after 2020 (diagnosis only, no new rule).

Run (from repo root): .venv/bin/python scripts/diagnose_dividend_lowvol_bollinger_eras.py
Needs ``scripts/research_dividend_lowvol_bollinger.py`` to have been run.
"""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from research_dividend_lowvol_bollinger import CONFIG, NAMES, OUT, SOURCE, backtest, load_index, round_trips  # noqa: E402
from xquant import band_timing as bt  # noqa: E402
from xquant import style_combo as sc  # noqa: E402

ERAS = {"2014-08~2019": ("2014-08-01", "2019-12-31"), "2020~2026-10": ("2020-01-01", "2026-10-16")}
TREND_WEEKS = 26


def era_slice(series, era):
    start, end = ERAS[era]
    return series[(series.index >= start) & (series.index <= end)]


def annualized_between(nav, start, end):
    seg = nav[(nav.index >= start) & (nav.index <= end)]
    prior = nav[nav.index < start]
    if len(prior):
        seg = pd.concat([prior.iloc[-1:], seg])
    return sc.annualized(seg)


def variance_ratio(weekly_log: pd.Series, q: int) -> float:
    """Variance of q-week returns over q times 1-week variance: above 1 trends, below 1 mean-reverts."""
    r = weekly_log.dropna()
    return float(r.rolling(q).sum().dropna().var(ddof=1) / (q * r.var(ddof=1)))


def block_bootstrap_vr(weekly_log, q, block=26, n=2000, seed=7):
    rng = np.random.default_rng(seed)
    values = weekly_log.dropna().to_numpy()
    out = []
    for _ in range(n):
        starts = rng.integers(0, len(values) - block + 1, size=len(values) // block + 1)
        sample = np.concatenate([values[s:s + block] for s in starts])[:len(values)]
        out.append(variance_ratio(pd.Series(sample), q))
    return np.quantile(out, [0.05, 0.95])


def split_scan(rule_nav, hold_nav):
    rows = []
    for year in range(2016, 2025):
        cut = f"{year}-01-01"
        before, after = rule_nav[rule_nav.index < cut], rule_nav[rule_nav.index >= cut]
        hold_before, hold_after = hold_nav[hold_nav.index < cut], hold_nav[hold_nav.index >= cut]
        rows.append({"split": year, "excess_before": sc.annualized(before) - sc.annualized(hold_before),
                     "excess_after": annualized_between(rule_nav, cut, "2027-01-01") - annualized_between(hold_nav, cut, "2027-01-01")})
    return pd.DataFrame(rows)


def yearly_attribution(weights, close, rule_nav):
    held = weights.shift(1).fillna(0.0)
    log_ret = np.log(close.reindex(weights.index)).diff().fillna(0.0)
    rows = []
    for year, idx in weights.groupby(weights.index.year).groups.items():
        rule = rule_nav.loc[idx]
        prior = rule_nav[rule_nav.index < idx[0]]
        base = prior.iloc[-1] if len(prior) else rule.iloc[0]
        rows.append({"year": year, "avg_position": float(held.loc[idx].mean()),
                     "index_log_return": float(log_ret.loc[idx].sum()),
                     "log_return_while_held": float((held.loc[idx] * log_ret.loc[idx]).sum()),
                     "rule_return": float(rule.iloc[-1] / base - 1)})
    return pd.DataFrame(rows)


def era_attribution(weights, close):
    held = weights.shift(1).fillna(0.0)
    log_ret = np.log(close.reindex(weights.index)).diff().fillna(0.0)
    rows = []
    for era in ERAS:
        h, r = era_slice(held, era), era_slice(log_ret, era)
        rows.append({"era": era, "avg_position": float(h.mean()), "index_log_return": float(r.sum()),
                     "captured_log_return": float((h * r).sum()),
                     "captured_share": float((h * r).sum() / r.sum()),
                     "held_daily_mean_annual": float(r[h > 0].mean() * 252), "out_daily_mean_annual": float(r[h == 0].mean() * 252)})
    return pd.DataFrame(rows)


def regime_table(close, levels, near=0.02):
    grouped = close.groupby(close.index.to_period("W-SUN"))
    weekly = pd.Series(grouped.last().to_numpy(), index=grouped.tail(1).index, dtype=float)
    log_weekly = np.log(weekly).diff()
    efficiency = (np.log(weekly) - np.log(weekly).shift(TREND_WEEKS)).abs() / log_weekly.abs().rolling(TREND_WEEKS).sum()
    frame = levels.copy()
    frame["zone"] = [bt.band_zone(r.close, r.upper, r.lower, near) or "between" for r in frame.itertuples()]
    frame["width"] = (frame["upper"] - frame["lower"]) / frame["mid"]
    rows = []
    for era in ERAS:
        r, f = era_slice(log_weekly, era), era_slice(frame, era)
        years = len(f) / 52.18
        vr13 = variance_ratio(r, 13)
        low, high = block_bootstrap_vr(r, 13)
        rows.append({"era": era, "annualized_weekly": float(np.exp(r.sum() / years) - 1), "vol": float(r.std() * np.sqrt(52)),
                     "lag1_autocorr": float(r.autocorr(1)), "vr4": variance_ratio(r, 4), "vr13": vr13, "vr13_p5": low, "vr13_p95": high,
                     "vr26": variance_ratio(r, 26), "efficiency_26w_mean": float(era_slice(efficiency, era).mean()),
                     "upper_weeks_share": float((f["zone"] == "upper").mean()), "lower_weeks_share": float((f["zone"] == "lower").mean()),
                     "band_width_median": float(f["width"].median())})
    return pd.DataFrame(rows)


def forward_by_era(close, levels, near=0.02, weeks_ahead=(13, 26, 52)):
    weekly = bt.weekly_band_levels(close, 20, 2.0)["close"]
    frame = levels.copy()
    frame["zone"] = [bt.band_zone(r.close, r.upper, r.lower, near) or "between" for r in frame.itertuples()]
    frame["episode"] = (frame["zone"] != frame["zone"].shift()).cumsum()
    rows = []
    for era in ERAS:
        f = era_slice(frame, era)
        for zone, label in [("all", "全部周"), ("lower", "接近下轨"), ("upper", "接近上轨")]:
            part = f if zone == "all" else f[f["zone"] == zone]
            row = {"era": era, "zone": label, "weeks": len(part), "episodes": part["episode"].nunique() if zone != "all" else np.nan}
            for w in weeks_ahead:
                fwd = (weekly.shift(-w) / weekly - 1).reindex(part.index).dropna()
                row[f"fwd{w}w"] = float(fwd.mean())
                row[f"win{w}w"] = float((fwd > 0).mean())
            rows.append(row)
    return pd.DataFrame(rows)


def round_trip_table(result, close):
    trips = round_trips(result, close)
    first_buy = trips["buy"].iloc[0]
    rows = [{"era": "2014-08~2019", "side": "首次买入前的空仓", "days": (first_buy - close.index[close.index.searchsorted(pd.Timestamp(CONFIG["start_after"]))]).days,
             "index_return": close[first_buy] / close[pd.Timestamp(CONFIG["start_after"])] - 1, "start": CONFIG["start_after"]}]
    for t in trips.itertuples():
        era = "2014-08~2019" if t.buy < pd.Timestamp("2020-01-01") else "2020~2026-10"
        rows.append({"era": era, "side": "持有", "days": t.days_held, "index_return": t.index_return, "start": t.buy})
        rows.append({"era": era if t.sell < pd.Timestamp("2020-01-01") else "2020~2026-10", "side": "空仓", "days": t.days_out_after,
                     "index_return": t.index_return_while_out, "start": t.sell})
    return pd.DataFrame(rows)


def return_sources(close, price):
    """Total return = dividends + valuation (rolling PE) + earnings, in annual log points; PE from the CSIndex file."""
    pe = pd.read_csv(SOURCE / "cache" / "csindex_H30269.csv", parse_dates=["日期"]).set_index("日期")["滚动市盈率"].dropna()
    rows = []
    for era, (start, end) in ERAS.items():
        def at_or_before(series, date):
            part = series[series.index <= date]
            return part.iloc[-1], part.index[-1]
        first = max(pd.Timestamp(start), pe.index[0])
        pe0, d0 = at_or_before(pe, first) if first > pe.index[0] else (pe.iloc[0], pe.index[0])
        pe1, d1 = at_or_before(pe, pd.Timestamp(end))
        years = (d1 - d0).days / 365.25
        tr = float(np.log(close[d1] / close[d0]) / years)
        px = float(np.log(price[d1] / price[d0]) / years)
        val = float(np.log(pe1 / pe0) / years)
        rows.append({"era": era, "from": d0.date(), "to": d1.date(), "pe_start": pe0, "pe_end": pe1, "total": tr, "dividends": tr - px,
                     "valuation": val, "earnings": px - val})
    return pd.DataFrame(rows)


def cross_index(close_other, label):
    dates = close_other.index
    prices = pd.DataFrame({"a": close_other, "b": close_other})
    start_i = int(dates.searchsorted(pd.Timestamp(CONFIG["start_after"])))
    levels = bt.weekly_band_levels(close_other)
    res = backtest(prices, bt.rule_all_in_out(levels, dates, start_i, 0.02), start_i)
    hold = backtest(prices, sc.rule_buy_hold({"a": 1.0, "b": 0.0}, start_i), start_i)
    rows = []
    for era, (s, e) in ERAS.items():
        rows.append({"index": label, "era": era, "rule": annualized_between(res.nav, s, e), "hold": annualized_between(hold.nav, s, e),
                     "avg_position": float(era_slice(res.weights["a"], era).mean())})
    return pd.DataFrame(rows)


def main():
    close, price = load_index("H20269"), load_index("H30269")
    close = close[close.index <= CONFIG["end"]]
    price = price.reindex(close.index)
    dates = close.index
    start_i = int(dates.searchsorted(pd.Timestamp(CONFIG["start_after"])))
    prices = pd.DataFrame({"a": close, "b": close})
    levels = bt.weekly_band_levels(close)
    v1 = backtest(prices, bt.rule_all_in_out(levels, dates, start_i, 0.02), start_i)
    hold = backtest(prices, sc.rule_buy_hold({"a": 1.0, "b": 0.0}, start_i), start_i)
    tables = {
        "era_split_scan": split_scan(v1.nav, hold.nav),
        "era_yearly_attribution": yearly_attribution(v1.weights["a"], close, v1.nav),
        "era_attribution": era_attribution(v1.weights["a"], close),
        "era_regime": regime_table(close, levels),
        "era_forward_returns": forward_by_era(close, levels),
        "era_round_trips": round_trip_table(v1, close),
        "era_return_sources": return_sources(close, price),
        "era_cross_index": pd.concat([cross_index(close, "红利低波全收益"), cross_index(load_index("H00300"), "沪深300全收益")]),
    }
    pd.set_option("display.width", 240, "display.max_columns", 30, "display.max_rows", 200, "display.float_format", lambda x: f"{x:.3f}")
    for name, table in tables.items():
        table.to_csv(OUT / f"{name}.csv", index=False)
        print(f"\n== {name}\n{table}")
    start_after_first_buy = {"2015-09-01": ("2015-09-01", "2019-12-31")}
    for label, (s, e) in start_after_first_buy.items():
        print("\nafter first buy", label, "V1", annualized_between(v1.nav, s, e), "hold", annualized_between(hold.nav, s, e))


if __name__ == "__main__":
    main()
