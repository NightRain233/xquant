import numpy as np
import pandas as pd

from xquant import style_combo as sc


def make_prices(n=400, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n)
    r = rng.normal(0.0003, [[0.01, 0.02]], size=(n, 2))
    return pd.DataFrame(100 * np.cumprod(1 + r, axis=0), index=idx, columns=["a", "b"])


def test_execution_after_signal_and_nav_identity():
    p = make_prices()
    res = sc.run_backtest(p, sc.rule_a(p.index, 150, "Q"), 150, cost=0.001)
    assert res.checks["exec_after_signal"]
    assert res.checks["max_cash_plus_holdings_residual"] < 1e-12
    assert (pd.to_datetime(res.trades["exec_date"]) > pd.to_datetime(res.trades["signal_date"])).all()
    assert res.nav.iloc[0] == 1.0  # starts in cash, nothing happens on the signal day itself


def test_zero_cost_buy_hold_matches_asset():
    p = make_prices()
    res = sc.run_backtest(p, sc.rule_buy_hold({"a": 1.0, "b": 0.0}, 100), 100, cost=0.0)
    exp = p["a"].iloc[101:] / p["a"].iloc[101]
    np.testing.assert_allclose(res.nav.iloc[1:].to_numpy(), exp.to_numpy(), rtol=1e-10)


def test_cost_reduces_nav_by_ten_bp_on_initial_buy():
    p = make_prices()
    res = sc.run_backtest(p, sc.rule_buy_hold({"a": 1.0, "b": 0.0}, 100), 100, cost=0.001)
    assert abs(res.trades["cost"].iloc[0] - 0.001 / 1.001) < 1e-9


def test_signal_ignores_future_data():
    p = make_prices()
    start = 150
    for factory in (lambda q: sc.rule_c(q, start), lambda q: sc.rule_d(q, start)):
        sig1 = factory(p)
        q = p.copy()
        q.iloc[300:] *= 3.0  # perturb the future only
        sig2 = factory(q)
        for i in range(start, 300):
            assert sig1(i) == sig2(i)


def test_inverse_vol_gives_calmer_asset_more_weight():
    p = make_prices()
    w = sc.inverse_vol_weights(p.pct_change().dropna().iloc[:60])
    assert w["a"] > w["b"] and abs(w["a"] + w["b"] - 1) < 1e-12


def test_rule_c_filter_switches_to_a_when_b_falls():
    idx = pd.bdate_range("2020-01-01", periods=300)
    b = np.r_[np.linspace(100, 200, 200), np.linspace(200, 80, 100)]
    p = pd.DataFrame({"a": 100.0, "b": b}, index=idx)
    res = sc.run_backtest(p, sc.rule_c(p, 200), 200, cost=0.0)
    assert res.weights["b"].iloc[-1] == 0.0 and res.weights["a"].iloc[-1] > 0.99


def test_rule_d_picks_stronger_asset():
    idx = pd.bdate_range("2020-01-01", periods=300)
    p = pd.DataFrame({"a": np.linspace(100, 110, 300), "b": np.linspace(100, 160, 300)}, index=idx)
    assert sc.rule_d(p, 200)(200) == {"a": 0.0, "b": 1.0}


def test_metrics_drawdown_and_recovery():
    idx = pd.bdate_range("2020-01-01", periods=5)
    nav = pd.Series([1, 1.2, 0.9, 1.0, 1.25], index=idx)
    assert abs(sc.drawdown(nav).min() + 0.25) < 1e-12
    days, ongoing = sc.longest_recovery_days(nav)
    assert days == (idx[4] - idx[1]).days and not ongoing
    ps = sc.period_stats(nav, str(idx[2].date()), str(idx[3].date()))
    assert abs(ps["return"] - (1.0 / 1.2 - 1)) < 1e-12
