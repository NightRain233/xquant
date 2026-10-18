import numpy as np
import pandas as pd

from xquant.etf_execution_research import (
    earmarked_monthly_buys, lot_orders, premium_buy_decision, premium_shock, replay_lot_account,
)


def test_lots_fees_and_spread_conserve_value_without_borrowing():
    prices = np.array([4.433, 2.353, 8.634])
    q, cash, trades = lot_orders([0, 0, 0], 50000, prices, [.45, .33, .22], spread_bps=20)
    fees = sum(t[4] for t in trades)
    spread = sum(t[5] for t in trades)
    assert np.all(q % 100 == 0)
    assert cash >= 0
    assert abs(cash+q@prices+fees+spread-50000) < 1e-8


def test_blocked_foreign_buy_keeps_cash_without_forcing_sale():
    q, cash, trades = lot_orders([500, 0], 5000, [10, 10], [.5, .5], buy_allowed=[True, False])
    assert np.array_equal(q, [400, 0])  # ordinary target rounding, not premium liquidation
    assert cash > 5900
    assert all(t[0] != 1 for t in trades)
    held, _, _ = lot_orders([0, 500], 5000, [10, 10], [.5, .5], buy_allowed=[True, False])
    assert held[1] == 400  # only the ordinary overweight reduction; no full liquidation


def test_premium_gate_never_uses_unpublished_nav_or_stale_quotes():
    kwargs = dict(ask=1.005, reference_lower=1, reference_available_at="2026-09-30T10:00:00+08:00",
                  quote_at="2026-09-30T09:59:50+08:00", decision_at="2026-09-30T10:00:00+08:00",
                  reference_verified=True)
    assert premium_buy_decision(**kwargs)[0]
    kwargs["reference_available_at"] = "2026-09-30T10:00:01+08:00"
    assert premium_buy_decision(**kwargs) == (False, "future_information")
    kwargs["reference_available_at"] = None
    assert premium_buy_decision(**kwargs) == (False, "reference_unverified")
    kwargs["reference_available_at"] = "2026-09-30T09:00:00+08:00"
    kwargs["quote_at"] = "2026-09-30T09:00:00+08:00"
    assert premium_buy_decision(**kwargs) == (False, "stale_quote")


def test_gate_warning_and_conservative_reference_bound():
    kwargs = dict(ask=1.02, reference_lower=1, reference_available_at="2026-09-30T09:00:00+08:00",
                  quote_at="2026-09-30T10:00:00+08:00", decision_at="2026-09-30T10:00:00+08:00",
                  reference_verified=True)
    assert premium_buy_decision(**kwargs) == (False, "premium_over_cap")
    kwargs["issuer_warning"] = True
    assert premium_buy_decision(**kwargs) == (False, "issuer_warning")


def test_cash_dividend_is_receivable_until_payment_and_does_not_create_profit():
    dates = pd.date_range("2026-01-16", periods=4)
    prices = pd.DataFrame({"asset": [10, 9, 9, 9]}, index=dates)
    targets = pd.DataFrame({"asset": 1.0}, index=dates)
    daily, _ = replay_lot_account(prices, prices, targets, {dates[0]}, {dates[0]: 1000},
                                  dividend={"column": 0, "ex_date": dates[1], "pay_date": dates[3], "per_share": 1},
                                  commission=0)
    assert daily.receivable.iloc[1] == 100
    assert daily.cash.iloc[1] == 0
    assert daily.cash.iloc[3] == 100
    assert np.allclose(daily.wealth, 1000)
    assert np.allclose(daily.unit_nav, 1)


def test_constant_premium_is_invisible_to_return_volatility_but_can_collapse():
    nav = np.array([100, 101, 100.5, 101.2, 102])
    assert np.allclose(np.diff(nav)/nav[:-1], np.diff(nav*1.2)/(nav*1.2)[:-1])
    assert abs(premium_shock(0, .2, 0)+1/6) < 1e-12
    assert abs(premium_shock(-.3, .2, 0)+5/12) < 1e-12


def test_repeated_monthly_flows_do_not_redistribute_blocked_asset_budget():
    q=np.zeros(2);cash=np.zeros(2);fees=0
    for _ in range(3):
        q,cash,paid=earmarked_monthly_buys(q,cash,1000,[.5,.5],[1,1],[False,True])
        fees+=paid.sum()
    assert cash[0]==1500
    assert q[0]==0
    assert q[1]==1400
    assert abs(q.sum()+cash.sum()+fees-3000)<1e-8
    q,cash,paid=earmarked_monthly_buys(q,cash,0,[.5,.5],[1,1],[True,True])
    assert q[0]==1400
    assert cash[0]>=0
