"""Single-asset position-sizing rules: volatility target, 30-week stage state, trend with leverage.

Plug into ``style_combo.run_backtest``: the asset is column ``a``; every signal
uses closes up to and including its own day only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from xquant.style_combo import Signal, is_period_end, is_week_end


def _weight_signal(weight: float) -> dict[str, float]:
    return {"a": float(weight), "b": 0.0}


def volatility_target_weight(realized_vol: float, target: float, floor: float, cap: float) -> float:
    """Weight that would run at ``target`` volatility, clipped to [floor, cap]."""
    return float(np.clip(target / realized_vol, floor, cap))


def rule_vol_target(close: pd.Series, start_i: int, target: float = 0.12, window: int = 20, floor: float = 0.2,
                    cap: float = 1.0, min_change: float = 0.10) -> Signal:
    """Weekly: size to target volatility from the last ``window`` daily returns; ignore small changes."""
    dates = close.index
    vol = (close.pct_change().rolling(window).std(ddof=1) * np.sqrt(252)).to_numpy(float)
    state = {"weight": None}

    def sig(i):
        if i != start_i and not is_week_end(dates, i):
            return None
        wanted = volatility_target_weight(vol[i], target, floor, cap)
        if state["weight"] is None or abs(wanted - state["weight"]) >= min_change:
            state["weight"] = wanted
            return _weight_signal(wanted)
        return None
    return sig


def stage_states(close: pd.Series, ma_weeks: int = 30, slope_weeks: int = 4) -> pd.Series:
    """Weekly on/off: on above a rising N-week mean, off below it, otherwise unchanged; indexed by week-end day."""
    grouped = close.groupby(close.index.to_period("W-SUN"))
    weekly = pd.Series(grouped.last().to_numpy(), index=grouped.tail(1).index, dtype=float)
    mean = weekly.rolling(ma_weeks).mean()
    rising = mean > mean.shift(slope_weeks)
    states, on = {}, False
    for date, value in weekly.items():
        if np.isnan(mean[date]):
            continue
        if value < mean[date]:
            on = False
        elif value > mean[date] and rising[date]:
            on = True
        states[date] = on
    return pd.Series(states, dtype=bool)


def rule_stage_blend(states: pd.Series, dates: pd.DatetimeIndex, start_i: int, on: float = 1.0, off: float = 0.5) -> Signal:
    """``on`` while the stage state is on, ``off`` otherwise; acts at week ends and at the start."""
    lookup = states.to_dict()
    known = states[states.index <= dates[start_i]]
    if known.empty:
        raise ValueError("stage state not warmed up at start")
    state = {"on": bool(known.iloc[-1])}

    def sig(i):
        previous = state["on"]
        if dates[i] in lookup:
            state["on"] = bool(lookup[dates[i]])
        if i == start_i or state["on"] != previous:
            return _weight_signal(on if state["on"] else off)
        return None
    return sig


def rule_trend_leverage(close: pd.Series, start_i: int, ma_days: int = 200, leverage: float = 1.5,
                        check: str = "week") -> Signal:
    """``leverage`` above the N-day mean, else cash; re-levers at month ends while on (weights drift otherwise)."""
    dates = close.index
    mean = close.rolling(ma_days).mean().to_numpy(float)
    values = close.to_numpy(float)
    if np.isnan(mean[start_i]):
        raise ValueError("moving average not warmed up at start")
    state = {"on": False}

    def sig(i):
        previous = state["on"]
        if i == start_i or check == "day" or is_week_end(dates, i):
            state["on"] = bool(values[i] > mean[i])
        if i == start_i or state["on"] != previous:
            return _weight_signal(leverage if state["on"] else 0.0)
        if state["on"] and is_period_end(dates, i, "M"):
            return _weight_signal(leverage)
        return None
    return sig
