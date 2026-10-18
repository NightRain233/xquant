"""Single-instrument trend checks that complete the Weinstein series (2026-10-18).

Three quick checks run during the review conversation, consolidated here so the
numbers in ``docs/notes/weinstein-summary-2026-10-18.md`` can be reproduced:

1. US indices: SPY and QQQ with the 30-week rules.
2. A-share indices: CSI 300 TR (H00300), Dividend Low-Vol TR (H20269) and
   CSI 2000 (932000, price only) with the same rules.
3. BTC-USD: 30/20-week Weinstein rules, plus daily, weekly and
   weekly+daily SuperTrend(10, 3) switches.

Rules (frozen, identical to the sector reviews where they overlap):
- "filter":    hold while the weekly close is above the 30-week SMA.
- "weinstein": buy when the weekly close is above a rising 30-week SMA
               (SMA now > SMA four weeks ago); sell when the weekly close falls
               below the SMA.
- SuperTrend:  SMA-ATR(10) x 3 on daily or weekly bars; hold while up.
Signals use completed bars only and trade at the next day's open. Indices with
close-only history (the CSI total-return series) trade at the next day's
close, which is slightly conservative. Cash earns zero.

Inputs are snapshots already saved by earlier reviews (no network):
- SPY:  outputs/weinstein-us-sector-2026-10-18/cache/yf_SPY.csv
- QQQ:  outputs/weinstein-quick-checks-2026-10-18/cache/yf_QQQ.csv
        (yfinance auto_adjust=True, fetched 2026-10-18)
- CSI:  outputs/dividend-lowvol-csi2000-2026-10-18/cache/csindex_*.csv
- BTC:  outputs/btc-satellite-corrected-prices-2026-10-18/market_data/BTC-USD.parquet

Run from the xquant root with any Python that has pandas, numpy and pyarrow:
  python scripts/research_weinstein_quick_checks.py
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "weinstein-quick-checks-2026-10-18"

INPUTS = {
    "SPY": ROOT / "outputs/weinstein-us-sector-2026-10-18/cache/yf_SPY.csv",
    "QQQ": OUT / "cache/yf_QQQ.csv",
    "H00300": ROOT / "outputs/dividend-lowvol-csi2000-2026-10-18/cache/csindex_H00300.csv",
    "H20269": ROOT / "outputs/dividend-lowvol-csi2000-2026-10-18/cache/csindex_H20269.csv",
    "932000": ROOT / "outputs/dividend-lowvol-csi2000-2026-10-18/cache/csindex_932000.csv",
    "BTC-USD": ROOT / "outputs/btc-satellite-corrected-prices-2026-10-18/market_data/BTC-USD.parquet",
}

MA_WEEKS = 30
SLOPE_LAG_WEEKS = 4
ST_ATR, ST_MULT = 10, 3.0


# ---------------------------------------------------------------- data loading

def load_yfinance(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col=0)
    frame.index = pd.to_datetime(frame.index, utc=True).tz_convert(None).normalize()
    return frame[["Open", "High", "Low", "Close"]].astype(float)


def load_csindex(path: Path) -> pd.DataFrame:
    """CSI history; total-return series have no open, so open = close."""
    frame = pd.read_csv(path, usecols=["日期", "收盘"])
    frame["日期"] = pd.to_datetime(frame["日期"])
    frame = frame.drop_duplicates("日期", keep="last").set_index("日期").sort_index()
    frame = frame.loc["2014-01-01":]
    close = frame["收盘"].astype(float)
    return pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close})


def load_btc(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    frame.columns = [str(c).capitalize() for c in frame.columns]
    frame.index = pd.to_datetime(frame.index)
    if frame.index.tz is not None:
        frame.index = frame.index.tz_localize(None)
    return frame[["Open", "High", "Low", "Close"]].astype(float).dropna()


# ---------------------------------------------------------------- signals

def weekly_bars(daily: pd.DataFrame, week_end: str) -> pd.DataFrame:
    bars = daily.resample(week_end).agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
    bars = bars.dropna()
    # stamp each week on its last real trading day, so holiday weeks are skipped
    last_day = daily["Close"].groupby(pd.Grouper(freq=week_end)).apply(
        lambda s: s.index[-1] if len(s) else pd.NaT).dropna()
    bars.index = pd.DatetimeIndex(last_day.loc[bars.index].values)
    return bars


def ma_rule(weekly_close: pd.Series, mode: str, weeks: int = MA_WEEKS) -> pd.Series:
    ma = weekly_close.rolling(weeks).mean()
    hold, out = 0, []
    for i in range(len(weekly_close)):
        if i < weeks + SLOPE_LAG_WEEKS:
            out.append(0)
            continue
        close, sma, sma_lag = weekly_close.iloc[i], ma.iloc[i], ma.iloc[i - SLOPE_LAG_WEEKS]
        if mode == "filter":
            hold = int(close > sma)
        elif hold and close < sma:
            hold = 0
        elif not hold and close > sma and sma > sma_lag:
            hold = 1
        out.append(hold)
    return pd.Series(out, index=weekly_close.index, dtype=float)


def supertrend_up(bars: pd.DataFrame, atr_window: int = ST_ATR, mult: float = ST_MULT) -> pd.Series:
    high, low, close = bars["High"], bars["Low"], bars["Close"]
    true_range = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = true_range.rolling(atr_window).mean()
    mid = (high + low) / 2
    upper, lower = (mid + mult * atr).to_numpy(), (mid - mult * atr).to_numpy()
    c = close.to_numpy()
    fu, fl = upper.copy(), lower.copy()
    direction = np.ones(len(bars))
    for i in range(1, len(bars)):
        fu[i] = upper[i] if (np.isnan(fu[i - 1]) or upper[i] < fu[i - 1] or c[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = lower[i] if (np.isnan(fl[i - 1]) or lower[i] > fl[i - 1] or c[i - 1] < fl[i - 1]) else fl[i - 1]
        prev = direction[i - 1]
        if prev == -1 and c[i] > fu[i - 1]:
            direction[i] = 1
        elif prev == 1 and c[i] < fl[i - 1]:
            direction[i] = -1
        else:
            direction[i] = prev
    held = pd.Series((direction == 1).astype(float), index=bars.index)
    held[atr.isna()] = 0.0
    return held


def to_daily(weekly_hold: pd.Series, daily_index: pd.DatetimeIndex) -> pd.Series:
    """A weekly decision is known at that week's last close."""
    return weekly_hold.reindex(daily_index).ffill().fillna(0.0)


# ---------------------------------------------------------------- simulation

def simulate(daily: pd.DataFrame, hold: pd.Series, cost: float) -> tuple[pd.Series, int]:
    """Signal at close t, trade at open t+1 (open == close for close-only data)."""
    target = hold.shift(1).fillna(0.0)
    nav, prev_pos, prev_close, trades = 1.0, 0.0, None, 0
    values = []
    for (_, bar), pos in zip(daily.iterrows(), target.to_numpy()):
        nav_open = nav if prev_close is None else nav * (1 + prev_pos * (bar.Open / prev_close - 1))
        if pos != prev_pos:
            nav_open *= 1 - cost
            trades += 1
        nav = nav_open * (1 + pos * (bar.Close / bar.Open - 1))
        prev_pos, prev_close = pos, bar.Close
        values.append(nav)
    return pd.Series(values, index=daily.index), trades


def window(nav: pd.Series, start=None, end=None) -> dict:
    s = nav.loc[start:end]
    years = (s.index[-1] - s.index[0]).days / 365.25
    return {
        "total_return": s.iloc[-1] / s.iloc[0] - 1,
        "cagr": (s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1 if years > 0 else np.nan,
        "max_drawdown": (s / s.cummax() - 1).min(),
        "years": years,
    }


# ---------------------------------------------------------------- experiments

US_WINDOWS = [("2000-01-01", "2002-12-31", "2000-02"), ("2007-10-01", "2009-03-31", "金融危机"),
              ("2020-02-01", "2020-04-30", "2020疫情"), ("2022-01-01", "2022-12-31", "2022"),
              ("2010-01-01", "2021-12-31", "2010-21")]
CN_WINDOWS = [("2015-06-12", "2016-01-31", "2015股灾"), ("2018-01-01", "2018-12-31", "2018"),
              ("2021-02-18", "2024-09-13", "2021-24熊市"), ("2024-01-01", "2024-02-29", "2024年1-2月"),
              ("2024-09-13", "2024-10-31", "924行情")]
BTC_WINDOWS = [("2017-12-17", "2018-12-15", "2018熊市"), ("2021-11-08", "2022-11-21", "2022熊市"),
               ("2020-10-01", "2021-04-14", "2020-21牛市"), ("2023-01-01", "2025-12-31", "2023-25"),
               ("2015-07-01", "2020-12-31", "2015-20"), ("2021-01-01", None, "2021以后")]


def run_ma_family(market: str, name: str, daily: pd.DataFrame, week_end: str, cost: float, windows) -> tuple[list, list]:
    weekly = weekly_bars(daily, week_end)["Close"]
    variants = {"filter": ma_rule(weekly, "filter"), "weinstein": ma_rule(weekly, "weinstein")}
    first = weekly.index[MA_WEEKS + SLOPE_LAG_WEEKS]
    start = daily.index[daily.index > first][0]
    curves = {"买入持有": (daily["Close"], 0, 1.0)}
    labels = {"filter": "站上30周线持有", "weinstein": "温斯坦(30周线上翘才买)"}
    for key, hold in variants.items():
        daily_hold = to_daily(hold, daily.index)
        nav, trades = simulate(daily, daily_hold, cost)
        curves[labels[key]] = (nav, trades, daily_hold.loc[start:].mean())
    return summarize(market, name, curves, start, windows)


def summarize(market, name, curves, start, windows):
    rows, periods = [], []
    for label, (nav, trades, exposure) in curves.items():
        nav = nav.loc[start:]
        full = window(nav)
        rows.append({"market": market, "instrument": name, "strategy": label,
                     "start": nav.index[0].date(), "end": nav.index[-1].date(),
                     "cagr": full["cagr"], "max_drawdown": full["max_drawdown"],
                     "switches_per_year": trades / full["years"], "exposure": exposure})
        for a, b, tag in windows:
            w = window(nav, a, b)
            periods.append({"market": market, "instrument": name, "strategy": label, "window": tag,
                            "total_return": w["total_return"], "cagr": w["cagr"], "max_drawdown": w["max_drawdown"]})
    return rows, periods


def run_btc(daily: pd.DataFrame, cost: float) -> tuple[list, list]:
    start = pd.Timestamp("2015-07-01")
    weekly = weekly_bars(daily, "W-SUN")
    daily_st = supertrend_up(daily)
    weekly_st = to_daily(supertrend_up(weekly), daily.index)
    signals = {
        "温斯坦 30 周": to_daily(ma_rule(weekly["Close"], "weinstein", 30), daily.index),
        "温斯坦 20 周": to_daily(ma_rule(weekly["Close"], "weinstein", 20), daily.index),
        "站上30周线持有": to_daily(ma_rule(weekly["Close"], "filter", 30), daily.index),
        "日线 SuperTrend": daily_st,
        "周线 SuperTrend": weekly_st,
        "周线+日线 SuperTrend": weekly_st * daily_st,
    }
    curves = {"买入持有": (daily["Close"], 0, 1.0)}
    for label, hold in signals.items():
        nav, trades = simulate(daily, hold, cost)
        curves[label] = (nav, trades, hold.loc[start:].mean())
    return summarize("BTC", "BTC-USD", curves, start, BTC_WINDOWS)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, periods = [], []
    for symbol in ("SPY", "QQQ"):
        r, p = run_ma_family("美股", symbol, load_yfinance(INPUTS[symbol]), "W-FRI", 0.001, US_WINDOWS)
        rows += r; periods += p
    for code, label in (("H00300", "沪深300全收益"), ("H20269", "红利低波全收益"), ("932000", "中证2000(价格)")):
        r, p = run_ma_family("A股", label, load_csindex(INPUTS[code]), "W-FRI", 0.001, CN_WINDOWS)
        rows += r; periods += p
    r, p = run_btc(load_btc(INPUTS["BTC-USD"]), 0.003)
    rows += r; periods += p

    pd.DataFrame(rows).to_csv(OUT / "research_summary.csv", index=False)
    pd.DataFrame(periods).to_csv(OUT / "period_windows.csv", index=False)
    pd.DataFrame([{"input": k, "path": str(v.relative_to(ROOT)), "sha256": sha256(v)} for k, v in INPUTS.items()]
                 ).to_csv(OUT / "data_manifest.csv", index=False)
    print(pd.DataFrame(rows).to_string(index=False, float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
