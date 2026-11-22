"""Direction 2 Research: Trend De-risking into Safe-Haven Shields (Gold / Trend-Filtered Gold / Gold+Bond)
instead of sitting in cash when S&P 500 weekly/monthly trend turns off.

Run (offline sandbox):
    .venv/bin/python -I scripts/research_sp500_dir2_trend_shield_2026_11_22.py

All data loaders, execution engine (close t signal -> close t+1 fill), metrics, and DCA evaluators
are imported strictly from ``src/xquant/sp500_lab.py``. Rules and parameters are frozen in CONFIG
before running; sensitivity grids are strictly for robustness verification (zero parameter selection).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from xquant import overlay_rules as ov  # noqa: E402
from xquant import position_rules as pr  # noqa: E402
from xquant import sp500_lab as lab  # noqa: E402

SLUG = "sp500-dir2-trend-shield-2026-11-22"
OUT_DIR = ROOT / "outputs" / SLUG

# --------------------------------------------------------------------------- Frozen pre-run CONFIG
CONFIG: dict[str, Any] = {
    "slug": SLUG,
    "direction": "dir2_trend_shield",
    "execution_clock": "Signal decided at close t using data <= t; order filled at close t+1.",
    "us_track": {
        "main_window": {
            "name": "us_2005",
            "start": lab.US_GLD_START,  # 2005-01-03
            "end": lab.US_END,          # 2026-10-16
            "gold_source": "gld_real",
            "segments": {
                "full": [lab.US_GLD_START, lab.US_END],
                "2005-2012": [lab.US_GLD_START, "2012-12-31"],
                "2013-2026": ["2013-01-01", lab.US_END],
            },
            "note": (
                "Pure real GLD ETF (launched 2004-11-18). For trend-filtered gold rules, "
                "gld_real 30-week SMA warms up in 2005-06 (slope in 2005-07); prior to warmup, "
                "weekly_stage2_state conservatively defaults to False (cash)."
            ),
        },
        "extended_window": {
            "name": "us_2001",
            "start": lab.US_GOLD_SPLICED_START,  # 2001-01-02
            "end": lab.US_END,                   # 2026-10-16
            "gold_source": "gold_spliced",
            "segments": {
                "full": [lab.US_GOLD_SPLICED_START, lab.US_END],
                "2001-2012": [lab.US_GOLD_SPLICED_START, "2012-12-31"],
                "2013-2026": ["2013-01-01", lab.US_END],
            },
            "note": (
                "Spliced gold uses real GLD from 2004-11-18 and backward-spliced gold proxy "
                "(deducting 0.40%/yr ETF fee) from 2000-08-30; gold 30w SMA warms up in 2001-03."
            ),
        },
        "costs_one_way": [0.001, 0.003],
        "weekly_signal": {"ma_weeks": 30, "slope_weeks": 4},
        "monthly_signal": {"ma_months": 10},
        "s2_spy_weights": {"on": 1.0, "off": 0.5},
        "mtf3_spy_weights": {"both_on": 1.0, "one_on": 0.5, "both_off": 0.0},
        "strategies": [
            "B0_SPY",
            "S2_CASH",
            "S2_GOLD",
            "S2_GOLD_TREND",
            "S2_BOND_GOLD",
            "S2_BOND_GOLD_TREND",
            "MTF3_CASH",
            "MTF3_GOLD",
            "MTF3_GOLD_TREND",
        ],
        "rolling_start_years": list(range(2005, 2024)),  # 2005..2023 inclusive (19 starts)
        "key_periods": {
            "GFC_2007_2009": ["2007-10-09", "2009-03-09"],
            "COVID_2020": ["2020-02-19", "2020-03-23"],
            "RATE_HIKE_2022": ["2022-01-01", "2022-12-31"],
            "BULL_2023_2026": ["2023-01-01", lab.US_END],
        },
        "dca_rolling_months": [120],
        "sensitivity": {
            "window": "us_2005",
            "cost_one_way": 0.001,
            "strategies": ["S2_GOLD", "S2_GOLD_TREND"],
            "spy_ma_weeks_grid": [20, 30, 40],
            "spy_off_weight_grid": [0.25, 0.50, 0.75],
            "gold_ma_weeks_grid": [20, 30, 40],
        },
    },
    "domestic_track": {
        "window": {
            "start": lab.DOMESTIC_START,  # 2014-10-08
            "end": lab.DOMESTIC_END,      # 2026-09-30
            "segments": {
                "full": [lab.DOMESTIC_START, lab.DOMESTIC_END],
                "2014-2020": [lab.DOMESTIC_START, "2020-12-31"],
                "2021-2026": ["2021-01-01", lab.DOMESTIC_END],
            },
        },
        "costs_one_way": [0.001, 0.003],
        "cash_annual": 0.02,
        "weekly_signal": {"ma_weeks": 30, "slope_weeks": 4},
        "cross_market_rule": (
            "For US_SIG on China trading day d (close decision), read only the latest completed "
            "US SPY weekly stage2 state with week-end date strictly < d (zero cross-market lookahead). "
            "Domestic gold trend uses 518880_full weekly stage2 state as of China close d."
        ),
        "strategies": [
            "B0_513500",
            "CN_S2_CASH_SELF",
            "CN_S2_GOLD_SELF",
            "CN_S2_GOLD_TREND_SELF",
            "CN_S2_CASH_US",
            "CN_S2_GOLD_US",
            "CN_S2_GOLD_TREND_US",
        ],
        "dca_rolling_months": [60, 120],
        "key_periods": {
            "COVID_2020": ["2020-02-19", "2020-03-23"],
            "RATE_HIKE_2022": ["2022-01-01", "2022-12-31"],
            "BULL_2023_2026": ["2023-01-01", lab.DOMESTIC_END],
        },
    },
}


# --------------------------------------------------------------------------- Signal builders
def weekly_state_bool(close: pd.Series, ma_weeks: int = 30, slope_weeks: int = 4) -> np.ndarray:
    """Wrapper around lab.weekly_stage2_state returning strict boolean numpy array."""
    st = lab.weekly_stage2_state(close, ma_weeks=ma_weeks, slope_weeks=slope_weeks)
    return st.astype(bool).to_numpy(dtype=bool)


def monthly_state_bool(close: pd.Series, months: int = 10) -> np.ndarray:
    """Month-end close > trailing ``months`` month-end SMA, updated strictly at month-end closes."""
    arr = ov.sma_month_end_state(close, months=months)
    return (arr > 0.5).astype(bool)


def us_weekly_state_strictly_before(
    us_close: pd.Series,
    target_dates: pd.DatetimeIndex,
    ma_weeks: int = 30,
    slope_weeks: int = 4,
) -> tuple[np.ndarray, pd.Series]:
    """Map US weekly stage2 states onto China trading days ``d`` using ONLY week-end dates strictly < d.

    Returns:
        state_bool: boolean array aligned to ``target_dates``.
        source_week_dates: pd.Series of the US week-end Timestamp actually read on each day ``d``.
    """
    week_states = pr.stage_states(us_close, ma_weeks=ma_weeks, slope_weeks=slope_weeks)
    week_dates = week_states.index.to_numpy()
    week_vals = week_states.to_numpy(dtype=bool)
    tgt_np = target_dates.to_numpy()

    # searchsorted(side='left') gives first index where week_dates[idx] >= d,
    # so idx - 1 is the last index with week_dates[k] < d (strictly before d).
    idx = np.searchsorted(week_dates, tgt_np, side="left") - 1
    if np.any(idx < 0):
        first_bad = target_dates[int(np.flatnonzero(idx < 0)[0])]
        raise ValueError(f"US weekly state not warmed up before target date {first_bad}")
    mapped_vals = week_vals[idx]
    mapped_dates = pd.Series(pd.DatetimeIndex(week_dates[idx]), index=target_dates, name="us_week_date")
    return mapped_vals, mapped_dates


def build_us_target_matrix(
    strategy: str,
    spy_w: np.ndarray,
    spy_m: np.ndarray,
    gold_w: np.ndarray,
    ief_w: np.ndarray,
    spy_off: float = 0.5,
) -> np.ndarray:
    """Construct (N, 3) target weight matrix for columns [spy, gold, ief]; remainder is cash."""
    n = len(spy_w)
    w = np.zeros((n, 3), dtype=float)
    shield_alloc = 1.0 - spy_off

    if strategy == "B0_SPY":
        w[:, 0] = 1.0
    elif strategy == "S2_CASH":
        w[:, 0] = np.where(spy_w, 1.0, spy_off)
    elif strategy == "S2_GOLD":
        w[:, 0] = np.where(spy_w, 1.0, spy_off)
        w[:, 1] = np.where(spy_w, 0.0, shield_alloc)
    elif strategy == "S2_GOLD_TREND":
        w[:, 0] = np.where(spy_w, 1.0, spy_off)
        w[:, 1] = np.where((~spy_w) & gold_w, shield_alloc, 0.0)
    elif strategy == "S2_BOND_GOLD":
        w[:, 0] = np.where(spy_w, 1.0, spy_off)
        w[:, 1] = np.where(spy_w, 0.0, shield_alloc * 0.5)
        w[:, 2] = np.where(spy_w, 0.0, shield_alloc * 0.5)
    elif strategy == "S2_BOND_GOLD_TREND":
        w[:, 0] = np.where(spy_w, 1.0, spy_off)
        w[:, 1] = np.where((~spy_w) & gold_w, shield_alloc * 0.5, 0.0)
        w[:, 2] = np.where((~spy_w) & ief_w, shield_alloc * 0.5, 0.0)
    elif strategy == "MTF3_CASH":
        score = spy_w.astype(int) + spy_m.astype(int)
        w[:, 0] = np.where(score == 2, 1.0, np.where(score == 1, 0.5, 0.0))
    elif strategy == "MTF3_GOLD":
        score = spy_w.astype(int) + spy_m.astype(int)
        w_spy = np.where(score == 2, 1.0, np.where(score == 1, 0.5, 0.0))
        w[:, 0] = w_spy
        w[:, 1] = 1.0 - w_spy
    elif strategy == "MTF3_GOLD_TREND":
        score = spy_w.astype(int) + spy_m.astype(int)
        w_spy = np.where(score == 2, 1.0, np.where(score == 1, 0.5, 0.0))
        w[:, 0] = w_spy
        w[:, 1] = np.where(gold_w, 1.0 - w_spy, 0.0)
    else:
        raise ValueError(f"Unknown US strategy: {strategy}")

    return w


def build_domestic_target_matrix(
    strategy: str,
    cn_eq_w: np.ndarray,
    us_eq_w: np.ndarray,
    cn_gold_w: np.ndarray,
    spy_off: float = 0.5,
) -> np.ndarray:
    """Construct (N, 2) target weight matrix for columns [c513500, c518880]; remainder is RMB cash."""
    n = len(cn_eq_w)
    w = np.zeros((n, 2), dtype=float)
    shield_alloc = 1.0 - spy_off

    if strategy == "B0_513500":
        w[:, 0] = 1.0
    elif strategy == "CN_S2_CASH_SELF":
        w[:, 0] = np.where(cn_eq_w, 1.0, spy_off)
    elif strategy == "CN_S2_GOLD_SELF":
        w[:, 0] = np.where(cn_eq_w, 1.0, spy_off)
        w[:, 1] = np.where(cn_eq_w, 0.0, shield_alloc)
    elif strategy == "CN_S2_GOLD_TREND_SELF":
        w[:, 0] = np.where(cn_eq_w, 1.0, spy_off)
        w[:, 1] = np.where((~cn_eq_w) & cn_gold_w, shield_alloc, 0.0)
    elif strategy == "CN_S2_CASH_US":
        w[:, 0] = np.where(us_eq_w, 1.0, spy_off)
    elif strategy == "CN_S2_GOLD_US":
        w[:, 0] = np.where(us_eq_w, 1.0, spy_off)
        w[:, 1] = np.where(us_eq_w, 0.0, shield_alloc)
    elif strategy == "CN_S2_GOLD_TREND_US":
        w[:, 0] = np.where(us_eq_w, 1.0, spy_off)
        w[:, 1] = np.where((~us_eq_w) & cn_gold_w, shield_alloc, 0.0)
    else:
        raise ValueError(f"Unknown domestic strategy: {strategy}")

    return w


def make_state_signal(target_matrix: np.ndarray, start_i: int) -> lab.MultiSignal:
    """Submit target vector at start_i and strictly when target vector changes vs day i-1."""
    mat = np.asarray(target_matrix, dtype=float)

    def sig(i: int, _actual: np.ndarray):
        if i == start_i or np.any(mat[i] != mat[i - 1]):
            return mat[i].copy()
        return None

    return sig


# --------------------------------------------------------------------------- Helpers for metrics & checks
def record_engine_check(tracker: list[dict], label: str, res: lab.MultiEngineResult) -> None:
    """Validate accounting invariants on every single backtest run."""
    c = res.checks
    w_sum = res.weights.sum(axis=1)
    max_w_sum_err = float(np.abs(w_sum - 1.0).max())
    min_actual_w = float(res.weights.min().min())
    ok = (
        c["max_cash_residual"] < 1e-10
        and c["nav_min"] > 0.0
        and c["target_weight_min"] >= -1e-12
        and c["target_sum_max"] <= 1.0 + 1e-12
        and max_w_sum_err < 1e-10
        and min_actual_w >= -1e-9
    )
    tracker.append(
        {
            "label": label,
            "ok": bool(ok),
            "max_cash_residual": float(c["max_cash_residual"]),
            "nav_min": float(c["nav_min"]),
            "target_weight_min": float(c["target_weight_min"]),
            "target_sum_max": float(c["target_sum_max"]),
            "max_weight_sum_err": max_w_sum_err,
            "min_actual_weight": min_actual_w,
        }
    )


def period_slice_metrics(res: lab.MultiEngineResult, start: str, end: str) -> dict:
    """Compute cumulative return, in-period max drawdown, and average asset allocations."""
    ts, te = pd.Timestamp(start), pd.Timestamp(end)
    nav = res.nav[(res.nav.index >= ts) & (res.nav.index <= te)]
    wts = res.weights[(res.weights.index >= ts) & (res.weights.index <= te)]
    trades = res.trades
    if not trades.empty:
        trades = trades[(trades["exec_date"] >= ts) & (trades["exec_date"] <= te) & (~trades["is_initial"])]
    nav_norm = nav / nav.iloc[0]
    dd = nav_norm / nav_norm.cummax() - 1.0
    out = {
        "actual_start": str(nav.index[0].date()),
        "actual_end": str(nav.index[-1].date()),
        "n_trading_days": int(len(nav)),
        "cum_return": float(nav_norm.iloc[-1] - 1.0),
        "max_dd": float(dd.min()),
        "trough_from_start": float(nav_norm.min() - 1.0),
        "trades_in_period": int(len(trades)),
    }
    for col in wts.columns:
        out[f"avg_w_{col}"] = float(wts[col].mean())
    return out


# --------------------------------------------------------------------------- Anti-lookahead verification
def run_anti_lookahead_checks(us: dict, dom: dict) -> dict:
    """Strict future-price perturbation tests and week-end update audits."""
    # 1. Verify weekly_stage2_state ONLY changes on week-end trading days (W-SUN last trading day)
    def check_week_end_only(series: pd.Series, name: str) -> dict:
        s = series.dropna()
        st = lab.weekly_stage2_state(s, 30, 4).astype(bool)
        grouped = s.groupby(s.index.to_period("W-SUN"))
        week_ends = set(grouped.tail(1).index)
        changed_dates = st.index[st != st.shift(1)].tolist()
        # First date is shift NaN artifact; ignore index[0]
        changed_dates = [d for d in changed_dates if d != st.index[0]]
        non_week_end_changes = [str(d.date()) for d in changed_dates if d not in week_ends]
        return {
            "series": name,
            "n_changes": len(changed_dates),
            "non_week_end_changes": non_week_end_changes,
            "ok": len(non_week_end_changes) == 0,
        }

    week_end_audits = [
        check_week_end_only(us["spy"], "us_spy"),
        check_week_end_only(us["gld_real"], "us_gld_real"),
        check_week_end_only(us["gold_spliced"], "us_gold_spliced"),
        check_week_end_only(us["ief"], "us_ief"),
        check_week_end_only(dom["c513500_full"], "cn_513500_full"),
        check_week_end_only(dom["c518880_full"], "cn_518880_full"),
    ]

    # 2. US perturbation test: perturb all prices strictly AFTER test date d; decisions <= d must match 100%
    us_dates = us["dates"]
    spy_w0 = weekly_state_bool(us["spy"], 30, 4)
    spy_m0 = monthly_state_bool(us["spy"], 10)
    gld_w0 = weekly_state_bool(us["gld_real"], 30, 4)
    ief_w0 = weekly_state_bool(us["ief"], 30, 4)
    us_base_mats = {
        s: build_us_target_matrix(s, spy_w0, spy_m0, gld_w0, ief_w0)
        for s in CONFIG["us_track"]["strategies"]
    }
    us_test_dates = [
        "2005-04-19",  # mid-week Tuesday
        "2008-09-17",  # GFC mid-week Wednesday
        "2008-10-31",  # GFC month-end Friday
        "2011-08-09",  # US downgrade Tuesday
        "2015-08-25",  # 2015 correction Tuesday
        "2020-03-11",  # COVID crash Wednesday
        "2022-06-30",  # 2022 bear month-end Thursday
        "2025-04-08",  # Recent mid-week Tuesday
    ]
    us_perturb_mismatches = 0
    for d_str in us_test_dates:
        d = pd.Timestamp(d_str)
        mask_future = us_dates > d
        mask_le = us_dates <= d
        # Extreme perturbation of all future closes (> d)
        spy_p = us["spy"].copy()
        gld_p = us["gld_real"].copy()
        ief_p = us["ief"].copy()
        spy_p.loc[mask_future] = spy_p.loc[mask_future] * 3.7 + 123.4
        gld_p.loc[mask_future] = gld_p.loc[mask_future] * 0.25 + 1.0
        ief_p.loc[mask_future] = ief_p.loc[mask_future] * 4.2 + 50.0

        sp_w = weekly_state_bool(spy_p, 30, 4)
        sp_m = monthly_state_bool(spy_p, 10)
        gl_w = weekly_state_bool(gld_p, 30, 4)
        ie_w = weekly_state_bool(ief_p, 30, 4)
        for s in CONFIG["us_track"]["strategies"]:
            mat_p = build_us_target_matrix(s, sp_w, sp_m, gl_w, ie_w)
            if not np.array_equal(us_base_mats[s][mask_le], mat_p[mask_le]):
                us_perturb_mismatches += 1

    # 3. Domestic SELF & US_SIG strict perturbation test:
    # For US_SIG, perturb US SPY prices on dates >= d (INCLUDING day d itself, since China closes before US opens!),
    # and perturb domestic prices on dates > d. Decisions on China days <= d must match 100%.
    cn_dates = dom["dates"]
    cn_eq_w0 = lab.weekly_stage2_state(dom["c513500_full"], 30, 4).astype(bool).reindex(cn_dates).to_numpy(bool)
    cn_gd_w0 = lab.weekly_stage2_state(dom["c518880_full"], 30, 4).astype(bool).reindex(cn_dates).to_numpy(bool)
    us_eq_w0, us_src_dates = us_weekly_state_strictly_before(us["spy"], cn_dates, 30, 4)
    cn_base_mats = {
        s: build_domestic_target_matrix(s, cn_eq_w0, us_eq_w0, cn_gd_w0)
        for s in CONFIG["domestic_track"]["strategies"]
    }

    # Verify strict date inequality u < d on every single China trading day
    date_gaps_days = (cn_dates - pd.DatetimeIndex(us_src_dates)).days
    min_cross_market_gap_days = int(date_gaps_days.min())
    strict_us_before_cn_ok = bool(min_cross_market_gap_days >= 1)

    cn_test_dates = [
        "2015-08-21",  # Friday (same-day US Friday must NOT leak!)
        "2018-10-12",  # Friday
        "2020-03-13",  # COVID Friday
        "2022-04-29",  # Month-end Friday
        "2022-09-21",  # Mid-week Wednesday
        "2025-04-03",  # Pre-holiday Thursday
    ]
    cn_self_mismatches = 0
    cn_us_mismatches = 0
    for d_str in cn_test_dates:
        d = pd.Timestamp(d_str)
        mask_le = cn_dates <= d

        c513_p = dom["c513500_full"].copy()
        c518_p = dom["c518880_full"].copy()
        c513_p.loc[c513_p.index > d] = c513_p.loc[c513_p.index > d] * 0.2
        c518_p.loc[c518_p.index > d] = c518_p.loc[c518_p.index > d] * 3.5

        spy_p = us["spy"].copy()
        # CRITICAL: perturb US prices on >= d (including day d itself!)
        spy_p.loc[spy_p.index >= d] = spy_p.loc[spy_p.index >= d] * 0.15

        eq_p = lab.weekly_stage2_state(c513_p, 30, 4).astype(bool).reindex(cn_dates).to_numpy(bool)
        gd_p = lab.weekly_stage2_state(c518_p, 30, 4).astype(bool).reindex(cn_dates).to_numpy(bool)
        us_p, _ = us_weekly_state_strictly_before(spy_p, cn_dates, 30, 4)

        for s in CONFIG["domestic_track"]["strategies"]:
            mat_p = build_domestic_target_matrix(s, eq_p, us_p, gd_p)
            if not np.array_equal(cn_base_mats[s][mask_le], mat_p[mask_le]):
                if s.endswith("_US"):
                    cn_us_mismatches += 1
                else:
                    cn_self_mismatches += 1

    # 4. Cross-check B0_SPY and S2_CASH vs legacy overlay_rules.simulate on 2005-01-03..2026-10-16
    legacy_md = ov.MarketData(us["dates"], us["spy"], us["ief"], us["cash_pos"], us["cash_neg"])
    legacy_b0 = ov.simulate(legacy_md, "B0", lab.US_GLD_START, cost=0.001)
    legacy_s2 = ov.simulate(legacy_md, "S2", lab.US_GLD_START, cost=0.001)

    prices_us = pd.DataFrame({"spy": us["spy"], "gold": us["gld_real"], "ief": us["ief"]}, index=us["dates"])
    start_i = int(us["dates"].searchsorted(pd.Timestamp(lab.US_GLD_START)))
    new_b0 = lab.run_multi_asset_overlay(
        prices_us, make_state_signal(us_base_mats["B0_SPY"], start_i), start_i, 0.001, us["cash_pos"], us["cash_neg"]
    )
    new_s2 = lab.run_multi_asset_overlay(
        prices_us, make_state_signal(us_base_mats["S2_CASH"], start_i), start_i, 0.001, us["cash_pos"], us["cash_neg"]
    )
    b0_diff = float((new_b0.nav - legacy_b0.nav).abs().max())
    s2_diff = float((new_s2.nav - legacy_s2.nav).abs().max())

    return {
        "week_end_only_audits": week_end_audits,
        "all_week_end_only_ok": all(x["ok"] for x in week_end_audits),
        "us_future_perturbation_test_dates": us_test_dates,
        "us_future_perturbation_mismatches": us_perturb_mismatches,
        "us_anti_lookahead_ok": us_perturb_mismatches == 0,
        "cn_future_perturbation_test_dates": cn_test_dates,
        "cn_self_perturbation_mismatches": cn_self_mismatches,
        "cn_us_sig_perturbation_mismatches_incl_same_day": cn_us_mismatches,
        "cn_anti_lookahead_ok": (cn_self_mismatches == 0 and cn_us_mismatches == 0),
        "us_sig_min_calendar_gap_days": min_cross_market_gap_days,
        "us_sig_strict_before_cn_ok": strict_us_before_cn_ok,
        "legacy_overlay_rules_b0_max_abs_nav_diff": b0_diff,
        "legacy_overlay_rules_s2_max_abs_nav_diff": s2_diff,
        "legacy_consistency_ok": (b0_diff < 1e-10 and s2_diff < 1e-10),
    }


# --------------------------------------------------------------------------- Main research pipeline
def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    us = lab.load_us_bundle()
    dom = lab.load_domestic_bundle()

    # Save frozen config + data diagnostics
    config_out = {
        **CONFIG,
        "data_diagnostics": {
            "us_dates": [str(us["dates"][0].date()), str(us["dates"][-1].date()), int(len(us["dates"]))],
            "gold_diag": us["gold_diag"],
            "domestic_dates": [str(dom["dates"][0].date()), str(dom["dates"][-1].date()), int(len(dom["dates"]))],
            "domestic_full_start": str(dom["c513500_full"].index[0].date()),
        },
    }
    (OUT_DIR / "config.json").write_text(json.dumps(config_out, indent=2, ensure_ascii=False))

    engine_checks: list[dict] = []

    # =======================================================================
    # PART A: US TRACK (us_2005 real GLD + us_2001 spliced gold; 10bp & 30bp)
    # =======================================================================
    us_dates = us["dates"]
    spy_w = weekly_state_bool(us["spy"], 30, 4)
    spy_m = monthly_state_bool(us["spy"], 10)
    ief_w = weekly_state_bool(us["ief"], 30, 4)

    us_summary_rows: list[dict] = []
    us_2005_10bp_results: dict[str, lab.MultiEngineResult] = {}
    us_2001_10bp_results: dict[str, lab.MultiEngineResult] = {}

    for win_cfg in (CONFIG["us_track"]["main_window"], CONFIG["us_track"]["extended_window"]):
        win_name = win_cfg["name"]
        gold_series = us[win_cfg["gold_source"]]
        gold_w = weekly_state_bool(gold_series, 30, 4)
        prices_us = pd.DataFrame(
            {"spy": us["spy"], "gold": gold_series, "ief": us["ief"]},
            index=us_dates,
        )
        start_i = int(us_dates.searchsorted(pd.Timestamp(win_cfg["start"])))

        for cost in CONFIG["us_track"]["costs_one_way"]:
            cost_bps = int(round(cost * 10000))
            run_map: dict[str, lab.MultiEngineResult] = {}

            for strat in CONFIG["us_track"]["strategies"]:
                tmat = build_us_target_matrix(strat, spy_w, spy_m, gold_w, ief_w, spy_off=0.5)
                res = lab.run_multi_asset_overlay(
                    prices_us, make_state_signal(tmat, start_i), start_i, cost, us["cash_pos"], us["cash_neg"]
                )
                record_engine_check(engine_checks, f"{win_name}_{cost_bps}bp_{strat}", res)
                run_map[strat] = res

                for seg_name, (seg_s, seg_e) in win_cfg["segments"].items():
                    m = lab.summarize_result(res, primary_col="spy", start=seg_s, end=seg_e)
                    us_summary_rows.append(
                        {
                            "window": win_name,
                            "gold_source": win_cfg["gold_source"],
                            "cost_bps": cost_bps,
                            "segment": seg_name,
                            "row_type": "strategy",
                            "strategy": strat,
                            "matched_to": "",
                            **m,
                        }
                    )

            # Fixed-weight controls (full window):
            # 1) Same average SPY weight + cash (month-end rebalanced), matching repo convention
            # 2) Same average multi-asset weights (SPY + Gold + IEF + cash, month-end rebalanced)
            for strat in CONFIG["us_track"]["strategies"]:
                if strat == "B0_SPY":
                    continue
                res = run_map[strat]
                avg_spy = float(res.weights["spy"].iloc[1:].mean())
                avg_gold = float(res.weights["gold"].iloc[1:].mean())
                avg_ief = float(res.weights["ief"].iloc[1:].mean())

                sig_fc = lab.fixed_weight_signal([avg_spy, 0.0, 0.0], us_dates, start_i, freq="M")
                res_fc = lab.run_multi_asset_overlay(prices_us, sig_fc, start_i, cost, us["cash_pos"], us["cash_neg"])
                record_engine_check(engine_checks, f"{win_name}_{cost_bps}bp_FIXED_CASH_{strat}", res_fc)
                m_fc = lab.summarize_result(res_fc, primary_col="spy")
                us_summary_rows.append(
                    {
                        "window": win_name,
                        "gold_source": win_cfg["gold_source"],
                        "cost_bps": cost_bps,
                        "segment": "full",
                        "row_type": "fixed_cash_match",
                        "strategy": f"FIXED_CASH_{strat}",
                        "matched_to": strat,
                        **m_fc,
                    }
                )

                # Static multi-asset blend control for strategies that hold Gold or IEF
                if avg_gold > 1e-6 or avg_ief > 1e-6:
                    sig_fm = lab.fixed_weight_signal([avg_spy, avg_gold, avg_ief], us_dates, start_i, freq="M")
                    res_fm = lab.run_multi_asset_overlay(
                        prices_us, sig_fm, start_i, cost, us["cash_pos"], us["cash_neg"]
                    )
                    record_engine_check(engine_checks, f"{win_name}_{cost_bps}bp_FIXED_MIX_{strat}", res_fm)
                    m_fm = lab.summarize_result(res_fm, primary_col="spy")
                    us_summary_rows.append(
                        {
                            "window": win_name,
                            "gold_source": win_cfg["gold_source"],
                            "cost_bps": cost_bps,
                            "segment": "full",
                            "row_type": "fixed_mix_match",
                            "strategy": f"FIXED_MIX_{strat}",
                            "matched_to": strat,
                            **m_fm,
                        }
                    )

            if win_name == "us_2005" and cost_bps == 10:
                us_2005_10bp_results = run_map
            if win_name == "us_2001" and cost_bps == 10:
                us_2001_10bp_results = run_map

    pd.DataFrame(us_summary_rows).to_csv(OUT_DIR / "summary_us.csv", index=False)

    # Save US main window 10bp daily NAVs
    nav_us_df = pd.DataFrame({k: v.nav for k, v in us_2005_10bp_results.items()})
    nav_us_df.to_csv(OUT_DIR / "nav_us_2005_10bp.csv", index_label="date")

    # =======================================================================
    # PART A2: US ROLLING START YEARS (2005..2023 -> 2026-10-16, 10bp, real GLD)
    # =======================================================================
    prices_us_real = pd.DataFrame(
        {"spy": us["spy"], "gold": us["gld_real"], "ief": us["ief"]},
        index=us_dates,
    )
    gold_w_real = weekly_state_bool(us["gld_real"], 30, 4)
    us_real_tmats = {
        strat: build_us_target_matrix(strat, spy_w, spy_m, gold_w_real, ief_w, spy_off=0.5)
        for strat in CONFIG["us_track"]["strategies"]
    }

    rolling_rows: list[dict] = []
    for yr in CONFIG["us_track"]["rolling_start_years"]:
        si = int(us_dates.searchsorted(pd.Timestamp(f"{yr}-01-01")))
        yr_metrics: dict[str, dict] = {}
        for strat in CONFIG["us_track"]["strategies"]:
            res = lab.run_multi_asset_overlay(
                prices_us_real, make_state_signal(us_real_tmats[strat], si), si, 0.001, us["cash_pos"], us["cash_neg"]
            )
            record_engine_check(engine_checks, f"roll_{yr}_{strat}", res)
            yr_metrics[strat] = lab.summarize_result(res, primary_col="spy")

        b0 = yr_metrics["B0_SPY"]
        s2c = yr_metrics["S2_CASH"]
        for strat, m in yr_metrics.items():
            rolling_rows.append(
                {
                    "start_year": yr,
                    "strategy": strat,
                    "start": m["start"],
                    "end": m["end"],
                    "years": m["years"],
                    "cagr": m["cagr"],
                    "vol": m["vol"],
                    "sharpe": m["sharpe"],
                    "max_dd": m["max_dd"],
                    "calmar": m["calmar"],
                    "beat_b0_cagr": bool(m["cagr"] > b0["cagr"]),
                    "beat_b0_sharpe": bool(m["sharpe"] > b0["sharpe"]),
                    "beat_b0_calmar": bool(m["calmar"] > b0["calmar"]),
                    "beat_b0_mdd": bool(m["max_dd"] > b0["max_dd"]),
                    "beat_s2cash_cagr": bool(m["cagr"] > s2c["cagr"]),
                    "beat_s2cash_sharpe": bool(m["sharpe"] > s2c["sharpe"]),
                    "beat_s2cash_calmar": bool(m["calmar"] > s2c["calmar"]),
                }
            )
    pd.DataFrame(rolling_rows).to_csv(OUT_DIR / "rolling_starts_us.csv", index=False)

    # =======================================================================
    # PART A3: US SENSITIVITY (S2_GOLD & S2_GOLD_TREND, us_2005, 10bp)
    # =======================================================================
    start_i_2005 = int(us_dates.searchsorted(pd.Timestamp(lab.US_GLD_START)))
    sens_rows: list[dict] = []
    spy_w_cache = {wm: weekly_state_bool(us["spy"], wm, 4) for wm in (20, 30, 40)}
    gld_w_cache = {gm: weekly_state_bool(us["gld_real"], gm, 4) for gm in (20, 30, 40)}

    # Grid 1: SPY MA weeks (20/30/40) x SPY off-weight (0.25/0.50/0.75), gold_ma = 30
    for strat in ("S2_GOLD", "S2_GOLD_TREND"):
        for spy_ma in (20, 30, 40):
            for spy_off in (0.25, 0.50, 0.75):
                tmat = build_us_target_matrix(
                    strat, spy_w_cache[spy_ma], spy_m, gld_w_cache[30], ief_w, spy_off=spy_off
                )
                res = lab.run_multi_asset_overlay(
                    prices_us_real,
                    make_state_signal(tmat, start_i_2005),
                    start_i_2005,
                    0.001,
                    us["cash_pos"],
                    us["cash_neg"],
                )
                record_engine_check(engine_checks, f"sens_g1_{strat}_spy{spy_ma}_off{spy_off}", res)
                m = lab.summarize_result(res, primary_col="spy")
                sens_rows.append(
                    {
                        "grid": "spy_ma_x_off_weight",
                        "strategy": strat,
                        "spy_ma_weeks": spy_ma,
                        "spy_off_weight": spy_off,
                        "gold_ma_weeks": 30 if strat == "S2_GOLD_TREND" else np.nan,
                        **m,
                    }
                )

    # Grid 2: Gold MA weeks (20/30/40) x SPY MA weeks (20/30/40) for S2_GOLD_TREND at spy_off = 0.50
    for spy_ma in (20, 30, 40):
        for gold_ma in (20, 30, 40):
            tmat = build_us_target_matrix(
                "S2_GOLD_TREND", spy_w_cache[spy_ma], spy_m, gld_w_cache[gold_ma], ief_w, spy_off=0.50
            )
            res = lab.run_multi_asset_overlay(
                prices_us_real,
                make_state_signal(tmat, start_i_2005),
                start_i_2005,
                0.001,
                us["cash_pos"],
                us["cash_neg"],
            )
            record_engine_check(engine_checks, f"sens_g2_S2_GOLD_TREND_spy{spy_ma}_gld{gold_ma}", res)
            m = lab.summarize_result(res, primary_col="spy")
            sens_rows.append(
                {
                    "grid": "spy_ma_x_gold_ma",
                    "strategy": "S2_GOLD_TREND",
                    "spy_ma_weeks": spy_ma,
                    "spy_off_weight": 0.50,
                    "gold_ma_weeks": gold_ma,
                    **m,
                }
            )
    pd.DataFrame(sens_rows).to_csv(OUT_DIR / "sensitivity.csv", index=False)

    # =======================================================================
    # PART B: DOMESTIC RMB TRACK (513500 + 518880, 2014-10-08..2026-09-30)
    # =======================================================================
    cn_dates = dom["dates"]
    prices_cn = pd.DataFrame(
        {"c513500": dom["c513500"], "c518880": dom["c518880"]},
        index=cn_dates,
    )
    cn_eq_w = lab.weekly_stage2_state(dom["c513500_full"], 30, 4).astype(bool).reindex(cn_dates).to_numpy(bool)
    cn_gold_w = lab.weekly_stage2_state(dom["c518880_full"], 30, 4).astype(bool).reindex(cn_dates).to_numpy(bool)
    us_eq_w_for_cn, _ = us_weekly_state_strictly_before(us["spy"], cn_dates, 30, 4)

    dom_summary_rows: list[dict] = []
    dom_10bp_results: dict[str, lab.MultiEngineResult] = {}

    for cost in CONFIG["domestic_track"]["costs_one_way"]:
        cost_bps = int(round(cost * 10000))
        run_map_cn: dict[str, lab.MultiEngineResult] = {}

        for strat in CONFIG["domestic_track"]["strategies"]:
            tmat = build_domestic_target_matrix(strat, cn_eq_w, us_eq_w_for_cn, cn_gold_w, spy_off=0.5)
            res = lab.run_multi_asset_overlay(
                prices_cn, make_state_signal(tmat, 0), 0, cost, dom["cash_pos"], dom["cash_neg"]
            )
            record_engine_check(engine_checks, f"cn_{cost_bps}bp_{strat}", res)
            run_map_cn[strat] = res

            for seg_name, (seg_s, seg_e) in CONFIG["domestic_track"]["window"]["segments"].items():
                m = lab.summarize_result(res, primary_col="c513500", start=seg_s, end=seg_e)
                dom_summary_rows.append(
                    {
                        "track": "domestic_rmb",
                        "cost_bps": cost_bps,
                        "segment": seg_name,
                        "row_type": "strategy",
                        "strategy": strat,
                        "signal_source": (
                            "HOLD"
                            if strat == "B0_513500"
                            else ("US_SIG" if strat.endswith("_US") else "SELF")
                        ),
                        "matched_to": "",
                        **m,
                    }
                )

        # Matched fixed controls (full domestic window)
        for strat in CONFIG["domestic_track"]["strategies"]:
            if strat == "B0_513500":
                continue
            res = run_map_cn[strat]
            avg_eq = float(res.weights["c513500"].iloc[1:].mean())
            avg_gd = float(res.weights["c518880"].iloc[1:].mean())

            sig_fc = lab.fixed_weight_signal([avg_eq, 0.0], cn_dates, 0, freq="M")
            res_fc = lab.run_multi_asset_overlay(prices_cn, sig_fc, 0, cost, dom["cash_pos"], dom["cash_neg"])
            record_engine_check(engine_checks, f"cn_{cost_bps}bp_FIXED_CASH_{strat}", res_fc)
            m_fc = lab.summarize_result(res_fc, primary_col="c513500")
            dom_summary_rows.append(
                {
                    "track": "domestic_rmb",
                    "cost_bps": cost_bps,
                    "segment": "full",
                    "row_type": "fixed_cash_match",
                    "strategy": f"FIXED_CASH_{strat}",
                    "signal_source": "FIXED_CASH",
                    "matched_to": strat,
                    **m_fc,
                }
            )

            if avg_gd > 1e-6:
                sig_fm = lab.fixed_weight_signal([avg_eq, avg_gd], cn_dates, 0, freq="M")
                res_fm = lab.run_multi_asset_overlay(prices_cn, sig_fm, 0, cost, dom["cash_pos"], dom["cash_neg"])
                record_engine_check(engine_checks, f"cn_{cost_bps}bp_FIXED_MIX_{strat}", res_fm)
                m_fm = lab.summarize_result(res_fm, primary_col="c513500")
                dom_summary_rows.append(
                    {
                        "track": "domestic_rmb",
                        "cost_bps": cost_bps,
                        "segment": "full",
                        "row_type": "fixed_mix_match",
                        "strategy": f"FIXED_MIX_{strat}",
                        "signal_source": "FIXED_MIX",
                        "matched_to": strat,
                        **m_fm,
                    }
                )

        if cost_bps == 10:
            dom_10bp_results = run_map_cn

    pd.DataFrame(dom_summary_rows).to_csv(OUT_DIR / "summary_domestic.csv", index=False)

    nav_dom_df = pd.DataFrame({k: v.nav for k, v in dom_10bp_results.items()})
    nav_dom_df.to_csv(OUT_DIR / "nav_domestic_10bp.csv", index_label="date")

    # =======================================================================
    # PART C: KEY CRISIS / REGIME PERIODS (key_periods.csv)
    # =======================================================================
    kp_rows: list[dict] = []
    for p_name, (ps, pe) in CONFIG["us_track"]["key_periods"].items():
        for strat, res in us_2005_10bp_results.items():
            pm = period_slice_metrics(res, ps, pe)
            kp_rows.append({"track": "us_2005_10bp", "period": p_name, "strategy": strat, **pm})

    for p_name, (ps, pe) in CONFIG["domestic_track"]["key_periods"].items():
        for strat, res in dom_10bp_results.items():
            pm = period_slice_metrics(res, ps, pe)
            kp_rows.append({"track": "domestic_10bp", "period": p_name, "strategy": strat, **pm})

    pd.DataFrame(kp_rows).to_csv(OUT_DIR / "key_periods.csv", index=False)

    # =======================================================================
    # PART D: DCA PERSPECTIVE (dca_summary.csv)
    # =======================================================================
    dca_rows: list[dict] = []

    # US main window (2005-2026, 10bp): full path + 120m rolling
    b0_us_nav = us_2005_10bp_results["B0_SPY"].nav
    for strat, res in us_2005_10bp_results.items():
        full_stats = lab.dca_full_path(res.nav, cost=0.001)
        roll_120 = lab.compare_dca_windows(res.nav, b0_us_nav, window_months=120, cost=0.001)
        dca_rows.append(
            {
                "track": "us_2005_10bp",
                "benchmark": "B0_SPY",
                "strategy": strat,
                "rolling_months": 120,
                "full_n_months": full_stats["n_months"],
                "full_xirr": full_stats["xirr"],
                "full_max_float_loss": full_stats["max_float_loss"],
                "full_unit_max_dd": full_stats["unit_max_dd"],
                "full_dca_ratio": full_stats["dca_ratio"],
                "full_terminal_per_unit": full_stats["terminal_per_unit"],
                **{f"roll_{k}": v for k, v in roll_120.items()},
            }
        )

    # US extended window (2001-2026, 10bp): full path + 120m rolling
    b0_us2001_nav = us_2001_10bp_results["B0_SPY"].nav
    for strat, res in us_2001_10bp_results.items():
        full_stats = lab.dca_full_path(res.nav, cost=0.001)
        roll_120 = lab.compare_dca_windows(res.nav, b0_us2001_nav, window_months=120, cost=0.001)
        dca_rows.append(
            {
                "track": "us_2001_10bp",
                "benchmark": "B0_SPY",
                "strategy": strat,
                "rolling_months": 120,
                "full_n_months": full_stats["n_months"],
                "full_xirr": full_stats["xirr"],
                "full_max_float_loss": full_stats["max_float_loss"],
                "full_unit_max_dd": full_stats["unit_max_dd"],
                "full_dca_ratio": full_stats["dca_ratio"],
                "full_terminal_per_unit": full_stats["terminal_per_unit"],
                **{f"roll_{k}": v for k, v in roll_120.items()},
            }
        )

    # Domestic RMB track (2014-2026, 10bp): full path + 60m & 120m rolling
    b0_cn_nav = dom_10bp_results["B0_513500"].nav
    for roll_m in CONFIG["domestic_track"]["dca_rolling_months"]:
        for strat, res in dom_10bp_results.items():
            full_stats = lab.dca_full_path(res.nav, cost=0.001)
            roll_stats = lab.compare_dca_windows(res.nav, b0_cn_nav, window_months=roll_m, cost=0.001)
            dca_rows.append(
                {
                    "track": "domestic_10bp",
                    "benchmark": "B0_513500",
                    "strategy": strat,
                    "rolling_months": roll_m,
                    "full_n_months": full_stats["n_months"],
                    "full_xirr": full_stats["xirr"],
                    "full_max_float_loss": full_stats["max_float_loss"],
                    "full_unit_max_dd": full_stats["unit_max_dd"],
                    "full_dca_ratio": full_stats["dca_ratio"],
                    "full_terminal_per_unit": full_stats["terminal_per_unit"],
                    **{f"roll_{k}": v for k, v in roll_stats.items()},
                }
            )

    pd.DataFrame(dca_rows).to_csv(OUT_DIR / "dca_summary.csv", index=False)

    # =======================================================================
    # PART E: SELF-CHECKS (self_checks.json)
    # =======================================================================
    anti_lookahead = run_anti_lookahead_checks(us, dom)
    max_cash_resid_all = max(x["max_cash_residual"] for x in engine_checks)
    min_nav_all = min(x["nav_min"] for x in engine_checks)
    min_tgt_w_all = min(x["target_weight_min"] for x in engine_checks)
    max_tgt_sum_all = max(x["target_sum_max"] for x in engine_checks)
    max_w_sum_err_all = max(x["max_weight_sum_err"] for x in engine_checks)
    failed_runs = [x for x in engine_checks if not x["ok"]]

    expected_files = [
        "config.json",
        "summary_us.csv",
        "summary_domestic.csv",
        "rolling_starts_us.csv",
        "key_periods.csv",
        "dca_summary.csv",
        "sensitivity.csv",
        "nav_us_2005_10bp.csv",
        "nav_domestic_10bp.csv",
    ]
    missing_files = [f for f in expected_files if not (OUT_DIR / f).exists()]

    self_checks = {
        "n_backtest_runs_checked": len(engine_checks),
        "n_failed_runs": len(failed_runs),
        "failed_runs": failed_runs,
        "max_cash_residual": max_cash_resid_all,
        "max_cash_residual_ok": bool(max_cash_resid_all < 1e-10),
        "nav_min": min_nav_all,
        "nav_min_ok": bool(min_nav_all > 0.0),
        "target_weight_min": min_tgt_w_all,
        "target_sum_max": max_tgt_sum_all,
        "max_actual_weight_sum_err": max_w_sum_err_all,
        "weights_legal_ok": bool(
            min_tgt_w_all >= -1e-12 and max_tgt_sum_all <= 1.0 + 1e-12 and max_w_sum_err_all < 1e-10
        ),
        "anti_lookahead": anti_lookahead,
        "missing_output_files": missing_files,
        "all_checks_passed": bool(
            len(failed_runs) == 0
            and max_cash_resid_all < 1e-10
            and min_nav_all > 0.0
            and min_tgt_w_all >= -1e-12
            and max_tgt_sum_all <= 1.0 + 1e-12
            and max_w_sum_err_all < 1e-10
            and anti_lookahead["all_week_end_only_ok"]
            and anti_lookahead["us_anti_lookahead_ok"]
            and anti_lookahead["cn_anti_lookahead_ok"]
            and anti_lookahead["us_sig_strict_before_cn_ok"]
            and anti_lookahead["legacy_consistency_ok"]
            and len(missing_files) == 0
        ),
    }
    (OUT_DIR / "self_checks.json").write_text(json.dumps(self_checks, indent=2, ensure_ascii=False))

    print(f"Completed {SLUG}. Total backtest runs checked: {len(engine_checks)}")
    print(f"All self checks passed: {self_checks['all_checks_passed']}")
    if not self_checks["all_checks_passed"]:
        raise SystemExit("SELF CHECKS FAILED! Inspect self_checks.json")


if __name__ == "__main__":
    main()
