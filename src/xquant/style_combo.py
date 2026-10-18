"""Two-asset style combination backtests (close-to-close, signal at t, trade at t+1).

Pure helpers for the dividend-low-vol + CSI 2000 research. Every rule is a
function of price history up to and including day ``i`` only; orders are
executed at the next trading day's close with a proportional cost.
Asset columns are always ``a`` (dividend low-vol) and ``b`` (CSI 2000).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

Weights = dict[str, float]
Signal = Callable[[int], "Weights | None"]


def is_period_end(dates: pd.DatetimeIndex, i: int, freq: str) -> bool:
    """True if day ``i`` is the last trading day of its period (needs next date)."""
    if i + 1 >= len(dates):
        return False
    return dates[i].to_period(freq) != dates[i + 1].to_period(freq)


def is_week_end(dates: pd.DatetimeIndex, i: int) -> bool:
    if i + 1 >= len(dates):
        return False
    return dates[i].to_period("W-SUN") != dates[i + 1].to_period("W-SUN")


def inverse_vol_weights(returns: pd.DataFrame) -> Weights:
    vol = returns[["a", "b"]].std(ddof=1)
    inv = 1.0 / vol
    w = inv / inv.sum()
    return {"a": float(w["a"]), "b": float(w["b"])}


def below_ma_weekly(close_b: pd.Series, weeks: int = 30) -> bool:
    """Latest weekly close of ``close_b`` (data up to its last date) below its N-week mean."""
    weekly = close_b.groupby(close_b.index.to_period("W-SUN")).last()
    if len(weekly) < weeks:
        raise ValueError("not enough weekly history")
    return bool(weekly.iloc[-1] < weekly.iloc[-weeks:].mean())


def lagged_return(close: pd.Series, i: int, calendar_days: int = 182) -> float:
    """Return over ~26 weeks ending at i, base = last close on/before date - days."""
    dates = close.index
    base = dates.searchsorted(dates[i] - pd.Timedelta(days=calendar_days), side="right") - 1
    if base < 0:
        raise ValueError("not enough history for momentum")
    return float(close.iloc[i] / close.iloc[base] - 1.0)


# ---- rule factories: each returns signal(i) -> target weights or None ----

def rule_buy_hold(weights: Weights, start_i: int) -> Signal:
    return lambda i: dict(weights) if i == start_i else None


def rule_a(dates, start_i: int, freq: str = "Q") -> Signal:
    def sig(i):
        if i == start_i or is_period_end(dates, i, freq):
            return {"a": 0.5, "b": 0.5}
        return None
    return sig


def rule_b(rets: pd.DataFrame, start_i: int, window: int = 20, every: int = 10) -> Signal:
    def sig(i):
        if (i - start_i) % every == 0:
            return inverse_vol_weights(rets.iloc[i - window + 1:i + 1])
        return None
    return sig


def rule_c(prices: pd.DataFrame, start_i: int, weeks: int = 30) -> Signal:
    dates = prices.index
    state = {"filtered": None}

    def sig(i):
        is_start = i == start_i
        new = state["filtered"]
        if is_start or is_week_end(dates, i):
            new = below_ma_weekly(prices["b"].iloc[:i + 1], weeks)
        changed = new != state["filtered"]
        state["filtered"] = new
        quarter_end = is_period_end(dates, i, "Q")
        if new:
            return {"a": 1.0, "b": 0.0} if changed else None
        if changed or quarter_end:
            return {"a": 0.5, "b": 0.5}
        return None
    return sig


def rule_d(prices: pd.DataFrame, start_i: int, calendar_days: int = 182) -> Signal:
    dates = prices.index

    def sig(i):
        if i == start_i or is_period_end(dates, i, "M"):
            ra = lagged_return(prices["a"].iloc[:i + 1], i, calendar_days)
            rb = lagged_return(prices["b"].iloc[:i + 1], i, calendar_days)
            return {"a": 1.0, "b": 0.0} if ra >= rb else {"a": 0.0, "b": 1.0}
        return None
    return sig


@dataclass
class BacktestResult:
    nav: pd.Series
    weights: pd.DataFrame           # end-of-day weights (position value / NAV)
    trades: pd.DataFrame            # one row per execution
    orders: pd.DataFrame            # signals: signal date, execute date
    checks: dict = field(default_factory=dict)


def run_backtest(prices: pd.DataFrame, signal: Signal, start_i: int, cost: float = 0.001) -> BacktestResult:
    """Start in cash at close of ``start_i``; signals are computed at close and executed at the next close."""
    cols = ["a", "b"]
    dates = prices.index
    px = prices[cols].to_numpy(float)
    shares = np.zeros(2)
    cash = 1.0
    pending, pending_i = None, None
    nav, wts, trades, orders = [], [], [], []
    max_resid = 0.0
    for i in range(start_i, len(dates)):
        if pending is not None:
            assert pending_i < i, "execution must be after signal"
            hold = shares * px[i]
            total = hold.sum() + cash
            w = np.array([pending[c] for c in cols])
            c_est = 0.0
            for _ in range(8):  # cost depends on trade size which depends on cost
                tgt = w * (total - c_est)
                c_est = cost * np.abs(tgt - hold).sum()
            tgt = w * (total - c_est)
            traded = np.abs(tgt - hold).sum()
            new_cash = total - c_est - tgt.sum()
            max_resid = max(max_resid, abs((tgt.sum() + new_cash + c_est) - total))
            shares = tgt / px[i]
            cash = new_cash
            trades.append({"signal_date": dates[pending_i], "exec_date": dates[i], "traded_amount": traded,
                           "traded_frac_of_nav": traded / total, "cost": c_est,
                           "w_a": w[0], "w_b": w[1], "is_initial": pending_i == start_i})
            pending = None
        value = shares * px[i]
        total = value.sum() + cash
        nav.append(total)
        wts.append(value / total)
        s = signal(i)
        if s is not None and i + 1 < len(dates):
            pending, pending_i = s, i
            orders.append({"signal_date": dates[i], "exec_date": dates[i + 1], **{f"w_{c}": s[c] for c in cols}})
    nav_s = pd.Series(nav, index=dates[start_i:], name="nav")
    w_df = pd.DataFrame(wts, index=dates[start_i:], columns=cols)
    tr = pd.DataFrame(trades)
    od = pd.DataFrame(orders)
    checks = {"max_cash_plus_holdings_residual": max_resid,
              "exec_after_signal": bool((pd.to_datetime(tr["exec_date"]) > pd.to_datetime(tr["signal_date"])).all()) if len(tr) else True,
              "min_cash": float(cash), "max_weight_sum": float(w_df.sum(axis=1).max())}
    return BacktestResult(nav_s, w_df, tr, od, checks)


# ---- metrics ----

def annualized(nav: pd.Series) -> float:
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    return float((nav.iloc[-1] / nav.iloc[0]) ** (1 / years) - 1)


def drawdown(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1.0


def longest_recovery_days(nav: pd.Series) -> tuple[int, bool]:
    """Longest calendar days from a peak until NAV regains it (ongoing counts to the last date)."""
    peak_date, peak, best, ongoing = nav.index[0], nav.iloc[0], 0, False
    for d, v in nav.items():
        if v >= peak:
            best = max(best, (d - peak_date).days)
            peak_date, peak = d, v
    tail = (nav.index[-1] - peak_date).days
    if nav.iloc[-1] < peak:
        ongoing = tail >= best
        best = max(best, tail)
    return int(best), bool(ongoing)


def rolling_worst(nav: pd.Series, window: int = 756) -> tuple[float, pd.Timestamp | None]:
    if len(nav) <= window:
        return float("nan"), None
    r = (nav / nav.shift(window)) ** (252 / window) - 1
    r = r.dropna()
    return float(r.min()), r.idxmin()


def summary_metrics(nav: pd.Series, trades: pd.DataFrame | None = None) -> dict:
    ret = nav.pct_change().dropna()
    rec, ongoing = longest_recovery_days(nav)
    worst, worst_end = rolling_worst(nav)
    out = {"annualized": annualized(nav), "max_drawdown": float(drawdown(nav).min()),
           "longest_recovery_days": rec, "recovery_ongoing": ongoing,
           "annual_vol": float(ret.std(ddof=1) * np.sqrt(252)),
           "rolling3y_worst_annualized": worst, "rolling3y_worst_end": worst_end}
    out["calmar"] = out["annualized"] / abs(out["max_drawdown"]) if out["max_drawdown"] else float("nan")
    if trades is not None:
        years = (nav.index[-1] - nav.index[0]).days / 365.25
        t = trades[~trades["is_initial"]] if len(trades) else trades
        out["turnover_per_year"] = float(t["traded_frac_of_nav"].sum() / years) if len(t) else 0.0
        out["cost_drag_total"] = float(trades["cost"].sum()) if len(trades) else 0.0
        out["n_trades"] = int(len(t))
    return out


def period_stats(nav: pd.Series, start: str, end: str) -> dict:
    """Return from the last close before ``start`` (or first NAV) to the last close <= end, and max drawdown inside."""
    before = nav[nav.index < pd.Timestamp(start)]
    seg = nav[(nav.index >= pd.Timestamp(start)) & (nav.index <= pd.Timestamp(end))]
    if seg.empty:
        return {"return": float("nan"), "max_drawdown": float("nan")}
    base = before.iloc[-1] if len(before) else seg.iloc[0]
    path = pd.concat([pd.Series([base]), seg.reset_index(drop=True)], ignore_index=True)
    return {"return": float(seg.iloc[-1] / base - 1), "max_drawdown": float(drawdown(path).min())}
