"""Overlay test of a single-sleeve filter on top of an existing daily main-line NAV.

The base NAV (its own weights, rebalancing and costs) is taken as given. The overlay only adds the return
effect of changing one sleeve's weight by a multiplier ``m`` (1 = unchanged, ``off`` when the trend filter is off),
the cut going to cash or being spread over the other sleeves, and the cost of each change.

Timing convention (same as the S&P studies): a decision at the close of day ``d`` is executed at the close of the
next trading day. The multiplier holding after the close of day ``t`` is therefore the state known at the close of
``t - 1``, and it earns the returns from ``t + 1`` onwards.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from xquant import position_rules as pr
from xquant.style_combo import annualized, drawdown

TRADING_DAYS = 252
CASH = "cash"


def trend_multiplier(close: pd.Series, off: float, ma_weeks: int = 30, slope_weeks: int = 4) -> pd.Series:
    """Holding multiplier after each day's close: 1 while the weekly 30-week trend is on, ``off`` otherwise.

    Weekly state is computed from closes up to each week end; it is applied one trading day later.
    Before the first state exists the multiplier is 1 (the trend is not yet defined, not a signal to cut).
    """
    states = pr.stage_states(close, ma_weeks=ma_weeks, slope_weeks=slope_weeks)
    known = states.reindex(close.index, method="ffill")
    decided = known.shift(1)  # state known at the previous close, executed at this close
    on = decided.fillna(True).astype(bool).to_numpy()
    return pd.Series(np.where(on, 1.0, float(off)), index=close.index, name="multiplier")


def overlay_return(weights: pd.DataFrame, returns: pd.DataFrame, multiplier: pd.Series, sleeve: str,
                   cost_per_side: float, reallocate: bool = False) -> tuple[pd.Series, pd.Series]:
    """Daily return added by the filter, and the traded fraction of NAV on each day.

    ``weights``: end-of-day weights of the base NAV (columns = assets plus ``CASH``), aligned to ``returns``.
    ``returns``: close-to-close returns of each asset (cash earns 0 here).
    ``reallocate``: spread the cut over the other sleeves pro rata instead of holding cash.
    """
    assets = [c for c in weights.columns if c != CASH]
    base_prev = weights.shift(1)  # weights that earn the return of day t
    mult_prev = multiplier.shift(1).fillna(1.0)  # multiplier in force while day t's return is earned
    scaled = base_prev.copy()
    cut = base_prev[sleeve] * (1.0 - mult_prev)
    scaled[sleeve] = base_prev[sleeve] * mult_prev
    if reallocate:
        others = [a for a in assets if a != sleeve]
        other_w = base_prev[others]
        total = other_w.sum(axis=1).replace(0.0, np.nan)
        scaled[others] = other_w.add(other_w.div(total, axis=0).mul(cut, axis=0), fill_value=0.0)
    else:
        scaled[CASH] = base_prev[CASH] + cut
    delta_w = (scaled[assets] - base_prev[assets]).fillna(0.0)
    effect = (delta_w * returns[assets].reindex(weights.index).fillna(0.0)).sum(axis=1)
    traded = (multiplier - multiplier.shift(1).fillna(1.0)).abs() * weights[sleeve].shift(1).fillna(0.0)
    cost = traded * cost_per_side
    return (effect - cost).rename("overlay_return"), traded.rename("traded_fraction")


def asset_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Close-to-close returns; the first row is NaN."""
    return prices.pct_change()


def nav_from_returns(returns: pd.Series, start_value: float = 100000.0) -> pd.Series:
    r = returns.fillna(0.0)
    nav = start_value * (1.0 + r).cumprod()
    nav.iloc[0] = start_value
    return nav


def window(series: pd.Series, start: str, end: str) -> pd.Series:
    return series[(series.index >= pd.Timestamp(start)) & (series.index <= pd.Timestamp(end))]


def perf(returns: pd.Series, risk_free: float = 0.0) -> dict:
    """Metrics on a daily return series, zero risk-free rate unless given (same definition for all rows)."""
    r = returns.dropna()
    nav = (1.0 + r).cumprod()
    nav = pd.concat([pd.Series([1.0], index=[r.index[0] - pd.Timedelta(days=1)]), nav])
    cagr = annualized(nav)
    dd = float(drawdown(nav).min())
    excess = r - risk_free / TRADING_DAYS
    sharpe = float(excess.mean() / excess.std(ddof=1) * np.sqrt(TRADING_DAYS))
    return {"cagr": cagr, "vol": float(r.std(ddof=1) * np.sqrt(TRADING_DAYS)), "sharpe": sharpe,
            "max_dd": dd, "calmar": cagr / abs(dd) if dd else float("nan"), "final_multiple": float(nav.iloc[-1])}
