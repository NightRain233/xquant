import numpy as np
import pandas as pd
import pytest

from xquant import overlay_rules as ov
from xquant import position_rules as pr
from xquant import style_combo as sc


def synthetic(n=900, seed=1):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2010-01-01", periods=n)
    spy = pd.Series(100 * np.cumprod(1 + rng.normal(0.0004, 0.012, n)), index=dates)
    bond = pd.Series(100 * np.cumprod(1 + rng.normal(0.0002, 0.004, n)), index=dates)
    pos, neg = ov.calendar_cash_factors(dates, np.full(n, 0.02), 0.015)
    unrate = pd.Series(rng.uniform(3, 6, 96), index=pd.period_range("2007-01", periods=96, freq="M"))
    return ov.MarketData(dates=dates, spy=spy, bond=bond, cash_pos=pos, cash_neg=neg, unrate=unrate)


def monthly_series(values, start="2000-01-03"):
    """Flat price within each month: month k has price values[k]."""
    dates = pd.bdate_range(start, periods=len(values) * 21)
    months = dates.to_period("M")
    first = pd.Index(sorted(set(months)))
    return pd.Series([float(values[first.get_loc(p)]) for p in months], index=dates)


def test_month_end_mask_marks_last_day_of_each_month():
    dates = pd.DatetimeIndex(["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-29", "2024-03-01"])
    assert ov.month_end_mask(dates).tolist() == [False, True, False, True, False]


def test_sma_month_end_state_turns_off_below_ten_month_mean():
    close = monthly_series(list(np.linspace(100, 200, 12)) + [60] * 3)
    state = ov.sma_month_end_state(close, months=10)
    dates = close.index
    me = ov.month_end_mask(dates)
    idx = np.flatnonzero(me)
    assert state[idx[9]] == 1.0          # 10th month end: rising path above its mean
    assert state[idx[-1]] == 0.0         # after the drop below the mean
    assert state[0] == 0.0               # no decision before the first month end
    assert (state[idx[9] + 1: idx[10] + 1] == state[idx[9]]).all()  # held between month ends


def test_absolute_momentum_on_when_stock_beats_bills():
    dates = pd.bdate_range("2019-01-01", periods=400)
    spy = pd.Series(np.linspace(100, 150, len(dates)), index=dates)
    cash_index = pd.Series(np.cumprod(np.full(len(dates), 1 + 0.02 / 365)), index=dates)
    state = ov.absolute_momentum_state(spy, cash_index, months=12)
    assert state[-1] == 1.0
    down = pd.Series(np.linspace(150, 100, len(dates)), index=dates)
    assert ov.absolute_momentum_state(down, cash_index, months=12)[-1] == 0.0


def test_gtt_needs_both_conditions_to_leave_equity():
    dates = pd.bdate_range("2000-01-03", periods=24 * 21)
    rising = pd.Series(np.linspace(100, 200, len(dates)), index=dates)
    falling = pd.Series(np.linspace(200, 100, len(dates)), index=dates)
    # unemployment: flat 4% for 12 months, then 9% in the 13th month
    periods = pd.period_range("1999-01", periods=40, freq="M")
    unrate = pd.Series(np.r_[np.full(30, 4.0), np.full(10, 9.0)], index=periods)
    state_falling = ov.gtt_state(falling, unrate, months=10)
    state_rising = ov.gtt_state(rising, unrate, months=10)
    last = len(dates) - 1
    assert state_falling[last] == 0.0           # below SMA and unemployment trend bad
    assert (state_rising == 1.0).all()          # above SMA: never out


def test_gtt_uses_unemployment_only_after_publication_lag():
    dates = pd.bdate_range("2000-01-03", periods=24 * 21)
    falling = pd.Series(np.linspace(200, 100, len(dates)), index=dates)
    periods = pd.period_range("1999-01", periods=40, freq="M")
    values = np.r_[np.full(24, 4.0), np.full(16, 9.0)]  # jumps in 2001-01 (period 24)
    unrate = pd.Series(values, index=periods)
    state = ov.gtt_state(falling, unrate, months=10)
    jump_month = pd.Period("2001-01", "M")
    month_end_dates = dates[ov.month_end_mask(dates)]
    at_jump_end = [d for d in month_end_dates if d.to_period("M") == jump_month][0]
    after_jump_end = [d for d in month_end_dates if d.to_period("M") == jump_month + 1][0]
    assert state[dates.get_loc(at_jump_end)] == 1.0    # UNRATE of 2001-01 is not yet published
    assert state[dates.get_loc(after_jump_end)] == 0.0


def test_vol_target_weight_uses_realized_vol_and_cap():
    rng = np.random.default_rng(3)
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 120))), index=pd.bdate_range("2015-01-01", periods=120))
    sig = ov.vol_target_band(close, start_i=60, target=0.15, cap=1.5, window=21, band=0.0)
    out = sig(60, np.array([0.0, 0.0]))
    log_ret = np.log(close).diff().to_numpy()
    vol = np.std(log_ret[60 - 20: 61], ddof=1) * np.sqrt(252)
    assert out[0] == pytest.approx(min(1.5, 0.15 / vol))
    assert out[1] == 0.0


def test_vol_target_band_blocks_small_changes():
    close = pd.Series(100 * np.cumprod(1 + np.resize([0.01, -0.01], 120)), index=pd.bdate_range("2015-01-01", periods=120))
    sig = ov.vol_target_band(close, start_i=60, target=0.15, cap=1.0, window=21, band=0.10)
    first = sig(60, np.array([0.0, 0.0]))
    assert first is not None
    # actual weight equal to the wanted weight: no order
    assert sig(61, np.array([first[0], 0.0])) is None


def test_tom_holds_last_day_and_first_three_days_only():
    dates = pd.bdate_range("2024-01-01", periods=60)
    captured = ov.captured_mask(dates, last_n=1, first_n=3)
    held = ov.held_by_date(dates, captured)
    month = dates.to_period("M")
    last_jan = dates[month == pd.Period("2024-01")][-1]
    days_jan = dates[month == pd.Period("2024-01")]
    pen = days_jan[-2]
    feb = dates[month == pd.Period("2024-02")]
    assert held[pen] and held[last_jan]
    assert held[feb[0]] and held[feb[1]]      # first three days' returns are earned
    assert not held[feb[2]]                   # sold at the close of the 3rd trading day
    assert not held[days_jan[-3]]


def test_hal_holds_november_to_april():
    dates = pd.bdate_range("2023-10-02", periods=160)
    held = ov.held_by_date(dates, ov.captured_mask(dates, months=(11, 12, 1, 2, 3, 4)))
    oct_last = dates[dates.to_period("M") == pd.Period("2023-10")][-1]
    apr_last = dates[dates.to_period("M") == pd.Period("2024-04")][-1]
    may_first = dates[dates.to_period("M") == pd.Period("2024-05")][0]
    assert held[oct_last]
    assert not held[apr_last]
    assert not held[may_first]


def test_rsi2_enters_on_dip_in_uptrend_and_exits_above_five_day_mean():
    dates = pd.bdate_range("2015-01-01", periods=261)
    close = pd.Series(np.r_[np.linspace(100, 200, 257), 180.0, 170.0, 160.0, 240.0], index=dates)
    sig = ov.rsi2_signal(close, start_i=210, entry_below=10.0)
    decided = [sig(i, np.array([0.0, 0.0])) for i in range(210, len(dates))]
    weights = [o[0] for o in decided if o is not None]
    first_entry = weights.index(1.0)              # dip in an uptrend: RSI(2) < 10 and close > 200-day mean
    assert 0.0 in weights[first_entry + 1:]       # rebound above the 5-day mean: exit


def test_wilder_rsi_bounds():
    rng = np.random.default_rng(5)
    close = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, 300)))
    rsi = ov.wilder_rsi(close, 2)
    finite = rsi[~np.isnan(rsi)]
    assert ((finite >= 0) & (finite <= 100)).all()


def test_engine_fills_at_next_close_and_matches_run_backtest():
    data = synthetic(400)
    start = 260
    prices = pd.DataFrame({"a": data.spy, "b": data.spy})
    sig_ref = pr.rule_trend_leverage(data.spy, start)
    ref = sc.run_backtest(prices, sig_ref, start, 0.001, pd.Series(0.02, index=data.dates), 0.015)
    res = ov.simulate(data, "S1", data.dates[start], cost=0.001)
    assert np.max(np.abs(res.nav.to_numpy() - ref.nav.to_numpy())) < 1e-10
    # the initial purchase executes one close after the signal
    assert res.trades.iloc[0]["exec_date"] == data.dates[start + 1]


def test_fixed_weight_rebalances_monthly_only():
    data = synthetic(900)
    res = ov.simulate(data, "FIXED", data.dates[260], cost=0.001, weight=0.6)
    assert res.weights["a"].iloc[-1] == pytest.approx(0.6, abs=0.05)
    assert ov.count_trades(res) >= 20  # roughly one rebalance per month over ~29 months


RULES_WITH_OPTIONS = [("B0", {}), ("S2", {}), ("S1", {}), ("F10", {"months": 10}), ("DM", {"months": 12}),
                      ("DM_IEF", {"months": 12}), ("GTT", {"months": 10}), ("VT", {"target": 0.15, "window": 21}),
                      ("VT15", {"target": 0.15, "window": 21}), ("F10xVT", {"months": 10, "target": 0.15, "window": 21}),
                      ("TOM", {"last_n": 1, "first_n": 3}), ("HAL", {}), ("RSI2", {"entry_below": 10.0})]


@pytest.mark.parametrize("rule,params", RULES_WITH_OPTIONS)
def test_no_lookahead_weights_match_truncated_data(rule, params):
    """Weights on every date <= T from data truncated at T equal the weights from the full data.

    The trading calendar is passed in full (it is known in advance); prices, cash and UNRATE are truncated.
    """
    full = synthetic(900, seed=7)
    start = 300
    full_res = ov.simulate(full, rule, full.dates[start], cost=0.001, **params)
    for k in (330, 520, 700):
        t = full.dates[k]
        cut = ov.MarketData(
            dates=full.dates[: k + 1], spy=full.spy.iloc[: k + 1], bond=full.bond.iloc[: k + 1],
            cash_pos=full.cash_pos[: k + 1], cash_neg=full.cash_neg[: k + 1],
            unrate=full.unrate[full.unrate.index <= t.to_period("M")], calendar=full.dates)
        cut_res = ov.simulate(cut, rule, full.dates[start], cost=0.001, **params)
        a = full_res.weights.loc[:t]
        b = cut_res.weights.loc[:t]
        assert a.index.equals(b.index)
        assert np.allclose(a.to_numpy(), b.to_numpy(), atol=1e-12), (rule, t)


def test_dca_constant_nav_has_no_loss_beyond_fee():
    dates = pd.bdate_range("2001-01-01", periods=24 * 22)
    nav = pd.Series(1.0, index=dates)
    contrib = ov.contribution_dates(dates, "2001-01-01", dates[-1])
    account = ov.dca_account(nav, contrib, dates[-1], fee=0.001)
    assert account["terminal_per_contributed"] == pytest.approx(0.999, rel=1e-9)
    assert account["max_float_loss"] == pytest.approx(-0.001, abs=1e-9)
    assert account["unit_max_dd"] == pytest.approx(0.0, abs=1e-12)


def test_ten_year_window_needs_complete_months():
    dates = pd.bdate_range("2000-01-03", "2026-10-16")
    win = ov.ten_year_window(dates, pd.Timestamp("2000-01-03"))
    contrib, end = win
    assert len(contrib) == 120
    assert end.to_period("M") == pd.Period("2009-12")
    assert ov.ten_year_window(dates, pd.Timestamp("2016-11-01")) is None
    assert ov.ten_year_window(dates, pd.Timestamp("2016-10-03")) is not None


def test_sd1_flat_market_invests_eighty_percent_and_keeps_reserve():
    dates = pd.bdate_range("2001-01-01", periods=24 * 22)
    spy = pd.Series(100.0, index=dates)
    cash_pos = pd.Series(1.0, index=dates)
    contrib = ov.contribution_dates(dates, "2001-01-01", dates[-1])
    out = ov.sd1_account(spy, cash_pos, contrib, dates[-1], fee=0.0)
    n = len(contrib)
    assert out["terminal_value"] == pytest.approx(n * 1.0, rel=1e-9)  # 0.8 invested + 0.2 reserve per month, flat price
    assert out["final_reserve"] == pytest.approx(0.2 * n, rel=1e-9)


def test_synthetic_bond_return_formula():
    y = pd.Series([4.0, 4.5, 4.2])  # percent
    r = ov.synthetic_bond_returns(y)
    assert r.iloc[1] == pytest.approx(4.0 / 100 / 252 - 7.5 * (0.5 / 100), rel=1e-12)
    assert r.iloc[0] == 0.0


def test_gtt_skips_unpublished_unemployment_months():
    dates = pd.bdate_range("2000-01-03", periods=24 * 21)
    falling = pd.Series(np.linspace(200, 100, len(dates)), index=dates)
    periods = pd.period_range("1999-01", periods=40, freq="M")
    values = np.r_[np.full(24, 4.0), np.full(16, 9.0)]
    unrate = pd.Series(values, index=periods).drop(pd.Period("2001-02", "M"))  # one unpublished month
    state = ov.gtt_state(falling, unrate, months=10)
    month_end_dates = dates[ov.month_end_mask(dates)]
    march_end = [d for d in month_end_dates if d.to_period("M") == pd.Period("2001-03", "M")][0]
    # at March 2001 month-end: latest published is 2001-01 (9%), mean of latest 12 published values > 4%: out
    assert state[dates.get_loc(march_end)] == 0.0
