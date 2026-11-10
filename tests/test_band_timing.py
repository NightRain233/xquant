import numpy as np
import pandas as pd
import pytest

from xquant import band_timing as bt
from xquant import style_combo as sc


def make_close(n=600, seed=0, drift=0.0003, vol=0.01):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2018-01-01", periods=n)
    return pd.Series(100 * np.cumprod(1 + rng.normal(drift, vol, n)), index=idx, name="close")


def levels_frame(dates, close, upper=110.0, mid=100.0, lower=90.0):
    return pd.DataFrame({"close": close, "mid": mid, "upper": upper, "lower": lower}, index=dates)


def run_signal(sig, n, start=0):
    return [sig(i) for i in range(start, n)]


def test_weekly_bands_match_hand_calculation():
    close = make_close(60)
    levels = bt.weekly_band_levels(close, window=5, k=2.0)
    weekly = close.groupby(close.index.to_period("W-SUN")).last()
    sample = weekly.iloc[:5].to_numpy()
    first = levels.iloc[0]
    assert first["mid"] == pytest.approx(sample.mean())
    assert first["upper"] == pytest.approx(sample.mean() + 2 * sample.std(ddof=0))
    assert first["lower"] == pytest.approx(sample.mean() - 2 * sample.std(ddof=0))
    assert levels.index[0].weekday() == 4  # business-day calendar: week ends on Friday


def test_weekly_bands_do_not_change_when_future_is_removed():
    close = make_close()
    full = bt.weekly_band_levels(close)
    cut = bt.weekly_band_levels(close.iloc[:400])
    common = full.index.intersection(cut.index)
    assert len(common) > 40
    pd.testing.assert_frame_equal(full.loc[common], cut.loc[common])


def test_daily_bands_do_not_change_when_future_is_removed_and_match_weekly_at_week_end():
    close = make_close()
    full = bt.daily_band_levels(close)
    cut = bt.daily_band_levels(close.iloc[:400])
    pd.testing.assert_frame_equal(full.loc[cut.index], cut)
    weekly = bt.weekly_band_levels(close)
    common = weekly.index[:-1].intersection(full.index)
    assert np.allclose(full.loc[common, ["mid", "upper", "lower"]], weekly.loc[common, ["mid", "upper", "lower"]])


def test_band_zone_boundaries():
    assert bt.band_zone(91.0, 110.0, 90.0, 0.02) == "lower"
    assert bt.band_zone(108.0, 110.0, 90.0, 0.02) == "upper"
    assert bt.band_zone(100.0, 110.0, 90.0, 0.02) is None
    assert bt.band_zone(100.0, 101.0, 99.0, 0.02) == "both"


def test_all_in_out_holds_position_between_bands():
    dates = pd.bdate_range("2020-01-01", periods=5)
    levels = levels_frame(dates, [100.0, 89.0, 100.0, 111.0, 100.0])
    out = run_signal(bt.rule_all_in_out(levels, dates, 0), 5)
    assert [o["a"] if o else None for o in out] == [0.0, 1.0, None, 0.0, None]


def test_all_in_out_ignores_tight_bands_and_can_start_held():
    dates = pd.bdate_range("2020-01-01", periods=2)
    levels = levels_frame(dates, [100.0, 100.0], upper=100.5, mid=100.0, lower=99.5)
    out = run_signal(bt.rule_all_in_out(levels, dates, 0, start_held=True), 2)
    assert [o["a"] if o else None for o in out] == [1.0, None]


def test_core_tilt_returns_to_base_at_middle_band():
    dates = pd.bdate_range("2020-01-01", periods=7)
    levels = levels_frame(dates, [100.0, 89.0, 95.0, 101.0, 111.0, 105.0, 99.0])
    out = run_signal(bt.rule_core_tilt(levels, dates, 0), 7)
    assert [o["a"] if o else None for o in out] == [0.7, 1.0, None, 0.7, 0.5, None, 0.7]


def test_trailing_yield_recovers_constant_dividend():
    idx = pd.bdate_range("2020-01-01", periods=300)
    price = pd.Series(100.0, index=idx)
    tr = pd.Series(100.0 * 1.05 ** (np.arange(300) / 252), index=idx)
    assert bt.trailing_dividend_yield(tr, price).iloc[-1] == pytest.approx(0.05)


def test_expanding_percentile_is_causal_and_needs_history():
    s = make_close(100)
    full = bt.expanding_percentile(s, min_periods=10)
    cut = bt.expanding_percentile(s.iloc[:50], min_periods=10)
    assert full.iloc[:9].isna().all()
    pd.testing.assert_series_equal(full.iloc[:50], cut)


def test_yield_tilt_weights_only_change_on_week_end():
    dates = pd.bdate_range("2020-01-06", periods=10)  # two Mon-Fri weeks
    pct = pd.Series([np.nan] * 3 + [0.9] * 3 + [0.1] * 4, index=dates)
    out = run_signal(bt.rule_yield_tilt(pct, dates, 0), 10)
    assert [o["a"] if o else None for o in out] == [0.7, None, None, None, 1.0, None, None, None, None, None]


def test_fixed_weight_rebalances_on_period_end():
    dates = pd.bdate_range("2020-03-25", periods=10)
    out = run_signal(bt.rule_fixed_weight(0.6, dates, 0), 10)
    active = [dates[i] for i, o in enumerate(out) if o]
    assert active == [dates[0], pd.Timestamp("2020-03-31")]


def test_cash_accrues_and_default_is_unchanged():
    close = make_close(400)
    prices = pd.DataFrame({"a": close, "b": close})
    flat = sc.run_backtest(prices, lambda i: None, 0, cash_annual=0.02)
    days = (close.index[-1] - close.index[0]).days
    assert flat.nav.iloc[-1] == pytest.approx(1.02 ** (days / 365))
    assert sc.run_backtest(prices, lambda i: None, 0).nav.iloc[-1] == 1.0


def test_all_in_out_executes_next_close_with_cost():
    dates = pd.bdate_range("2020-01-01", periods=4)
    close = pd.Series([100.0, 89.0, 100.0, 110.0], index=dates)
    levels = levels_frame(dates, [100.0, 89.0, 100.0, 100.0])
    prices = pd.DataFrame({"a": close, "b": close})
    res = sc.run_backtest(prices, bt.rule_all_in_out(levels, dates, 0), 0, cost=0.0)
    # signal on day 1 close (89), bought at day 2 close (100), so day 3 NAV reflects 100 -> 110 only
    assert res.nav.iloc[2] == pytest.approx(1.0)
    assert res.nav.iloc[3] == pytest.approx(1.1)


def test_placebo_scores_perfect_timing_above_every_shift():
    idx = pd.bdate_range("2020-01-01", periods=400)
    rng = np.random.default_rng(1)
    returns = pd.Series(rng.normal(0.0, 0.01, 400), index=idx)
    perfect = pd.Series((returns.shift(-1) > 0).astype(float).to_numpy(), index=idx)
    out = bt.timing_placebo(perfect, returns, cash_annual=0.0)
    assert out["share_placebo_ge_actual"] == 0.0
    assert out["actual_annualized"] > out["placebo_p95_annualized"]
    assert out["n_shifts"] == 400 - 2 * 60 + 1


def test_placebo_constant_position_has_no_timing_effect():
    idx = pd.bdate_range("2020-01-01", periods=300)
    returns = pd.Series(np.random.default_rng(2).normal(0.0, 0.01, 300), index=idx)
    out = bt.timing_placebo(pd.Series(1.0, index=idx), returns, cash_annual=0.0)
    assert out["placebo_median_annualized"] == pytest.approx(out["actual_annualized"])
