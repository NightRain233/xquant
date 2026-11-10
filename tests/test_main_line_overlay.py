import numpy as np
import pandas as pd

from xquant import main_line_overlay as mo
from xquant import position_rules as pr


def _rise_then_fall(n_up=260, n_down=60):
    dates = pd.bdate_range("2010-01-01", periods=n_up + n_down)
    up = np.linspace(100, 220, n_up)
    down = np.linspace(220, 120, n_down)
    return pd.Series(np.r_[up, down], index=dates)


def test_multiplier_is_one_while_trend_on_and_off_after_break():
    close = _rise_then_fall()
    mult = mo.trend_multiplier(close, off=0.5)
    states = pr.stage_states(close)
    first_off_week = states[states == False].index[0]  # noqa: E712
    first_cut_day = mult[mult == 0.5].index[0]
    assert first_cut_day > first_off_week
    assert close.index.get_loc(first_cut_day) == close.index.get_loc(first_off_week) + 1
    assert (mult[: close.index.get_loc(first_cut_day)] == 1.0).all()


def test_multiplier_has_no_lookahead():
    close = _rise_then_fall()
    full = mo.trend_multiplier(close, off=0.5)
    cut_at = close.index[300]
    truncated = mo.trend_multiplier(close[:cut_at], off=0.5)
    pd.testing.assert_series_equal(full[:cut_at], truncated, check_names=False)


def test_multiplier_one_gives_no_effect_and_no_cost():
    dates = pd.bdate_range("2020-01-01", periods=30)
    weights = pd.DataFrame({"a": 0.5, "b": 0.3, "cash": 0.2}, index=dates)
    returns = pd.DataFrame({"a": 0.01, "b": -0.02}, index=dates)
    ones = pd.Series(1.0, index=dates)
    effect, traded = mo.overlay_return(weights, returns, ones, sleeve="a", cost_per_side=0.003)
    assert np.allclose(effect.fillna(0.0), 0.0)
    assert np.allclose(traded.fillna(0.0), 0.0)


def test_cut_goes_to_cash_and_costs_on_switch_day():
    dates = pd.bdate_range("2020-01-01", periods=10)
    weights = pd.DataFrame({"a": 0.4, "b": 0.6, "cash": 0.0}, index=dates)
    returns = pd.DataFrame({"a": 0.02, "b": 0.0}, index=dates)
    mult = pd.Series(1.0, index=dates)
    mult.iloc[4:] = 0.5  # executed at the close of day 4, held from day 5 onwards
    effect, traded = mo.overlay_return(weights, returns, mult, sleeve="a", cost_per_side=0.003)
    assert np.isclose(traded.iloc[4], 0.5 * 0.4)
    assert np.isclose(effect.iloc[4], -0.003 * 0.2)  # only the cost on the switch day
    assert np.isclose(effect.iloc[5], -0.5 * 0.4 * 0.02)  # the cut earns cash (0), not the sleeve's return
    assert np.isclose(effect.iloc[6], -0.5 * 0.4 * 0.02)


def test_reallocation_spreads_cut_over_other_sleeves():
    dates = pd.bdate_range("2020-01-01", periods=6)
    weights = pd.DataFrame({"a": 0.4, "b": 0.3, "c": 0.3, "cash": 0.0}, index=dates)
    returns = pd.DataFrame({"a": 0.0, "b": 0.01, "c": 0.03}, index=dates)
    mult = pd.Series(1.0, index=dates)
    mult.iloc[1:] = 0.5
    effect, _ = mo.overlay_return(weights, returns, mult, sleeve="a", cost_per_side=0.0, reallocate=True)
    cut = 0.2
    expected = cut * (0.5 * 0.01 + 0.5 * 0.03)  # cut split pro rata between b and c (equal weights here)
    assert np.isclose(effect.iloc[3], expected)
