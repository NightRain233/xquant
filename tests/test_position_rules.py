import numpy as np
import pandas as pd
import pytest

from xquant import position_rules as pr
from xquant import style_combo as sc


def make_close(n=600, seed=0, drift=0.0004, vol=0.01):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2018-01-01", periods=n)
    return pd.Series(100 * np.cumprod(1 + rng.normal(drift, vol, n)), index=idx)


def collect(sig, n, start=0):
    return [sig(i) for i in range(start, n)]


def test_volatility_target_weight_clips():
    assert pr.volatility_target_weight(0.24, 0.12, 0.2, 1.0) == pytest.approx(0.5)
    assert pr.volatility_target_weight(0.06, 0.12, 0.2, 1.0) == 1.0
    assert pr.volatility_target_weight(2.0, 0.12, 0.2, 1.0) == 0.2


def test_vol_target_only_acts_on_week_ends_with_big_enough_changes():
    close = make_close(200, vol=0.015)
    start = 30
    out = collect(pr.rule_vol_target(close, start), len(close) - 1, start)
    active = [(close.index[start + j], o["a"]) for j, o in enumerate(out) if o]
    assert active[0][0] == close.index[start]
    assert all(d.weekday() == 4 for d, _ in active[1:])
    for (_, a), (_, b) in zip(active, active[1:]):
        assert abs(a - b) >= 0.10


def test_vol_target_signal_does_not_change_when_future_is_removed():
    close = make_close(300)
    full = collect(pr.rule_vol_target(close, 40), 200, 40)
    cut = collect(pr.rule_vol_target(close.iloc[:201], 40), 200, 40)
    assert full == cut


def test_stage_states_need_rising_mean_to_turn_on_and_break_to_turn_off():
    idx = pd.bdate_range("2020-01-06", periods=5 * 12)
    weekly = [100.0] * 4 + [101, 102, 103, 104] + [90, 90, 90, 90]
    close = pd.Series(np.repeat(weekly, 5), index=idx, dtype=float)
    states = pr.stage_states(close, ma_weeks=3, slope_weeks=1)
    assert bool(states.iloc[0]) is False            # flat, mean not rising
    assert bool(states[pd.Timestamp("2020-02-28")]) is True   # week 8: above a rising mean
    assert bool(states.iloc[-1]) is False           # back below the mean


def test_stage_states_do_not_change_when_future_is_removed():
    close = make_close()
    full = pr.stage_states(close)
    cut = pr.stage_states(close.iloc[:400])
    common = full.index.intersection(cut.index)
    pd.testing.assert_series_equal(full.loc[common], cut.loc[common])


def test_stage_blend_switches_between_on_and_off_weights():
    dates = pd.bdate_range("2020-01-06", periods=15)
    states = pd.Series([False, True, False], index=[dates[4], dates[9], dates[14]])
    out = collect(pr.rule_stage_blend(states, dates, 4), 15, 4)
    active = [(j + 4, o["a"]) for j, o in enumerate(out) if o]
    assert active == [(4, 0.5), (9, 1.0), (14, 0.5)]


def test_trend_leverage_relevers_monthly_and_is_flat_below_mean():
    idx = pd.bdate_range("2020-01-01", periods=60)
    close = pd.Series(np.arange(100.0, 160.0), index=idx)
    out = collect(pr.rule_trend_leverage(close, 10, ma_days=5, leverage=1.5), 60, 10)
    assert out[0]["a"] == 1.5
    relevers = [idx[10 + j] for j, o in enumerate(out) if o and j > 0]
    assert all(sc.is_period_end(idx, idx.get_loc(d), "M") for d in relevers) and relevers
    falling = pd.Series(np.arange(160.0, 100.0, -1.0), index=idx)
    assert collect(pr.rule_trend_leverage(falling, 10, ma_days=5), 60, 10)[0]["a"] == 0.0


def test_borrow_pays_rate_plus_spread_and_cash_series_uses_previous_close():
    idx = pd.bdate_range("2020-01-01", periods=30)
    flat = pd.Series(100.0, index=idx)
    prices = pd.DataFrame({"a": flat, "b": flat})
    levered = sc.run_backtest(prices, lambda i: {"a": 1.5, "b": 0.0} if i == 0 else None, 0, cost=0.0,
                              cash_annual=0.03, borrow_spread=0.02)
    days = (idx[-1] - idx[1]).days
    # the first day still earns the cash rate; the position is set at that day's close
    start_value = 1.03 ** ((idx[1] - idx[0]).days / 365)
    assert levered.nav.iloc[-1] == pytest.approx(start_value * (1.5 - 0.5 * 1.05 ** (days / 365)))
    rates = pd.Series(0.0, index=idx)
    rates.iloc[5:] = 0.10
    cash = sc.run_backtest(prices, lambda i: None, 0, cost=0.0, cash_annual=rates)
    assert cash.nav.iloc[5] == 1.0                  # the rate set at close 5 only pays from day 6
    assert cash.nav.iloc[6] > 1.0
