"""Point-in-time distribution signals and separate raw-share cash accounting.

No broker orders. A distribution is signal income on ex-date, a registered
holder receivable in the ledger, and spendable only after cash posting.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from xquant.cashflow_research import solve_rebalance


def distribution_returns(closes, actions):
    """Causal close total returns; future actions never restate earlier rows.

    Splits use their first post-conversion quote date. Per-share distributions
    refer to pre-event shares (the covered events have no simultaneous split).
    An announcement date earlier than ex-date is required, not an invented
    precise historical publication timestamp.
    """
    result = closes.pct_change(fill_method=None)
    for event in actions.to_dict("records"):
        day = pd.Timestamp(event["effective_quote_date"])
        symbol = event["symbol"]
        if symbol not in closes or day not in closes.index:
            continue
        position = closes.index.get_loc(day)
        if position == 0:
            continue
        if pd.Timestamp(event["announcement_date"]) >= day:
            raise ValueError("Action availability not established before event")
        ratio = float(event.get("split_ratio", 1))
        income = float(event.get("cash_per_share", 0))
        result.loc[day, symbol] = (
            closes.loc[day, symbol] * ratio + income
        ) / closes.iloc[position - 1][symbol] - 1
    return result


@dataclass
class DividendMarket:
    dates: pd.DatetimeIndex
    symbols: list[str]
    opening: np.ndarray
    closing: np.ndarray
    targets: np.ndarray
    rebalance: np.ndarray
    actions: list[dict]
    deposits: np.ndarray


def replay_dividend_account(market, *, flows, start_index=0, fee_bps=1.0,
                            export_details=True, invest_new_money=True):
    """Fractional shares, fixed targets/calendar, literal gross commission.

    Cash distribution payment posts AFTER the modeled open on official pay
    date. Reinvestment waits for a scheduled rebalance. Monthly subscriptions
    invest only their new cash when no rebalance is scheduled. Receivables
    belong to equity but never fund orders. Original unfiltered ETF baseline.
    """
    n, width = market.closing.shape
    if not np.isfinite(market.closing).all() or (market.closing <= 0).any():
        raise ValueError("All close valuation marks must be finite and positive")
    if not np.isfinite(market.targets).all() or (market.targets < 0).any() or not np.allclose(market.targets.sum(axis=1),1):
        raise ValueError("Targets must be finite, long-only, and sum to one")
    if fee_bps < 0 or any(value < 0 for value in flows.values()):
        raise ValueError("Negative commissions or subscriptions are unsupported")
    fee = fee_bps / 10000
    q = np.zeros(width)
    cash = receivable = principal = units = paid = previous_wealth = 0.0
    peak = 1.0
    previous_close = market.closing[start_index].copy()
    dates = market.dates
    registered, entitlement, pending = {}, {}, {}
    actions_by_date = {}
    for number, event in enumerate(market.actions):
        if event["symbol"] not in market.symbols:
            continue
        event = dict(event, event_id=number, column=market.symbols.index(event["symbol"]))
        if float(event.get("cash_per_share", 0)):
            for kind, field in [("register", "record_date"), ("ex", "effective_quote_date"), ("pay", "pay_date")]:
                actions_by_date.setdefault(pd.Timestamp(event[field]), []).append((kind, event))
        else:
            actions_by_date.setdefault(pd.Timestamp(event.get("corporate_action_date", event["effective_quote_date"])), []).append(("split", event))
    rows, fills, events = [], [], []
    for i in range(start_index, n):
        date = dates[i]
        op, close = market.opening[i], market.closing[i]
        old_q = q.copy()
        bridge_close = previous_close.copy()
        pre_conversion_close = close.copy()
        dividend_income = 0.0
        day_events = actions_by_date.get(date, [])
        for kind, event in day_events:
            k, eid = event["column"], event["event_id"]
            if kind == "split":
                ratio = float(event["split_ratio"])
                if event.get("corporate_action_date"):
                    # The official conversion posts after the halt-day close;
                    # close marks are already divided by the ratio by caller.
                    pre_conversion_close[k] *= ratio
                else:
                    # Minimal fixture / first-quote-date conversion.
                    q[k] *= ratio
                    old_q[k] *= ratio
                    bridge_close[k] /= ratio
            elif kind == "ex":
                # Starting after registration creates no entitlement, even
                # if a newly funded account buys on ex-date.
                amount = registered.get(eid, 0.0) * float(event["cash_per_share"])
                entitlement[eid] = amount
                pending[eid] = amount
                receivable += amount
                dividend_income += amount
                if export_details:
                    events.append([date, eid, event["symbol"], "ex_receivable_before_open", registered.get(eid, 0.), float(event["cash_per_share"]), amount, cash, receivable])
        flow = float(flows.get(i, 0))
        pre_flow_price = np.nan
        if flow:
            if not np.isfinite(op).all() or (op <= 0).any():
                raise ValueError("Subscription cannot use an absent opening")
            before = float(cash + q @ op + receivable)
            pre_flow_price = before / units if units else 1.0
            units += flow / pre_flow_price
            principal += flow
            cash += flow
        cost = 0.0
        changed = False
        if market.rebalance[i] and (q.sum() > 0 or cash > 0):
            if not np.isfinite(op).all() or (op <= 0).any():
                raise ValueError("Rebalance cannot use an absent opening")
            old_values = q * op
            new_values, cost = solve_rebalance(old_values, cash, market.targets[i], fee)
            q = new_values / op
            cash = 0.0
            changed = True
            if export_details:
                for k in range(width):
                    delta = q[k] - old_q[k]
                    fills.append([date, market.symbols[k], delta, op[k], abs(delta)*op[k], abs(delta)*op[k]*fee, "rebalance"])
        elif flow and invest_new_money:
            notional = flow / (1 + fee)
            delta = notional * market.targets[i] / op
            q += delta
            cost = flow - notional
            cash -= flow
            changed = True
            if export_details:
                for k in range(width):
                    fills.append([date, market.symbols[k], delta[k], op[k], delta[k]*op[k], delta[k]*op[k]*fee, "subscription"])
        # Income and split-neutral raw-price movement are separate attribution.
        if changed:
            asset_pnl = old_q * (op - bridge_close) + q * (pre_conversion_close - op)
        else:
            asset_pnl = old_q * (pre_conversion_close - bridge_close)
        pnl = float(asset_pnl.sum() + dividend_income)
        for kind, event in day_events:
            eid, k = event["event_id"], event["column"]
            if kind == "register":
                registered[eid] = q[k]
                if export_details:
                    events.append([date, eid, event["symbol"], "registered_after_close", q[k], float(event["cash_per_share"]), 0., cash, receivable])
            elif kind == "pay":
                amount = pending.pop(eid, 0.0)
                cash += amount
                receivable -= amount
                if export_details:
                    events.append([date, eid, event["symbol"], "cash_paid_after_close", registered.get(eid, 0.), float(event["cash_per_share"]), amount, cash, receivable])
            elif kind == "split":
                ratio = float(event["split_ratio"])
                if event.get("corporate_action_date"):
                    q[k] *= ratio
                if export_details:
                    phase="split_after_close" if event.get("corporate_action_date") else "split_before_open"
                    events.append([date,eid,event["symbol"],phase,q[k],ratio,0.,cash,receivable])
        paid += cost
        wealth = float(cash + q @ close + receivable)
        if units <= 0:
            raise ValueError("Account must start with an external contribution")
        unit = wealth / units
        peak = max(peak, unit)
        residual = wealth - previous_wealth - flow - pnl + cost
        if abs(residual) > max(1e-7, wealth*1e-11) or cash < -1e-7 or receivable < -1e-7:
            raise AssertionError("Cash/receivable/P&L conservation failed")
        liquidation = float(cash + receivable + q @ close * (1-fee))
        rows.append([wealth, liquidation, principal, flow, cost, paid, unit, unit/peak-1,
                     liquidation-principal, liquidation/principal-1, pnl, residual,
                     pre_flow_price, cash, receivable, dividend_income,
                     float(cash+q@close*(1-fee)), *q, *asset_pnl])
        previous_wealth, previous_close = wealth, close.copy()
    daily = pd.DataFrame(rows, index=dates[start_index:], columns=[
        "wealth", "liquidation_wealth", "principal", "contribution", "cost", "cumulative_cost",
        "unit_nav", "unit_drawdown", "profit", "profit_ratio", "market_pnl", "account_residual",
        "pre_flow_unit_price", "cash", "receivable", "dividend_income", "available_liquidation",
        *["quantity_"+c for c in market.symbols], *["price_pnl_"+c for c in market.symbols]])
    daily.index.name = "date"
    trades = pd.DataFrame(fills, columns=["date", "symbol", "quantity_delta", "price", "notional", "commission", "type"])
    if len(trades):trades=trades.sort_values(["date","quantity_delta"],kind="stable").reset_index(drop=True)
    event_frame = pd.DataFrame(events, columns=["date", "event_id", "symbol", "phase", "registered_or_split_quantity", "per_share_or_ratio", "amount", "cash_after", "receivable_after"])
    return daily, trades, event_frame
