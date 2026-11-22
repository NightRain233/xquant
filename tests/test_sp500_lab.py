"""Unit tests for src/xquant/sp500_lab.py shared engine, metrics, DCA, and data loaders."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from xquant import overlay_rules as ov
from xquant import sp500_lab as lab


def test_multi_asset_engine_matches_overlay_rules_exactly():
    """2-asset run_multi_asset_overlay must reproduce overlay_rules.run_overlay to 1e-12."""
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2020-01-02", periods=120)
    a = pd.Series(100.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.012, len(dates)))), index=dates)
    b = pd.Series(50.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.006, len(dates)))), index=dates)
    prices = pd.DataFrame({"a": a, "b": b}, index=dates)
    cash_pos, cash_neg = ov.calendar_cash_factors(dates, np.full(len(dates), 0.03), 0.015)

    def sig(i, w_now):
        if i == 10:
            return np.array([1.0, 0.0])
        if i == 30:
            return np.array([0.5, 0.5])
        if i == 60:
            return np.array([0.0, 0.0])
        if i == 90:
            return np.array([0.7, 0.2])
        return None

    r_old = ov.run_overlay(prices, sig, start_i=10, cost=0.001, cash_pos=cash_pos, cash_neg=cash_neg)
    r_new = lab.run_multi_asset_overlay(prices, sig, start_i=10, cost=0.001, cash_pos=cash_pos, cash_neg=cash_neg)

    np.testing.assert_allclose(r_new.nav.to_numpy(), r_old.nav.to_numpy(), rtol=0, atol=1e-12)
    np.testing.assert_allclose(r_new.weights[["a", "b"]].to_numpy(), r_old.weights[["a", "b"]].to_numpy(), rtol=0, atol=1e-12)
    assert len(r_new.trades) == len(r_old.trades)
    assert r_new.checks["max_cash_residual"] < 1e-12


def test_no_lookahead_next_close_execution():
    """Signal at close t must not capture day t's return; fill occurs at close t+1."""
    dates = pd.bdate_range("2022-01-03", periods=5)
    prices = pd.DataFrame({"spy": [100.0, 200.0, 220.0, 220.0, 220.0]}, index=dates)
    cash_pos = np.ones(len(dates))

    # Signal emitted at i=0 (close 100), fills at i=1 (close 200), so it only captures 200 -> 220 (+10%)
    res = lab.run_multi_asset_overlay(
        prices,
        lambda i, _w: np.array([1.0]) if i == 0 else None,
        start_i=0,
        cost=0.0,
        cash_pos=cash_pos,
    )
    assert pytest.approx(res.nav.iloc[1], rel=1e-12) == 1.0
    assert pytest.approx(res.nav.iloc[2], rel=1e-12) == 1.1


def test_extra_daily_drag_reduces_return_smoothly():
    dates = pd.bdate_range("2020-01-02", periods=253)
    prices = pd.DataFrame({"spy": np.full(len(dates), 100.0)}, index=dates)
    cash_pos = np.ones(len(dates))
    sig = lambda i, _w: np.array([1.0]) if i == 0 else None
    res_no = lab.run_multi_asset_overlay(prices, sig, 0, 0.0, cash_pos)
    res_drag = lab.run_multi_asset_overlay(prices, sig, 0, 0.0, cash_pos, extra_daily_drag={"spy": 0.015})
    assert pytest.approx(res_no.nav.iloc[-1], rel=1e-12) == 1.0
    # Over ~1 calendar year, 1.5% annual drag leaves ~0.985
    assert 0.980 < res_drag.nav.iloc[-1] < 0.990


def test_three_asset_weights_and_dca_metrics():
    dates = pd.bdate_range("2015-01-02", periods=1500)
    t = np.arange(len(dates))
    prices = pd.DataFrame(
        {
            "spy": 100.0 * (1.0 + 0.0003) ** t,
            "gold": 100.0 * (1.0 + 0.0002) ** t,
            "ief": 100.0 * (1.0 + 0.0001) ** t,
        },
        index=dates,
    )
    cash_pos, cash_neg = ov.calendar_cash_factors(dates, np.full(len(dates), 0.02), 0.015)
    sig = lab.fixed_weight_signal([0.6, 0.25, 0.15], dates, 0, freq="Q")
    res = lab.run_multi_asset_overlay(prices, sig, 0, 0.001, cash_pos, cash_neg)
    assert res.checks["max_cash_residual"] < 1e-12
    assert res.checks["nav_min"] > 0
    m = lab.summarize_result(res, primary_col="spy")
    assert m["cagr"] > 0.03
    assert abs(m["avg_w_spy"] - 0.6) < 0.05
    dca_full = lab.dca_full_path(res.nav, cost=0.001)
    assert dca_full["xirr"] > 0.03
    w = lab.dca_rolling_windows(res.nav, window_months=36, cost=0.001)
    assert len(w) > 10


def test_weekly_stage2_state_returns_strict_bool_dtype():
    dates = pd.bdate_range("2020-01-02", periods=300)
    close = pd.Series(np.linspace(100.0, 150.0, len(dates)), index=dates)
    st = lab.weekly_stage2_state(close, ma_weeks=10, slope_weeks=2)
    assert st.dtype == np.dtype("bool")
    assert (~st).dtype == np.dtype("bool")
    assert int((~st).sum()) < len(st)


def test_reconcile_fast_dca_matches_lab_dca_rolling_windows():
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "scripts" / "reconcile_sp500_four_directions_2026_11_22.py"
    spec = importlib.util.spec_from_file_location("reconcile_sp500", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2018-01-02", periods=1100)
    nav = pd.Series(np.exp(np.cumsum(rng.normal(0.0004, 0.01, len(dates)))), index=dates)
    slow = lab.dca_rolling_windows(nav, window_months=36, cost=0.001)
    fast = mod.fast_dca_rolling_windows(nav, window_months=36, cost=0.001)
    assert list(fast["start"]) == list(slow["start"])
    assert list(fast["end"]) == list(slow["end"])
    np.testing.assert_allclose(fast["xirr"].to_numpy(), slow["xirr"].to_numpy(), rtol=0, atol=1e-6)
    np.testing.assert_allclose(fast["dca_ratio"].to_numpy(), slow["dca_ratio"].to_numpy(), rtol=0, atol=1e-6)


def test_daily_buffered_mtf3_hysteresis_and_no_lookahead():
    dates = pd.bdate_range("2020-01-02", periods=300)
    # Build steady uptrend then gentle dip inside deadband (-1.5%) then sharp drop (-8%)
    px = np.linspace(100.0, 150.0, 260).tolist() + [144.0] * 10 + [120.0] * 30
    close = pd.Series(px, index=dates)

    s_fast = lab.daily_buffered_stage_state(close, ma_days=50, slope_days=10, buffer=0.03)
    s_slow = lab.daily_buffered_ma_state(close, ma_days=80, buffer=0.03)
    w = lab.daily_buffered_mtf3_equity_weight(close, ma_fast=50, slope_days=10, ma_slow=80, buffer=0.03)

    assert s_fast.dtype == np.dtype("bool")
    assert s_slow.dtype == np.dtype("bool")
    assert set(w.unique()).issubset({0.0, 0.5, 1.0})
    # Uptrend should be ON (1.0), slight dip stays ON inside deadband, sharp drop turns OFF (0.0)
    assert w.iloc[255] == 1.0
    assert w.iloc[265] == 1.0
    assert w.iloc[-1] == 0.0

    # Strict anti-lookahead: mutating future prices after idx=200 must not change any state <= 200
    perturbed = close.copy()
    perturbed.iloc[201:] *= 0.25
    w_pert = lab.daily_buffered_mtf3_equity_weight(perturbed, ma_fast=50, slope_days=10, ma_slow=80, buffer=0.03)
    np.testing.assert_array_equal(w.iloc[:201].to_numpy(), w_pert.iloc[:201].to_numpy())


def test_map_us_series_to_cn_strict_prevents_same_day_leakage():
    us_dates = pd.DatetimeIndex(["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19"])
    us_sig = pd.Series([1.0, 0.5, 0.0, 1.0], index=us_dates)
    cn_dates = pd.DatetimeIndex(["2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20"])
    mapped, min_lag = lab.map_us_series_to_cn_strict(us_sig, cn_dates)
    assert min_lag == 1
    assert mapped.tolist() == [1.0, 0.5, 0.0, 1.0]


def test_daily_buffered_st_ma_weight_tiers_and_no_lookahead():
    idx = pd.date_range("2022-01-01", periods=320, freq="D")
    px = np.concatenate([
        np.full(100, 100.0),
        np.linspace(100.0, 180.0, 120),
        np.linspace(180.0, 145.0, 20),
        np.linspace(145.0, 80.0, 80),
    ])
    close = pd.Series(px, index=idx)
    high = close * 1.02
    low = close * 0.98
    w = lab.daily_buffered_st_ma_weight(high, low, close, atr_window=10, multiplier=3.0, ma_days=100, buffer=0.05)
    assert set(w.unique()).issubset({0.0, 0.5, 1.0})
    assert w.iloc[210] == 1.0
    assert w.iloc[-1] == 0.0
    # Strict anti-lookahead perturbation check
    pert_c = close.copy()
    pert_c.iloc[215:] *= 0.3
    w_pert = lab.daily_buffered_st_ma_weight(
        pert_c * 1.02, pert_c * 0.98, pert_c, atr_window=10, multiplier=3.0, ma_days=100, buffer=0.05
    )
    np.testing.assert_array_equal(w.iloc[:215].to_numpy(), w_pert.iloc[:215].to_numpy())


def test_daily_buffered_vol_throttle_hysteresis_and_no_lookahead():
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2020-01-02", periods=220)
    rets = np.concatenate([
        rng.normal(0.0, 0.004, 80),   # ~6% ann vol -> calm (1.0)
        rng.normal(0.0, 0.011, 60),   # ~17% ann vol -> mid (0.6)
        rng.normal(0.0, 0.025, 80),   # ~40% ann vol -> panic (0.2)
    ])
    close = pd.Series(100.0 * np.cumprod(1.0 + rets), index=idx)
    w = lab.daily_buffered_vol_throttle(
        close, vol_window=21, low_vol=0.14, high_vol=0.22, hysteresis=0.02, mid_weight=0.6, high_weight=0.2
    )
    assert set(w.unique()).issubset({0.2, 0.6, 1.0})
    assert w.iloc[70] == 1.0
    assert w.iloc[-1] == 0.2
    pert = close.copy()
    pert.iloc[120:] *= 2.0
    w_pert = lab.daily_buffered_vol_throttle(
        pert, vol_window=21, low_vol=0.14, high_vol=0.22, hysteresis=0.02, mid_weight=0.6, high_weight=0.2
    )
    np.testing.assert_array_equal(w.iloc[:120].to_numpy(), w_pert.iloc[:120].to_numpy())
