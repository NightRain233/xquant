import numpy as np
import pandas as pd

from xquant.cashflow_research import (PreparedDcaMarket, account_summary, principal_loss_events,
                                     replay_dca, solve_rebalance, xirr)


def market(prices, deposits=(0, 2), visible=(1, 3)):
    n = len(prices)
    values = np.repeat(np.asarray(prices, float)[:, None], 3, axis=1)
    return PreparedDcaMarket(pd.date_range("2020-01-01", periods=n), values, values,
                             np.tile([1/3]*3, (n, 1)), np.tile([.5, .5], (n, 1)),
                             np.zeros(n, bool), np.asarray(prices, float), np.array(deposits),
                             np.array(visible), np.array([prices[0], prices[2]], float), ["a", "b"])


def test_new_money_does_not_manufacture_unit_returns_or_fix_dollar_loss():
    data = market([100, 80, 80, 80])
    daily, _ = replay_dca(data, "Three", contribution=100, fee_bps=0)
    np.testing.assert_allclose(daily.wealth, [100, 80, 180, 180])
    np.testing.assert_allclose(daily.unit_nav, [1, .8, .8, .8])
    np.testing.assert_allclose(daily.profit.iloc[1:3], [-20, -20])
    assert np.isclose(daily.profit_ratio.iloc[2], -.1)
    assert daily.account_residual.abs().max() < 1e-10


def test_foreign_open_cannot_change_earlier_account_or_spend_future_contribution():
    data = market([100, 100, 100, 100])
    daily, _ = replay_dca(data, "SP500", contribution=100, fee_bps=0)
    assert daily.wealth.iloc[0] == 100  # Cash before the later US opening.
    shocked = market([100, 100, 100, 100])
    shocked.spy_entry_cny[0] = 1000
    changed, _ = replay_dca(shocked, "SP500", contribution=100, fee_bps=0)
    assert changed.wealth.iloc[0] == daily.wealth.iloc[0]
    assert changed.wealth.iloc[1] == 10
    assert changed.wealth.iloc[2] == 110


def test_rebalance_and_subscription_fees_conserve_cash_and_quantity():
    target = np.array([.2, .8])
    old = np.array([80., 20.])
    new, fee = solve_rebalance(old, 100, target, .001)
    np.testing.assert_allclose(new.sum()+fee, 200, atol=1e-8)
    np.testing.assert_allclose(fee, np.abs(new-old).sum()*.001, atol=1e-8)
    data = market([100, 120, 80, 100])
    data.rebalance[2] = True
    daily, trades = replay_dca(data, "Three", contribution=100, fee_bps=10)
    assert daily.account_residual.abs().max() < 1e-10
    assert np.isclose(trades.cost_cny.sum(), daily.cost.sum())
    assert daily.liquidation_wealth.iloc[-1] < daily.wealth.iloc[-1]


def test_money_weighted_return_matches_known_cashflows():
    dates = pd.to_datetime(["2019-01-01", "2020-01-01"])
    contribution = pd.Series([100., 0.], index=dates)
    value = 100*1.10**(365/365.25)
    assert np.isclose(xirr(contribution, value, dates[-1]), .10)


def test_principal_loss_recovery_censors_unrecovered_account():
    daily = pd.DataFrame({"profit": [-1., -10., 1., -3.], "profit_ratio": [-.01, -.1, .01, -.03]},
                         index=pd.date_range("2020-01-01", periods=4))
    events = principal_loss_events(daily)
    assert events.censored.tolist() == [False, True]
    assert events.calendar_days.tolist() == [2, 0]
    assert pd.isna(events.recovery.iloc[-1])


def test_stopping_contributions_keeps_the_existing_market_risk():
    data = market([100, 90, 80, 70])
    stopped, _ = replay_dca(data, "Two", contribution=100, stop_after=1, fee_bps=0)
    continued, _ = replay_dca(data, "Two", contribution=100, fee_bps=0)
    assert stopped.principal.iloc[-1] == 100
    assert continued.principal.iloc[-1] == 200
    np.testing.assert_allclose(stopped.unit_nav, continued.unit_nav)
    assert np.isclose(stopped.profit.iloc[-1], -30)
    assert np.isclose(continued.profit.iloc[-1], -42.5)


def test_amount_scaling_does_not_change_returns_or_recovery_without_minimum_fees():
    data = market([100, 80, 120, 100])
    small, _ = replay_dca(data, "Three", contribution=100, fee_bps=10)
    large, _ = replay_dca(data, "Three", contribution=10000, fee_bps=10)
    np.testing.assert_allclose(large.wealth, small.wealth*100)
    np.testing.assert_allclose(large.profit_ratio, small.profit_ratio)
    np.testing.assert_allclose(large.unit_nav, small.unit_nav)
