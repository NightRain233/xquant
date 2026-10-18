"""Small, auditable next-open research kernel; no external calendars or services.

The native cost convention is half-L1 turnover INCLUDING cash. It is deliberately
distinct from charging fees on each actual buy/sell notional.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def replay(opens, closes, targets, *, cost_bps=10.0, cost_mode="native"):
    """Targets are indexed by execution day, already lagged by the caller.

    Returns currency P&L attribution (overnight old quantities, intraday new
    quantities), close weights and trades. Fractional shares, cash has no yield.
    """
    if not opens.index.equals(closes.index) or not opens.columns.equals(closes.columns):
        raise ValueError("Price axes must match")
    if cost_mode not in {"native", "gross"}:
        raise ValueError("Unknown cost mode")
    q = np.zeros(closes.shape[1])
    cash = previous_nav = 100000.0
    previous_close = closes.iloc[0].to_numpy(float)
    rows, weights, trades = [], [], []
    target_map = {day: row.to_numpy(float) for day, row in targets.iterrows()}
    for day, opening, close in zip(closes.index, opens.to_numpy(float), closes.to_numpy(float)):
        cost = turnover = 0.0
        pnl = q * (close - previous_close)
        if day in target_map:
            target = target_map[day]
            if not np.isfinite(opening).all() or (opening <= 0).any():
                raise ValueError("Cannot execute at invalid open")
            if (target < 0).any() or not np.isclose(target.sum(), 1):
                raise ValueError("Targets must be long-only and fully invested")
            values = q * opening
            gross = cash + values.sum()
            turnover = (np.abs(target - values / gross).sum() + abs(cash / gross)) / 2
            cost = gross * turnover * cost_bps / 10000
            if cost_mode == "gross":
                for _ in range(100):
                    updated = np.abs((gross - cost) * target - values).sum() * cost_bps / 10000
                    if abs(updated - cost) < 1e-10:
                        cost = updated
                        break
                    cost = updated
            new_q = (gross - cost) * target / opening
            pnl = q * (opening - previous_close) + new_q * (close - opening)
            for i, symbol in enumerate(closes.columns):
                trades.append((day, symbol, new_q[i] - q[i], opening[i], cost,
                               turnover, target[i]))
            q, cash = new_q, 0.0
        nav = cash + q @ close
        residual = nav - previous_nav - pnl.sum() + cost
        rows.append([nav, cash, cost, turnover, residual, *pnl])
        weights.append(q * close / nav)
        previous_close, previous_nav = close, nav
    daily = pd.DataFrame(rows, index=closes.index,
                         columns=["nav", "cash", "cost", "turnover", "pnl_residual", *closes.columns])
    daily.index.name = "date"
    weight_frame = pd.DataFrame(weights, index=closes.index, columns=closes.columns)
    trade_frame = pd.DataFrame(trades, columns=["date", "symbol", "quantity_delta", "open",
                                              "group_cost", "turnover", "target"])
    return daily, weight_frame, trade_frame


def performance(nav):
    returns = nav.pct_change().dropna()
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    scale = len(returns) / years
    drawdown = nav / nav.cummax() - 1
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1 / years) - 1
    downside = np.sqrt(np.square(returns.clip(upper=0)).mean())
    return {"total_return": nav.iloc[-1] / nav.iloc[0] - 1, "cagr": cagr,
            "volatility": returns.std(ddof=1) * np.sqrt(scale),
            "max_drawdown": drawdown.min(),
            "sharpe_zero_rf": returns.mean() / returns.std(ddof=1) * np.sqrt(scale),
            "sortino_zero_target": returns.mean() / downside * np.sqrt(scale),
            "calmar": cagr / abs(drawdown.min()), "underwater_share": (drawdown < 0).mean()}


def rolling_windows(nav, years):
    ends = nav.index[nav.index >= nav.index[0] + pd.DateOffset(years=years)]
    starts = nav.index.searchsorted(ends - pd.DateOffset(years=years), side="right") - 1
    total = nav.loc[ends].to_numpy() / nav.iloc[starts].to_numpy() - 1
    elapsed = (ends - nav.index[starts]).days / 365.25
    return pd.DataFrame({"start": nav.index[starts], "end": ends, "total_return": total,
                         "cagr": (1 + total) ** (1 / elapsed) - 1})


def drawdown_events(nav):
    peak = nav.iloc[0]
    peak_date = nav.index[0]
    trough, trough_date = peak, peak_date
    active = False
    rows = []
    for day, value in nav.items():
        if value >= peak:
            if active:
                rows.append([peak_date, trough_date, day, trough / peak - 1,
                             (day - peak_date).days, (day - trough_date).days, False])
            peak, peak_date, trough, trough_date, active = value, day, value, day, False
        else:
            active = True
            if value < trough:
                trough, trough_date = value, day
    if active:
        rows.append([peak_date, trough_date, pd.NaT, trough / peak - 1,
                     (nav.index[-1] - peak_date).days, np.nan, True])
    return pd.DataFrame(rows, columns=["peak", "trough", "recovery", "depth",
                                       "underwater_calendar_days", "trough_to_recovery_days", "censored"])


def entry_recovery(nav):
    """Every close entry: first later NAV >= entry; no later crossing is censored."""
    values = nav.to_numpy()
    rows = []
    for i in range(len(nav) - 1):
        found = np.flatnonzero(values[i + 1:] >= values[i])
        end = i + 1 + found[0] if len(found) else len(nav) - 1
        rows.append([nav.index[i], nav.index[end] if len(found) else pd.NaT,
                     (nav.index[end] - nav.index[i]).days, not len(found)])
    return pd.DataFrame(rows, columns=["entry", "recovery", "calendar_days", "censored"])
