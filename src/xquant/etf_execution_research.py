"""Domestic ETF execution diagnostics; no broker connection or live orders."""
from __future__ import annotations

import numpy as np
import pandas as pd


def premium_buy_decision(*, ask, reference_lower, reference_available_at,
                         quote_at, decision_at, reference_verified,
                         issuer_warning=False, premium_cap=0.01):
    """Conservative draft gate. A NAV date alone never establishes availability.

    reference_lower must be a justified lower bound on current fair value, not
    simply the last published overseas NAV. Unknown information blocks buying.
    """
    if issuer_warning:
        return False, "issuer_warning"
    if not reference_verified or reference_available_at is None:
        return False, "reference_unverified"
    decision = pd.Timestamp(decision_at)
    available = pd.Timestamp(reference_available_at)
    quote = pd.Timestamp(quote_at)
    if available > decision or quote > decision:
        return False, "future_information"
    if (decision-quote).total_seconds() > 60:
        return False, "stale_quote"
    if not np.isfinite([ask, reference_lower]).all() or min(ask, reference_lower) <= 0:
        return False, "invalid_reference"
    if ask/reference_lower-1 > premium_cap+1e-12:
        return False, "premium_over_cap"
    return True, "eligible"


def lot_orders(quantity, cash, prices, target, *, commission=0.0001,
               spread_bps=0.0, rebalance=True, buy_allowed=None, lot=100):
    """Sell overweight lots, then buy with available cash; never short or borrow.

    A blocked buy is retained as cash, without redistributing its target. No
    premium-triggered liquidation. Spread is a stated scenario around mid.
    Rounding is downward, so this is an approximate target execution model.
    """
    quantity = np.asarray(quantity, dtype=float).copy()
    prices = np.asarray(prices, dtype=float)
    target = np.asarray(target, dtype=float)
    allowed = np.ones(len(prices), bool) if buy_allowed is None else np.asarray(buy_allowed, bool)
    if (prices <= 0).any() or (target < 0).any() or target.sum() > 1+1e-12:
        raise ValueError("Invalid prices or allocation")
    half = spread_bps/20000
    ask, bid = prices*(1+half), prices*(1-half)
    gross = float(cash+quantity@prices)
    desired_value = gross*target if rebalance else cash*target
    desired_q = np.floor(desired_value/(ask*(1+commission))/lot)*lot
    records = []
    if rebalance:
        for k in range(len(prices)):
            sell = max(0.0, quantity[k]-desired_q[k])
            if sell:
                notional = sell*bid[k]
                cash += notional*(1-commission)
                quantity[k] -= sell
                records.append((k, -sell, bid[k], notional, notional*commission, sell*(prices[k]-bid[k])))
    for k in range(len(prices)):
        if not allowed[k]:
            continue
        want = max(0.0, desired_q[k]-quantity[k]) if rebalance else desired_q[k]
        affordable = np.floor(max(cash, 0)/(ask[k]*(1+commission))/lot)*lot
        buy = min(want, affordable)
        if buy:
            notional = buy*ask[k]
            cash -= notional*(1+commission)
            quantity[k] += buy
            records.append((k, buy, ask[k], notional, notional*commission, buy*(ask[k]-prices[k])))
    if cash < -1e-8 or (quantity < 0).any() or not np.allclose(quantity/lot, np.round(quantity/lot)):
        raise AssertionError("Lot/cash constraint violated")
    return quantity, max(cash, 0.0), records


def replay_lot_account(opening, closing, targets, rebalance_dates, contributions,
                       *, dividend=None, spread_bps=0, commission=0.0001):
    """Raw-price small-account diagnostic, including dividend receivable/pay date.

    All ETF orders at modeled same Chinese open. Actual halt/auction fills and
    historical premiums are NOT gated: the required timestamp data is absent.
    """
    q = np.zeros(closing.shape[1])
    cash = units = principal = receivable = paid = spread_paid = 0.0
    pending = {}
    rows, fills = [], []
    previous_q = q.copy()
    peak = 1.0
    for date in closing.index:
        if dividend and date == pd.Timestamp(dividend["ex_date"]):
            entitlement = previous_q[dividend["column"]]*dividend["per_share"]
            receivable += entitlement
            pending[pd.Timestamp(dividend["pay_date"])] = entitlement
        if date in pending:
            cash += pending[date]
            receivable -= pending[date]
        flow = float(contributions.get(date, 0))
        op = opening.loc[date].to_numpy(float)
        close = closing.loc[date].to_numpy(float)
        if flow:
            before = float(cash+q@op+receivable)
            units += flow/(before/units if units else 1.0)
            cash += flow
            principal += flow
        records = []
        if date in rebalance_dates or flow:
            if not np.isfinite(op).all():
                raise ValueError("Trading at an absent raw opening")
            q, cash, records = lot_orders(q, cash, op, targets.loc[date].to_numpy(float),
                                         commission=commission, spread_bps=spread_bps,
                                         rebalance=date in rebalance_dates)
        for record in records:
            k, delta, price, notional, fee, spread = record
            paid += fee
            spread_paid += spread
            fills.append([date, closing.columns[k], delta, price, notional, fee, spread])
        wealth = float(cash+q@close+receivable)
        unit = wealth/units
        peak = max(peak, unit)
        weight_error = float(np.max(np.abs(q*close/wealth-targets.loc[date].to_numpy(float))))
        rows.append([date, wealth, principal, flow, cash, receivable, paid, spread_paid,
                     unit, unit/peak-1, wealth-principal, weight_error, *q])
        previous_q = q.copy()
    frame = pd.DataFrame(rows, columns=["date", "wealth", "principal", "contribution", "cash",
                                        "receivable", "commission", "spread_cost", "unit_nav",
                                        "unit_drawdown", "profit", "max_weight_error", *closing.columns]).set_index("date")
    trades = pd.DataFrame(fills, columns=["date", "symbol", "quantity_delta", "price", "notional", "commission", "spread_cost"])
    return frame, trades


def premium_shock(nav_return, premium_before, premium_after):
    return (1+nav_return)*(1+premium_after)/(1+premium_before)-1


def earmarked_monthly_buys(quantity, budgets, new_money, target, asks, allowed,
                           *, commission=0.0001, lot=100):
    """Per-ETF virtual cash buckets prevent repeated blocked flows spilling over.

    Existing buckets survive; only NEW money is divided by the latest target.
    A full scheduled rebalance needs a separate portfolio target calculation.
    """
    q=np.asarray(quantity,float).copy()
    cash=np.asarray(budgets,float).copy()+new_money*np.asarray(target,float)
    asks=np.asarray(asks,float)
    if new_money<0 or (cash<0).any() or (asks<=0).any() or not np.isclose(np.sum(target),1):
        raise ValueError("Invalid earmarked budget")
    fees=np.zeros(len(q))
    for k in range(len(q)):
        if allowed[k]:
            buy=np.floor(cash[k]/(asks[k]*(1+commission))/lot)*lot
            notional=buy*asks[k]
            fees[k]=notional*commission
            cash[k]-=notional+fees[k]
            q[k]+=buy
    return q,cash,fees
