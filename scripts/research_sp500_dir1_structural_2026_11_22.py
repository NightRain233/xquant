"""Direction 1 Research: Non-timing Structural Enhancements for S&P 500.

Covers three tracks under the unified sp500_lab execution clock (close t decision,
close t+1 execution, proportional per-side transaction cost, identical cash rates):
  A. US Dollar track: S&P 500 (SPY) + Gold structural dual-core (real GLD 2005-2026
     and spliced gold 2001-2026), plus SPY+Gold+IEF and matched-average-SPY cash controls.
  B. Domestic RMB track: Real 513500 + 518880 gold dual-core (2014-2026) and matched
     average-513500 cash controls.
  C. US S&P 500 factor structural controls (always-invested equity: Quality SPHQ,
     Equal-Weight RSP, Low-Vol SPLV, SPHQ+GLD, and Stage2-switched SPY/SPLV).

All strategy rules and parameters are frozen in CONFIG prior to execution.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from xquant import overlay_rules as ov
from xquant import sp500_lab as lab

OUT_DIR = ROOT / "outputs" / "sp500-dir1-structural-2026-11-22"

# Frozen configuration before running any backtest
CONFIG: dict = {
    "experiment_slug": "sp500-dir1-structural-2026-11-22",
    "direction": "dir1_structural_no_timing",
    "execution_clock": "signal at close t using data <= t; fill at close t+1",
    "costs": [0.001, 0.003],
    "primary_cost": 0.001,
    "us_main_window": {
        "name": "us_main_2005",
        "start": "2005-01-03",
        "end": "2026-10-16",
        "gold_series": "gld_real",
        "subperiods": [
            {"label": "full", "start": "2005-01-03", "end": "2026-10-16"},
            {"label": "2005-2012", "start": "2005-01-03", "end": "2012-12-31"},
            {"label": "2013-2026", "start": "2013-01-01", "end": "2026-10-16"},
        ],
    },
    "us_ext_window": {
        "name": "us_ext_2001",
        "start": "2001-01-02",
        "end": "2026-10-16",
        "gold_series": "gold_spliced",
        "subperiods": [
            {"label": "full", "start": "2001-01-02", "end": "2026-10-16"},
            {"label": "2001-2012", "start": "2001-01-02", "end": "2012-12-31"},
            {"label": "2013-2026", "start": "2013-01-01", "end": "2026-10-16"},
        ],
    },
    "domestic_window": {
        "name": "domestic_2014",
        "start": "2014-10-08",
        "end": "2026-09-30",
        "subperiods": [
            {"label": "full", "start": "2014-10-08", "end": "2026-09-30"},
            {"label": "2014-2020", "start": "2014-10-08", "end": "2020-12-31"},
            {"label": "2021-2026", "start": "2021-01-01", "end": "2026-09-30"},
        ],
    },
    "us_factors_c1_window": {
        "name": "us_factors_c1_2006",
        "start": "2006-01-03",
        "end": "2026-10-16",
        "subperiods": [
            {"label": "full", "start": "2006-01-03", "end": "2026-10-16"},
            {"label": "2006-2012", "start": "2006-01-03", "end": "2012-12-31"},
            {"label": "2013-2026", "start": "2013-01-01", "end": "2026-10-16"},
        ],
    },
    "us_factors_c2_window": {
        "name": "us_factors_c2_2011",
        "start": "2011-06-01",
        "end": "2026-10-16",
        "subperiods": [
            {"label": "full", "start": "2011-06-01", "end": "2026-10-16"},
            {"label": "2011-2018", "start": "2011-06-01", "end": "2018-12-31"},
            {"label": "2019-2026", "start": "2019-01-01", "end": "2026-10-16"},
        ],
    },
    "invvol_params": {
        "window": 21,
        "min_periods": 21,
        "rebalance_freq": "M",
        "primary_weight_bounds": [0.50, 0.85],
        "return_type": "log_return",
    },
    "cash_match_rebalance_freq": "M",
    "stage2_params": {
        "ma_weeks": 30,
        "slope_weeks": 4,
        "on_weights_spy_splv": [1.0, 0.0],
        "off_weights_spy_splv": [0.5, 0.5],
    },
    "key_periods_us_main": [
        {"period": "GFC_2007_2009", "start": "2007-10-09", "end": "2009-03-09"},
        {"period": "COVID_2020", "start": "2020-02-19", "end": "2020-03-23"},
        {"period": "BEAR_2022", "start": "2022-01-01", "end": "2022-12-31"},
        {"period": "BULL_2023_2026", "start": "2023-01-01", "end": "2026-10-16"},
    ],
    "key_periods_us_ext_extra": [
        {"period": "DOTCOM_2001_2002", "start": "2001-01-02", "end": "2002-10-09"},
    ],
    "key_periods_domestic": [
        {"period": "COVID_2020", "start": "2020-02-19", "end": "2020-03-23"},
        {"period": "BEAR_2022", "start": "2022-01-01", "end": "2022-12-31"},
        {"period": "BULL_2023_2026", "start": "2023-01-01", "end": "2026-09-30"},
    ],
    "sensitivity": {
        "rebalance_freqs": ["M", "Q", "Y", "NONE"],
        "gold_weights_q": [0.15, 0.20, 0.25, 0.30],
        "invvol_windows": [21, 42, 63],
    },
    "dca_windows": {
        "us_main": [120],
        "domestic": [60, 120],
        "us_factors_c1": [120],
    },
    "self_check_thresholds": {
        "max_cash_residual_lt": 1e-10,
        "nav_min_gt": 0.0,
        "weight_sum_max_le": 1.0001,
        "weight_min_ge": -1e-12,
    },
}


# --------------------------------------------------------------------------- Signal builders


def invvol_two_asset_signal(
    primary_full: pd.Series,
    secondary_full: pd.Series,
    dates: pd.DatetimeIndex,
    start_i: int,
    window: int = 21,
    w_min: float = 0.50,
    w_max: float = 0.85,
    freq: str = "M",
    min_periods: int = 21,
) -> lab.MultiSignal:
    """Inverse-volatility two-asset weight rule using strictly past log-return volatility.

    At each decision close ``i`` (initial ``start_i`` and each period-end of ``freq``),
    computes realized sample std of the trailing ``window`` daily log returns up to and
    including close ``i``, sets primary weight ``vol_sec / (vol_pri + vol_sec)`` clipped
    to ``[w_min, w_max]``, and assigns the remainder to the secondary asset.
    """
    log_r1 = np.log(primary_full / primary_full.shift(1))
    log_r2 = np.log(secondary_full / secondary_full.shift(1))
    v1_series = log_r1.rolling(window, min_periods=min_periods).std(ddof=1).reindex(dates)
    v2_series = log_r2.rolling(window, min_periods=min_periods).std(ddof=1).reindex(dates)
    v1 = v1_series.to_numpy(float)
    v2 = v2_series.to_numpy(float)

    if freq == "M":
        mask = ov.month_end_mask(dates)
    else:
        mask = np.zeros(len(dates), dtype=bool)
        if len(dates) > 1:
            mask[:-1] = dates[:-1].to_period(freq) != dates[1:].to_period(freq)

    def sig(i: int, _actual: np.ndarray) -> Optional[np.ndarray]:
        if i != start_i and not mask[i]:
            return None
        s1 = v1[i]
        s2 = v2[i]
        if not (np.isfinite(s1) and np.isfinite(s2) and s1 > 0.0 and s2 > 0.0):
            raise ValueError(
                f"Invalid realized vol at {dates[i]} (window={window}): v1={s1}, v2={s2}"
            )
        raw_w1 = s2 / (s1 + s2)
        w1 = float(np.clip(raw_w1, w_min, w_max))
        return np.array([w1, 1.0 - w1], dtype=float)

    return sig


def stage2_style_switch_signal(
    s2_state: pd.Series,
    dates: pd.DatetimeIndex,
    start_i: int,
    on_weights: tuple[float, float] = (1.0, 0.0),
    off_weights: tuple[float, float] = (0.5, 0.5),
) -> lab.MultiSignal:
    """Always-invested style switch driven by SPY weekly Stage2 state.

    Matches position_rules.rule_stage_blend convention: acts at ``start_i`` and whenever
    the weekly Stage2 boolean state flips at a week-end close (no extra intra-regime rebal).
    """
    aligned = s2_state.reindex(dates).to_numpy(bool)
    w_on = np.asarray(on_weights, dtype=float)
    w_off = np.asarray(off_weights, dtype=float)
    state = {"on": None}

    def sig(i: int, _actual: np.ndarray) -> Optional[np.ndarray]:
        cur = bool(aligned[i])
        if i == start_i or state["on"] is None or cur != state["on"]:
            state["on"] = cur
            return w_on if cur else w_off
        return None

    return sig


# --------------------------------------------------------------------------- Audit & helpers


def audit_result(label: str, res: lab.MultiEngineResult, asset_cols: list[str]) -> dict:
    """Run strict numerical and accounting self-checks on a MultiEngineResult."""
    nav = res.nav
    wts = res.weights
    asset_w = wts[asset_cols]
    asset_sum = asset_w.sum(axis=1)
    total_sum = wts.sum(axis=1)

    max_cash_res = float(res.checks["max_cash_residual"])
    nav_min = float(res.checks["nav_min"])
    nav_has_nan = bool(nav.isna().any() or not np.all(np.isfinite(nav.to_numpy(float))))
    wts_has_nan = bool(wts.isna().any().any() or not np.all(np.isfinite(wts.to_numpy(float))))
    target_sum_max = float(res.checks["target_sum_max"])
    actual_asset_sum_max = float(asset_sum.max())
    actual_asset_min = float(asset_w.min().min())
    total_sum_max_err = float(np.abs(total_sum - 1.0).max())

    thr = CONFIG["self_check_thresholds"]
    passed = (
        (max_cash_res < thr["max_cash_residual_lt"])
        and (nav_min > thr["nav_min_gt"])
        and (not nav_has_nan)
        and (not wts_has_nan)
        and (target_sum_max <= thr["weight_sum_max_le"])
        and (actual_asset_sum_max <= thr["weight_sum_max_le"])
        and (actual_asset_min >= thr["weight_min_ge"])
        and (total_sum_max_err < 1e-10)
    )
    return {
        "label": label,
        "passed": bool(passed),
        "max_cash_residual": max_cash_res,
        "nav_min": nav_min,
        "nav_has_nan": nav_has_nan,
        "weights_has_nan": wts_has_nan,
        "target_sum_max": target_sum_max,
        "actual_asset_sum_max": actual_asset_sum_max,
        "actual_asset_min": actual_asset_min,
        "total_weight_sum_max_err": total_sum_max_err,
        "n_days": int(len(nav)),
        "n_trades": int(len(res.trades)),
    }


def run_causality_checks(us: dict, cn: dict) -> list[dict]:
    """Verify no look-ahead bias: perturbing future prices leaves earlier signals identical."""
    checks = []

    # 1. US INVVOL causality check
    dates = us["dates"]
    start_i = int(dates.searchsorted(pd.Timestamp(CONFIG["us_main_window"]["start"])))
    cutoff_i = start_i + 1500
    sig_orig = invvol_two_asset_signal(us["spy"], us["gld_real"], dates, start_i)
    spy_pert = us["spy"].copy()
    gld_pert = us["gld_real"].copy()
    spy_pert.iloc[cutoff_i + 1 :] *= 1.75
    gld_pert.iloc[cutoff_i + 1 :] *= 0.40
    sig_pert = invvol_two_asset_signal(spy_pert, gld_pert, dates, start_i)

    max_diff = 0.0
    dummy = np.array([0.5, 0.5])
    for i in range(start_i, cutoff_i + 1):
        a = sig_orig(i, dummy)
        b = sig_pert(i, dummy)
        if (a is None) != (b is None):
            max_diff = float("inf")
            break
        if a is not None and b is not None:
            max_diff = max(max_diff, float(np.max(np.abs(a - b))))
    checks.append({"check": "causality_us_invvol", "passed": max_diff == 0.0, "max_diff": max_diff})

    # 2. Domestic INVVOL causality check
    cn_dates = cn["dates"]
    cn_cutoff = 1200
    cn_cutoff_date = cn_dates[cn_cutoff]
    sig_cn_orig = invvol_two_asset_signal(cn["c513500_full"], cn["c518880_full"], cn_dates, 0)
    c1_pert = cn["c513500_full"].copy()
    c2_pert = cn["c518880_full"].copy()
    c1_pert.loc[c1_pert.index > cn_cutoff_date] *= 2.0
    c2_pert.loc[c2_pert.index > cn_cutoff_date] *= 0.5
    sig_cn_pert = invvol_two_asset_signal(c1_pert, c2_pert, cn_dates, 0)

    max_diff_cn = 0.0
    for i in range(0, cn_cutoff + 1):
        a = sig_cn_orig(i, dummy)
        b = sig_cn_pert(i, dummy)
        if (a is None) != (b is None):
            max_diff_cn = float("inf")
            break
        if a is not None and b is not None:
            max_diff_cn = max(max_diff_cn, float(np.max(np.abs(a - b))))
    checks.append(
        {"check": "causality_domestic_invvol", "passed": max_diff_cn == 0.0, "max_diff": max_diff_cn}
    )

    # 3. Stage2 causality check (using a week-end cutoff so current week is complete)
    s2_orig = lab.weekly_stage2_state(us["spy"], ma_weeks=30, slope_weeks=4)
    # Pick a Friday well into C2 window
    c2_start_i = int(dates.searchsorted(pd.Timestamp(CONFIG["us_factors_c2_window"]["start"])))
    wk_ends = us["spy"].groupby(dates.to_period("W-SUN")).tail(1).index
    wk_cutoff_date = wk_ends[wk_ends >= pd.Timestamp("2018-06-01")][0]
    wk_cutoff_i = int(dates.searchsorted(wk_cutoff_date))
    spy_pert2 = us["spy"].copy()
    spy_pert2.iloc[wk_cutoff_i + 1 :] *= 0.25
    s2_pert = lab.weekly_stage2_state(spy_pert2, ma_weeks=30, slope_weeks=4)
    s2_eq = bool((s2_orig.iloc[c2_start_i : wk_cutoff_i + 1] == s2_pert.iloc[c2_start_i : wk_cutoff_i + 1]).all())
    checks.append(
        {
            "check": "causality_stage2_weekly",
            "passed": s2_eq,
            "cutoff_week_end": str(wk_cutoff_date.date()),
        }
    )

    return checks


def slice_period_stats(nav: pd.Series, start: str, end: str) -> dict:
    """Compute crisis/regime period return, max drawdown, and annualized vol."""
    part = nav[(nav.index >= pd.Timestamp(start)) & (nav.index <= pd.Timestamp(end))]
    if len(part) < 2:
        raise ValueError(f"Period slice too short: {start}..{end} ({len(part)} rows)")
    norm = part / part.iloc[0]
    total_ret = float(norm.iloc[-1] - 1.0)
    dd = norm / norm.cummax() - 1.0
    max_dd = float(dd.min())
    rets = norm.pct_change().dropna()
    ann_vol = float(rets.std(ddof=1) * np.sqrt(lab.TRADING_DAYS)) if len(rets) > 1 else np.nan
    return {
        "actual_start": str(part.index[0].date()),
        "actual_end": str(part.index[-1].date()),
        "n_days": int(len(part)),
        "total_return": total_ret,
        "max_dd": max_dd,
        "ann_vol": ann_vol,
    }


def add_relative_columns(
    df: pd.DataFrame,
    group_cols: list[str],
    bench_strategy: str,
) -> pd.DataFrame:
    """Attach benchmark-relative deltas and matched-cash deltas for each group."""
    df = df.copy()
    rel_cols = [
        "excess_cagr_vs_b0",
        "sharpe_diff_vs_b0",
        "calmar_diff_vs_b0",
        "mdd_improve_vs_b0",
        "cagr_vs_cash_match",
        "sharpe_vs_cash_match",
        "calmar_vs_cash_match",
        "mdd_improve_vs_cash_match",
    ]
    for col in rel_cols:
        df[col] = np.nan

    for _, grp in df.groupby(group_cols, sort=False):
        b0_rows = grp[grp["strategy"] == bench_strategy]
        if b0_rows.empty:
            continue
        b0 = b0_rows.iloc[0]
        idx = grp.index
        df.loc[idx, "excess_cagr_vs_b0"] = grp["cagr"] - b0["cagr"]
        df.loc[idx, "sharpe_diff_vs_b0"] = grp["sharpe"] - b0["sharpe"]
        df.loc[idx, "calmar_diff_vs_b0"] = grp["calmar"] - b0["calmar"]
        # Positive means smaller drawdown magnitude than B0
        df.loc[idx, "mdd_improve_vs_b0"] = grp["max_dd"] - b0["max_dd"]

        # Match each strategy against its corresponding CASH_MATCH_<strategy> if present
        cash_lookup = {
            row["matched_to"]: row
            for _, row in grp.iterrows()
            if isinstance(row.get("matched_to"), str) and row["matched_to"]
        }
        for r_idx, row in grp.iterrows():
            sname = row["strategy"]
            if sname in cash_lookup:
                cm = cash_lookup[sname]
                df.loc[r_idx, "cagr_vs_cash_match"] = row["cagr"] - cm["cagr"]
                df.loc[r_idx, "sharpe_vs_cash_match"] = row["sharpe"] - cm["sharpe"]
                df.loc[r_idx, "calmar_vs_cash_match"] = row["calmar"] - cm["calmar"]
                df.loc[r_idx, "mdd_improve_vs_cash_match"] = row["max_dd"] - cm["max_dd"]

    return df


# --------------------------------------------------------------------------- Track A: US Gold


def run_us_gold_track(us: dict, audits: list[dict]) -> tuple[pd.DataFrame, dict, dict]:
    """Run Track A (US SPY + Gold dual-core) across main 2005 and extended 2001 windows."""
    dates = us["dates"]
    cash_pos = us["cash_pos"]
    cash_neg = us["cash_neg"]

    summary_rows: list[dict] = []
    main_results_by_cost: dict[float, dict[str, lab.MultiEngineResult]] = {}
    ext_results_by_cost: dict[float, dict[str, lab.MultiEngineResult]] = {}

    for win_cfg, store in [
        (CONFIG["us_main_window"], main_results_by_cost),
        (CONFIG["us_ext_window"], ext_results_by_cost),
    ]:
        win_name = win_cfg["name"]
        start_i = int(dates.searchsorted(pd.Timestamp(win_cfg["start"])))
        gold_key = win_cfg["gold_series"]
        gold_s = us[gold_key].rename("gold")
        spy_s = us["spy"].rename("spy")
        ief_s = us["ief"].rename("ief")

        px_spy = pd.DataFrame({"spy": spy_s}, index=dates)
        px_spy_gold = pd.DataFrame({"spy": spy_s, "gold": gold_s}, index=dates)
        px_spy_gold_ief = pd.DataFrame({"spy": spy_s, "gold": gold_s, "ief": ief_s}, index=dates)

        inv_cfg = CONFIG["invvol_params"]

        for cost in CONFIG["costs"]:
            cost_bps = int(round(cost * 10000))
            run_map: dict[str, tuple[lab.MultiEngineResult, list[str], str]] = {}

            # 1. B0_SPY
            res_b0 = lab.run_multi_asset_overlay(
                px_spy,
                lab.fixed_weight_signal([1.0], dates, start_i, freq="NONE"),
                start_i,
                cost,
                cash_pos,
                cash_neg,
            )
            run_map["B0_SPY"] = (res_b0, ["spy"], "")

            # 2. GOLD_75_25_Q
            res_75 = lab.run_multi_asset_overlay(
                px_spy_gold,
                lab.fixed_weight_signal([0.75, 0.25], dates, start_i, freq="Q"),
                start_i,
                cost,
                cash_pos,
                cash_neg,
            )
            run_map["GOLD_75_25_Q"] = (res_75, ["spy", "gold"], "")

            # 3. GOLD_80_20_Q
            res_80 = lab.run_multi_asset_overlay(
                px_spy_gold,
                lab.fixed_weight_signal([0.80, 0.20], dates, start_i, freq="Q"),
                start_i,
                cost,
                cash_pos,
                cash_neg,
            )
            run_map["GOLD_80_20_Q"] = (res_80, ["spy", "gold"], "")

            # 4. GOLD_INVVOL_M
            res_iv = lab.run_multi_asset_overlay(
                px_spy_gold,
                invvol_two_asset_signal(
                    spy_s,
                    gold_s,
                    dates,
                    start_i,
                    window=inv_cfg["window"],
                    w_min=inv_cfg["primary_weight_bounds"][0],
                    w_max=inv_cfg["primary_weight_bounds"][1],
                    freq=inv_cfg["rebalance_freq"],
                    min_periods=inv_cfg["min_periods"],
                ),
                start_i,
                cost,
                cash_pos,
                cash_neg,
            )
            run_map["GOLD_INVVOL_M"] = (res_iv, ["spy", "gold"], "")

            # 5. GOLD_BOND_70_15_15_Q
            res_gb = lab.run_multi_asset_overlay(
                px_spy_gold_ief,
                lab.fixed_weight_signal([0.70, 0.15, 0.15], dates, start_i, freq="Q"),
                start_i,
                cost,
                cash_pos,
                cash_neg,
            )
            run_map["GOLD_BOND_70_15_15_Q"] = (res_gb, ["spy", "gold", "ief"], "")

            # 6. Matched average-SPY + Cash controls (monthly rebalanced)
            for base_name in ["GOLD_75_25_Q", "GOLD_80_20_Q", "GOLD_INVVOL_M", "GOLD_BOND_70_15_15_Q"]:
                base_res = run_map[base_name][0]
                full_stats = lab.summarize_result(base_res, primary_col="spy")
                w_spy = float(full_stats["avg_primary_weight"])
                res_cm = lab.run_multi_asset_overlay(
                    px_spy,
                    lab.fixed_weight_signal(
                        [w_spy], dates, start_i, freq=CONFIG["cash_match_rebalance_freq"]
                    ),
                    start_i,
                    cost,
                    cash_pos,
                    cash_neg,
                )
                run_map[f"CASH_MATCH_{base_name}"] = (res_cm, ["spy"], base_name)

            store[cost] = {k: v[0] for k, v in run_map.items()}

            for sname, (res, cols, matched_to) in run_map.items():
                audits.append(audit_result(f"{win_name}|{cost_bps}bp|{sname}", res, cols))
                is_cash_match = bool(matched_to)
                for sp in win_cfg["subperiods"]:
                    metrics = lab.summarize_result(
                        res, primary_col="spy", start=sp["start"], end=sp["end"]
                    )
                    summary_rows.append(
                        {
                            "window": win_name,
                            "gold_series": gold_key,
                            "cost_bps": cost_bps,
                            "subperiod": sp["label"],
                            "strategy": sname,
                            "is_cash_match": is_cash_match,
                            "matched_to": matched_to,
                            **metrics,
                        }
                    )

    df = pd.DataFrame(summary_rows)
    df = add_relative_columns(df, ["window", "cost_bps", "subperiod"], bench_strategy="B0_SPY")
    return df, main_results_by_cost, ext_results_by_cost


# --------------------------------------------------------------------------- Track B: Domestic RMB


def run_domestic_track(cn: dict, audits: list[dict]) -> tuple[pd.DataFrame, dict]:
    """Run Track B (Domestic RMB 513500 + 518880 gold dual-core)."""
    dates = cn["dates"]
    cash_pos = cn["cash_pos"]
    cash_neg = cn["cash_neg"]
    start_i = 0

    px_513 = pd.DataFrame({"c513500": cn["c513500"]}, index=dates)
    px_pair = pd.DataFrame({"c513500": cn["c513500"], "c518880": cn["c518880"]}, index=dates)

    win_cfg = CONFIG["domestic_window"]
    inv_cfg = CONFIG["invvol_params"]
    summary_rows: list[dict] = []
    results_by_cost: dict[float, dict[str, lab.MultiEngineResult]] = {}

    for cost in CONFIG["costs"]:
        cost_bps = int(round(cost * 10000))
        run_map: dict[str, tuple[lab.MultiEngineResult, list[str], str]] = {}

        res_b0 = lab.run_multi_asset_overlay(
            px_513,
            lab.fixed_weight_signal([1.0], dates, start_i, freq="NONE"),
            start_i,
            cost,
            cash_pos,
            cash_neg,
        )
        run_map["B0_513500"] = (res_b0, ["c513500"], "")

        res_75 = lab.run_multi_asset_overlay(
            px_pair,
            lab.fixed_weight_signal([0.75, 0.25], dates, start_i, freq="Q"),
            start_i,
            cost,
            cash_pos,
            cash_neg,
        )
        run_map["CN_75_25_Q"] = (res_75, ["c513500", "c518880"], "")

        res_80 = lab.run_multi_asset_overlay(
            px_pair,
            lab.fixed_weight_signal([0.80, 0.20], dates, start_i, freq="Q"),
            start_i,
            cost,
            cash_pos,
            cash_neg,
        )
        run_map["CN_80_20_Q"] = (res_80, ["c513500", "c518880"], "")

        res_iv = lab.run_multi_asset_overlay(
            px_pair,
            invvol_two_asset_signal(
                cn["c513500_full"],
                cn["c518880_full"],
                dates,
                start_i,
                window=inv_cfg["window"],
                w_min=inv_cfg["primary_weight_bounds"][0],
                w_max=inv_cfg["primary_weight_bounds"][1],
                freq=inv_cfg["rebalance_freq"],
                min_periods=inv_cfg["min_periods"],
            ),
            start_i,
            cost,
            cash_pos,
            cash_neg,
        )
        run_map["CN_INVVOL_M"] = (res_iv, ["c513500", "c518880"], "")

        for base_name in ["CN_75_25_Q", "CN_80_20_Q", "CN_INVVOL_M"]:
            base_res = run_map[base_name][0]
            w_pri = float(lab.summarize_result(base_res, primary_col="c513500")["avg_primary_weight"])
            res_cm = lab.run_multi_asset_overlay(
                px_513,
                lab.fixed_weight_signal(
                    [w_pri], dates, start_i, freq=CONFIG["cash_match_rebalance_freq"]
                ),
                start_i,
                cost,
                cash_pos,
                cash_neg,
            )
            run_map[f"CASH_MATCH_{base_name}"] = (res_cm, ["c513500"], base_name)

        results_by_cost[cost] = {k: v[0] for k, v in run_map.items()}

        for sname, (res, cols, matched_to) in run_map.items():
            audits.append(audit_result(f"domestic|{cost_bps}bp|{sname}", res, cols))
            is_cash_match = bool(matched_to)
            for sp in win_cfg["subperiods"]:
                metrics = lab.summarize_result(
                    res, primary_col="c513500", start=sp["start"], end=sp["end"]
                )
                summary_rows.append(
                    {
                        "window": win_cfg["name"],
                        "cost_bps": cost_bps,
                        "subperiod": sp["label"],
                        "strategy": sname,
                        "is_cash_match": is_cash_match,
                        "matched_to": matched_to,
                        **metrics,
                    }
                )

    df = pd.DataFrame(summary_rows)
    df = add_relative_columns(df, ["window", "cost_bps", "subperiod"], bench_strategy="B0_513500")
    return df, results_by_cost


# --------------------------------------------------------------------------- Track C: US Factors


def run_us_factors_track(us: dict, audits: list[dict]) -> tuple[pd.DataFrame, dict, dict]:
    """Run Track C (US S&P 500 structural factor controls C1 2006-2026 & C2 2011-2026)."""
    dates = us["dates"]
    cash_pos = us["cash_pos"]
    cash_neg = us["cash_neg"]

    spy = us["spy"].rename("spy")
    sphq = us["sphq"].rename("sphq")
    rsp = us["rsp"].rename("rsp")
    splv = us["splv"].rename("splv")
    gld = us["gld_real"].rename("gold")

    s2_cfg = CONFIG["stage2_params"]
    s2_state = lab.weekly_stage2_state(
        spy, ma_weeks=s2_cfg["ma_weeks"], slope_weeks=s2_cfg["slope_weeks"]
    )

    summary_rows: list[dict] = []
    c1_results_by_cost: dict[float, dict[str, lab.MultiEngineResult]] = {}
    c2_results_by_cost: dict[float, dict[str, lab.MultiEngineResult]] = {}

    # --- C1: 2006-01-03 to 2026-10-16
    c1_cfg = CONFIG["us_factors_c1_window"]
    c1_start_i = int(dates.searchsorted(pd.Timestamp(c1_cfg["start"])))
    px_spy = pd.DataFrame({"spy": spy}, index=dates)
    px_sphq = pd.DataFrame({"sphq": sphq}, index=dates)
    px_rsp = pd.DataFrame({"rsp": rsp}, index=dates)
    px_spy_sphq = pd.DataFrame({"spy": spy, "sphq": sphq}, index=dates)
    px_sphq_gld = pd.DataFrame({"sphq": sphq, "gold": gld}, index=dates)
    px_spy_gld = pd.DataFrame({"spy": spy, "gold": gld}, index=dates)

    for cost in CONFIG["costs"]:
        cost_bps = int(round(cost * 10000))
        run_map_c1: dict[str, tuple[lab.MultiEngineResult, list[str], str]] = {
            "B0_SPY": (
                lab.run_multi_asset_overlay(
                    px_spy, lab.fixed_weight_signal([1.0], dates, c1_start_i, freq="NONE"),
                    c1_start_i, cost, cash_pos, cash_neg,
                ),
                ["spy"],
                "spy",
            ),
            "SPHQ_100": (
                lab.run_multi_asset_overlay(
                    px_sphq, lab.fixed_weight_signal([1.0], dates, c1_start_i, freq="NONE"),
                    c1_start_i, cost, cash_pos, cash_neg,
                ),
                ["sphq"],
                "sphq",
            ),
            "RSP_100": (
                lab.run_multi_asset_overlay(
                    px_rsp, lab.fixed_weight_signal([1.0], dates, c1_start_i, freq="NONE"),
                    c1_start_i, cost, cash_pos, cash_neg,
                ),
                ["rsp"],
                "rsp",
            ),
            "SPY_SPHQ_50_50_Q": (
                lab.run_multi_asset_overlay(
                    px_spy_sphq, lab.fixed_weight_signal([0.50, 0.50], dates, c1_start_i, freq="Q"),
                    c1_start_i, cost, cash_pos, cash_neg,
                ),
                ["spy", "sphq"],
                "spy",
            ),
            "SPHQ_GLD_75_25_Q": (
                lab.run_multi_asset_overlay(
                    px_sphq_gld, lab.fixed_weight_signal([0.75, 0.25], dates, c1_start_i, freq="Q"),
                    c1_start_i, cost, cash_pos, cash_neg,
                ),
                ["sphq", "gold"],
                "sphq",
            ),
            # Reference peer on identical 2006-2026 window to isolate Quality vs SPY inside 75/25 Gold
            "SPY_GLD_75_25_Q_REF": (
                lab.run_multi_asset_overlay(
                    px_spy_gld, lab.fixed_weight_signal([0.75, 0.25], dates, c1_start_i, freq="Q"),
                    c1_start_i, cost, cash_pos, cash_neg,
                ),
                ["spy", "gold"],
                "spy",
            ),
        }
        c1_results_by_cost[cost] = {k: v[0] for k, v in run_map_c1.items()}
        for sname, (res, cols, pri_col) in run_map_c1.items():
            audits.append(audit_result(f"c1_factors|{cost_bps}bp|{sname}", res, cols))
            for sp in c1_cfg["subperiods"]:
                metrics = lab.summarize_result(res, primary_col=pri_col, start=sp["start"], end=sp["end"])
                summary_rows.append(
                    {
                        "window": c1_cfg["name"],
                        "cost_bps": cost_bps,
                        "subperiod": sp["label"],
                        "strategy": sname,
                        "matched_to": "",
                        **metrics,
                    }
                )

    # --- C2: 2011-06-01 to 2026-10-16
    c2_cfg = CONFIG["us_factors_c2_window"]
    c2_start_i = int(dates.searchsorted(pd.Timestamp(c2_cfg["start"])))
    px_splv = pd.DataFrame({"splv": splv}, index=dates)
    px_spy_splv = pd.DataFrame({"spy": spy, "splv": splv}, index=dates)

    for cost in CONFIG["costs"]:
        cost_bps = int(round(cost * 10000))
        run_map_c2: dict[str, tuple[lab.MultiEngineResult, list[str], str]] = {
            "B0_SPY": (
                lab.run_multi_asset_overlay(
                    px_spy, lab.fixed_weight_signal([1.0], dates, c2_start_i, freq="NONE"),
                    c2_start_i, cost, cash_pos, cash_neg,
                ),
                ["spy"],
                "spy",
            ),
            "SPLV_100": (
                lab.run_multi_asset_overlay(
                    px_splv, lab.fixed_weight_signal([1.0], dates, c2_start_i, freq="NONE"),
                    c2_start_i, cost, cash_pos, cash_neg,
                ),
                ["splv"],
                "splv",
            ),
            "SPY_SPLV_50_50_Q": (
                lab.run_multi_asset_overlay(
                    px_spy_splv, lab.fixed_weight_signal([0.50, 0.50], dates, c2_start_i, freq="Q"),
                    c2_start_i, cost, cash_pos, cash_neg,
                ),
                ["spy", "splv"],
                "spy",
            ),
            "SPHQ_100": (
                lab.run_multi_asset_overlay(
                    px_sphq, lab.fixed_weight_signal([1.0], dates, c2_start_i, freq="NONE"),
                    c2_start_i, cost, cash_pos, cash_neg,
                ),
                ["sphq"],
                "sphq",
            ),
            "STYLE_S2_SPLV": (
                lab.run_multi_asset_overlay(
                    px_spy_splv,
                    stage2_style_switch_signal(
                        s2_state,
                        dates,
                        c2_start_i,
                        on_weights=tuple(s2_cfg["on_weights_spy_splv"]),
                        off_weights=tuple(s2_cfg["off_weights_spy_splv"]),
                    ),
                    c2_start_i,
                    cost,
                    cash_pos,
                    cash_neg,
                ),
                ["spy", "splv"],
                "spy",
            ),
        }
        c2_results_by_cost[cost] = {k: v[0] for k, v in run_map_c2.items()}
        for sname, (res, cols, pri_col) in run_map_c2.items():
            audits.append(audit_result(f"c2_factors|{cost_bps}bp|{sname}", res, cols))
            for sp in c2_cfg["subperiods"]:
                metrics = lab.summarize_result(res, primary_col=pri_col, start=sp["start"], end=sp["end"])
                summary_rows.append(
                    {
                        "window": c2_cfg["name"],
                        "cost_bps": cost_bps,
                        "subperiod": sp["label"],
                        "strategy": sname,
                        "matched_to": "",
                        **metrics,
                    }
                )

    df = pd.DataFrame(summary_rows)
    df = add_relative_columns(df, ["window", "cost_bps", "subperiod"], bench_strategy="B0_SPY")
    return df, c1_results_by_cost, c2_results_by_cost


# --------------------------------------------------------------------------- Key crisis periods


def build_key_periods_table(
    us_main_10bp: dict[str, lab.MultiEngineResult],
    us_ext_10bp: dict[str, lab.MultiEngineResult],
    domestic_10bp: dict[str, lab.MultiEngineResult],
    factors_c1_10bp: dict[str, lab.MultiEngineResult],
    factors_c2_10bp: dict[str, lab.MultiEngineResult],
) -> pd.DataFrame:
    rows: list[dict] = []

    def append_block(track: str, results: dict[str, lab.MultiEngineResult], bench: str, periods: list[dict]):
        for p in periods:
            b_stats = slice_period_stats(results[bench].nav, p["start"], p["end"])
            for sname, res in results.items():
                st = slice_period_stats(res.nav, p["start"], p["end"])
                rows.append(
                    {
                        "track": track,
                        "period": p["period"],
                        "req_start": p["start"],
                        "req_end": p["end"],
                        "strategy": sname,
                        **st,
                        "excess_ret_vs_bench": st["total_return"] - b_stats["total_return"],
                        "mdd_improve_vs_bench": st["max_dd"] - b_stats["max_dd"],
                    }
                )

    append_block("us_main_2005", us_main_10bp, "B0_SPY", CONFIG["key_periods_us_main"])
    append_block("us_ext_2001", us_ext_10bp, "B0_SPY", CONFIG["key_periods_us_ext_extra"])
    append_block("domestic_2014", domestic_10bp, "B0_513500", CONFIG["key_periods_domestic"])
    append_block("us_factors_c1_2006", factors_c1_10bp, "B0_SPY", CONFIG["key_periods_us_main"])
    c2_periods = [p for p in CONFIG["key_periods_us_main"] if p["start"] >= "2011-06-01"]
    append_block("us_factors_c2_2011", factors_c2_10bp, "B0_SPY", c2_periods)

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- DCA evaluation


def build_dca_table(
    us_main_by_cost: dict[float, dict[str, lab.MultiEngineResult]],
    domestic_by_cost: dict[float, dict[str, lab.MultiEngineResult]],
    factors_c1_by_cost: dict[float, dict[str, lab.MultiEngineResult]],
) -> pd.DataFrame:
    rows: list[dict] = []

    def eval_track(
        track: str,
        results: dict[str, lab.MultiEngineResult],
        bench: str,
        cost: float,
        rolling_windows: list[int],
    ):
        cost_bps = int(round(cost * 10000))
        bench_nav = results[bench].nav
        bench_full = lab.dca_full_path(bench_nav, cost=cost)

        for sname, res in results.items():
            full = lab.dca_full_path(res.nav, cost=cost)
            row_base = {
                "track": track,
                "cost_bps": cost_bps,
                "strategy": sname,
                "full_n_months": full["n_months"],
                "full_xirr": full["xirr"],
                "full_xirr_diff_vs_b0": full["xirr"] - bench_full["xirr"],
                "full_max_float_loss": full["max_float_loss"],
                "full_float_loss_improve_vs_b0": full["max_float_loss"] - bench_full["max_float_loss"],
                "full_unit_max_dd": full["unit_max_dd"],
                "full_dca_ratio": full["dca_ratio"],
                "full_dca_ratio_diff_vs_b0": full["dca_ratio"] - bench_full["dca_ratio"],
                "full_terminal_per_unit": full["terminal_per_unit"],
            }
            for wm in rolling_windows:
                cmp = lab.compare_dca_windows(res.nav, bench_nav, window_months=wm, cost=cost)
                rows.append(
                    {
                        **row_base,
                        "rolling_months": wm,
                        **cmp,
                    }
                )

    for cost in CONFIG["costs"]:
        eval_track("us_main_2005", us_main_by_cost[cost], "B0_SPY", cost, CONFIG["dca_windows"]["us_main"])
        eval_track("domestic_2014", domestic_by_cost[cost], "B0_513500", cost, CONFIG["dca_windows"]["domestic"])

    # Also evaluate C1 factors at primary 10bp for completeness
    eval_track(
        "us_factors_c1_2006",
        factors_c1_by_cost[CONFIG["primary_cost"]],
        "B0_SPY",
        CONFIG["primary_cost"],
        CONFIG["dca_windows"]["us_factors_c1"],
    )

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- Sensitivity tests


def run_sensitivity_suite(
    us: dict,
    cn: dict,
    us_main_10bp: dict[str, lab.MultiEngineResult],
    domestic_10bp: dict[str, lab.MultiEngineResult],
    audits: list[dict],
) -> pd.DataFrame:
    """Parameter sensitivity checks (never used to pick winners ex-post)."""
    cost = CONFIG["primary_cost"]
    rows: list[dict] = []

    # --- US Main Window (2005-2026, real GLD, 10bp)
    dates = us["dates"]
    start_i = int(dates.searchsorted(pd.Timestamp(CONFIG["us_main_window"]["start"])))
    spy = us["spy"].rename("spy")
    gld = us["gld_real"].rename("gold")
    ief = us["ief"].rename("ief")
    px_pair = pd.DataFrame({"spy": spy, "gold": gld}, index=dates)
    px_tri = pd.DataFrame({"spy": spy, "gold": gld, "ief": ief}, index=dates)
    b0_stats = lab.summarize_result(us_main_10bp["B0_SPY"], primary_col="spy")

    def record_us(axis: str, param: str, variant: str, res: lab.MultiEngineResult, cols: list[str]):
        audits.append(audit_result(f"sens_us|{axis}|{variant}", res, cols))
        st = lab.summarize_result(res, primary_col="spy")
        rows.append(
            {
                "track": "us_main_2005",
                "axis": axis,
                "param": param,
                "variant": variant,
                "cost_bps": 10,
                **st,
                "excess_cagr_vs_b0": st["cagr"] - b0_stats["cagr"],
                "sharpe_diff_vs_b0": st["sharpe"] - b0_stats["sharpe"],
                "calmar_diff_vs_b0": st["calmar"] - b0_stats["calmar"],
                "mdd_improve_vs_b0": st["max_dd"] - b0_stats["max_dd"],
            }
        )

    # 1. Rebalance frequency (M / Q / Y / NONE) for 75/25, 80/20, and 70/15/15
    for freq in CONFIG["sensitivity"]["rebalance_freqs"]:
        res75 = lab.run_multi_asset_overlay(
            px_pair, lab.fixed_weight_signal([0.75, 0.25], dates, start_i, freq=freq),
            start_i, cost, us["cash_pos"], us["cash_neg"],
        )
        record_us("rebal_freq_75_25", freq, f"GOLD_75_25_{freq}", res75, ["spy", "gold"])

        res80 = lab.run_multi_asset_overlay(
            px_pair, lab.fixed_weight_signal([0.80, 0.20], dates, start_i, freq=freq),
            start_i, cost, us["cash_pos"], us["cash_neg"],
        )
        record_us("rebal_freq_80_20", freq, f"GOLD_80_20_{freq}", res80, ["spy", "gold"])

        res_tri = lab.run_multi_asset_overlay(
            px_tri, lab.fixed_weight_signal([0.70, 0.15, 0.15], dates, start_i, freq=freq),
            start_i, cost, us["cash_pos"], us["cash_neg"],
        )
        record_us("rebal_freq_70_15_15", freq, f"GOLD_BOND_70_15_15_{freq}", res_tri, ["spy", "gold", "ief"])

    # 2. Gold allocation weight (15% / 20% / 25% / 30%, quarterly rebalanced)
    for w_gold in CONFIG["sensitivity"]["gold_weights_q"]:
        w_spy = round(1.0 - w_gold, 4)
        res_w = lab.run_multi_asset_overlay(
            px_pair, lab.fixed_weight_signal([w_spy, w_gold], dates, start_i, freq="Q"),
            start_i, cost, us["cash_pos"], us["cash_neg"],
        )
        pct_g = int(round(w_gold * 100))
        pct_s = int(round(w_spy * 100))
        record_us("gold_weight_q", f"{pct_g}%", f"GOLD_{pct_s}_{pct_g}_Q", res_w, ["spy", "gold"])

    # 3. InvVol lookback window (21 / 42 / 63 days, monthly rebalanced, SPY in [0.50, 0.85])
    bounds = CONFIG["invvol_params"]["primary_weight_bounds"]
    for win in CONFIG["sensitivity"]["invvol_windows"]:
        res_iv = lab.run_multi_asset_overlay(
            px_pair,
            invvol_two_asset_signal(
                spy, gld, dates, start_i,
                window=win, w_min=bounds[0], w_max=bounds[1], freq="M", min_periods=21,
            ),
            start_i, cost, us["cash_pos"], us["cash_neg"],
        )
        record_us("invvol_window_m", f"{win}d", f"GOLD_INVVOL_{win}D_M", res_iv, ["spy", "gold"])

    # --- Domestic RMB Window (2014-2026, 10bp) cross-market sensitivity verification
    cn_dates = cn["dates"]
    px_cn = pd.DataFrame({"c513500": cn["c513500"], "c518880": cn["c518880"]}, index=cn_dates)
    cn_b0_stats = lab.summarize_result(domestic_10bp["B0_513500"], primary_col="c513500")

    def record_cn(axis: str, param: str, variant: str, res: lab.MultiEngineResult):
        audits.append(audit_result(f"sens_cn|{axis}|{variant}", res, ["c513500", "c518880"]))
        st = lab.summarize_result(res, primary_col="c513500")
        rows.append(
            {
                "track": "domestic_2014",
                "axis": axis,
                "param": param,
                "variant": variant,
                "cost_bps": 10,
                **st,
                "excess_cagr_vs_b0": st["cagr"] - cn_b0_stats["cagr"],
                "sharpe_diff_vs_b0": st["sharpe"] - cn_b0_stats["sharpe"],
                "calmar_diff_vs_b0": st["calmar"] - cn_b0_stats["calmar"],
                "mdd_improve_vs_b0": st["max_dd"] - cn_b0_stats["max_dd"],
            }
        )

    for freq in CONFIG["sensitivity"]["rebalance_freqs"]:
        res_cn75 = lab.run_multi_asset_overlay(
            px_cn, lab.fixed_weight_signal([0.75, 0.25], cn_dates, 0, freq=freq),
            0, cost, cn["cash_pos"], cn["cash_neg"],
        )
        record_cn("rebal_freq_75_25", freq, f"CN_75_25_{freq}", res_cn75)

    for w_gold in CONFIG["sensitivity"]["gold_weights_q"]:
        w_pri = round(1.0 - w_gold, 4)
        res_cnw = lab.run_multi_asset_overlay(
            px_cn, lab.fixed_weight_signal([w_pri, w_gold], cn_dates, 0, freq="Q"),
            0, cost, cn["cash_pos"], cn["cash_neg"],
        )
        pct_g = int(round(w_gold * 100))
        pct_s = int(round(w_pri * 100))
        record_cn("gold_weight_q", f"{pct_g}%", f"CN_{pct_s}_{pct_g}_Q", res_cnw)

    for win in CONFIG["sensitivity"]["invvol_windows"]:
        res_cniv = lab.run_multi_asset_overlay(
            px_cn,
            invvol_two_asset_signal(
                cn["c513500_full"], cn["c518880_full"], cn_dates, 0,
                window=win, w_min=bounds[0], w_max=bounds[1], freq="M", min_periods=21,
            ),
            0, cost, cn["cash_pos"], cn["cash_neg"],
        )
        record_cn("invvol_window_m", f"{win}d", f"CN_INVVOL_{win}D_M", res_cniv)

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- Main entry


def save_nav_frame(results: dict[str, lab.MultiEngineResult], path: Path) -> None:
    df = pd.DataFrame({k: v.nav for k, v in results.items()})
    df.index.name = "date"
    df.to_csv(path, float_format="%.10f")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    us = lab.load_us_bundle()
    cn = lab.load_domestic_bundle()

    # Freeze config + data diagnostics
    config_out = {
        **CONFIG,
        "data_diagnostics": {
            "us_dates": [str(us["dates"][0].date()), str(us["dates"][-1].date()), int(len(us["dates"]))],
            "gold_diag": us["gold_diag"],
            "domestic_dates": [
                str(cn["dates"][0].date()),
                str(cn["dates"][-1].date()),
                int(len(cn["dates"])),
            ],
        },
    }
    (OUT_DIR / "config.json").write_text(
        json.dumps(config_out, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    audits: list[dict] = []

    # Run all tracks
    df_us_gold, us_main_by_cost, us_ext_by_cost = run_us_gold_track(us, audits)
    df_domestic, domestic_by_cost = run_domestic_track(cn, audits)
    df_factors, c1_by_cost, c2_by_cost = run_us_factors_track(us, audits)

    # Key crisis periods
    df_periods = build_key_periods_table(
        us_main_by_cost[CONFIG["primary_cost"]],
        us_ext_by_cost[CONFIG["primary_cost"]],
        domestic_by_cost[CONFIG["primary_cost"]],
        c1_by_cost[CONFIG["primary_cost"]],
        c2_by_cost[CONFIG["primary_cost"]],
    )

    # DCA evaluation
    df_dca = build_dca_table(us_main_by_cost, domestic_by_cost, c1_by_cost)

    # Sensitivity suite
    df_sens = run_sensitivity_suite(
        us,
        cn,
        us_main_by_cost[CONFIG["primary_cost"]],
        domestic_by_cost[CONFIG["primary_cost"]],
        audits,
    )

    # Save required CSVs
    df_us_gold.to_csv(OUT_DIR / "summary_us_gold.csv", index=False)
    df_domestic.to_csv(OUT_DIR / "summary_domestic_gold.csv", index=False)
    df_factors.to_csv(OUT_DIR / "summary_us_factors.csv", index=False)
    df_periods.to_csv(OUT_DIR / "key_periods.csv", index=False)
    df_dca.to_csv(OUT_DIR / "dca_summary.csv", index=False)
    df_sens.to_csv(OUT_DIR / "sensitivity.csv", index=False)

    # Save daily NAVs (10bp) for parent coordinator verification
    save_nav_frame(us_main_by_cost[CONFIG["primary_cost"]], OUT_DIR / "nav_us_2005_10bp.csv")
    save_nav_frame(domestic_by_cost[CONFIG["primary_cost"]], OUT_DIR / "nav_domestic_10bp.csv")
    save_nav_frame(c1_by_cost[CONFIG["primary_cost"]], OUT_DIR / "nav_factors_2006_10bp.csv")
    save_nav_frame(c2_by_cost[CONFIG["primary_cost"]], OUT_DIR / "nav_factors_2011_10bp.csv")

    # Causality & accounting self-checks
    causality = run_causality_checks(us, cn)
    all_runs_passed = all(a["passed"] for a in audits)
    all_causality_passed = all(c["passed"] for c in causality)
    self_checks = {
        "overall_passed": bool(all_runs_passed and all_causality_passed),
        "total_runs_checked": int(len(audits)),
        "runs_passed": int(sum(1 for a in audits if a["passed"])),
        "runs_failed": int(sum(1 for a in audits if not a["passed"])),
        "worst_max_cash_residual": float(max(a["max_cash_residual"] for a in audits)),
        "global_nav_min": float(min(a["nav_min"] for a in audits)),
        "any_nav_nan": bool(any(a["nav_has_nan"] for a in audits)),
        "any_weights_nan": bool(any(a["weights_has_nan"] for a in audits)),
        "global_target_sum_max": float(max(a["target_sum_max"] for a in audits)),
        "global_actual_asset_sum_max": float(max(a["actual_asset_sum_max"] for a in audits)),
        "global_actual_asset_min": float(min(a["actual_asset_min"] for a in audits)),
        "causality_checks": causality,
        "failed_runs": [a for a in audits if not a["passed"]],
        "per_run_audits": audits,
    }
    (OUT_DIR / "self_checks.json").write_text(
        json.dumps(self_checks, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Done. Output written to {OUT_DIR}")
    print(
        f"Self-checks overall_passed={self_checks['overall_passed']} "
        f"({self_checks['runs_passed']}/{self_checks['total_runs_checked']} runs, "
        f"worst_cash_resid={self_checks['worst_max_cash_residual']:.3e}, "
        f"nav_min={self_checks['global_nav_min']:.4f}, "
        f"asset_sum_max={self_checks['global_actual_asset_sum_max']:.6f})"
    )
    if not self_checks["overall_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
