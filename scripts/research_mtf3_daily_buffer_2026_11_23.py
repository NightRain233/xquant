"""Formal Research Study: Daily Buffered MTF-3 (Spatial Hysteresis Replacing Calendar Month-End).

Pre-registered hypothesis (2026-11-23):
Calendar-locked MTF-3 (30W Friday + 10M month-end) filters noise via calendar waiting, which delays
both defensive exits during mid-month crashes and re-entry during recoveries. Replacing calendar
waiting with daily closing evaluation + symmetric spatial hysteresis buffer (±2% / ±3% around
150-day rising SMA and 210-day SMA) may preserve deep-bear drawdown control while reducing turnover,
improving Sharpe/Calmar, and narrowing bull-market drag—WITHOUT degrading robustness across rolling
10-year DCA, annual starts, safe-haven shields, gold bear markets, or parameter neighborhoods.

Run (offline sandbox, from repo root):
    .venv/bin/python -I scripts/research_mtf3_daily_buffer_2026_11_23.py
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
from xquant import sp500_lab as lab  # noqa: E402
from xquant.weinstein_stage import load_yfinance_csv  # noqa: E402

SLUG = "mtf3-daily-buffer-2026-11-23"
OUT_DIR = ROOT / "outputs" / SLUG
QQQ_CACHE = ROOT / "outputs" / "weinstein-quick-checks-2026-10-18" / "cache" / "yf_QQQ.csv"

CONFIG: dict[str, Any] = {
    "slug": SLUG,
    "execution_clock": "Signal at close t using data <= t only; order fills at close t+1 with proportional one-way cost.",
    "primary_candidates": {
        "MTF3_BUF2": {"ma_fast": 150, "slope_days": 20, "ma_slow": 210, "buffer": 0.02},
        "MTF3_BUF3": {"ma_fast": 150, "slope_days": 20, "ma_slow": 210, "buffer": 0.03},
    },
    "controls": {
        "B0": "100% Buy & Hold",
        "S2_CASH": "Weekly 30W rising SMA (100% / 50%)",
        "MTF3_ORIG": "Weekly 30W rising SMA + Monthly 10M SMA (100% / 50% / 0%)",
        "MTF3_D0": "Daily 150d rising SMA + 210d SMA, 0% buffer (whipsaw control)",
        "GOLD_75_25_Q": "75% Equity + 25% Gold, quarterly rebalanced",
        "S2_GOLD": "S2 with 50% defensive leg in Gold",
        "S2_GOLD_TREND": "S2 with 50% defensive leg in Gold only when Gold 30W trend is ON",
        "S2_BOND_GOLD": "S2 with 50% defensive leg split 25% Gold + 25% IEF",
    },
    "windows": {
        "us_2000": ["2000-01-03", lab.US_END],
        "us_2005_shields": [lab.US_GLD_START, lab.US_END],
        "gold_bear_stress": ["2011-09-01", "2022-12-31"],
        "domestic_2014": [lab.DOMESTIC_START, lab.DOMESTIC_END],
    },
    "costs": {"10bp": 0.001, "30bp": 0.003, "50bp": 0.005},
    "sensitivity_grid": {
        "buffers": [0.0, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04],
        "ma_pairs": [[120, 180], [150, 210], [180, 240]],
    },
    "circular_shift_trials": 200,
    "pre_registered_bars": {
        "beats_orig_mtf3_sharpe_and_calmar_at_10bp_and_30bp": True,
        "lower_turnover_than_orig_mtf3": True,
        "max_dd_near_orig_mtf3_cap": -0.22,
        "10y_dca_ratio_win_rate_ge_80pct": 0.80,
        "robust_across_buffer_1p5_to_3p0_without_magic_spike": True,
    },
}


# --------------------------------------------------------------------------- Fast exact DCA helpers
def _fast_xirr(amounts: np.ndarray, year_fracs: np.ndarray) -> float:
    """Solve sum(amount * (1 + r)**(-t)) == 0 via Newton-Raphson with bisection fallback."""
    if not (np.any(amounts > 0) and np.any(amounts < 0)):
        return np.nan
    r = 0.08
    for _ in range(30):
        base = 1.0 + r
        if base <= 1e-6:
            break
        disc = base ** (-year_fracs)
        f = float(np.dot(amounts, disc))
        df = float(-np.dot(amounts * year_fracs, disc) / base)
        if abs(df) < 1e-14:
            break
        step = f / df
        r_new = r - step
        if r_new <= -0.99 or r_new > 10.0:
            break
        r = r_new
        if abs(step) < 1e-9:
            return float(r)
    lo, hi = -0.95, 5.0
    f_lo = float(np.dot(amounts, (1.0 + lo) ** (-year_fracs)))
    f_hi = float(np.dot(amounts, (1.0 + hi) ** (-year_fracs)))
    if f_lo * f_hi > 0:
        return np.nan
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        f_mid = float(np.dot(amounts, (1.0 + mid) ** (-year_fracs)))
        if abs(f_mid) < 1e-10 or (hi - lo) < 1e-9:
            return float(mid)
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return float(0.5 * (lo + hi))


def fast_dca_rolling_windows(nav: pd.Series, window_months: int = 120, cost: float = 0.001) -> pd.DataFrame:
    """Exact monthly DCA rolling windows matching sp500_lab.dca_rolling_windows."""
    nav_arr = nav.to_numpy(dtype=float)
    dates = pd.DatetimeIndex(nav.index)
    month_starts = np.flatnonzero(~dates.to_period("M").duplicated())
    rows: list[dict[str, Any]] = []
    if len(month_starts) < window_months:
        return pd.DataFrame(rows)
    d_yrs = (dates - dates[0]).days.to_numpy(dtype=np.float64) / 365.25
    for k in range(0, len(month_starts) - window_months + 1):
        idxs = month_starts[k : k + window_months]
        i0 = int(idxs[0])
        i1 = int(month_starts[k + window_months] - 1) if (k + window_months) < len(month_starts) else (len(nav_arr) - 1)
        sub_nav = nav_arr[i0 : i1 + 1]
        buy_rel = idxs - i0
        units_bought = (1.0 - cost) / sub_nav[buy_rel]
        cum_units = np.zeros(len(sub_nav), dtype=float)
        cum_prin = np.zeros(len(sub_nav), dtype=float)
        np.add.at(cum_units, buy_rel, units_bought)
        np.add.at(cum_prin, buy_rel, 1.0)
        cum_units = np.cumsum(cum_units)
        cum_prin = np.cumsum(cum_prin)
        val = cum_units * sub_nav
        max_prin_dd = float(np.min(val / cum_prin - 1.0))
        twr_dd = float(np.min(sub_nav / np.maximum.accumulate(sub_nav) - 1.0))
        term = float(val[-1])
        amounts = np.empty(window_months + 1, dtype=float)
        amounts[:window_months] = -1.0
        amounts[-1] = term
        t0 = d_yrs[i0]
        yfracs = np.empty(window_months + 1, dtype=float)
        yfracs[:window_months] = d_yrs[idxs] - t0
        yfracs[-1] = d_yrs[i1] - t0
        xirr = _fast_xirr(amounts, yfracs)
        assert np.isfinite(xirr), f"Non-finite XIRR at {dates[i0].date()} -> {dates[i1].date()}"
        ratio = float(xirr / abs(twr_dd)) if (np.isfinite(xirr) and twr_dd < 0) else np.nan
        rows.append(
            {
                "start": str(dates[i0].date()),
                "end": str(dates[i1].date()),
                "xirr": xirr,
                "twr_max_dd": twr_dd,
                "max_principal_dd": max_prin_dd,
                "ret_dd_ratio": ratio,
                "terminal_multiple": term / float(window_months),
            }
        )
    return pd.DataFrame(rows)


def rolling_loss_probabilities(nav: pd.Series, horizons_years: tuple[int, ...] = (1, 3, 5, 10)) -> dict[str, float]:
    """Fraction of daily entry points with negative return after N calendar years."""
    dates = pd.DatetimeIndex(nav.index)
    vals = nav.to_numpy(dtype=float)
    out: dict[str, float] = {}
    for yr in horizons_years:
        target_dates = dates + pd.DateOffset(years=yr)
        end_pos = np.searchsorted(dates.to_numpy(), target_dates.to_numpy(), side="left")
        valid = end_pos < len(vals)
        if valid.sum() < 20:
            out[f"loss_prob_{yr}y"] = np.nan
            out[f"worst_cagr_{yr}y"] = np.nan
            continue
        ret = vals[end_pos[valid]] / vals[valid] - 1.0
        out[f"loss_prob_{yr}y"] = float(np.mean(ret < 0.0))
        out[f"worst_cagr_{yr}y"] = float((1.0 + np.min(ret)) ** (1.0 / yr) - 1.0)
    return out


# --------------------------------------------------------------------------- Signal builders
def matrix_signal(weight_matrix: np.ndarray, start_i: int):
    """Emit target weight row on start_i and whenever target row changes."""
    def sig(i: int, _actual: np.ndarray):
        if i == start_i or (i > start_i and not np.array_equal(weight_matrix[i], weight_matrix[i - 1])):
            return weight_matrix[i]
        return None
    return sig


def build_shield_weights(
    eq_w: np.ndarray,
    gold_trend: np.ndarray,
    mode: str,
) -> np.ndarray:
    """Build (N, 3) weights for [eq, gold, ief] given equity weight eq_w and defensive mode."""
    n = len(eq_w)
    w = np.zeros((n, 3), dtype=float)
    w[:, 0] = eq_w
    rem = 1.0 - eq_w
    if mode == "cash":
        pass
    elif mode == "gold":
        w[:, 1] = rem
    elif mode == "gold_trend":
        w[:, 1] = np.where(gold_trend, rem, 0.0)
    elif mode == "bond_gold":
        w[:, 1] = 0.5 * rem
        w[:, 2] = 0.5 * rem
    else:
        raise ValueError(mode)
    return w


def build_tvt50_signal(close: pd.Series, start_i: int, gold_trend: np.ndarray | None = None, mode: str = "cash", ncols: int = 3):
    vol = np.log(close).diff().rolling(21).std(ddof=1).to_numpy(dtype=float) * np.sqrt(252.0)
    trend = lab.weekly_stage2_state(close, ma_weeks=30, slope_weeks=4).to_numpy(dtype=bool)

    def sig(i: int, actual: np.ndarray):
        v = vol[i]
        if not np.isfinite(v) or v <= 0.0:
            return None
        cap = 1.0 if trend[i] else 0.50
        w_eq = float(np.clip(min(cap, 0.15 / v), 0.0, 1.0))
        rem = 1.0 - w_eq
        w_gold = 0.0
        if mode == "gold":
            w_gold = rem
        elif mode == "gold_trend" and gold_trend is not None:
            w_gold = rem if gold_trend[i] else 0.0
        wanted = np.zeros(ncols, dtype=float)
        wanted[0] = w_eq
        if ncols > 1:
            wanted[1] = w_gold
        if i == start_i:
            return wanted
        if max(abs(wanted[0] - actual[0]), abs(wanted[1] - actual[1]) if ncols > 1 else 0.0) > 0.10:
            return wanted
        return None
    return sig


def run_and_check(prices: pd.DataFrame, sig, start_i: int, cost: float, cash_pos, cash_neg, checks_agg: dict):
    res = lab.run_multi_asset_overlay(prices, sig, start_i, cost, cash_pos, cash_neg)
    checks_agg["max_cash_residual"] = max(checks_agg["max_cash_residual"], res.checks["max_cash_residual"])
    checks_agg["min_nav"] = min(checks_agg["min_nav"], res.checks["nav_min"])
    checks_agg["min_target_weight"] = min(checks_agg["min_target_weight"], res.checks["target_weight_min"])
    checks_agg["max_target_sum"] = max(checks_agg["max_target_sum"], res.checks["target_sum_max"])
    checks_agg["runs"] += 1
    return res


def circular_shift_test(
    close: pd.Series,
    eq_w: np.ndarray,
    start_i: int,
    cash_pos: np.ndarray,
    cash_neg: np.ndarray,
    cost: float = 0.001,
    n_trials: int = 200,
) -> dict[str, float]:
    """Compare true timing Sharpe/Calmar against circularly shifted weight sequences."""
    prices = pd.DataFrame({"eq": close}, index=close.index)
    true_res = lab.run_multi_asset_overlay(prices, matrix_signal(eq_w[:, None], start_i), start_i, cost, cash_pos, cash_neg)
    true_m = lab.summarize_result(true_res, primary_col="eq")
    w_active = eq_w[start_i:]
    m = len(w_active)
    shifts = np.linspace(21, m - 21, n_trials, dtype=int)
    beat_sharpe = 0
    beat_calmar = 0
    beat_dd = 0
    for sh in shifts:
        rolled = np.empty_like(eq_w)
        rolled[:start_i] = eq_w[:start_i]
        rolled[start_i:] = np.roll(w_active, int(sh))
        r = lab.run_multi_asset_overlay(prices, matrix_signal(rolled[:, None], start_i), start_i, cost, cash_pos, cash_neg)
        rm = lab.summarize_result(r, primary_col="eq")
        if rm["sharpe"] >= true_m["sharpe"]:
            beat_sharpe += 1
        if rm["calmar"] >= true_m["calmar"]:
            beat_calmar += 1
        if rm["max_dd"] >= true_m["max_dd"]:
            beat_dd += 1
    return {
        "true_sharpe": true_m["sharpe"],
        "true_calmar": true_m["calmar"],
        "true_max_dd": true_m["max_dd"],
        "p_sharpe": beat_sharpe / n_trials,
        "p_calmar": beat_calmar / n_trials,
        "p_max_dd": beat_dd / n_trials,
        "n_trials": n_trials,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    checks_agg = {
        "runs": 0,
        "max_cash_residual": 0.0,
        "min_nav": float("inf"),
        "min_target_weight": float("inf"),
        "max_target_sum": 0.0,
    }

    us = lab.load_us_bundle()
    qqq = load_yfinance_csv(QQQ_CACHE)["close"].reindex(us["dates"]).ffill().rename("qqq")
    cn = lab.load_domestic_bundle()

    # ----------------------------------------------------------------------- 0. Anti-lookahead perturbation self-check
    spy_full = us["spy"]
    cutoff = pd.Timestamp("2015-06-30")
    spy_pert = spy_full.copy()
    spy_pert.loc[spy_pert.index > cutoff] *= 0.4
    w_clean = lab.daily_buffered_mtf3_equity_weight(spy_full, buffer=0.03)
    w_pert = lab.daily_buffered_mtf3_equity_weight(spy_pert, buffer=0.03)
    si_check = int(spy_full.index.searchsorted(pd.Timestamp("2000-01-03")))
    r_clean = lab.run_multi_asset_overlay(
        pd.DataFrame({"spy": spy_full}), matrix_signal(w_clean.to_numpy()[:, None], si_check),
        si_check, 0.001, us["cash_pos"], us["cash_neg"],
    )
    r_pert = lab.run_multi_asset_overlay(
        pd.DataFrame({"spy": spy_pert}), matrix_signal(w_pert.to_numpy()[:, None], si_check),
        si_check, 0.001, us["cash_pos"], us["cash_neg"],
    )
    lookahead_nav_diff = float(np.max(np.abs(
        r_clean.nav.loc[:cutoff].to_numpy() - r_pert.nav.loc[:cutoff].to_numpy()
    )))
    assert lookahead_nav_diff == 0.0, f"Lookahead violation: {lookahead_nav_diff}"
    checks_agg["anti_lookahead_perturbation_max_diff"] = lookahead_nav_diff

    # Precompute core US signals on SPY and QQQ
    def compute_eq_signals(close: pd.Series) -> dict[str, np.ndarray]:
        w_s2 = lab.weekly_stage2_state(close, ma_weeks=30, slope_weeks=4).to_numpy(dtype=bool)
        m_10 = lab.monthly_ma_state(close, ma_months=10).to_numpy(dtype=bool)
        score_orig = w_s2.astype(int) + m_10.astype(int)
        return {
            "B0": np.ones(len(close), dtype=float),
            "S2": np.where(w_s2, 1.0, 0.5),
            "MTF3_ORIG": np.where(score_orig == 2, 1.0, np.where(score_orig == 1, 0.5, 0.0)),
            "MTF3_D0": lab.daily_buffered_mtf3_equity_weight(close, buffer=0.0).to_numpy(dtype=float),
            "MTF3_BUF2": lab.daily_buffered_mtf3_equity_weight(close, buffer=0.02).to_numpy(dtype=float),
            "MTF3_BUF3": lab.daily_buffered_mtf3_equity_weight(close, buffer=0.03).to_numpy(dtype=float),
        }

    spy_sigs = compute_eq_signals(us["spy"])
    qqq_sigs = compute_eq_signals(qqq)
    gld_real_trend = lab.weekly_stage2_state(us["gld_real"].dropna(), ma_weeks=30, slope_weeks=4).reindex(us["dates"]).fillna(False).to_numpy(dtype=bool)
    gld_spliced_trend = lab.weekly_stage2_state(us["gold_spliced"].dropna(), ma_weeks=30, slope_weeks=4).reindex(us["dates"]).fillna(False).to_numpy(dtype=bool)

    # ----------------------------------------------------------------------- 1. Track 1: SPY & QQQ 26-year (2000-2026)
    si_2000 = int(us["dates"].searchsorted(pd.Timestamp("2000-01-03")))
    rows_spy_2000: list[dict] = []
    rows_qqq_2000: list[dict] = []
    spy_navs_2000: dict[str, pd.Series] = {}
    qqq_navs_2000: dict[str, pd.Series] = {}
    spy_navs_2000_30bp: dict[str, pd.Series] = {}
    qqq_navs_2000_30bp: dict[str, pd.Series] = {}

    for asset_name, close, sigs, out_rows, nav_store, nav_store_30 in [
        ("SPY", us["spy"], spy_sigs, rows_spy_2000, spy_navs_2000, spy_navs_2000_30bp),
        ("QQQ", qqq, qqq_sigs, rows_qqq_2000, qqq_navs_2000, qqq_navs_2000_30bp),
    ]:
        px_df = pd.DataFrame({"eq": close, "gold": us["gold_spliced"].fillna(1.0), "ief": us["ief"]}, index=us["dates"])
        for cost_label, cost_val in [("10bp", 0.001), ("30bp", 0.003), ("50bp", 0.005)]:
            for sname in ["B0", "S2", "MTF3_ORIG", "MTF3_D0", "MTF3_BUF2", "MTF3_BUF3", "TVT50"]:
                if sname == "TVT50":
                    sig = build_tvt50_signal(close, si_2000, mode="cash", ncols=3)
                else:
                    sig = matrix_signal(build_shield_weights(sigs[sname], gld_spliced_trend, "cash"), si_2000)
                res = run_and_check(px_df, sig, si_2000, cost_val, us["cash_pos"], us["cash_neg"], checks_agg)
                if cost_label == "10bp":
                    nav_store[sname] = res.nav
                elif cost_label == "30bp":
                    nav_store_30[sname] = res.nav
                for seg, (s_dt, e_dt) in [("full", ("2000-01-03", lab.US_END)), ("2000-2012", ("2000-01-03", "2012-12-31")), ("2013-2026", ("2013-01-01", lab.US_END))]:
                    m = lab.summarize_result(res, primary_col="eq", start=s_dt, end=e_dt)
                    lp = rolling_loss_probabilities(res.nav) if seg == "full" else {}
                    out_rows.append({"asset": asset_name, "cost": cost_label, "segment": seg, "strategy": sname, **m, **lp})
            # Fixed-exposure matched controls at 10bp for MTF3_BUF2 & MTF3_BUF3
            if cost_label == "10bp":
                for ref in ["MTF3_BUF2", "MTF3_BUF3"]:
                    avg_w = float(np.mean(sigs[ref][si_2000:]))
                    sig = lab.fixed_weight_signal([avg_w, 0.0, 0.0], us["dates"], si_2000, freq="M")
                    res = run_and_check(px_df, sig, si_2000, cost_val, us["cash_pos"], us["cash_neg"], checks_agg)
                    m = lab.summarize_result(res, primary_col="eq")
                    out_rows.append({"asset": asset_name, "cost": cost_label, "segment": "full", "strategy": f"FIXED_MATCH_{ref}", **m})

    pd.DataFrame(rows_spy_2000).to_csv(OUT_DIR / "summary_spy_2000.csv", index=False)
    pd.DataFrame(rows_qqq_2000).to_csv(OUT_DIR / "summary_qqq_2000.csv", index=False)

    # ----------------------------------------------------------------------- 2. Track 2: Shields (2005-2026 pure GLD) + Gold Bear Stress (2011-09 to 2022-12)
    si_2005 = int(us["dates"].searchsorted(pd.Timestamp(lab.US_GLD_START)))
    px_us_2005 = pd.DataFrame({"eq": us["spy"], "gold": us["gld_real"], "ief": us["ief"]}, index=us["dates"])
    px_qqq_2005 = pd.DataFrame({"eq": qqq, "gold": us["gld_real"], "ief": us["ief"]}, index=us["dates"])

    shield_specs = [
        ("B0_SPY", "B0", "cash"),
        ("GOLD_75_25_Q", "FIXED_75_25", "gold"),
        ("S2_CASH", "S2", "cash"),
        ("S2_GOLD", "S2", "gold"),
        ("S2_GOLD_TREND", "S2", "gold_trend"),
        ("S2_BOND_GOLD", "S2", "bond_gold"),
        ("MTF3_ORIG_CASH", "MTF3_ORIG", "cash"),
        ("MTF3_ORIG_GOLD", "MTF3_ORIG", "gold"),
        ("MTF3_BUF2_CASH", "MTF3_BUF2", "cash"),
        ("MTF3_BUF2_GOLD", "MTF3_BUF2", "gold"),
        ("MTF3_BUF2_GOLD_TREND", "MTF3_BUF2", "gold_trend"),
        ("MTF3_BUF2_BOND_GOLD", "MTF3_BUF2", "bond_gold"),
        ("MTF3_BUF3_CASH", "MTF3_BUF3", "cash"),
        ("MTF3_BUF3_GOLD", "MTF3_BUF3", "gold"),
        ("MTF3_BUF3_GOLD_TREND", "MTF3_BUF3", "gold_trend"),
        ("MTF3_BUF3_BOND_GOLD", "MTF3_BUF3", "bond_gold"),
    ]
    rows_shields: list[dict] = []
    rows_gold_bear: list[dict] = []
    shield_navs_10bp: dict[str, pd.Series] = {}
    shield_navs_30bp: dict[str, pd.Series] = {}
    qqq_shield_navs_10bp: dict[str, pd.Series] = {}

    for track_label, px_df, eq_sigs in [("SPY", px_us_2005, spy_sigs), ("QQQ", px_qqq_2005, qqq_sigs)]:
        for cost_label, cost_val in [("10bp", 0.001), ("30bp", 0.003), ("50bp", 0.005)]:
            for strat_name, base, mode in shield_specs:
                label = strat_name if track_label == "SPY" else strat_name.replace("SPY", "QQQ")
                if base == "FIXED_75_25":
                    sig = lab.fixed_weight_signal([0.75, 0.25, 0.0], us["dates"], si_2005, freq="Q")
                else:
                    sig = matrix_signal(build_shield_weights(eq_sigs[base], gld_real_trend, mode), si_2005)
                res = run_and_check(px_df, sig, si_2005, cost_val, us["cash_pos"], us["cash_neg"], checks_agg)
                if track_label == "SPY" and cost_label == "10bp":
                    shield_navs_10bp[label] = res.nav
                elif track_label == "SPY" and cost_label == "30bp":
                    shield_navs_30bp[label] = res.nav
                elif track_label == "QQQ" and cost_label == "10bp":
                    qqq_shield_navs_10bp[label] = res.nav

                for seg, (s_dt, e_dt) in [("full", (lab.US_GLD_START, lab.US_END)), ("2005-2012", (lab.US_GLD_START, "2012-12-31")), ("2013-2026", ("2013-01-01", lab.US_END))]:
                    m = lab.summarize_result(res, primary_col="eq", start=s_dt, end=e_dt)
                    rows_shields.append({"asset": track_label, "cost": cost_label, "segment": seg, "strategy": label, **m})

                if cost_label == "10bp":
                    mgb = lab.summarize_result(res, primary_col="eq", start="2011-09-01", end="2022-12-31")
                    rows_gold_bear.append({"asset": track_label, "cost": cost_label, "strategy": label, **mgb})

    pd.DataFrame(rows_shields).to_csv(OUT_DIR / "summary_us_2005_shields.csv", index=False)
    pd.DataFrame(rows_gold_bear).to_csv(OUT_DIR / "gold_bear_stress_2011_2022.csv", index=False)

    # ----------------------------------------------------------------------- 3. Track 3: 10-Year Rolling Monthly DCA
    dca_rows: list[dict] = []
    for scope, nav_map, base_key, cost_val, cost_label in [
        ("SPY_2000_2026", spy_navs_2000, "B0", 0.001, "10bp"),
        ("SPY_2000_2026", spy_navs_2000_30bp, "B0", 0.003, "30bp"),
        ("QQQ_2000_2026", qqq_navs_2000, "B0", 0.001, "10bp"),
        ("SPY_SHIELDS_2005_2026", shield_navs_10bp, "B0_SPY", 0.001, "10bp"),
        ("SPY_SHIELDS_2005_2026", shield_navs_30bp, "B0_SPY", 0.003, "30bp"),
        ("QQQ_SHIELDS_2005_2026", qqq_shield_navs_10bp, "B0_QQQ", 0.001, "10bp"),
    ]:
        base_w = fast_dca_rolling_windows(nav_map[base_key], window_months=120, cost=cost_val)
        for sname, nav in nav_map.items():
            w = fast_dca_rolling_windows(nav, window_months=120, cost=cost_val)
            full_d = lab.dca_full_path(nav, cost=cost_val)
            dca_rows.append(
                {
                    "scope": scope,
                    "cost": cost_label,
                    "strategy": sname,
                    "n_windows": len(w),
                    "full_xirr": full_d["xirr"],
                    "full_max_principal_dd": full_d["max_float_loss"],
                    "full_terminal_per_1": full_d["terminal_per_unit"],
                    "med_10y_xirr": float(w["xirr"].median()),
                    "worst_10y_xirr": float(w["xirr"].min()),
                    "med_10y_max_prin_dd": float(w["max_principal_dd"].median()),
                    "worst_10y_max_prin_dd": float(w["max_principal_dd"].min()),
                    "xirr_win_vs_b0": float(np.mean(w["xirr"].to_numpy() > base_w["xirr"].to_numpy())),
                    "ratio_win_vs_b0": float(np.mean(w["ret_dd_ratio"].to_numpy() > base_w["ret_dd_ratio"].to_numpy())),
                }
            )
    pd.DataFrame(dca_rows).to_csv(OUT_DIR / "rolling_dca_10y.csv", index=False)

    # ----------------------------------------------------------------------- 4. Track 4: Annual Rolling Starts (2000-2023)
    start_rows: list[dict] = []
    for asset_name, nav_map, base_key in [("SPY", spy_navs_2000, "B0"), ("QQQ", qqq_navs_2000, "B0")]:
        b0_nav = nav_map[base_key]
        rf_full = us["cash_pos"] - 1.0
        rf_ser = pd.Series(rf_full, index=us["dates"])
        for yr in range(2000, 2024):
            s_dt = f"{yr}-01-01"
            b0_slice = b0_nav[b0_nav.index >= s_dt]
            b0_yrs = (b0_slice.index[-1] - b0_slice.index[0]).days / 365.25
            b0_cagr = float((b0_slice.iloc[-1] / b0_slice.iloc[0]) ** (1.0 / b0_yrs) - 1.0)
            b0_ret = b0_slice.pct_change().dropna()
            b0_ex = b0_ret - rf_ser.reindex(b0_ret.index).fillna(0.0)
            b0_sh = float(b0_ex.mean() / b0_ex.std(ddof=1) * np.sqrt(252.0))
            b0_dd = float((b0_slice / b0_slice.cummax() - 1.0).min())
            b0_cal = b0_cagr / abs(b0_dd)
            for sname in ["S2", "MTF3_ORIG", "MTF3_BUF2", "MTF3_BUF3", "TVT50"]:
                nv = nav_map[sname]
                sl = nv[nv.index >= s_dt]
                yrs = (sl.index[-1] - sl.index[0]).days / 365.25
                cagr = float((sl.iloc[-1] / sl.iloc[0]) ** (1.0 / yrs) - 1.0)
                ret = sl.pct_change().dropna()
                ex = ret - rf_ser.reindex(ret.index).fillna(0.0)
                sh = float(ex.mean() / ex.std(ddof=1) * np.sqrt(252.0))
                dd = float((sl / sl.cummax() - 1.0).min())
                cal = cagr / abs(dd)
                start_rows.append(
                    {
                        "asset": asset_name,
                        "start_year": yr,
                        "strategy": sname,
                        "cagr": cagr,
                        "b0_cagr": b0_cagr,
                        "cagr_diff": cagr - b0_cagr,
                        "sharpe": sh,
                        "b0_sharpe": b0_sh,
                        "beat_sharpe": int(sh > b0_sh),
                        "max_dd": dd,
                        "b0_max_dd": b0_dd,
                        "dd_reduction_pct": (abs(b0_dd) - abs(dd)) / abs(b0_dd),
                        "calmar": cal,
                        "b0_calmar": b0_cal,
                        "beat_calmar": int(cal > b0_cal),
                    }
                )
    pd.DataFrame(start_rows).to_csv(OUT_DIR / "rolling_starts_annual.csv", index=False)

    # ----------------------------------------------------------------------- 5. Track 5: Domestic 513500 (Self + Strict US T-1 Signal)
    cn_dates = cn["dates"]
    px_cn = pd.DataFrame({"eq": cn["c513500"], "gold": cn["c518880"], "ief": cn["c518880"]}, index=cn_dates)
    cn_gold_trend = lab.weekly_stage2_state(cn["c518880_full"], ma_weeks=30, slope_weeks=4).reindex(cn_dates).fillna(False).to_numpy(dtype=bool)
    cn_self_w = lab.weekly_stage2_state(cn["c513500_full"], ma_weeks=30, slope_weeks=4).reindex(cn_dates).fillna(False).to_numpy(dtype=bool)
    cn_self_m = lab.monthly_ma_state(cn["c513500_full"], ma_months=10).reindex(cn_dates).fillna(False).to_numpy(dtype=bool)
    cn_self_orig = np.where(cn_self_w.astype(int) + cn_self_m.astype(int) == 2, 1.0, np.where(cn_self_w.astype(int) + cn_self_m.astype(int) == 1, 0.5, 0.0))
    cn_self_buf3 = lab.daily_buffered_mtf3_equity_weight(cn["c513500_full"], buffer=0.03).reindex(cn_dates).fillna(0.0).to_numpy(dtype=float)

    us_buf2_mapped, lag2 = lab.map_us_series_to_cn_strict(pd.Series(spy_sigs["MTF3_BUF2"], index=us["dates"]), cn_dates)
    us_buf3_mapped, lag3 = lab.map_us_series_to_cn_strict(pd.Series(spy_sigs["MTF3_BUF3"], index=us["dates"]), cn_dates)
    us_orig_mapped, lag0 = lab.map_us_series_to_cn_strict(pd.Series(spy_sigs["MTF3_ORIG"], index=us["dates"]), cn_dates)
    checks_agg["cn_cross_market_min_lag_days"] = min(lag0, lag2, lag3)

    # Full-series TVT50 on 513500_full sliced to start_i
    cn_full_dates = cn["c513500_full"].index
    si_cn = int(cn_full_dates.searchsorted(pd.Timestamp(lab.DOMESTIC_START)))
    px_cn_full = pd.DataFrame({"eq": cn["c513500_full"], "gold": cn["c518880_full"], "ief": cn["c518880_full"]}, index=cn_full_dates)
    cpos_cn_full, cneg_cn_full = ov.calendar_cash_factors(cn_full_dates, np.full(len(cn_full_dates), 0.02), 0.0)
    cn_gold_full = lab.weekly_stage2_state(cn["c518880_full"], ma_weeks=30, slope_weeks=4).to_numpy(dtype=bool)

    cn_rows: list[dict] = []
    cn_cases = [
        ("B0_513500", np.ones(len(cn_dates)), "cash"),
        ("CN_75_25_Q", "FIXED_75_25", "gold"),
        ("CN_MTF3_SELF_ORIG", cn_self_orig, "cash"),
        ("CN_MTF3_SELF_BUF3", cn_self_buf3, "cash"),
        ("CN_MTF3_US_ORIG_CASH", us_orig_mapped.to_numpy(dtype=float), "cash"),
        ("CN_MTF3_US_BUF2_CASH", us_buf2_mapped.to_numpy(dtype=float), "cash"),
        ("CN_MTF3_US_BUF2_GOLD", us_buf2_mapped.to_numpy(dtype=float), "gold"),
        ("CN_MTF3_US_BUF3_CASH", us_buf3_mapped.to_numpy(dtype=float), "cash"),
        ("CN_MTF3_US_BUF3_GOLD", us_buf3_mapped.to_numpy(dtype=float), "gold"),
        ("CN_MTF3_US_BUF3_GOLD_TREND", us_buf3_mapped.to_numpy(dtype=float), "gold_trend"),
    ]
    for cost_label, cost_val in [("10bp", 0.001), ("30bp", 0.003)]:
        for sname, w_eq, mode in cn_cases:
            if isinstance(w_eq, str):
                sig = lab.fixed_weight_signal([0.75, 0.25, 0.0], cn_dates, 0, freq="Q")
            else:
                sig = matrix_signal(build_shield_weights(w_eq, cn_gold_trend, mode), 0)
            res = run_and_check(px_cn, sig, 0, cost_val, cn["cash_pos"], cn["cash_neg"], checks_agg)
            m = lab.summarize_result(res, primary_col="eq")
            cn_rows.append({"cost": cost_label, "strategy": sname, **m})
        for tname, tmode in [("TVT50_CASH", "cash"), ("TVT50_GOLD", "gold")]:
            sig = build_tvt50_signal(cn["c513500_full"], si_cn, gold_trend=cn_gold_full, mode=tmode, ncols=3)
            res = run_and_check(px_cn_full, sig, si_cn, cost_val, cpos_cn_full, cneg_cn_full, checks_agg)
            m = lab.summarize_result(res, primary_col="eq")
            cn_rows.append({"cost": cost_label, "strategy": tname, **m})

    pd.DataFrame(cn_rows).to_csv(OUT_DIR / "summary_domestic_513500.csv", index=False)

    # ----------------------------------------------------------------------- 6. Track 6: Full 21-Combo Sensitivity Grid + Circular Shift
    sens_rows: list[dict] = []
    for asset_name, close in [("SPY", us["spy"]), ("QQQ", qqq)]:
        px_1 = pd.DataFrame({"eq": close}, index=us["dates"])
        for ma_fast, ma_slow in CONFIG["sensitivity_grid"]["ma_pairs"]:
            for buf in CONFIG["sensitivity_grid"]["buffers"]:
                w = lab.daily_buffered_mtf3_equity_weight(close, ma_fast=ma_fast, slope_days=20, ma_slow=ma_slow, buffer=buf).to_numpy(dtype=float)
                res = run_and_check(px_1, matrix_signal(w[:, None], si_2000), si_2000, 0.001, us["cash_pos"], us["cash_neg"], checks_agg)
                m = lab.summarize_result(res, primary_col="eq")
                m1 = lab.summarize_result(res, primary_col="eq", start="2000-01-03", end="2012-12-31")
                m2 = lab.summarize_result(res, primary_col="eq", start="2013-01-01", end=lab.US_END)
                sens_rows.append(
                    {
                        "asset": asset_name,
                        "ma_fast": ma_fast,
                        "ma_slow": ma_slow,
                        "buffer_pct": buf * 100.0,
                        "cagr": m["cagr"],
                        "sharpe": m["sharpe"],
                        "max_dd": m["max_dd"],
                        "calmar": m["calmar"],
                        "trades_per_year": m["trades_per_year"],
                        "sharpe_00_12": m1["sharpe"],
                        "cagr_13_26": m2["cagr"],
                        "sharpe_13_26": m2["sharpe"],
                    }
                )
    pd.DataFrame(sens_rows).to_csv(OUT_DIR / "sensitivity_grid.csv", index=False)

    circ_results = {
        "SPY_MTF3_BUF2": circular_shift_test(us["spy"], spy_sigs["MTF3_BUF2"], si_2000, us["cash_pos"], us["cash_neg"], 0.001, CONFIG["circular_shift_trials"]),
        "SPY_MTF3_BUF3": circular_shift_test(us["spy"], spy_sigs["MTF3_BUF3"], si_2000, us["cash_pos"], us["cash_neg"], 0.001, CONFIG["circular_shift_trials"]),
        "QQQ_MTF3_BUF2": circular_shift_test(qqq, qqq_sigs["MTF3_BUF2"], si_2000, us["cash_pos"], us["cash_neg"], 0.001, CONFIG["circular_shift_trials"]),
        "QQQ_MTF3_BUF3": circular_shift_test(qqq, qqq_sigs["MTF3_BUF3"], si_2000, us["cash_pos"], us["cash_neg"], 0.001, CONFIG["circular_shift_trials"]),
    }

    # ----------------------------------------------------------------------- 7. Key Historical Periods & Annual Returns (SPY)
    key_windows = [
        ("2000_2002_dotcom", "2000-03-01", "2002-10-31"),
        ("2008_gfc", "2007-10-01", "2009-03-31"),
        ("2011_euro_whipsaw", "2011-05-01", "2011-12-31"),
        ("2015_2016_chop", "2015-07-01", "2016-06-30"),
        ("2018_q4", "2018-09-20", "2018-12-31"),
        ("2020_covid_crash", "2020-02-19", "2020-03-23"),
        ("2020_full_year", "2020-01-02", "2020-12-31"),
        ("2022_rate_bear", "2022-01-03", "2022-12-30"),
        ("2025_tariff_drop", "2025-02-19", "2025-04-30"),
        ("2023_2026_bull", "2023-01-03", lab.US_END),
    ]
    kp_rows: list[dict] = []
    for pname, s_dt, e_dt in key_windows:
        row: dict[str, Any] = {"period": pname, "start": s_dt, "end": e_dt}
        for sname in ["B0", "S2", "MTF3_ORIG", "MTF3_BUF2", "MTF3_BUF3", "TVT50"]:
            nv = spy_navs_2000[sname]
            sl = nv[(nv.index >= s_dt) & (nv.index <= e_dt)]
            row[f"{sname}_ret"] = float(sl.iloc[-1] / sl.iloc[0] - 1.0)
            row[f"{sname}_mdd"] = float((sl / sl.cummax() - 1.0).min())
        kp_rows.append(row)
    pd.DataFrame(kp_rows).to_csv(OUT_DIR / "key_periods.csv", index=False)

    ann_df = pd.DataFrame({
        sname: spy_navs_2000[sname].resample("YE").last().pct_change().dropna()
        for sname in ["B0", "S2", "MTF3_ORIG", "MTF3_BUF2", "MTF3_BUF3", "TVT50"]
    })
    ann_df.index = ann_df.index.year
    ann_df.index.name = "year"
    ann_df.to_csv(OUT_DIR / "annual_returns.csv")

    # Save config & self-checks
    checks_agg["circular_shift"] = circ_results
    checks_agg["all_passed"] = bool(
        checks_agg["max_cash_residual"] < 1e-12
        and checks_agg["min_nav"] > 0.0
        and checks_agg["min_target_weight"] >= -1e-12
        and checks_agg["max_target_sum"] <= 1.0 + 1e-12
        and checks_agg["anti_lookahead_perturbation_max_diff"] == 0.0
        and checks_agg["cn_cross_market_min_lag_days"] >= 1
    )
    assert checks_agg["all_passed"], f"Self-checks failed: {checks_agg}"
    (OUT_DIR / "config.json").write_text(json.dumps(CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "self_checks.json").write_text(json.dumps(checks_agg, indent=2, ensure_ascii=False), encoding="utf-8")

    # Console summary for immediate inspection
    print("=== SELF CHECKS ===")
    print(json.dumps(checks_agg, indent=2))
    print("\n=== SPY 2000-2026 (10bp full) ===")
    df_s = pd.DataFrame(rows_spy_2000)
    print(df_s[(df_s["cost"] == "10bp") & (df_s["segment"] == "full")][["strategy", "cagr", "sharpe", "max_dd", "calmar", "trades_per_year", "loss_prob_5y", "loss_prob_10y"]].to_string(index=False))
    print("\n=== SPY SHIELDS 2005-2026 (10bp full) ===")
    df_sh = pd.DataFrame(rows_shields)
    print(df_sh[(df_sh["asset"] == "SPY") & (df_sh["cost"] == "10bp") & (df_sh["segment"] == "full")][["strategy", "cagr", "sharpe", "max_dd", "calmar", "max_underwater_years", "annual_turnover"]].to_string(index=False))
    print("\n=== GOLD BEAR STRESS 2011-09 to 2022-12 (SPY, 10bp) ===")
    df_gb = pd.DataFrame(rows_gold_bear)
    print(df_gb[df_gb["asset"] == "SPY"][["strategy", "cagr", "sharpe", "max_dd", "calmar"]].to_string(index=False))
    print("\n=== 10Y ROLLING DCA SUMMARY ===")
    df_dca = pd.DataFrame(dca_rows)
    print(df_dca[df_dca["cost"] == "10bp"][["scope", "strategy", "full_xirr", "full_max_principal_dd", "med_10y_xirr", "worst_10y_xirr", "xirr_win_vs_b0", "ratio_win_vs_b0"]].to_string(index=False))
    print("\n=== ANNUAL STARTS WIN SUMMARY (24 years 2000-2023) ===")
    df_st = pd.DataFrame(start_rows)
    print(df_st.groupby(["asset", "strategy"])[["cagr_diff", "beat_sharpe", "beat_calmar", "dd_reduction_pct"]].agg({"cagr_diff": "median", "beat_sharpe": "sum", "beat_calmar": "sum", "dd_reduction_pct": "median"}).to_string())
    print("\n=== DOMESTIC 513500 (2014-2026, 10bp) ===")
    df_cn = pd.DataFrame(cn_rows)
    print(df_cn[df_cn["cost"] == "10bp"][["strategy", "cagr", "sharpe", "max_dd", "calmar", "trades_per_year"]].to_string(index=False))
    print("\n=== KEY PERIODS (SPY) ===")
    print(pd.DataFrame(kp_rows)[["period", "B0_ret", "S2_ret", "MTF3_ORIG_ret", "MTF3_BUF2_ret", "MTF3_BUF3_ret", "TVT50_ret"]].to_string(index=False))


if __name__ == "__main__":
    main()
