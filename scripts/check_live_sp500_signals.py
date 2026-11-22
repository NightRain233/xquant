"""Read-only live signal check for Plan A (Three-Asset Core + BTC Satellite), Plan B (75/25), and Plan C (S2 & TVT-50).

Uses the exact frozen repository formulas:
* Three-asset core: 20-day inverse volatility on 510300.SS / 513100.SS / 518880.SS (``xquant.portfolio``).
* BTC satellite: daily SuperTrend(10, 3) direction on BTC-USD (``xquant.indicators``).
* S&P 500 / 513500 / Nasdaq-100 / Gold: 30-week rising SMA (``xquant.position_rules``) & 21-day realized vol TVT-50.

Never mutates any frozen research cache.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src")]
from xquant import indicators as ind  # noqa: E402
from xquant import portfolio as pf  # noqa: E402
from xquant import position_rules as pr  # noqa: E402


def fetch_history(ticker: str, auto_adjust: bool = True, period: str = "2y") -> pd.DataFrame:
    df = yf.Ticker(ticker).history(period=period, auto_adjust=auto_adjust, actions=False)
    if df.empty:
        raise ValueError(f"no data for {ticker}")
    df.index = pd.DatetimeIndex(df.index.astype(str).str.slice(0, 10))
    return df[~df.index.duplicated(keep="last")].sort_index()


def inspect_ticker(label: str, ticker: str, auto_adjust: bool = True) -> dict | None:
    df = fetch_history(ticker, auto_adjust=auto_adjust)
    close = df["Close"].dropna()
    weekly = close.groupby(close.index.to_period("W-SUN")).last()
    week_dates = close.index.to_series().groupby(close.index.to_period("W-SUN")).last()
    weekly.index = pd.DatetimeIndex(week_dates.values)

    ma30 = weekly.rolling(30).mean()
    slope4 = ma30 - ma30.shift(4)
    st = pr.stage_states(close, ma_weeks=30, slope_weeks=4)

    last_date = close.index[-1]
    last_px = float(close.iloc[-1])
    w_date = weekly.index[-1]
    w_px = float(weekly.iloc[-1])
    w_ma30 = float(ma30.iloc[-1])
    w_ma30_prev4 = float(ma30.iloc[-5])
    w_slope = float(slope4.iloc[-1])
    w_stage2 = bool(st.iloc[-1])
    gap_pct = (w_px / w_ma30 - 1.0) * 100.0

    hi52 = float(close.tail(252).max())
    dd_52w = (last_px / hi52 - 1.0) * 100.0
    vol21 = float(np.log(close).diff().tail(21).std(ddof=1) * np.sqrt(252.0)) * 100.0
    tvt_cap = 100.0 if w_stage2 else 50.0
    tvt_raw = (15.0 / vol21 * 100.0) if vol21 > 0 else np.nan
    tvt_target_w = min(tvt_cap, tvt_raw) if np.isfinite(tvt_raw) else np.nan

    recent = pd.DataFrame(
        {
            "week_close": weekly.tail(6).round(2),
            "ma30": ma30.tail(6).round(2),
            "gap%": ((weekly / ma30 - 1.0) * 100.0).tail(6).round(2),
            "ma30_rising": (slope4 > 0).tail(6),
            "S2_on": st.tail(6),
        }
    )

    print(f"\n=== {label} ({ticker}) ===")
    print(f"Latest trading date : {last_date.date()} | Close: {last_px:.2f} | Drawdown from 52w high ({hi52:.2f}): {dd_52w:.2f}%")
    print(f"Latest week ({w_date.date()}) : Close={w_px:.2f} vs 30W-SMA={w_ma30:.2f} ({gap_pct:+.2f}%)")
    print(f"30W-SMA 4w ago      : {w_ma30_prev4:.2f} | 4-week slope: {w_slope:+.2f} ({'RISING' if w_slope > 0 else 'FALLING'})")
    print(f"S2 Stage-2 Signal   : {'ON (100%)' if w_stage2 else 'OFF (50% defensive)'}")
    print(f"21d Annualized Vol  : {vol21:.1f}% | TVT-50 raw(15%/vol)={tvt_raw:.1f}%, cap={tvt_cap:.0f}% -> target={tvt_target_w:.1f}%")
    print(recent.to_string())
    return {
        "ticker": ticker,
        "date": str(last_date.date()),
        "close": last_px,
        "ma30": w_ma30,
        "gap_pct": gap_pct,
        "s2_on": w_stage2,
        "vol21": vol21,
        "tvt_target_w": tvt_target_w,
    }


def inspect_plan_a() -> None:
    """Compute Plan A live snapshot: 20-day inverse-vol core (510300/513100/518880) + BTC SuperTrend(10,3)."""
    print("\n================ PLAN A: THREE-ASSET CORE + 7.5% BTC SATELLITE ================")
    core_syms = ["510300.SS", "513100.SS", "518880.SS"]
    closes = {}
    for sym in core_syms:
        closes[sym] = fetch_history(sym, auto_adjust=True, period="6mo")["Close"]
    df_core = pd.DataFrame(closes).dropna()
    rets = df_core.pct_change().dropna().tail(20)
    w_core = pf.inverse_volatility_weights(rets, core_syms)
    vols_20 = rets.std(ddof=1) * np.sqrt(252.0) * 100.0

    btc = fetch_history("BTC-USD", auto_adjust=False, period="1y")
    st_dir = ind.supertrend_direction(btc["High"], btc["Low"], btc["Close"], atr_window=10, multiplier=3.0)
    btc_on = bool(st_dir.iloc[-1])
    # Find last flip date
    flips = st_dir[st_dir != st_dir.shift(1)]
    last_flip = flips.index[-1].date() if len(flips) else btc.index[0].date()

    print(f"Core common date    : {df_core.index[-1].date()} (20-day inverse-volatility weights)")
    for sym in core_syms:
        core_pct = w_core[sym] * 100.0
        total_pct = w_core[sym] * 92.5
        print(f"  {sym:10s}: 20d_ann_vol={vols_20[sym]:5.1f}% | Core100%={core_pct:5.1f}% | Total(92.5% core)={total_pct:5.1f}%")
    print(f"BTC-USD ({btc.index[-1].date()}) : Close={float(btc['Close'].iloc[-1]):.2f} | Daily SuperTrend(10,3)={'ON -> HOLD 7.5%' if btc_on else 'OFF -> CASH 7.5%'} (since {last_flip})")


def main() -> None:
    try:
        inspect_plan_a()
    except Exception as exc:
        print(f"Plan A error: {type(exc).__name__}: {exc}")

    print("\n================ PLAN B / PLAN C / MARKET SNAPSHOT ================")
    for label, ticker, adj in [
        ("S&P 500 Index", "^GSPC", False),
        ("SPY ETF (Total Return)", "SPY", True),
        ("Domestic S&P 500 ETF (513500)", "513500.SS", True),
        ("Nasdaq-100 Index", "^NDX", False),
        ("QQQ ETF (Total Return)", "QQQ", True),
        ("Domestic Nasdaq-100 ETF (513100)", "513100.SS", True),
        ("Gold ETF (USD)", "GLD", True),
        ("Domestic Gold ETF (518880)", "518880.SS", True),
        ("Bitcoin", "BTC-USD", False),
    ]:
        try:
            inspect_ticker(label, ticker, auto_adjust=adj)
        except Exception as exc:
            print(f"{label} ({ticker}) error: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
