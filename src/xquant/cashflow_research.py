"""Cash-flow account research with causal quotes and exact external-flow units.

Market clocks/targets are prepared once by the research job. Foreign buys are
separate, later events; their price cannot enter an earlier CNY valuation.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class PreparedDcaMarket:
    dates: pd.DatetimeIndex
    core_open: np.ndarray
    core_close: np.ndarray
    three_targets: np.ndarray
    two_targets: np.ndarray
    rebalance: np.ndarray
    spy_mark: np.ndarray
    deposit_indices: np.ndarray
    spy_execution_visible: np.ndarray
    spy_entry_cny: np.ndarray
    monthly_labels: list[str]


def solve_rebalance(values, cash, target, fee_rate):
    """Gross buy/sell notional fees, solved against post-cost target holdings."""
    gross = float(np.sum(values) + cash)
    cost = 0.0
    for _ in range(100):
        updated = float(np.abs((gross-cost)*target-values).sum()*fee_rate)
        if abs(updated-cost) <= max(1e-9, gross*1e-14):
            return (gross-updated)*target, updated
        cost = updated
    raise RuntimeError("Fee fixed point did not converge")


def replay_dca(market, strategy, *, start_month=0, stop_after=None,
               contribution=10000.0, fee_bps=10.0, fx_cost_bps=0.0):
    """New cash buys latest known target proportions; scheduled rebalances persist.

    Contribution before domestic open. Units issue at pre-flow opening NAV;
    deposits cannot manufacture TWR gains. SPY orders wait for their own open.
    ``spy_execution_visible`` is the first Shanghai valuation AFTER US execution.
    """
    if strategy not in {"Three", "Two", "SP500"}:
        raise ValueError("Unknown strategy")
    deposits = market.deposit_indices
    last_month = len(deposits) if stop_after is None else min(len(deposits), start_month+stop_after)
    eligible = np.arange(start_month, last_month)
    flow_map = {int(deposits[j]): contribution for j in eligible}
    start_index = int(deposits[start_month])
    fee = fee_bps/10000
    fx_fee = fx_cost_bps/10000
    n = len(market.dates)
    output = np.zeros((n-start_index, 13), dtype=float)
    cash = principal = units = paid = 0.0
    previous_wealth = 0.0
    trades = []
    if strategy == "SP500":
        q = 0.0
        events = {}
        for j in eligible:
            visible = int(market.spy_execution_visible[j])
            if visible < n:
                events.setdefault(visible, []).append(j)
        previous_price = float(market.spy_mark[start_index])
    else:
        columns = np.array([0, 1, 2]) if strategy == "Three" else np.array([1, 2])
        q = np.zeros(len(columns))
        previous_close = market.core_close[start_index, columns].copy()
        target_array = market.three_targets if strategy == "Three" else market.two_targets
    peak_unit = 1.0
    for i in range(start_index, n):
        flow = float(flow_map.get(i, 0.0))
        cost = 0.0
        before_price = np.nan
        if strategy == "SP500":
            price = float(market.spy_mark[i])
            pnl = q*(price-previous_price)
            for j in events.get(i, []):
                if cash < contribution-1e-7:
                    raise AssertionError("US buy spent cash that had not arrived")
                entry = float(market.spy_entry_cny[j])
                notional = contribution/((1+fee)*(1+fx_fee))
                new_q = notional/entry
                transaction_cost = contribution-notional
                pnl += new_q*(price-entry)
                q += new_q
                cash -= contribution
                cost += transaction_cost
                trades.append([i, j, 0, new_q, entry, notional, transaction_cost, "subscription"])
            before = cash+q*price
            if flow:
                before_price = before/units if units>0 else 1.0
                units += flow/before_price
                cash += flow
                principal += flow
            wealth = cash+q*price
            asset_value = q*price
            liquidation = cash+asset_value*(1-fee)*(1-fx_fee)
            previous_price = price
        else:
            opening = market.core_open[i, columns]
            close = market.core_close[i, columns]
            old_q = q.copy()
            pnl = q@(close-previous_close)
            if flow:
                if not np.isfinite(opening).all() or (opening<=0).any():
                    raise ValueError("Contribution at invalid opening")
                before = float(cash+q@opening)
                before_price = before/units if units>0 else 1.0
                units += flow/before_price
                cash += flow
                principal += flow
            target = target_array[i]
            if market.rebalance[i] and cash+np.sum(q)>0:
                if not np.isfinite(opening).all():
                    raise ValueError("Rebalance at invalid opening")
                old_value = q*opening
                new_values, cost = solve_rebalance(old_value, cash, target, fee)
                q = new_values/opening
                cash = 0.0
                pnl = old_q@(opening-previous_close)+q@(close-opening)
                notionals = np.abs(new_values-old_value)
                for k, symbol_index in enumerate(columns):
                    trades.append([i, -1, int(symbol_index), q[k]-old_q[k], opening[k], notionals[k], notionals[k]*fee, "rebalance"])
            elif flow:
                notional = flow/(1+fee)
                new_q = notional*target/opening
                cost = flow-notional
                q += new_q
                cash -= flow
                pnl = old_q@(close-previous_close)+new_q@(close-opening)
                for k, symbol_index in enumerate(columns):
                    trades.append([i, -1, int(symbol_index), new_q[k], opening[k], notional*target[k], cost*target[k], "subscription"])
            wealth = float(cash+q@close)
            asset_value = float(q@close)
            liquidation = cash+asset_value*(1-fee)
            previous_close = close
        paid += cost
        unit_nav = wealth/units
        peak_unit = max(peak_unit, unit_nav)
        residual = wealth-previous_wealth-flow-pnl+cost
        if abs(residual)>max(1e-7, wealth*1e-11) or cash < -1e-7:
            raise AssertionError("Cash-flow/P&L conservation failed")
        output[i-start_index] = [wealth, liquidation, principal, flow, cost, paid,
                                unit_nav, unit_nav/peak_unit-1, liquidation-principal,
                                liquidation/principal-1, pnl, residual, before_price]
        previous_wealth = wealth
    daily = pd.DataFrame(output, index=market.dates[start_index:], columns=[
        "wealth", "liquidation_wealth", "principal", "contribution", "cost", "cumulative_cost",
        "unit_nav", "unit_drawdown", "profit", "profit_ratio", "market_pnl", "account_residual", "pre_flow_unit_price"])
    daily.index.name = "date"
    trade_frame = pd.DataFrame(trades, columns=["valuation_index", "funding_month_index", "symbol_index",
                                               "quantity_delta", "execution_price_cny", "gross_notional_cny", "cost_cny", "type"])
    return daily, trade_frame


def xirr(contributions, terminal, terminal_date):
    """Unique money-weighted root for negative deposits and one positive terminal."""
    flows = contributions[contributions>0]
    if flows.empty:
        return np.nan
    duration = (pd.Timestamp(terminal_date)-flows.index).days.to_numpy()/365.25
    if duration.max() < 1/365.25:
        return np.nan
    amounts = flows.to_numpy(float)
    def balance(log_growth):
        return float(terminal-np.dot(amounts, np.exp(log_growth*duration)))
    lo, hi = -30.0, 10.0
    if balance(lo)<0 or balance(hi)>0:
        return np.nan
    for _ in range(120):
        middle = (lo+hi)/2
        if balance(middle)>0:
            lo = middle
        else:
            hi = middle
    return float(np.expm1((lo+hi)/2))


def principal_loss_events(daily):
    """Below contributed principal, with observed calendar durations and censoring."""
    profit = daily.profit.to_numpy(float)
    ratio = daily.profit_ratio.to_numpy(float)
    negative = profit < -1e-7
    starts = np.flatnonzero(negative & ~np.r_[False, negative[:-1]])
    ends = np.flatnonzero(negative & ~np.r_[negative[1:], False])
    rows = []
    for start, end in zip(starts, ends):
        worst_amount = start+int(np.argmin(profit[start:end+1]))
        worst_ratio = start+int(np.argmin(ratio[start:end+1]))
        censored = end == len(daily)-1
        recovery_index = end if censored else end+1
        rows.append({"start": daily.index[start], "worst_amount": profit[worst_amount],
                     "worst_amount_date": daily.index[worst_amount], "worst_ratio": ratio[worst_ratio],
                     "worst_ratio_date": daily.index[worst_ratio],
                     "recovery": pd.NaT if censored else daily.index[recovery_index],
                     "calendar_days": (daily.index[recovery_index]-daily.index[start]).days, "censored": censored})
    return pd.DataFrame(rows, columns=["start", "worst_amount", "worst_amount_date", "worst_ratio",
                                       "worst_ratio_date", "recovery", "calendar_days", "censored"])


def account_summary(daily):
    first = daily.index[0]
    end = daily.index[-1]
    events = principal_loss_events(daily)
    completed = events.loc[~events.censored] if len(events) else events
    i_amount = daily.profit.idxmin()
    i_ratio = daily.profit_ratio.idxmin()
    negative = daily.profit < -1e-7
    # Economic break-even persists only through the observed endpoint, not a forecast.
    last_negative = int(np.flatnonzero(negative.to_numpy())[-1]) if negative.any() else -1
    durable = daily.index[last_negative+1] if last_negative < len(daily)-1 else pd.NaT
    stable_months = daily.profit.resample("ME").last()
    stable = (stable_months>=0).rolling(3).sum().eq(3)
    dates = stable_months.index[stable]
    stable_date = dates[0] if len(dates) else pd.NaT
    rate = xirr(daily.contribution, daily.liquidation_wealth.iloc[-1], end)
    observed_years = (end-first).days/365.25
    twr_cagr = daily.unit_nav.iloc[-1]**(1/observed_years)-1 if observed_years>=1 else np.nan
    return {"start": first, "end": end, "contributions": int((daily.contribution>0).sum()),
            "principal": daily.principal.iloc[-1], "terminal_wealth": daily.wealth.iloc[-1],
            "terminal_liquidation": daily.liquidation_wealth.iloc[-1], "profit": daily.profit.iloc[-1],
            "profit_on_principal": daily.profit_ratio.iloc[-1], "xirr": rate if observed_years>=1 else np.nan,
            "xirr_real_assumed_inflation2pct": (1+rate)/1.02-1 if observed_years>=1 and np.isfinite(rate) else np.nan,
            "twr_cagr": twr_cagr, "unit_max_drawdown": daily.unit_drawdown.min(),
            "worst_loss_amount": daily.profit.loc[i_amount], "worst_loss_amount_date": i_amount,
            "principal_at_worst_amount": daily.principal.loc[i_amount],
            "worst_loss_ratio": daily.profit_ratio.loc[i_ratio], "worst_loss_ratio_date": i_ratio,
            "principal_at_worst_ratio": daily.principal.loc[i_ratio],
            "negative_valuation_share": negative.mean(), "material_loss_gt1pct_share": (daily.profit_ratio<-.01).mean(),
            "material_loss_gt5pct_share": (daily.profit_ratio<-.05).mean(),
            "longest_completed_principal_loss_days": completed.calendar_days.max() if len(completed) else 0,
            "longest_censored_principal_loss_days": events.loc[events.censored, "calendar_days"].max() if len(events) else 0,
            "first_three_month_end_nonnegative": stable_date, "final_observed_breakeven": durable,
            "total_trade_cost": daily.cost.sum(), "terminal_exit_cost": daily.wealth.iloc[-1]-daily.liquidation_wealth.iloc[-1],
            "max_account_residual": daily.account_residual.abs().max()}
