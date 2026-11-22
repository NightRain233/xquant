"""Read-only live signal check for S&P 500 (^GSPC / SPY), Gold (GLD), BTC-USD, and 513500 (if available).

Uses the exact frozen repository formulas (30-week SMA & 4-week slope from ``xquant.position_rules``,
21-day realized volatility for TVT-50) without mutating any frozen research cache.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src")]
from xquant import position_rules as pr  # noqa: E402


def inspect_ticker(label: str, ticker: str, auto_adjust: bool = True) -> None:
    df = yf.Ticker(ticker).history(period="2y", auto_adjust=auto_adjust, actions=False)
    if df.empty:
        print(f"{label} ({ticker}): NO DATA")
        return
    df.index = pd.DatetimeIndex(df.index.astype(str).str.slice(0, 10))
    close = df["Close"].dropna()
    weekly = close.groupby(close.index.to_period("W-SUN")).last()
    # Build weekly series indexed by week-end trading date (matching position_rules.stage_states)
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

    # Also compute 52w high drawdown & 21d realized annualized vol
    hi52 = float(close.tail(252).max())
    dd_52w = (last_px / hi52 - 1.0) * 100.0
    vol21 = float(np.log(close).diff().tail(21).std(ddof=1) * np.sqrt(252.0)) * 100.0
    tvt_cap = 100.0 if w_stage2 else 50.0
    tvt_target_w = min(tvt_cap, 15.0 / vol21 * 100.0) if vol21 > 0 else np.nan

    # Recent 6 weekly closes vs MA30
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
    print(f"21d Annualized Vol  : {vol21:.1f}% | TVT-50 target equity weight: {tvt_target_w:.1f}%")
    print(recent.to_string())


def main() -> None:
    for label, ticker, adj in [
        ("S&P 500 Index", "^GSPC", False),
        ("SPY ETF (Total Return)", "SPY", True),
        ("Nasdaq-100 Index", "^NDX", False),
        ("QQQ ETF (Total Return)", "QQQ", True),
        ("Domestic Nasdaq-100 ETF (513100)", "513100.SS", True),
        ("Domestic S&P 500 ETF (513500)", "513500.SS", True),
        ("Gold ETF", "GLD", True),
        ("Bitcoin", "BTC-USD", False),
    ]:
        try:
            inspect_ticker(label, ticker, auto_adjust=adj)
        except Exception as exc:
            print(f"{label} ({ticker}) error: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
