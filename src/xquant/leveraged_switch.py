"""Leveraged-ETF regime switching: synthetic daily-reset prices, buffered regimes and a cash/TQQQ/QQQ backtest.

Signals are read at the close of day ``i``; trades execute at the close of ``i + lag`` (``lag=1`` by default)
with a proportional cost. Cash accrues the previous close's annual rate per 365 calendar days.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

ASSETS = ("lev", "base")
Decide = Callable[[int, np.ndarray], "np.ndarray | None"]


def synthetic_leveraged(close: pd.Series, rate: pd.Series, leverage: float = 3.0, fee: float = 0.0095,
                        spread: float = 0.005) -> pd.Series:
    """Daily-reset leveraged price from an index close; financing is ``(leverage - 1) * (rate + spread)``."""
    rate = rate.reindex(close.index).ffill()
    days = close.index.to_series().diff().dt.days.to_numpy(float)
    drag = ((leverage - 1.0) * (rate.shift(1).to_numpy(float) + spread) + fee) * days / 365.0
    ret = leverage * close.pct_change().to_numpy(float) - drag
    ret[0] = 0.0
    out = pd.Series(np.cumprod(1.0 + ret), index=close.index, name="synthetic")
    assert out.notna().all() and (out > 0).all(), "synthetic price must stay positive"
    return out


def extension(close: pd.Series, window: int = 200) -> pd.Series:
    """Close relative to its simple moving average, minus one (NaN during warm-up)."""
    return close / close.rolling(window).mean() - 1.0


def buffered_regime(ext: pd.Series, up: float, down: float) -> pd.Series:
    """+1 after ``ext >= up``, -1 after ``ext <= -down``; in between keep the last state (0 before any signal)."""
    state, out = 0, []
    for v in ext.to_numpy(float):
        if not np.isnan(v):
            if v >= up:
                state = 1
            elif v <= -down:
                state = -1
        out.append(state)
    return pd.Series(out, index=ext.index, name="regime")


@dataclass
class SwitchResult:
    nav: pd.Series
    weights: pd.DataFrame
    trades: pd.DataFrame


def run_switch(prices: pd.DataFrame, rate: pd.Series, decide: Decide, start_i: int, initial: np.ndarray,
               cost: float = 0.001, lag: int = 1) -> SwitchResult:
    """Hold ``prices[["lev", "base"]]`` plus cash. ``decide(i, weights_at_close_i)`` returns target weights or None.

    ``initial`` weights are bought at the close of ``start_i`` (cost charged). With ``lag=0`` trades fill at the
    same close as the signal, which is only an approximation of trading just before the close.
    """
    assert lag in (0, 1)
    dates = prices.index
    px = prices[list(ASSETS)].to_numpy(float)
    rates = rate.reindex(dates).ffill().to_numpy(float)
    shares, cash = np.zeros(2), 1.0
    pending = None
    nav, wts, trades = [], [], []

    def rebalance(i, target):
        nonlocal shares, cash
        hold = shares * px[i]
        total = hold.sum() + cash
        c = 0.0
        for _ in range(8):  # cost depends on trade size which depends on cost
            c = cost * np.abs(target * (total - c) - hold).sum()
        tgt = target * (total - c)
        trades.append({"date": dates[i], "w_lev": target[0], "w_base": target[1],
                       "traded_frac": float(np.abs(tgt - hold).sum() / total), "cost": c})
        shares, cash = tgt / px[i], total - c - tgt.sum()

    for i in range(start_i, len(dates)):
        if i > start_i:
            cash *= (1.0 + rates[i - 1]) ** ((dates[i] - dates[i - 1]).days / 365.0)
        if i == start_i and np.abs(initial).sum() > 0:
            rebalance(i, np.asarray(initial, float))
        if pending is not None:
            rebalance(i, pending)
            pending = None
        w = shares * px[i] / ((shares * px[i]).sum() + cash)
        target = decide(i, w)
        if target is not None and np.abs(np.asarray(target) - w).sum() > 1e-9:
            if lag == 0:
                rebalance(i, np.asarray(target, float))
            elif i + 1 < len(dates):
                pending = np.asarray(target, float)
        value = shares * px[i]
        total = value.sum() + cash
        nav.append(total)
        wts.append(value / total)
    assert cash > -1e-9 and min(nav) > 0
    return SwitchResult(pd.Series(nav, index=dates[start_i:], name="nav"),
                        pd.DataFrame(wts, index=dates[start_i:], columns=list(ASSETS)), pd.DataFrame(trades))


def forum_rule(regime: pd.Series, lev_ext: "pd.Series | None", dca_months: int = 6, month_days: int = 21,
               reduce_at: float = 0.30, exit_at: float = 0.40, reduced: tuple[float, float] = (0.5, 0.5)) -> Decide:
    """Bull: 100% lev (``reduced`` when ``lev_ext >= reduce_at``, cash when ``>= exit_at``).

    Bear: sell to cash, then every ``month_days`` move ``cash / remaining tranches`` into base, ``dca_months`` times.
    Neutral regime (0, before the first signal) holds cash. ``lev_ext=None`` disables the protection.
    """
    reg = regime.to_numpy(int)
    ext = None if lev_ext is None else lev_ext.to_numpy(float)
    bear_start = np.full(len(reg), -1)
    for i in range(len(reg)):
        if reg[i] == -1:
            bear_start[i] = bear_start[i - 1] if i and reg[i - 1] == -1 else i

    def decide(i: int, w: np.ndarray):
        if reg[i] == 1:
            if ext is not None and ext[i] >= exit_at:
                return np.array([0.0, 0.0])
            if ext is not None and ext[i] >= reduce_at:
                return np.array(reduced)
            return np.array([1.0, 0.0])
        if reg[i] == -1:
            days = i - bear_start[i]
            if w[0] > 1e-9:
                return np.array([0.0, w[1]])
            k, cash = days // month_days, 1.0 - w.sum()
            if days > 0 and days % month_days == 0 and k <= dca_months:
                return np.array([0.0, w[1] + cash / (dca_months - k + 1)])
            if k > dca_months and cash > 1e-6:  # a backtest started after the schedule ended
                return np.array([0.0, 1.0])
            return None
        return None if w.sum() < 1e-9 else np.array([0.0, 0.0])

    return decide


def simple_rule(signal_ext: pd.Series, up: float = 0.0, down: float = 0.0) -> Decide:
    """100% lev while the buffered regime of ``signal_ext`` is bullish, otherwise cash."""
    reg = buffered_regime(signal_ext, up, down).to_numpy(int) if (up or down) else \
        np.where(signal_ext.to_numpy(float) > 0, 1, -1)

    def decide(i: int, w: np.ndarray):
        return np.array([1.0, 0.0]) if reg[i] == 1 else np.array([0.0, 0.0])

    return decide
