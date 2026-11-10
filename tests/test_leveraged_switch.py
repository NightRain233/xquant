import numpy as np
import pandas as pd
import pytest

from xquant import leveraged_switch as ls


def _dates(n):
    return pd.bdate_range("2020-01-01", periods=n)


def test_synthetic_leveraged_triples_daily_returns_minus_costs():
    d = _dates(3)
    close = pd.Series([100.0, 110.0, 99.0], index=d)
    rate = pd.Series(0.0, index=d)
    out = ls.synthetic_leveraged(close, rate, leverage=3.0, fee=0.0, spread=0.0)
    assert out.iloc[1] == pytest.approx(1.3)
    assert out.iloc[2] == pytest.approx(1.3 * (1 - 0.3))
    costly = ls.synthetic_leveraged(close, pd.Series(0.05, index=d), fee=0.01, spread=0.005)
    days = (d[1] - d[0]).days
    assert costly.iloc[1] == pytest.approx(1 + 0.3 - (2 * 0.055 + 0.01) * days / 365)


def test_buffered_regime_keeps_state_inside_band():
    ext = pd.Series([np.nan, 0.01, 0.05, 0.0, -0.02, -0.04, 0.03, 0.04])
    assert ls.buffered_regime(ext, 0.04, 0.03).tolist() == [0, 0, 1, 1, 1, -1, -1, 1]


def test_run_switch_trades_next_close_and_charges_cost():
    d = _dates(4)
    prices = pd.DataFrame({"lev": [1.0, 1.0, 2.0, 2.0], "base": 1.0}, index=d)
    decide = lambda i, w: np.array([1.0, 0.0]) if i == 0 else None
    res = ls.run_switch(prices, pd.Series(0.0, index=d), decide, 0, np.zeros(2), cost=0.0)
    assert res.nav.tolist() == pytest.approx([1.0, 1.0, 2.0, 2.0])
    same = ls.run_switch(prices, pd.Series(0.0, index=d), decide, 0, np.zeros(2), cost=0.01, lag=0)
    assert same.nav.iloc[-1] == pytest.approx(2.0 / 1.01)


def test_forum_rule_sells_then_dollar_cost_averages_into_base():
    n = 12
    d = _dates(n)
    regime = pd.Series([1, 1] + [-1] * (n - 2), index=d)
    prices = pd.DataFrame({"lev": 1.0, "base": 1.0}, index=d)
    decide = ls.forum_rule(regime, None, dca_months=2, month_days=3)
    res = ls.run_switch(prices, pd.Series(0.0, index=d), decide, 0, np.array([1.0, 0.0]), cost=0.0)
    w = res.weights
    assert w["lev"].iloc[2] == pytest.approx(1.0)  # bear seen at close 2, sold at close 3
    assert w["lev"].iloc[3] == 0 and w["base"].iloc[3] == 0
    assert w["base"].iloc[6] == pytest.approx(0.5)  # 3 days after bear start, filled next close
    assert w["base"].iloc[9] == pytest.approx(1.0)
    assert w["base"].iloc[-1] == pytest.approx(1.0)


def test_forum_rule_protection_reduces_then_exits():
    d = _dates(3)
    regime = pd.Series(1, index=d)
    ext = pd.Series([0.1, 0.35, 0.45], index=d)
    decide = ls.forum_rule(regime, ext)
    w = np.array([1.0, 0.0])
    assert decide(0, w) is not None and decide(0, w).tolist() == [1.0, 0.0]
    assert decide(1, w).tolist() == [0.5, 0.5]
    assert decide(2, w).tolist() == [0.0, 0.0]
