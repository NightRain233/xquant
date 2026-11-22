"""S&P 500 4-direction research — Direction 3:
VIX / VIX3M term-structure crash brake + early re-entry, credit-spread risk brake
(lagged FRED BAA10Y & live HYG/IEF), and cross-market transfer to domestic 513500 + 518880.

Strictly offline, close-to-close execution (signal at close t, fill at close t+1),
all shared engine/metric/DCA calculations imported from ``xquant.sp500_lab``.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from xquant import overlay_rules as ov  # noqa: E402
from xquant import position_rules as pr  # noqa: E402
from xquant import sp500_lab as lab  # noqa: E402
from xquant import style_combo as sc  # noqa: E402

SLUG = "sp500-dir3-vix-credit-2026-11-22"
OUT_DIR = ROOT / "outputs" / SLUG

CONFIG = {
    "slug": SLUG,
    "direction": "Dir3: VIX/VIX3M Term Structure Brake + Credit Spread Brake + Domestic 513500 Transfer",
    "execution_clock": "Signal at close t (using strictly <= t data; FRED BAA10Y strictly <= t-1; domestic cross-market US signals strictly < d); fill at close t+1.",
    "costs": {"10bp": 0.001, "30bp": 0.003},
    "tracks": {
        "3A_vix_us": {
            "window": [lab.US_VIX3M_START, lab.US_END],
            "segments": {
                "2006-2012": [lab.US_VIX3M_START, "2012-12-31"],
                "2013-2026": ["2013-01-01", lab.US_END],
            },
            "gold_series": "gld_real",
            "vix_brake": {
                "trigger_ratio": 1.00,
                "recover_ratio": 0.95,
                "recover_days": 3,
                "off_spy_weight": 0.50,
                "init_brake_on": False,
            },
            "vix_graded": {
                "tier1_ratio": 1.00,
                "tier1_spy": 0.50,
                "tier2_ratio": 1.10,
                "tier2_vix": 30.0,
                "tier2_spy": 0.25,
                "recover_to_50_ratio": 1.05,
                "recover_to_100_ratio": 0.95,
                "recover_days": 3,
                "init_tier": 0,
            },
            "s2_baseline": {"ma_weeks": 30, "slope_weeks": 4, "on_spy": 1.0, "off_spy": 0.5},
            "vt15_baseline": {"target_vol": 0.15, "window": 21, "band": 0.10, "cap": 1.0},
            "sensitivity_grid": {
                "variants": ["VIX_BRAKE_CASH", "VIX_BRAKE_GOLD"],
                "cost": "10bp",
                "trigger_ratio": [0.98, 1.00, 1.03, 1.05],
                "recover_ratio": 0.95,
                "recover_days": [1, 3, 5],
                "off_spy_weight": [0.0, 0.25, 0.50],
            },
        },
        "3B_credit_us": {
            "baa_2000_window": [lab.US_MAIN_START, lab.US_END],
            "baa_2000_segments": {
                "2000-2012": [lab.US_MAIN_START, "2012-12-31"],
                "2013-2026": ["2013-01-01", lab.US_END],
            },
            "baa_2005_window": [lab.US_GLD_START, lab.US_END],
            "baa_2005_segments": {
                "2005-2012": [lab.US_GLD_START, "2012-12-31"],
                "2013-2026": ["2013-01-01", lab.US_END],
            },
            "baa_rule": {
                "fred_extra_lag_trading_days": 1,
                "baa_sma_days": 126,
                "baa_mom_days": 21,
                "spy_sma_days": 200,
                "check_freq": "week_end",
                "off_spy_weight": 0.50,
            },
            "hyg_ief_window": ["2007-10-01", lab.US_END],
            "hyg_ief_segments": {
                "2007-2012": ["2007-10-01", "2012-12-31"],
                "2013-2026": ["2013-01-01", lab.US_END],
            },
            "hyg_ief_rule": {
                "ratio_ma_weeks": 26,
                "spy_ma_weeks": 30,
                "check_freq": "week_end",
                "off_spy_weight": 0.50,
            },
        },
        "3C_domestic": {
            "window": [lab.DOMESTIC_START, lab.DOMESTIC_END],
            "segments": {
                "2014-2020": [lab.DOMESTIC_START, "2020-12-31"],
                "2021-2026": ["2021-01-01", lab.DOMESTIC_END],
            },
            "cross_market_rule": "At A-share close d, read strictly latest US close with us_date < d.",
            "s2_source_primary": "513500_self_weekly_s2 (warmed up on c513500_full from 2014-01-15)",
            "s2_source_transfer_ref": "SPY_weekly_s2 (strictly us_date < d)",
            "dca_rolling_months": [60, 120],
        },
    },
    "key_periods_us": {
        "2000-03~2002-10_dotcom": ["2000-03-24", "2002-10-09"],
        "2007-10~2009-03_gfc": ["2007-10-01", "2009-03-31"],
        "2011-05~2011-10_euro_debt": ["2011-05-01", "2011-10-31"],
        "2018-10~2018-12_q4_selloff": ["2018-10-01", "2018-12-31"],
        "2020-02-19~2020-03-23_covid_crash": ["2020-02-19", "2020-03-23"],
        "2020-03-24~2020-08-31_covid_v_rebound": ["2020-03-24", "2020-08-31"],
        "2020-02-19~2020-12-31_covid_full_cycle": ["2020-02-19", "2020-12-31"],
        "2022_full_year_bear": ["2022-01-01", "2022-12-31"],
        "2023~2026_bull_and_recent": ["2023-01-01", lab.US_END],
    },
    "key_periods_domestic": {
        "2018-10~2018-12_q4_selloff": ["2018-10-01", "2018-12-31"],
        "2020-02-19~2020-03-23_covid_crash": ["2020-02-19", "2020-03-23"],
        "2020-03-24~2020-08-31_covid_v_rebound": ["2020-03-24", "2020-08-31"],
        "2020-02-19~2020-12-31_covid_full_cycle": ["2020-02-19", "2020-12-31"],
        "2022_full_year_bear": ["2022-01-01", "2022-12-31"],
        "2023~2026_bull_and_recent": ["2023-01-01", lab.DOMESTIC_END],
    },
}


# ---------------------------------------------------------------------------
# Signal & state builders (strictly causal: decision at close i uses <= i only)
# ---------------------------------------------------------------------------


def build_state_change_signal(target_weights: np.ndarray, start_i: int) -> lab.MultiSignal:
    """Submit target weight vector at ``start_i`` and whenever the target vector changes."""
    arr = np.asarray(target_weights, dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"target_weights must be 2D, got shape {arr.shape}")

    def sig(i: int, _w_now: np.ndarray) -> Optional[np.ndarray]:
        if i == start_i or np.any(arr[i] != arr[i - 1]):
            return arr[i].copy()
        return None

    return sig


def build_vt_signal(
    close: pd.Series,
    start_i: int,
    n_assets: int,
    target: float = 0.15,
    window: int = 21,
    band: float = 0.10,
    cap: float = 1.0,
) -> lab.MultiSignal:
    """Exact match to ``overlay_rules.vol_target_band`` adapted to N-asset engine."""
    log_ret = np.log(close).diff()
    vol = log_ret.rolling(window).std(ddof=1).to_numpy(float) * np.sqrt(lab.TRADING_DAYS)
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = np.where(vol > 0, target / vol, np.inf)
    wanted = np.where(np.isnan(vol), np.nan, np.minimum(cap, raw))

    def sig(i: int, w_now: np.ndarray) -> Optional[np.ndarray]:
        desired = wanted[i]
        if np.isnan(desired):
            return None
        if i == start_i or abs(desired - w_now[0]) > band:
            vec = np.zeros(n_assets, dtype=float)
            vec[0] = desired
            return vec
        return None

    return sig


def compute_vix_brake_state(
    ratio: pd.Series,
    start_date: str,
    trigger_ratio: float = 1.00,
    recover_ratio: float = 0.95,
    recover_days: int = 3,
) -> pd.Series:
    """Binary VIX/VIX3M brake state starting from ``start_date`` (initialized False = 100% SPY).

    Rules evaluated at close i (strictly using ratio[i]):
    - If ratio[i] > trigger_ratio -> brake_on = True, cool_streak = 0.
    - Else if brake_on:
        if ratio[i] < recover_ratio -> cool_streak += 1; if cool_streak >= recover_days -> brake_on = False, cool_streak = 0.
        else -> cool_streak = 0.
    - Before ``start_date``: False (unused).
    """
    idx = ratio.index
    vals = ratio.to_numpy(float)
    start_i = int(idx.searchsorted(pd.Timestamp(start_date)))
    out = np.zeros(len(idx), dtype=bool)
    brake_on = False
    cool_streak = 0
    for i in range(start_i, len(idx)):
        r = vals[i]
        if np.isnan(r):
            out[i] = brake_on
            continue
        if r > trigger_ratio:
            brake_on = True
            cool_streak = 0
        elif brake_on:
            if r < recover_ratio:
                cool_streak += 1
                if cool_streak >= recover_days:
                    brake_on = False
                    cool_streak = 0
            else:
                cool_streak = 0
        out[i] = brake_on
    return pd.Series(out, index=idx, name="vix_brake_on")


def compute_vix_graded_spy_weight(
    ratio: pd.Series,
    vix: pd.Series,
    start_date: str,
    tier1_ratio: float = 1.00,
    tier1_spy: float = 0.50,
    tier2_ratio: float = 1.10,
    tier2_vix: float = 30.0,
    tier2_spy: float = 0.25,
    recover_to_50_ratio: float = 1.05,
    recover_to_100_ratio: float = 0.95,
    recover_days: int = 3,
) -> pd.Series:
    """Three-tier hysteretic VIX brake returning target SPY weight (1.0 / 0.50 / 0.25).

    Rules at close i:
    - Downshift is immediate:
      * If ratio > tier2_ratio and vix > tier2_vix -> tier = 2 (25% SPY), reset both streaks.
      * Else if tier == 0 and ratio > tier1_ratio -> tier = 1 (50% SPY), reset both streaks.
      * Else if tier == 1 and ratio > tier1_ratio -> stay tier 1, reset rec_to_100 streak.
    - Upshift requires ``recover_days`` consecutive closes:
      * From tier 2: rec_to_50 counts consecutive closes < recover_to_50_ratio;
        rec_to_100 counts consecutive closes < recover_to_100_ratio.
        If rec_to_100 >= recover_days -> tier = 0 (100% SPY);
        elif rec_to_50 >= recover_days -> tier = 1 (50% SPY), keeping rec_to_100 progress.
      * From tier 1: rec_to_100 counts consecutive closes < recover_to_100_ratio;
        if rec_to_100 >= recover_days -> tier = 0 (100% SPY).
    """
    idx = ratio.index
    r_vals = ratio.to_numpy(float)
    v_vals = vix.to_numpy(float)
    start_i = int(idx.searchsorted(pd.Timestamp(start_date)))
    tier_to_w = {0: 1.0, 1: tier1_spy, 2: tier2_spy}
    out = np.ones(len(idx), dtype=float)

    tier = 0
    rec50 = 0
    rec100 = 0
    for i in range(start_i, len(idx)):
        r = r_vals[i]
        v = v_vals[i]
        if np.isnan(r) or np.isnan(v):
            out[i] = tier_to_w[tier]
            continue

        if r > tier2_ratio and v > tier2_vix:
            tier = 2
            rec50 = 0
            rec100 = 0
        elif tier == 0:
            if r > tier1_ratio:
                tier = 1
                rec50 = 0
                rec100 = 0
        elif tier == 2:
            rec50 = rec50 + 1 if r < recover_to_50_ratio else 0
            rec100 = rec100 + 1 if r < recover_to_100_ratio else 0
            if rec100 >= recover_days:
                tier = 0
                rec50 = 0
                rec100 = 0
            elif rec50 >= recover_days:
                tier = 1
                rec50 = 0
        elif tier == 1:
            if r > tier1_ratio:
                rec100 = 0
            else:
                rec100 = rec100 + 1 if r < recover_to_100_ratio else 0
                if rec100 >= recover_days:
                    tier = 0
                    rec50 = 0
                    rec100 = 0

        out[i] = tier_to_w[tier]

    return pd.Series(out, index=idx, name="vix_graded_spy_w")


def compute_baa_credit_brake_state(
    baa10y: pd.Series,
    spy: pd.Series,
    start_date: str,
    sma_days: int = 126,
    mom_days: int = 21,
    spy_sma_days: int = 200,
) -> pd.Series:
    """Weekly-checked FRED BAA10Y risk brake with strict 1-trading-day publication lag.

    At trading day i, only ``baa10y[i-1]`` (and earlier) is readable.
    Checked on every completed week-end (``sc.is_week_end``) and at ``start_i``.
    """
    dates = pd.DatetimeIndex(spy.index)
    baa_lag1 = baa10y.shift(1)
    baa_sma = baa_lag1.rolling(sma_days).mean()
    baa_prev = baa_lag1.shift(mom_days)
    spy_sma = spy.rolling(spy_sma_days).mean()

    raw_cond = (baa_lag1 > baa_sma) & (baa_lag1 > baa_prev) & (spy < spy_sma)
    raw_arr = raw_cond.fillna(False).to_numpy(bool)

    start_i = int(dates.searchsorted(pd.Timestamp(start_date)))
    out = np.zeros(len(dates), dtype=bool)
    cur = False
    for i in range(start_i, len(dates)):
        if i == start_i or sc.is_week_end(dates, i):
            cur = bool(raw_arr[i])
        out[i] = cur
    return pd.Series(out, index=dates, name="baa_credit_brake_on")


def compute_hyg_ief_brake_state(
    hyg: pd.Series,
    ief: pd.Series,
    spy: pd.Series,
    start_date: str,
    ratio_ma_weeks: int = 26,
    spy_ma_weeks: int = 30,
) -> pd.Series:
    """Weekly-checked real-time credit ratio (HYG / IEF) brake (zero FRED lag).

    Triggered at a completed week-end when (HYG/IEF < 26-week SMA) AND (SPY < 30-week SMA).
    Only completed week-ends (``sc.is_week_end``) are used to form the weekly closes,
    guaranteeing strict truncation invariance even if truncated mid-week.
    """
    dates = pd.DatetimeIndex(spy.index)
    week_ends = np.array([sc.is_week_end(dates, i) for i in range(len(dates))], dtype=bool)
    we_idx = dates[week_ends]

    ratio_daily = hyg / ief
    w_ratio = ratio_daily.loc[we_idx]
    w_ratio_ma = w_ratio.rolling(ratio_ma_weeks).mean()

    w_spy = spy.loc[we_idx]
    w_spy_ma = w_spy.rolling(spy_ma_weeks).mean()

    w_trig = ((w_ratio < w_ratio_ma) & (w_spy < w_spy_ma)).fillna(False)

    start_i = int(dates.searchsorted(pd.Timestamp(start_date)))
    trig_lookup = w_trig.to_dict()
    out = np.zeros(len(dates), dtype=bool)
    cur = False
    # Seed initial state from the most recent completed week-end <= start_date (if any)
    prior_we = w_trig[w_trig.index <= dates[start_i]]
    if not prior_we.empty:
        cur = bool(prior_we.iloc[-1])

    for i in range(start_i, len(dates)):
        d = dates[i]
        if d in trig_lookup:
            cur = bool(trig_lookup[d])
        out[i] = cur
    return pd.Series(out, index=dates, name="hyg_ief_brake_on")


def map_us_series_strictly_before_cn(
    us_series: pd.Series, cn_dates: pd.DatetimeIndex
) -> tuple[pd.Series, pd.Series]:
    """For each A-share date d, return value from the latest US trading date strictly < d.

    Also returns a Series of the matched US dates for anti-lookahead auditing.
    """
    us_s = us_series.dropna().sort_index()
    us_idx = pd.DatetimeIndex(us_s.index)
    pos = us_idx.searchsorted(cn_dates, side="left") - 1
    if np.any(pos < 0):
        raise ValueError("Some A-share dates have no strictly earlier US observation")
    matched_dates = us_idx[pos]
    matched_vals = us_s.iloc[pos].to_numpy()
    return (
        pd.Series(matched_vals, index=cn_dates, name=us_series.name),
        pd.Series(matched_dates, index=cn_dates, name="used_us_date"),
    )


def count_brake_episodes(flag: pd.Series, start: str, end: str) -> dict:
    """Count False->True trigger episodes and share of days active within [start, end]."""
    sub = flag[(flag.index >= pd.Timestamp(start)) & (flag.index <= pd.Timestamp(end))].astype(bool)
    if sub.empty:
        return {"n_triggers": 0, "pct_days_brake_on": 0.0}
    arr = sub.to_numpy(bool)
    transitions = int(np.sum((~arr[:-1]) & arr[1:])) if len(arr) > 1 else 0
    if arr[0]:
        transitions += 1
    return {
        "n_triggers": transitions,
        "pct_days_brake_on": float(arr.mean()),
    }


def make_two_asset_weights(
    spy_w: pd.Series,
    alt_w: pd.Series,
) -> np.ndarray:
    return np.column_stack([spy_w.to_numpy(float), alt_w.to_numpy(float)])


def extract_2020_timeline(
    res: lab.MultiEngineResult,
    spy_col: str,
    start: str = "2020-02-01",
    end: str = "2020-07-01",
) -> list[dict]:
    """List exact execution dates and target weights during the 2020 COVID crash & rebound."""
    t = res.trades
    if t.empty:
        return []
    sub = t[(t["exec_date"] >= pd.Timestamp(start)) & (t["exec_date"] <= pd.Timestamp(end))]
    events = []
    for _, row in sub.iterrows():
        d = pd.Timestamp(row["exec_date"])
        w_spy = float(res.weights.loc[d, spy_col])
        w_cash = float(res.weights.loc[d, "cash"])
        alt_cols = [c for c in res.weights.columns if c not in (spy_col, "cash")]
        w_alt = float(res.weights.loc[d, alt_cols[0]]) if alt_cols else 0.0
        events.append(
            {
                "exec_date": str(d.date()),
                "traded_frac": round(float(row["traded_frac"]), 4),
                "w_spy_after": round(w_spy, 4),
                "w_alt_after": round(w_alt, 4),
                "w_cash_after": round(w_cash, 4),
            }
        )
    return events


def evaluate_key_periods(
    results_10bp: dict[str, lab.MultiEngineResult],
    bench_name: str,
    primary_col: str,
    periods: dict[str, list[str]],
    track: str,
) -> list[dict]:
    rows = []
    bench_nav = results_10bp[bench_name].nav
    for period_label, (p_start, p_end) in periods.items():
        if pd.Timestamp(p_start) < bench_nav.index[0] - pd.Timedelta(days=10):
            continue
        b_stats = sc.period_stats(bench_nav, p_start, p_end)
        for strat_name, res in results_10bp.items():
            if pd.Timestamp(p_start) < res.nav.index[0] - pd.Timedelta(days=10):
                continue
            st = sc.period_stats(res.nav, p_start, p_end)
            w_seg = res.weights[(res.weights.index >= pd.Timestamp(p_start)) & (res.weights.index <= pd.Timestamp(p_end))]
            avg_spy = float(w_seg[primary_col].mean()) if not w_seg.empty else np.nan
            alt_cols = [c for c in res.weights.columns if c not in (primary_col, "cash")]
            avg_alt = float(w_seg[alt_cols[0]].mean()) if (alt_cols and not w_seg.empty) else 0.0
            rows.append(
                {
                    "track": track,
                    "period": period_label,
                    "start": p_start,
                    "end": p_end,
                    "strategy": strat_name,
                    "return": st["return"],
                    "excess_vs_bench": st["return"] - b_stats["return"],
                    "max_dd": st["max_drawdown"],
                    "dd_reduction_vs_bench": st["max_drawdown"] - b_stats["max_drawdown"],
                    "avg_primary_weight": avg_spy,
                    "avg_alt_weight": avg_alt,
                }
            )
    return rows


def summarize_with_segments(
    track: str,
    window_label: str,
    cost_label: str,
    strat_name: str,
    res: lab.MultiEngineResult,
    primary_col: str,
    segments: dict[str, list[str]],
    brake_info: Optional[dict] = None,
) -> list[dict]:
    rows = []
    full_m = lab.summarize_result(res, primary_col=primary_col)
    base_row = {
        "track": track,
        "window": window_label,
        "segment": "full",
        "cost": cost_label,
        "strategy": strat_name,
        **full_m,
    }
    if brake_info:
        base_row["n_triggers_full"] = brake_info["n_triggers"]
        base_row["pct_days_brake_on_full"] = brake_info["pct_days_brake_on"]
    else:
        base_row["n_triggers_full"] = np.nan
        base_row["pct_days_brake_on_full"] = np.nan
    rows.append(base_row)

    for seg_name, (s_start, s_end) in segments.items():
        seg_m = lab.summarize_result(res, primary_col=primary_col, start=s_start, end=s_end)
        rows.append(
            {
                "track": track,
                "window": window_label,
                "segment": seg_name,
                "cost": cost_label,
                "strategy": strat_name,
                **seg_m,
                "n_triggers_full": np.nan,
                "pct_days_brake_on_full": np.nan,
            }
        )
    return rows


def run_dca_suite(
    track: str,
    window_label: str,
    results_by_cost: dict[tuple[str, str], lab.MultiEngineResult],
    strategy_order: list[str],
    bench_name: str,
    rolling_months_list: list[int],
) -> list[dict]:
    rows = []
    for cost_label, cost_val in CONFIG["costs"].items():
        bench_nav = results_by_cost[(cost_label, bench_name)].nav
        for strat in strategy_order:
            nav = results_by_cost[(cost_label, strat)].nav
            fp = lab.dca_full_path(nav, cost=cost_val)
            row = {
                "track": track,
                "window": window_label,
                "cost": cost_label,
                "strategy": strat,
                "dca_type": "full_path",
                "rolling_months": 0,
                **fp,
            }
            rows.append(row)

            # Rolling DCA windows for 10bp (and 30bp for completeness on key strategies)
            if cost_label == "10bp":
                for win_m in rolling_months_list:
                    comp = lab.compare_dca_windows(nav, bench_nav, window_months=win_m, cost=cost_val)
                    rows.append(
                        {
                            "track": track,
                            "window": window_label,
                            "cost": cost_label,
                            "strategy": strat,
                            "dca_type": f"rolling_{win_m}m",
                            "rolling_months": win_m,
                            **comp,
                        }
                    )
    return rows


# ---------------------------------------------------------------------------
# Anti-lookahead & engine parity self-checks
# ---------------------------------------------------------------------------


def run_self_checks(
    us: dict,
    cn: dict,
    vix_brake_full: pd.Series,
    vix_graded_full: pd.Series,
    baa_brake_full: pd.Series,
    hyg_brake_full: pd.Series,
    cn_vix_brake: pd.Series,
    cn_used_us_dates: pd.Series,
    all_results: dict[str, lab.MultiEngineResult],
    res_3a_10bp: dict[str, lab.MultiEngineResult],
    res_3c_10bp: dict[str, lab.MultiEngineResult],
) -> dict:
    # 1. Engine accounting & bounds across every single run
    max_cash_res = max(r.checks["max_cash_residual"] for r in all_results.values())
    min_nav = min(r.checks["nav_min"] for r in all_results.values())
    min_tgt = min(r.checks["target_weight_min"] for r in all_results.values())
    max_tgt_sum = max(r.checks["target_sum_max"] for r in all_results.values())
    all_finite = all(np.all(np.isfinite(r.nav.to_numpy(float))) for r in all_results.values())

    # 2. Exact engine parity against overlay_rules.simulate for S2_CASH and VT_15 on 3A window
    md = ov.MarketData(
        dates=us["dates"],
        spy=us["spy"],
        bond=us["ief"],
        cash_pos=us["cash_pos"],
        cash_neg=us["cash_neg"],
    )
    ref_s2 = ov.simulate(md, "S2", lab.US_VIX3M_START, cost=0.001)
    ref_vt = ov.simulate(md, "VT", lab.US_VIX3M_START, cost=0.001)
    s2_parity_err = float((res_3a_10bp["S2_CASH"].nav - ref_s2.nav).abs().max())
    vt_parity_err = float((res_3a_10bp["VT_15"].nav - ref_vt.nav).abs().max())

    # 3. Anti-lookahead truncation invariance: VIX brake & graded brake & HYG/IEF
    trunc_dates = ["2011-08-18", "2020-03-11", "2022-06-15"]  # include mid-week dates!
    vix_ratio = us["vix"] / us["vix3m"]
    vix_trunc_ok = True
    graded_trunc_ok = True
    hyg_trunc_ok = True
    baa_trunc_ok = True
    for td in trunc_dates:
        ts = pd.Timestamp(td)
        sub_ratio = vix_ratio.loc[:ts]
        sub_vix = us["vix"].loc[:ts]
        vb_sub = compute_vix_brake_state(sub_ratio, lab.US_VIX3M_START)
        if not vb_sub.equals(vix_brake_full.loc[:ts]):
            vix_trunc_ok = False

        vg_sub = compute_vix_graded_spy_weight(sub_ratio, sub_vix, lab.US_VIX3M_START)
        if not vg_sub.equals(vix_graded_full.loc[:ts]):
            graded_trunc_ok = False

        hyg_sub = compute_hyg_ief_brake_state(
            us["hyg"].loc[:ts], us["ief"].loc[:ts], us["spy"].loc[:ts], "2007-10-01"
        )
        if not hyg_sub.equals(hyg_brake_full.loc[:ts]):
            hyg_trunc_ok = False

        baa_sub = compute_baa_credit_brake_state(
            us["baa10y"].loc[:ts], us["spy"].loc[:ts], lab.US_MAIN_START
        )
        if not baa_sub.equals(baa_brake_full.loc[:ts]):
            baa_trunc_ok = False

    # 4. Strict FRED BAA10Y +1 trading-day lag perturbation test & raw observation date check
    # Perturb baa10y at a Friday close i_test and verify decision at i_test is completely unchanged,
    # while decision on a later date can see it.
    dates = us["dates"]
    baa_raw = lab.load_fred_csv(lab.CACHE_DIR / "fred_BAA10Y.csv")
    baa_raw_dates = pd.Series(baa_raw.index, index=baa_raw.index).reindex(dates).ffill()
    baa_obs_used_at_i = baa_raw_dates.shift(1)
    start_2000_i = int(dates.searchsorted(pd.Timestamp(lab.US_MAIN_START)))
    prev_trading_dates = pd.Series(dates, index=dates).shift(1)
    fred_obs_strictly_lagged = bool(
        (baa_obs_used_at_i.iloc[start_2000_i:] <= prev_trading_dates.iloc[start_2000_i:]).all()
    )
    # Perturbation test at 2020-03-13 (Friday during crash) and 2008-10-10 (Friday)
    baa_perturb_ok = True
    for test_day in ["2008-10-10", "2020-03-13", "2022-06-17"]:
        ts = pd.Timestamp(test_day)
        perturbed = us["baa10y"].copy()
        perturbed.loc[ts:] = 99.0  # massive shock starting at ts
        b_pert = compute_baa_credit_brake_state(perturbed, us["spy"], lab.US_MAIN_START)
        # Decision at ts MUST be identical to unperturbed because ts only reads baa10y[ts-1]
        if not b_pert.loc[:ts].equals(baa_brake_full.loc[:ts]):
            baa_perturb_ok = False

    # 5. Strict cross-market < d check for domestic 513500 track
    cn_dates = cn["dates"]
    day_gaps = (cn_dates - pd.DatetimeIndex(cn_used_us_dates)).days.to_numpy(int)
    cn_strictly_before_us = bool(np.all(day_gaps >= 1))
    # Perturbation check: flip US VIX brake on and after an A-share trading day d -> A-share day d must be unchanged
    cn_perturb_ok = True
    for d_str in ["2020-02-25", "2020-03-23", "2022-05-05"]:
        d_ts = pd.Timestamp(d_str)
        if d_ts not in cn_dates:
            d_ts = cn_dates[cn_dates.searchsorted(d_ts)]
        vix_flipped = vix_brake_full.copy()
        vix_flipped.loc[vix_flipped.index >= d_ts] = ~vix_flipped.loc[vix_flipped.index >= d_ts]
        mapped_flip, _ = map_us_series_strictly_before_cn(vix_flipped, cn_dates)
        if not mapped_flip.loc[:d_ts].equals(cn_vix_brake.loc[:d_ts]):
            cn_perturb_ok = False

    # 6. Trigger & turnover summary across core 10bp strategies
    turnover_audit = {}
    for key, res in all_results.items():
        if not key.endswith("_10bp"):
            continue
        m = lab.summarize_result(res, primary_col=res.weights.columns[0])
        turnover_audit[key] = {
            "n_non_init_trades": int((~res.trades["is_initial"]).sum()) if not res.trades.empty else 0,
            "trades_per_year": round(m["trades_per_year"], 2),
            "annual_turnover": round(m["annual_turnover"], 4),
            "avg_primary_weight": round(m["avg_primary_weight"], 4),
        }

    # Verify active timing strategies actually traded (catch any degenerate locked-state bugs)
    active_must_trade = [
        "3A_S2_CASH_10bp",
        "3A_VT_15_10bp",
        "3A_VIX_BRAKE_CASH_10bp",
        "3A_VIX_BRAKE_GOLD_10bp",
        "3A_VIX_BRAKE_GOLD_TREND_10bp",
        "3A_VIX_GRADED_CASH_10bp",
        "3A_VIX_OR_S2_CASH_10bp",
        "3A_VIX_OR_S2_GOLD_10bp",
        "3A_VIX_OR_S2_GOLD_TREND_10bp",
        "3B2000_CREDIT_BAA_CASH_10bp",
        "3B2005_CREDIT_BAA_GOLD_10bp",
        "3B2007_HYG_IEF_CASH_10bp",
        "3B2007_HYG_IEF_GOLD_10bp",
        "3C_CN_VIX_BRAKE_CASH_10bp",
        "3C_CN_VIX_BRAKE_GOLD_10bp",
        "3C_CN_VIX_OR_S2_GOLD_10bp",
    ]
    all_active_traded = all(turnover_audit[k]["n_non_init_trades"] > 0 for k in active_must_trade)

    # 7. Exact 2020 crash & V-rebound trade timelines
    timeline_2020 = {
        k: extract_2020_timeline(res, "spy")
        for k, res in res_3a_10bp.items()
        if k in {
            "S2_CASH",
            "VT_15",
            "VIX_BRAKE_CASH",
            "VIX_BRAKE_GOLD",
            "VIX_GRADED_CASH",
            "VIX_OR_S2_CASH",
            "VIX_OR_S2_GOLD",
        }
    }
    timeline_2020_cn = {
        k: extract_2020_timeline(res, "c513500")
        for k, res in res_3c_10bp.items()
        if k in {"CN_VIX_BRAKE_CASH", "CN_VIX_BRAKE_GOLD", "CN_VIX_OR_S2_GOLD"}
    }

    checks = {
        "all_passed": bool(
            max_cash_res < 1e-10
            and min_nav > 0.0
            and min_tgt >= -1e-12
            and max_tgt_sum <= 1.0 + 1e-12
            and all_finite
            and s2_parity_err < 1e-12
            and vt_parity_err < 1e-12
            and vix_trunc_ok
            and graded_trunc_ok
            and hyg_trunc_ok
            and baa_trunc_ok
            and fred_obs_strictly_lagged
            and baa_perturb_ok
            and cn_strictly_before_us
            and cn_perturb_ok
            and all_active_traded
        ),
        "all_active_strategies_traded": all_active_traded,
        "engine_accounting": {
            "n_backtests_checked": len(all_results),
            "max_cash_residual": max_cash_res,
            "max_cash_residual_lt_1e10": bool(max_cash_res < 1e-10),
            "nav_min": min_nav,
            "nav_min_gt_0": bool(min_nav > 0.0),
            "target_weight_min": min_tgt,
            "target_sum_max": max_tgt_sum,
            "all_nav_finite": all_finite,
        },
        "overlay_rules_parity": {
            "S2_CASH_max_abs_nav_diff": s2_parity_err,
            "VT_15_max_abs_nav_diff": vt_parity_err,
        },
        "anti_lookahead": {
            "truncation_test_dates": trunc_dates,
            "vix_brake_truncation_invariant": vix_trunc_ok,
            "vix_graded_truncation_invariant": graded_trunc_ok,
            "hyg_ief_truncation_invariant": hyg_trunc_ok,
            "baa10y_truncation_invariant": baa_trunc_ok,
            "fred_baa10y_obs_date_le_prev_trading_day": fred_obs_strictly_lagged,
            "fred_baa10y_same_day_perturbation_invariant": baa_perturb_ok,
            "domestic_us_date_strictly_lt_cn_date": cn_strictly_before_us,
            "domestic_min_calendar_day_gap": int(day_gaps.min()),
            "domestic_median_calendar_day_gap": float(np.median(day_gaps)),
            "domestic_same_day_us_perturbation_invariant": cn_perturb_ok,
        },
        "brake_episode_stats": {
            "3A_VIX_BRAKE_2006_2026": count_brake_episodes(vix_brake_full, lab.US_VIX3M_START, lab.US_END),
            "3B_BAA10Y_2000_2026": count_brake_episodes(baa_brake_full, lab.US_MAIN_START, lab.US_END),
            "3B_HYG_IEF_2007_2026": count_brake_episodes(hyg_brake_full, "2007-10-01", lab.US_END),
            "3C_CN_VIX_BRAKE_2014_2026": count_brake_episodes(cn_vix_brake, lab.DOMESTIC_START, lab.DOMESTIC_END),
        },
        "turnover_audit_10bp": turnover_audit,
        "timeline_2020_us": timeline_2020,
        "timeline_2020_cn": timeline_2020_cn,
    }
    return checks


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "config.json").write_text(
        json.dumps(CONFIG, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    us = lab.load_us_bundle()
    cn = lab.load_domestic_bundle()
    us_dates = us["dates"]
    spy = us["spy"]
    gld = us["gld_real"]
    ief = us["ief"]
    hyg = us["hyg"]
    vix = us["vix"]
    vix3m = us["vix3m"]
    baa10y = us["baa10y"]
    cash_pos = us["cash_pos"]
    cash_neg = us["cash_neg"]

    all_results: dict[str, lab.MultiEngineResult] = {}
    key_period_rows: list[dict] = []
    dca_rows: list[dict] = []

    # =========================================================================
    # Track 3A: VIX / VIX3M Term Structure (2006-08-01 ~ 2026-10-16, gld_real)
    # =========================================================================
    start_3a = int(us_dates.searchsorted(pd.Timestamp(lab.US_VIX3M_START)))
    px_3a = pd.DataFrame({"spy": spy, "gld": gld}, index=us_dates)
    vix_ratio = vix / vix3m

    s2_spy_daily = lab.weekly_stage2_state(spy, ma_weeks=30, slope_weeks=4).astype(bool)
    # Warm up gld_real weekly stage2 on its valid history (starts 2004-11-18, valid from 2005-06-10)
    s2_gld_valid = lab.weekly_stage2_state(gld.dropna(), ma_weeks=30, slope_weeks=4).astype(bool)
    s2_gld_daily = s2_gld_valid.reindex(us_dates).fillna(False).astype(bool)
    assert s2_spy_daily.dtype == np.dtype(bool) and s2_gld_daily.dtype == np.dtype(bool)

    vix_brake_on = compute_vix_brake_state(
        vix_ratio,
        start_date=lab.US_VIX3M_START,
        trigger_ratio=1.00,
        recover_ratio=0.95,
        recover_days=3,
    )
    vix_graded_w = compute_vix_graded_spy_weight(
        vix_ratio,
        vix,
        start_date=lab.US_VIX3M_START,
        tier1_ratio=1.00,
        tier1_spy=0.50,
        tier2_ratio=1.10,
        tier2_vix=30.0,
        tier2_spy=0.25,
        recover_to_50_ratio=1.05,
        recover_to_100_ratio=0.95,
        recover_days=3,
    )
    vix_or_s2_off = vix_brake_on | (~s2_spy_daily)

    def make_3a_signals() -> dict[str, lab.MultiSignal]:
        w_s2 = np.where(s2_spy_daily.to_numpy(bool), 1.0, 0.5)
        w_vb = np.where(vix_brake_on.to_numpy(bool), 0.5, 1.0)
        w_vb_gld = np.where(vix_brake_on.to_numpy(bool), 0.5, 0.0)
        w_vb_gld_tr = np.where(vix_brake_on.to_numpy(bool) & s2_gld_daily.to_numpy(bool), 0.5, 0.0)
        w_grd = vix_graded_w.to_numpy(float)
        w_or = np.where(vix_or_s2_off.to_numpy(bool), 0.5, 1.0)
        w_or_gld = np.where(vix_or_s2_off.to_numpy(bool), 0.5, 0.0)
        w_or_gld_tr = np.where(vix_or_s2_off.to_numpy(bool) & s2_gld_daily.to_numpy(bool), 0.5, 0.0)
        z = np.zeros(len(us_dates), dtype=float)

        return {
            "B0_SPY": lab.fixed_weight_signal([1.0, 0.0], us_dates, start_3a, freq="NONE"),
            "S2_CASH": build_state_change_signal(np.column_stack([w_s2, z]), start_3a),
            "VT_15": build_vt_signal(spy, start_3a, n_assets=2, target=0.15, window=21, band=0.10, cap=1.0),
            "VIX_BRAKE_CASH": build_state_change_signal(np.column_stack([w_vb, z]), start_3a),
            "VIX_BRAKE_GOLD": build_state_change_signal(np.column_stack([w_vb, w_vb_gld]), start_3a),
            "VIX_BRAKE_GOLD_TREND": build_state_change_signal(np.column_stack([w_vb, w_vb_gld_tr]), start_3a),
            "VIX_GRADED_CASH": build_state_change_signal(np.column_stack([w_grd, z]), start_3a),
            "VIX_OR_S2_CASH": build_state_change_signal(np.column_stack([w_or, z]), start_3a),
            "VIX_OR_S2_GOLD": build_state_change_signal(np.column_stack([w_or, w_or_gld]), start_3a),
            "VIX_OR_S2_GOLD_TREND": build_state_change_signal(np.column_stack([w_or, w_or_gld_tr]), start_3a),
        }

    core_3a_names = [
        "B0_SPY",
        "S2_CASH",
        "VT_15",
        "VIX_BRAKE_CASH",
        "VIX_BRAKE_GOLD",
        "VIX_BRAKE_GOLD_TREND",
        "VIX_GRADED_CASH",
        "VIX_OR_S2_CASH",
        "VIX_OR_S2_GOLD",
        "VIX_OR_S2_GOLD_TREND",
    ]
    brake_flags_3a = {
        "S2_CASH": ~s2_spy_daily,
        "VIX_BRAKE_CASH": vix_brake_on,
        "VIX_BRAKE_GOLD": vix_brake_on,
        "VIX_BRAKE_GOLD_TREND": vix_brake_on,
        "VIX_GRADED_CASH": vix_graded_w < 0.999,
        "VIX_OR_S2_CASH": vix_or_s2_off,
        "VIX_OR_S2_GOLD": vix_or_s2_off,
        "VIX_OR_S2_GOLD_TREND": vix_or_s2_off,
    }

    res_3a: dict[tuple[str, str], lab.MultiEngineResult] = {}
    for cost_label, cost_val in CONFIG["costs"].items():
        sigs = make_3a_signals()
        for name in core_3a_names:
            r = lab.run_multi_asset_overlay(px_3a, sigs[name], start_3a, cost_val, cash_pos, cash_neg)
            res_3a[(cost_label, name)] = r
            all_results[f"3A_{name}_{cost_label}"] = r

    # Matched average-SPY-weight fixed cash benchmarks (and fixed SPY+GLD benchmarks for gold variants)
    matched_3a_specs = []
    for ref_name in ["VIX_BRAKE_CASH", "VIX_GRADED_CASH", "VIX_OR_S2_CASH", "S2_CASH", "VT_15"]:
        w_avg = float(res_3a[("10bp", ref_name)].weights["spy"].iloc[1:].mean())
        matched_3a_specs.append((f"FIXED_CASH_MATCH_{ref_name}", [w_avg, 0.0]))
    for ref_name in ["VIX_BRAKE_GOLD", "VIX_OR_S2_GOLD"]:
        w_s = float(res_3a[("10bp", ref_name)].weights["spy"].iloc[1:].mean())
        w_g = float(res_3a[("10bp", ref_name)].weights["gld"].iloc[1:].mean())
        matched_3a_specs.append((f"FIXED_GOLD_MATCH_{ref_name}", [w_s, w_g]))

    all_3a_names = core_3a_names + [m[0] for m in matched_3a_specs]
    for cost_label, cost_val in CONFIG["costs"].items():
        for m_name, m_w in matched_3a_specs:
            sig = lab.fixed_weight_signal(m_w, us_dates, start_3a, freq="M")
            r = lab.run_multi_asset_overlay(px_3a, sig, start_3a, cost_val, cash_pos, cash_neg)
            res_3a[(cost_label, m_name)] = r
            all_results[f"3A_{m_name}_{cost_label}"] = r

    summary_3a_rows: list[dict] = []
    segs_3a = CONFIG["tracks"]["3A_vix_us"]["segments"]
    for cost_label in CONFIG["costs"]:
        for name in all_3a_names:
            b_info = (
                count_brake_episodes(brake_flags_3a[name], lab.US_VIX3M_START, lab.US_END)
                if name in brake_flags_3a
                else None
            )
            summary_3a_rows.extend(
                summarize_with_segments(
                    "3A_vix_us", "2006-2026", cost_label, name, res_3a[(cost_label, name)], "spy", segs_3a, b_info
                )
            )
    pd.DataFrame(summary_3a_rows).to_csv(OUT_DIR / "summary_vix_us.csv", index=False)

    res_3a_10bp = {n: res_3a[("10bp", n)] for n in all_3a_names}
    pd.DataFrame({n: res_3a_10bp[n].nav for n in core_3a_names}).to_csv(
        OUT_DIR / "nav_vix_us_10bp.csv", index_label="date"
    )
    key_period_rows.extend(
        evaluate_key_periods(
            {n: res_3a_10bp[n] for n in core_3a_names},
            "B0_SPY",
            "spy",
            CONFIG["key_periods_us"],
            "3A_vix_us",
        )
    )
    dca_rows.extend(run_dca_suite("3A_vix_us", "2006-2026", res_3a, all_3a_names, "B0_SPY", [120]))

    # Track 3A parameter sensitivity (10bp, 4 x 3 x 3 x 2 = 72 runs)
    sens_rows: list[dict] = []
    grid = CONFIG["tracks"]["3A_vix_us"]["sensitivity_grid"]
    z_us = np.zeros(len(us_dates), dtype=float)
    for variant in grid["variants"]:
        use_gold = variant == "VIX_BRAKE_GOLD"
        for trig in grid["trigger_ratio"]:
            for rdays in grid["recover_days"]:
                vb = compute_vix_brake_state(
                    vix_ratio,
                    start_date=lab.US_VIX3M_START,
                    trigger_ratio=trig,
                    recover_ratio=grid["recover_ratio"],
                    recover_days=rdays,
                )
                ep = count_brake_episodes(vb, lab.US_VIX3M_START, lab.US_END)
                vb_arr = vb.to_numpy(bool)
                for off_w in grid["off_spy_weight"]:
                    w_spy = np.where(vb_arr, off_w, 1.0)
                    w_gld = np.where(vb_arr, 1.0 - off_w, 0.0) if use_gold else z_us
                    sig = build_state_change_signal(np.column_stack([w_spy, w_gld]), start_3a)
                    r = lab.run_multi_asset_overlay(px_3a, sig, start_3a, 0.001, cash_pos, cash_neg)
                    m = lab.summarize_result(r, primary_col="spy")
                    all_results[f"SENS_{variant}_t{trig}_d{rdays}_w{off_w}_10bp"] = r
                    sens_rows.append(
                        {
                            "variant": variant,
                            "trigger_ratio": trig,
                            "recover_ratio": grid["recover_ratio"],
                            "recover_days": rdays,
                            "off_spy_weight": off_w,
                            "n_triggers": ep["n_triggers"],
                            "pct_days_brake_on": ep["pct_days_brake_on"],
                            **m,
                        }
                    )
    pd.DataFrame(sens_rows).to_csv(OUT_DIR / "sensitivity.csv", index=False)

    # =========================================================================
    # Track 3B: Credit Spread Risk Brakes
    #   3B-1: FRED BAA10Y (strict lag 1 trading day), 2000-01-03 ~ 2026-10-16
    #   3B-2: FRED BAA10Y + gld_real, 2005-01-03 ~ 2026-10-16
    #   3B-3: Real-time HYG / IEF (zero FRED lag), 2007-10-01 ~ 2026-10-16
    # =========================================================================
    summary_3b_rows: list[dict] = []

    # 3B-1: 2000-01-03 ~ 2026-10-16 (SPY + cash only; avoid gld NaNs pre-2004-11-18!)
    start_2000 = int(us_dates.searchsorted(pd.Timestamp(lab.US_MAIN_START)))
    px_2000 = pd.DataFrame({"spy": spy}, index=us_dates)
    baa_brake_2000 = compute_baa_credit_brake_state(baa10y, spy, lab.US_MAIN_START)

    def make_3b_2000_signals() -> dict[str, lab.MultiSignal]:
        w_s2 = np.where(s2_spy_daily.to_numpy(bool), 1.0, 0.5)[:, None]
        w_baa = np.where(baa_brake_2000.to_numpy(bool), 0.5, 1.0)[:, None]
        return {
            "B0_SPY": lab.fixed_weight_signal([1.0], us_dates, start_2000, freq="NONE"),
            "S2_CASH": build_state_change_signal(w_s2, start_2000),
            "VT_15": build_vt_signal(spy, start_2000, n_assets=1, target=0.15, window=21, band=0.10, cap=1.0),
            "CREDIT_BAA_CASH": build_state_change_signal(w_baa, start_2000),
        }

    names_2000 = ["B0_SPY", "S2_CASH", "VT_15", "CREDIT_BAA_CASH"]
    res_2000: dict[tuple[str, str], lab.MultiEngineResult] = {}
    for cost_label, cost_val in CONFIG["costs"].items():
        sigs = make_3b_2000_signals()
        for name in names_2000:
            r = lab.run_multi_asset_overlay(px_2000, sigs[name], start_2000, cost_val, cash_pos, cash_neg)
            res_2000[(cost_label, name)] = r
            all_results[f"3B2000_{name}_{cost_label}"] = r

    w_baa_avg = float(res_2000[("10bp", "CREDIT_BAA_CASH")].weights["spy"].iloc[1:].mean())
    for cost_label, cost_val in CONFIG["costs"].items():
        sig_m = lab.fixed_weight_signal([w_baa_avg], us_dates, start_2000, freq="M")
        r = lab.run_multi_asset_overlay(px_2000, sig_m, start_2000, cost_val, cash_pos, cash_neg)
        res_2000[(cost_label, "FIXED_CASH_MATCH_CREDIT_BAA")] = r
        all_results[f"3B2000_FIXED_CASH_MATCH_CREDIT_BAA_{cost_label}"] = r
    all_names_2000 = names_2000 + ["FIXED_CASH_MATCH_CREDIT_BAA"]

    segs_2000 = CONFIG["tracks"]["3B_credit_us"]["baa_2000_segments"]
    for cost_label in CONFIG["costs"]:
        for name in all_names_2000:
            b_info = (
                count_brake_episodes(baa_brake_2000, lab.US_MAIN_START, lab.US_END)
                if name == "CREDIT_BAA_CASH"
                else (count_brake_episodes(~s2_spy_daily, lab.US_MAIN_START, lab.US_END) if name == "S2_CASH" else None)
            )
            summary_3b_rows.extend(
                summarize_with_segments(
                    "3B_credit_baa_2000", "2000-2026", cost_label, name, res_2000[(cost_label, name)], "spy", segs_2000, b_info
                )
            )
    pd.DataFrame({n: res_2000[("10bp", n)].nav for n in all_names_2000}).to_csv(
        OUT_DIR / "nav_credit_2000_10bp.csv", index_label="date"
    )
    key_period_rows.extend(
        evaluate_key_periods(
            {n: res_2000[("10bp", n)] for n in names_2000},
            "B0_SPY",
            "spy",
            CONFIG["key_periods_us"],
            "3B_credit_baa_2000",
        )
    )
    dca_rows.extend(run_dca_suite("3B_credit_baa_2000", "2000-2026", res_2000, all_names_2000, "B0_SPY", [120]))

    # 3B-2: 2005-01-03 ~ 2026-10-16 (CREDIT_BAA_GOLD using real GLD)
    start_2005 = int(us_dates.searchsorted(pd.Timestamp(lab.US_GLD_START)))
    px_2005 = pd.DataFrame({"spy": spy, "gld": gld}, index=us_dates)
    baa_brake_2005 = compute_baa_credit_brake_state(baa10y, spy, lab.US_GLD_START)

    def make_3b_2005_signals() -> dict[str, lab.MultiSignal]:
        w_baa = np.where(baa_brake_2005.to_numpy(bool), 0.5, 1.0)
        w_gld = np.where(baa_brake_2005.to_numpy(bool), 0.5, 0.0)
        return {
            "B0_SPY": lab.fixed_weight_signal([1.0, 0.0], us_dates, start_2005, freq="NONE"),
            "CREDIT_BAA_CASH": build_state_change_signal(np.column_stack([w_baa, z_us]), start_2005),
            "CREDIT_BAA_GOLD": build_state_change_signal(np.column_stack([w_baa, w_gld]), start_2005),
        }

    names_2005 = ["B0_SPY", "CREDIT_BAA_CASH", "CREDIT_BAA_GOLD"]
    res_2005: dict[tuple[str, str], lab.MultiEngineResult] = {}
    for cost_label, cost_val in CONFIG["costs"].items():
        sigs = make_3b_2005_signals()
        for name in names_2005:
            r = lab.run_multi_asset_overlay(px_2005, sigs[name], start_2005, cost_val, cash_pos, cash_neg)
            res_2005[(cost_label, name)] = r
            all_results[f"3B2005_{name}_{cost_label}"] = r

    segs_2005 = CONFIG["tracks"]["3B_credit_us"]["baa_2005_segments"]
    for cost_label in CONFIG["costs"]:
        for name in names_2005:
            b_info = (
                count_brake_episodes(baa_brake_2005, lab.US_GLD_START, lab.US_END)
                if name.startswith("CREDIT_BAA")
                else None
            )
            summary_3b_rows.extend(
                summarize_with_segments(
                    "3B_credit_baa_2005", "2005-2026", cost_label, name, res_2005[(cost_label, name)], "spy", segs_2005, b_info
                )
            )
    dca_rows.extend(run_dca_suite("3B_credit_baa_2005", "2005-2026", res_2005, names_2005, "B0_SPY", [120]))

    # 3B-3: 2007-10-01 ~ 2026-10-16 (HYG / IEF live credit ratio, zero FRED lag)
    start_2007 = int(us_dates.searchsorted(pd.Timestamp("2007-10-01")))
    px_2007 = pd.DataFrame({"spy": spy, "gld": gld}, index=us_dates)
    hyg_brake_2007 = compute_hyg_ief_brake_state(hyg, ief, spy, "2007-10-01", ratio_ma_weeks=26, spy_ma_weeks=30)

    def make_3b_2007_signals() -> dict[str, lab.MultiSignal]:
        w_s2 = np.where(s2_spy_daily.to_numpy(bool), 1.0, 0.5)
        w_hyg = np.where(hyg_brake_2007.to_numpy(bool), 0.5, 1.0)
        w_gld = np.where(hyg_brake_2007.to_numpy(bool), 0.5, 0.0)
        return {
            "B0_SPY": lab.fixed_weight_signal([1.0, 0.0], us_dates, start_2007, freq="NONE"),
            "S2_CASH": build_state_change_signal(np.column_stack([w_s2, z_us]), start_2007),
            "HYG_IEF_CASH": build_state_change_signal(np.column_stack([w_hyg, z_us]), start_2007),
            "HYG_IEF_GOLD": build_state_change_signal(np.column_stack([w_hyg, w_gld]), start_2007),
        }

    names_2007 = ["B0_SPY", "S2_CASH", "HYG_IEF_CASH", "HYG_IEF_GOLD"]
    res_2007: dict[tuple[str, str], lab.MultiEngineResult] = {}
    for cost_label, cost_val in CONFIG["costs"].items():
        sigs = make_3b_2007_signals()
        for name in names_2007:
            r = lab.run_multi_asset_overlay(px_2007, sigs[name], start_2007, cost_val, cash_pos, cash_neg)
            res_2007[(cost_label, name)] = r
            all_results[f"3B2007_{name}_{cost_label}"] = r

    w_hyg_avg = float(res_2007[("10bp", "HYG_IEF_CASH")].weights["spy"].iloc[1:].mean())
    for cost_label, cost_val in CONFIG["costs"].items():
        sig_m = lab.fixed_weight_signal([w_hyg_avg, 0.0], us_dates, start_2007, freq="M")
        r = lab.run_multi_asset_overlay(px_2007, sig_m, start_2007, cost_val, cash_pos, cash_neg)
        res_2007[(cost_label, "FIXED_CASH_MATCH_HYG_IEF")] = r
        all_results[f"3B2007_FIXED_CASH_MATCH_HYG_IEF_{cost_label}"] = r
    all_names_2007 = names_2007 + ["FIXED_CASH_MATCH_HYG_IEF"]

    segs_2007 = CONFIG["tracks"]["3B_credit_us"]["hyg_ief_segments"]
    for cost_label in CONFIG["costs"]:
        for name in all_names_2007:
            b_info = (
                count_brake_episodes(hyg_brake_2007, "2007-10-01", lab.US_END)
                if name.startswith("HYG_IEF")
                else None
            )
            summary_3b_rows.extend(
                summarize_with_segments(
                    "3B_credit_hyg_ief_2007", "2007-2026", cost_label, name, res_2007[(cost_label, name)], "spy", segs_2007, b_info
                )
            )
    pd.DataFrame(summary_3b_rows).to_csv(OUT_DIR / "summary_credit_us.csv", index=False)

    key_period_rows.extend(
        evaluate_key_periods(
            {n: res_2007[("10bp", n)] for n in names_2007},
            "B0_SPY",
            "spy",
            CONFIG["key_periods_us"],
            "3B_credit_hyg_ief_2007",
        )
    )
    dca_rows.extend(run_dca_suite("3B_credit_hyg_ief_2007", "2007-2026", res_2007, all_names_2007, "B0_SPY", [120]))

    # =========================================================================
    # Track 3C: Domestic Transfer (513500 + 518880, 2014-10-08 ~ 2026-09-30)
    # =========================================================================
    cn_dates = cn["dates"]
    c513 = cn["c513500"]
    c518 = cn["c518880"]
    cn_cash_pos = cn["cash_pos"]
    cn_cash_neg = cn["cash_neg"]
    px_cn = pd.DataFrame({"c513500": c513, "c518880": c518}, index=cn_dates)
    start_cn = 0

    # Strictly < d mapping of completed US VIX brake state and US SPY S2 state
    cn_vix_brake, cn_used_us_dates = map_us_series_strictly_before_cn(vix_brake_on, cn_dates)
    cn_vix_brake = cn_vix_brake.astype(bool)
    cn_s2_us, _ = map_us_series_strictly_before_cn(s2_spy_daily, cn_dates)
    cn_s2_us = cn_s2_us.astype(bool)

    # 513500 self weekly S2 (warmed up from 2014-01-15 on c513500_full; valid since 2014-08-08)
    cn_s2_self_full = lab.weekly_stage2_state(cn["c513500_full"], ma_weeks=30, slope_weeks=4).astype(bool)
    cn_s2_self = cn_s2_self_full.reindex(cn_dates).fillna(False).astype(bool)

    cn_or_s2_self_off = cn_vix_brake | (~cn_s2_self)
    cn_or_s2_us_off = cn_vix_brake | (~cn_s2_us)
    z_cn = np.zeros(len(cn_dates), dtype=float)

    def make_3c_signals() -> dict[str, lab.MultiSignal]:
        w_s2 = np.where(cn_s2_self.to_numpy(bool), 1.0, 0.5)
        w_vb = np.where(cn_vix_brake.to_numpy(bool), 0.5, 1.0)
        w_vb_g = np.where(cn_vix_brake.to_numpy(bool), 0.5, 0.0)
        w_or = np.where(cn_or_s2_self_off.to_numpy(bool), 0.5, 1.0)
        w_or_g = np.where(cn_or_s2_self_off.to_numpy(bool), 0.5, 0.0)
        w_or_us = np.where(cn_or_s2_us_off.to_numpy(bool), 0.5, 1.0)
        w_or_us_g = np.where(cn_or_s2_us_off.to_numpy(bool), 0.5, 0.0)

        return {
            "B0_513500": lab.fixed_weight_signal([1.0, 0.0], cn_dates, start_cn, freq="NONE"),
            "CN_S2_CASH": build_state_change_signal(np.column_stack([w_s2, z_cn]), start_cn),
            "CN_VIX_BRAKE_CASH": build_state_change_signal(np.column_stack([w_vb, z_cn]), start_cn),
            "CN_VIX_BRAKE_GOLD": build_state_change_signal(np.column_stack([w_vb, w_vb_g]), start_cn),
            "CN_VIX_OR_S2_CASH": build_state_change_signal(np.column_stack([w_or, z_cn]), start_cn),
            "CN_VIX_OR_S2_GOLD": build_state_change_signal(np.column_stack([w_or, w_or_g]), start_cn),
            "CN_VIX_OR_S2_US_GOLD": build_state_change_signal(np.column_stack([w_or_us, w_or_us_g]), start_cn),
        }

    core_3c_names = [
        "B0_513500",
        "CN_S2_CASH",
        "CN_VIX_BRAKE_CASH",
        "CN_VIX_BRAKE_GOLD",
        "CN_VIX_OR_S2_CASH",
        "CN_VIX_OR_S2_GOLD",
        "CN_VIX_OR_S2_US_GOLD",
    ]
    brake_flags_3c = {
        "CN_S2_CASH": ~cn_s2_self,
        "CN_VIX_BRAKE_CASH": cn_vix_brake,
        "CN_VIX_BRAKE_GOLD": cn_vix_brake,
        "CN_VIX_OR_S2_CASH": cn_or_s2_self_off,
        "CN_VIX_OR_S2_GOLD": cn_or_s2_self_off,
        "CN_VIX_OR_S2_US_GOLD": cn_or_s2_us_off,
    }

    res_3c: dict[tuple[str, str], lab.MultiEngineResult] = {}
    for cost_label, cost_val in CONFIG["costs"].items():
        sigs = make_3c_signals()
        for name in core_3c_names:
            r = lab.run_multi_asset_overlay(px_cn, sigs[name], start_cn, cost_val, cn_cash_pos, cn_cash_neg)
            res_3c[(cost_label, name)] = r
            all_results[f"3C_{name}_{cost_label}"] = r

    # Matched average-513500-weight fixed cash and fixed gold benchmarks
    matched_3c_specs = []
    for ref_name in ["CN_VIX_BRAKE_CASH", "CN_VIX_OR_S2_CASH"]:
        w_avg = float(res_3c[("10bp", ref_name)].weights["c513500"].iloc[1:].mean())
        matched_3c_specs.append((f"CN_FIXED_CASH_MATCH_{ref_name}", [w_avg, 0.0]))
    for ref_name in ["CN_VIX_BRAKE_GOLD", "CN_VIX_OR_S2_GOLD"]:
        w_s = float(res_3c[("10bp", ref_name)].weights["c513500"].iloc[1:].mean())
        w_g = float(res_3c[("10bp", ref_name)].weights["c518880"].iloc[1:].mean())
        matched_3c_specs.append((f"CN_FIXED_GOLD_MATCH_{ref_name}", [w_s, w_g]))

    all_3c_names = core_3c_names + [m[0] for m in matched_3c_specs]
    for cost_label, cost_val in CONFIG["costs"].items():
        for m_name, m_w in matched_3c_specs:
            sig = lab.fixed_weight_signal(m_w, cn_dates, start_cn, freq="M")
            r = lab.run_multi_asset_overlay(px_cn, sig, start_cn, cost_val, cn_cash_pos, cn_cash_neg)
            res_3c[(cost_label, m_name)] = r
            all_results[f"3C_{m_name}_{cost_label}"] = r

    summary_3c_rows: list[dict] = []
    segs_3c = CONFIG["tracks"]["3C_domestic"]["segments"]
    for cost_label in CONFIG["costs"]:
        for name in all_3c_names:
            b_info = (
                count_brake_episodes(brake_flags_3c[name], lab.DOMESTIC_START, lab.DOMESTIC_END)
                if name in brake_flags_3c
                else None
            )
            summary_3c_rows.extend(
                summarize_with_segments(
                    "3C_domestic", "2014-2026", cost_label, name, res_3c[(cost_label, name)], "c513500", segs_3c, b_info
                )
            )
    pd.DataFrame(summary_3c_rows).to_csv(OUT_DIR / "summary_domestic.csv", index=False)

    res_3c_10bp = {n: res_3c[("10bp", n)] for n in all_3c_names}
    pd.DataFrame({n: res_3c_10bp[n].nav for n in core_3c_names}).to_csv(
        OUT_DIR / "nav_domestic_10bp.csv", index_label="date"
    )
    key_period_rows.extend(
        evaluate_key_periods(
            {n: res_3c_10bp[n] for n in core_3c_names},
            "B0_513500",
            "c513500",
            CONFIG["key_periods_domestic"],
            "3C_domestic",
        )
    )
    dca_rows.extend(run_dca_suite("3C_domestic", "2014-2026", res_3c, all_3c_names, "B0_513500", [60, 120]))

    # Write combined key_periods.csv and dca_summary.csv
    pd.DataFrame(key_period_rows).to_csv(OUT_DIR / "key_periods.csv", index=False)
    pd.DataFrame(dca_rows).to_csv(OUT_DIR / "dca_summary.csv", index=False)

    # Run and save comprehensive self-checks
    checks = run_self_checks(
        us=us,
        cn=cn,
        vix_brake_full=vix_brake_on,
        vix_graded_full=vix_graded_w,
        baa_brake_full=baa_brake_2000,
        hyg_brake_full=hyg_brake_2007,
        cn_vix_brake=cn_vix_brake,
        cn_used_us_dates=cn_used_us_dates,
        all_results=all_results,
        res_3a_10bp=res_3a_10bp,
        res_3c_10bp=res_3c_10bp,
    )
    (OUT_DIR / "self_checks.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not checks["all_passed"]:
        raise RuntimeError(f"Self-checks FAILED: {json.dumps(checks, indent=2)}")

    print(f"[OK] All outputs written to {OUT_DIR}")
    print(f"[OK] All self-checks passed ({checks['engine_accounting']['n_backtests_checked']} backtests).")


if __name__ == "__main__":
    main()
