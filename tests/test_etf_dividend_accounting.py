import numpy as np
import pandas as pd
import pytest

from xquant.etf_dividend_accounting import DividendMarket, distribution_returns, replay_dividend_account


def market(prices, targets=None, actions=None, rebalance=None):
    dates = pd.date_range("2026-01-01", periods=len(prices))
    px = np.array(prices, dtype=float).reshape(len(prices), -1)
    width = px.shape[1]
    return DividendMarket(dates, [str(i) for i in range(width)], px.copy(), px.copy(),
                          np.array(targets if targets is not None else [[1/width]*width]*len(px)),
                          np.array(rebalance if rebalance is not None else [True]*len(px)),
                          actions or [], np.array([0]))


def dividend():
    return {"symbol":"0", "announcement_date":"2025-12-20", "record_date":"2026-01-01",
            "effective_quote_date":"2026-01-02", "pay_date":"2026-01-04", "cash_per_share":1., "split_ratio":1.}


def test_ex_date_signal_is_income_not_a_mechanical_market_loss():
    px = pd.DataFrame({"0":[10.,9.,9.,9.]}, index=pd.date_range("2026-01-01", periods=4))
    returns = distribution_returns(px, pd.DataFrame([dividend()]))
    assert returns.loc["2026-01-02", "0"] == 0
    future = dict(dividend(), effective_quote_date="2026-01-04", announcement_date="2026-01-03")
    pd.testing.assert_frame_equal(returns.iloc[:3], distribution_returns(px, pd.DataFrame([dividend(),future])).iloc[:3])


def test_registered_holder_sells_on_ex_date_and_still_gets_cash():
    m = market([[10.,10.],[9.,10.],[9.,10.],[9.,10.],[9.,10.]],
               targets=[[1.,0.],[0.,1.],[0.,1.],[0.,1.],[0.,1.]], actions=[dividend()])
    daily, _, events = replay_dividend_account(m, flows={0:100.}, fee_bps=0)
    np.testing.assert_allclose(daily.wealth,100)
    assert daily.receivable.iloc[1] == 10
    assert daily.quantity_0.iloc[1] == 0
    assert daily.cash.iloc[3] == 10
    assert daily.quantity_1.iloc[3] == 9  # pay-date OPEN cannot use end-of-day cash
    assert daily.quantity_1.iloc[4] == 10
    assert events.loc[events.phase=="cash_paid_after_close", "amount"].iloc[0] == 10


def test_ex_date_new_holder_has_no_distribution_rights():
    daily, _, _ = replay_dividend_account(market([10.,9.,9.,9.],actions=[dividend()]),
                                         flows={1:90.}, start_index=1, fee_bps=0)
    assert daily.dividend_income.sum() == 0
    assert daily.receivable.max() == 0
    assert daily.wealth.iloc[-1] == 90


def test_split_changes_quantity_without_income_or_loss():
    split = {"symbol":"0","announcement_date":"2025-12-20","effective_quote_date":"2026-01-02",
             "split_ratio":5.,"cash_per_share":0.}
    m = market([10.,2.,2.2],actions=[split])
    daily, _, _ = replay_dividend_account(m, flows={0:100.},fee_bps=0)
    np.testing.assert_allclose(daily.wealth,[100.,100.,110.])
    assert daily.quantity_0.iloc[1] == 50
    r=distribution_returns(pd.DataFrame({"0":[10.,2.,2.2]},index=m.dates),pd.DataFrame([split]))
    assert r.iloc[1,0] == 0


def test_official_conversion_posts_on_halt_day_close_before_resumed_quote():
    split={"symbol":"0","announcement_date":"2025-12-20","corporate_action_date":"2026-01-02",
           "effective_quote_date":"2026-01-03","split_ratio":5.,"cash_per_share":0.}
    m=market([10.,2.,2.2],actions=[split],rebalance=[True,False,False])
    m.opening[1,0]=np.nan
    daily,_,events=replay_dividend_account(m,flows={0:100.},fee_bps=0)
    np.testing.assert_allclose(daily.wealth,[100.,100.,110.])
    np.testing.assert_allclose(daily.quantity_0,[10.,50.,50.])
    assert events.phase.iloc[0]=="split_after_close"


def test_subscription_unit_price_includes_receivable_but_cannot_spend_it():
    m=market([10.,9.,9.,9.,9.],actions=[dividend()])
    daily, trades, _=replay_dividend_account(m,flows={0:100.,2:100.},fee_bps=0)
    assert daily.pre_flow_unit_price.iloc[2] == 1
    assert daily.wealth.iloc[2] == 200
    assert daily.receivable.iloc[2] == 10
    assert trades.loc[trades.date==m.dates[2],"notional"].sum() == pytest.approx(100.)


def test_cash_reinvestment_waits_for_fixed_calendar_and_commission_conserves():
    m=market([10.,9.,9.,9.,9.,9.],actions=[dividend()],rebalance=[True,False,False,False,False,True])
    daily,trades,_=replay_dividend_account(m,flows={0:100.},fee_bps=1)
    assert daily.cash.iloc[3] > 0
    assert daily.cash.iloc[4] == daily.cash.iloc[3]
    assert daily.cash.iloc[5] == 0
    assert list(trades.date)==[m.dates[0],m.dates[5]]
    np.testing.assert_allclose(daily.account_residual,0,atol=1e-12)
    assert daily.cumulative_cost.iloc[-1] == pytest.approx(trades.commission.sum())


def test_unannounced_action_is_rejected():
    event=dict(dividend(),announcement_date="2026-01-02")
    px=pd.DataFrame({"0":[10.,9.]},index=pd.date_range("2026-01-01",periods=2))
    with pytest.raises(ValueError):distribution_returns(px,pd.DataFrame([event]))
