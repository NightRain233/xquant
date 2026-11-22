"""Direction 4: Domestic 513500 practical enhancements (TVT-50 gold shield + real premium-protected DCA)
and crypto-exchange US-stock friction stress test.

Run (offline sandbox, from repo root):
    .venv/bin/python -I scripts/research_sp500_dir4_domestic_crypto_2026_11_22.py

All parameters and rules are frozen in ``CONFIG`` before execution.
All signals decide at close t using information <= close t only, and fill at close t+1.
For domestic QDII premium rules, ONLY ``premium_decision`` (derived from known T-2 NAV and
prior US close) is used for trading decisions; ``premium_after`` is strictly forbidden as a signal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xquant import cashflow_research as cf  # noqa: E402
from xquant import overlay_rules as ov  # noqa: E402
from xquant import sp500_lab as lab  # noqa: E402

SLUG = "sp500-dir4-domestic-crypto-2026-11-22"
OUT = ROOT / "outputs" / SLUG

CONFIG = {
    "slug": SLUG,
    "execution_clock": "Signal at close t (using data <= close t only); order fills at close t+1 with proportional one-way cost.",
    "anti_lookahead_premium": "ONLY premium_decision (T-2 NAV + overnight US ETF return) is used for signals; premium_after is strictly prohibited.",
    "part_a_domestic_overlay": {
        "window": [lab.DOMESTIC_START, lab.DOMESTIC_END],
        "segments": {
            "FULL": [lab.DOMESTIC_START, lab.DOMESTIC_END],
            "2014-2020": [lab.DOMESTIC_START, "2020-12-31"],
            "2021-2026": ["2021-01-01", lab.DOMESTIC_END],
        },
        "costs": {"10bp": 0.001, "30bp": 0.003},
        "cash_annual_rmb": 0.02,
        "tvt50_frozen": {
            "vol_window": 21,
            "target_vol": 0.15,
            "on_cap": 1.00,
            "off_cap": 0.50,
            "rebalance_band": 0.10,
            "weekly_stage_ma_weeks": 30,
            "weekly_stage_slope_weeks": 4,
            "gold_trend_ma_weeks": 30,
            "gold_trend_slope_weeks": 4,
        },
        "prem_trim_frozen": {
            "trim_above": 0.06,
            "restore_below": 0.02,
            "trimmed_eq_weight": 0.50,
        },
        "tvt50_prem_frozen": {
            "prem_cap_above": 0.06,
            "prem_cap_weight": 0.50,
        },
        "strategies": [
            "B0_513500",
            "TVT50_CASH",
            "TVT50_GOLD",
            "TVT50_GOLD_TREND",
            "TVT50_HALF_GOLD_CASH",
            "PREM_TRIM_GOLD",
            "PREM_TRIM_CASH",
            "TVT50_PREM_GOLD",
            "TVT50_PREM_GOLD_TREND",
        ],
        "key_periods": [
            {"label": "2016_prem_crash", "start": "2016-12-21", "end": "2017-01-24"},
            {"label": "2018_q4_selloff", "start": "2018-10-01", "end": "2018-12-31"},
            {"label": "2020_covid_crash", "start": "2020-02-01", "end": "2020-03-31"},
            {"label": "2022_rate_bear", "start": "2022-01-01", "end": "2022-12-31"},
            {"label": "2024_2025_prem_tariff", "start": "2024-12-01", "end": "2025-04-30"},
            {"label": "2023_2026_bull_gold", "start": "2023-01-01", "end": "2026-09-30"},
        ],
        "sensitivity_10bp": {
            "tvt_target_vols": [0.12, 0.15, 0.18],
            "tvt_off_caps": [0.25, 0.50, 0.75],
            "prem_trim_thresholds": [0.04, 0.06, 0.08, 0.10],
            "prem_restore_threshold": 0.02,
        },
    },
    "part_b_domestic_dca_parking": {
        "window": [lab.DOMESTIC_START, lab.DOMESTIC_END],
        "contribution": "1.0 unit cash injected on the first mainland trading day of every month",
        "costs": {"10bp": 0.001, "30bp": 0.003},
        "rolling_windows_months": [60, 120],
        "strategies": [
            "DCA_PLAIN",
            "DCA_PREM3_CASH",
            "DCA_PREM3_GOLD",
            "DCA_PREM5_GOLD",
            "DCA_TVT50_GOLD",
        ],
        "tvt_dca_prem_park_threshold": 0.05,
    },
    "part_c_crypto_stress": {
        "window": [lab.US_GLD_START, lab.US_END],
        "gold_series": "gld_real (pure GLD ETF, no pre-2004 splice)",
        "strategies": [
            "B0_SPY",
            "GOLD_75_25_Q",
            "S2_CASH",
            "S2_GOLD",
            "TVT50_CASH",
            "TVT50_GOLD",
        ],
        "scenarios": [
            {"scenario": "US_ETF_10bp", "cost": 0.001, "spy_drag_mode": "zero", "spy_drag_annual": 0.0},
            {"scenario": "CRYPTO_SPOT_DIV_30bp", "cost": 0.003, "spy_drag_mode": "zero", "spy_drag_annual": 0.0},
            {"scenario": "CRYPTO_SPOT_DIV_50bp", "cost": 0.005, "spy_drag_mode": "zero", "spy_drag_annual": 0.0},
            {"scenario": "CRYPTO_SPOT_NODIV_30bp", "cost": 0.003, "spy_drag_mode": "measured_spy_dividend_yield", "spy_drag_annual": None},
            {"scenario": "CRYPTO_PERP_5PCT_20bp", "cost": 0.002, "spy_drag_mode": "fixed_funding", "spy_drag_annual": 0.05},
            {"scenario": "CRYPTO_PERP_8PCT_20bp", "cost": 0.002, "spy_drag_mode": "fixed_funding", "spy_drag_annual": 0.08},
        ],
        "dca_rolling_window_months": 120,
    },
}


# --------------------------------------------------------------------------- Helpers & Signal Builders

def compute_realized_vol(close_full: pd.Series, window: int = 21) -> pd.Series:
    return np.log(close_full).diff().rolling(window).std(ddof=1) * np.sqrt(lab.TRADING_DAYS)


def build_tvt_signal(
    vol_arr: np.ndarray,
    eq_trend_arr: np.ndarray,
    start_i: int,
    *,
    defensive_mode: str = "cash",
    gold_trend_arr: Optional[np.ndarray] = None,
    prem_arr: Optional[np.ndarray] = None,
    target_vol: float = 0.15,
    on_cap: float = 1.0,
    off_cap: float = 0.50,
    band: float = 0.10,
    prem_cap_above: Optional[float] = None,
):
    """Unified TVT-50 2-asset signal ([equity, gold], rest in cash).

    defensive_mode:
      - 'cash': unallocated weight stays in cash
      - 'gold': unallocated weight goes 100% into gold
      - 'gold_trend': unallocated weight goes into gold iff gold_trend_arr[i] is True, else cash
      - 'half_gold_cash': unallocated weight split 50% gold / 50% cash
    """
    def sig(i: int, actual: np.ndarray) -> Optional[np.ndarray]:
        v = vol_arr[i]
        if not np.isfinite(v) or v <= 0.0:
            return None
        trend_on = bool(eq_trend_arr[i])
        cap = on_cap if trend_on else off_cap
        if prem_cap_above is not None and prem_arr is not None:
            p = prem_arr[i]
            if np.isfinite(p) and p > prem_cap_above:
                cap = min(cap, off_cap)
        w_eq = float(min(cap, target_vol / v))
        w_eq = float(np.clip(w_eq, 0.0, 1.0))
        rem = 1.0 - w_eq
        if defensive_mode == "cash":
            w_gold = 0.0
        elif defensive_mode == "gold":
            w_gold = rem
        elif defensive_mode == "gold_trend":
            w_gold = rem if (gold_trend_arr is not None and bool(gold_trend_arr[i])) else 0.0
        elif defensive_mode == "half_gold_cash":
            w_gold = 0.5 * rem
        else:
            raise ValueError(f"unknown defensive_mode: {defensive_mode}")
        wanted = np.array([w_eq, w_gold], dtype=float)
        if i == start_i:
            return wanted
        # Trigger rebalance when primary equity or defensive gold deviates from actual by > band.
        # For cash-only and full-gold modes, max(|w_eq - a_eq|, |w_gold - a_gold|) == |w_eq - a_eq|.
        if max(abs(wanted[0] - actual[0]), abs(wanted[1] - actual[1])) > band:
            return wanted
        return None

    return sig


def build_prem_trim_signal(
    prem_arr: np.ndarray,
    start_i: int,
    *,
    defensive_mode: str = "gold",
    trim_above: float = 0.06,
    restore_below: float = 0.02,
    trimmed_eq_weight: float = 0.50,
):
    """Hysteresis premium-risk overlay: 100% 513500 by default; trim to 50% when prem > trim_above,
    restore to 100% when prem < restore_below. Uses ONLY premium_decision."""
    state = {"trimmed": None}

    def target_vec(trimmed: bool) -> np.ndarray:
        if not trimmed:
            return np.array([1.0, 0.0], dtype=float)
        rem = 1.0 - trimmed_eq_weight
        return np.array([trimmed_eq_weight, rem if defensive_mode == "gold" else 0.0], dtype=float)

    def sig(i: int, _actual: np.ndarray) -> Optional[np.ndarray]:
        p = prem_arr[i]
        if state["trimmed"] is None:
            init_trim = bool(np.isfinite(p) and p > trim_above)
            state["trimmed"] = init_trim
            return target_vec(init_trim)
        prev = state["trimmed"]
        curr = prev
        if np.isfinite(p):
            if (not prev) and (p > trim_above):
                curr = True
            elif prev and (p < restore_below):
                curr = False
        state["trimmed"] = curr
        if curr != prev:
            return target_vec(curr)
        return None

    return sig


def build_s2_signal(eq_trend_arr: np.ndarray, start_i: int, defensive_mode: str = "cash"):
    """Frozen S2 weekly Stage-2 half-trend rule: 100% equity on trend-on, 50% equity + 50% cash/gold on trend-off."""
    state = {"last": None}

    def sig(i: int, _actual: np.ndarray) -> Optional[np.ndarray]:
        on = bool(eq_trend_arr[i])
        if i == start_i or state["last"] is None or on != state["last"]:
            state["last"] = on
            if on:
                return np.array([1.0, 0.0], dtype=float)
            return np.array([0.5, 0.5 if defensive_mode == "gold" else 0.0], dtype=float)
        return None

    return sig


def key_period_metrics(nav: pd.Series, start: str, end: str) -> dict:
    part = ov.segment_slice(nav, start, end)
    if len(part) < 2:
        return {"period_return": np.nan, "period_max_dd": np.nan}
    ret = float(part.iloc[-1] / part.iloc[0] - 1.0)
    dd = float((part / part.cummax() - 1.0).min())
    return {"period_return": ret, "period_max_dd": dd}


# --------------------------------------------------------------------------- Part B: Real Cashflow DCA Parking Engine

def simulate_dca_parking_account(
    dates: pd.DatetimeIndex,
    p_eq: np.ndarray,
    p_gold: np.ndarray,
    cash_pos: np.ndarray,
    prem_dec: np.ndarray,
    prem_after: np.ndarray,
    mode: str,
    *,
    cost: float = 0.001,
    prem_threshold: Optional[float] = None,
    tvt_w_eq: Optional[np.ndarray] = None,
    tvt_band: float = 0.10,
    tvt_prem_park_thr: float = 0.05,
) -> dict:
    """Real cashflow monthly DCA account simulator (1 unit injected on first trading day of each month).

    Strict causality / anti-lookahead:
      - ``DCA_PLAIN``: mechanical buy on contribution day close (no signal read).
      - All premium-dependent and TVT rules decide at close i using data <= close i (ONLY ``prem_dec[i]``),
        and execute orders at close i + 1 with one-way proportional cost on every buy/sell leg.
    """
    n = len(dates)
    months = dates.to_period("M")
    is_contrib = np.zeros(n, dtype=bool)
    is_contrib[0] = True
    if n > 1:
        is_contrib[1:] = months[1:] != months[:-1]
    contrib_dates = dates[is_contrib]

    sh_eq = 0.0
    sh_gold = 0.0
    cash = 0.0
    principal = 0.0

    # Pending order state decided at close i-1, executed at close i
    # Types: None, ('BUY_EQ_CASH',), ('PARK_GOLD',), ('SWITCH_ALL_TO_EQ',),
    #        ('TVT_REBAL', w_eq_tgt), ('TVT_INJECT', w_eq_new)
    pending = None

    val_arr = np.empty(n, dtype=float)
    princ_arr = np.empty(n, dtype=float)
    twr_nav = np.empty(n, dtype=float)
    twr_curr = 1.0
    prev_val_post = 0.0

    buy_eq_amounts: list[float] = []
    buy_eq_prem_dec: list[float] = []
    buy_eq_prem_after: list[float] = []
    total_cost_paid = 0.0
    max_cash_resid = 0.0
    n_trades = 0
    delayed_months = 0
    order_lag_violations = 0

    for i in range(n):
        # 1) Accrue cash interest from close i-1 to close i
        if i > 0:
            cash *= cash_pos[i]

        # Pre-contribution / pre-trade mark-to-market for TWR return
        val_before_flow = sh_eq * p_eq[i] + sh_gold * p_gold[i] + cash

        # 2) Execute pending order decided at close i-1 at today's close i
        if pending is not None:
            kind = pending[0]
            dec_i = pending[-1]
            if dec_i >= i:
                order_lag_violations += 1

            if kind == "BUY_EQ_CASH":
                if cash > 1e-12:
                    amt = cash
                    c = amt * cost
                    net = amt - c
                    sh_eq += net / p_eq[i]
                    cash = 0.0
                    total_cost_paid += c
                    n_trades += 1
                    buy_eq_amounts.append(amt)
                    buy_eq_prem_dec.append(float(prem_dec[i]))
                    buy_eq_prem_after.append(float(prem_after[i]))
                    max_cash_resid = max(max_cash_resid, abs((net + c) - amt))

            elif kind == "PARK_GOLD":
                if cash > 1e-12:
                    amt = cash
                    c = amt * cost
                    net = amt - c
                    sh_gold += net / p_gold[i]
                    cash = 0.0
                    total_cost_paid += c
                    n_trades += 1
                    max_cash_resid = max(max_cash_resid, abs((net + c) - amt))

            elif kind == "SWITCH_ALL_TO_EQ":
                # Sell all parked gold (pay sell cost), then buy 513500 with proceeds + cash (pay buy cost)
                total_before = sh_gold * p_gold[i] + cash
                sell_cost = 0.0
                if sh_gold > 1e-12:
                    gross_g = sh_gold * p_gold[i]
                    sell_cost = gross_g * cost
                    cash += gross_g - sell_cost
                    sh_gold = 0.0
                    total_cost_paid += sell_cost
                    n_trades += 1
                buy_cost = 0.0
                net_eq = 0.0
                if cash > 1e-12:
                    amt = cash
                    buy_cost = amt * cost
                    net_eq = amt - buy_cost
                    sh_eq += net_eq / p_eq[i]
                    cash = 0.0
                    total_cost_paid += buy_cost
                    n_trades += 1
                    buy_eq_amounts.append(amt)
                    buy_eq_prem_dec.append(float(prem_dec[i]))
                    buy_eq_prem_after.append(float(prem_after[i]))
                max_cash_resid = max(max_cash_resid, abs((net_eq + sell_cost + buy_cost) - total_before))

            elif kind == "TVT_REBAL":
                w_eq_tgt = float(pending[1])
                w_tgt = np.array([w_eq_tgt, 1.0 - w_eq_tgt], dtype=float)
                hold = np.array([sh_eq * p_eq[i], sh_gold * p_gold[i]], dtype=float)
                total = float(hold.sum() + cash)
                if total > 1e-12:
                    c_est = 0.0
                    for _ in range(8):
                        tgt = w_tgt * (total - c_est)
                        c_est = float(cost * np.abs(tgt - hold).sum())
                    tgt = w_tgt * (total - c_est)
                    new_cash = float(total - c_est - tgt.sum())
                    max_cash_resid = max(max_cash_resid, abs((float(tgt.sum()) + new_cash + c_est) - total))
                    eq_buy = float(tgt[0] - hold[0])
                    if eq_buy > 1e-12:
                        buy_eq_amounts.append(eq_buy)
                        buy_eq_prem_dec.append(float(prem_dec[i]))
                        buy_eq_prem_after.append(float(prem_after[i]))
                    sh_eq = float(tgt[0] / p_eq[i])
                    sh_gold = float(tgt[1] / p_gold[i])
                    cash = new_cash
                    total_cost_paid += c_est
                    n_trades += 1

            elif kind == "TVT_INJECT":
                # Only deploy cash according to (w_eq_new, 1 - w_eq_new), leaving existing shares untouched
                w_eq_new = float(pending[1])
                if cash > 1e-12:
                    amt = cash
                    c = amt * cost
                    net = amt - c
                    net_eq = net * w_eq_new
                    net_gold = net * (1.0 - w_eq_new)
                    sh_eq += net_eq / p_eq[i]
                    sh_gold += net_gold / p_gold[i]
                    cash = 0.0
                    total_cost_paid += c
                    n_trades += 1
                    if amt * w_eq_new > 1e-12:
                        buy_eq_amounts.append(amt * w_eq_new)
                        buy_eq_prem_dec.append(float(prem_dec[i]))
                        buy_eq_prem_after.append(float(prem_after[i]))
                    max_cash_resid = max(max_cash_resid, abs((net_eq + net_gold + c) - amt))

            pending = None

        # TWR daily update (uses value after execution of prior-day portfolio trades, before today's external cashflow)
        val_after_rebal_pre_flow = sh_eq * p_eq[i] + sh_gold * p_gold[i] + cash
        if i == 0:
            twr_curr = 1.0
        else:
            if prev_val_post > 1e-12:
                twr_curr *= val_after_rebal_pre_flow / prev_val_post
        twr_nav[i] = twr_curr

        # 3) Monthly external cashflow injection on first trading day of month
        injected_today = False
        if is_contrib[i]:
            cash += 1.0
            principal += 1.0
            injected_today = True
            if mode == "DCA_PLAIN":
                # Mechanical purchase at contribution day close (does not read premium)
                amt = cash
                c = amt * cost
                net = amt - c
                sh_eq += net / p_eq[i]
                cash = 0.0
                total_cost_paid += c
                n_trades += 1
                buy_eq_amounts.append(amt)
                buy_eq_prem_dec.append(float(prem_dec[i]))
                buy_eq_prem_after.append(float(prem_after[i]))
                max_cash_resid = max(max_cash_resid, abs((net + c) - amt))
                # For day 0 TWR consistency, reflect initial buy cost in prev_val_post
                if i == 0:
                    twr_curr = (sh_eq * p_eq[i] + sh_gold * p_gold[i] + cash) / principal
                    twr_nav[i] = twr_curr

        val_now = sh_eq * p_eq[i] + sh_gold * p_gold[i] + cash
        val_arr[i] = val_now
        princ_arr[i] = principal
        prev_val_post = val_now

        # 4) Close-of-day decision for execution at close i+1 (strictly no lookahead)
        if i < n - 1 and mode != "DCA_PLAIN":
            p = prem_dec[i]
            if mode == "DCA_PREM_CASH":
                assert prem_threshold is not None
                if cash > 1e-12:
                    if np.isfinite(p) and p <= prem_threshold:
                        pending = ("BUY_EQ_CASH", i)
                    elif injected_today:
                        delayed_months += 1

            elif mode == "DCA_PREM_GOLD":
                assert prem_threshold is not None
                high_prem = bool(np.isfinite(p) and p > prem_threshold)
                if not high_prem:
                    if sh_gold > 1e-12:
                        pending = ("SWITCH_ALL_TO_EQ", i)
                    elif cash > 1e-12:
                        pending = ("BUY_EQ_CASH", i)
                else:
                    if injected_today:
                        delayed_months += 1
                    if cash > 1e-12:
                        pending = ("PARK_GOLD", i)

            elif mode == "DCA_TVT50_GOLD":
                assert tvt_w_eq is not None
                w_tgt = float(tvt_w_eq[i])
                high_prem = bool(np.isfinite(p) and p > tvt_prem_park_thr)
                eq_val = sh_eq * p_eq[i]
                actual_eq_w = eq_val / val_now if val_now > 1e-12 else 0.0

                if high_prem:
                    if injected_today:
                        delayed_months += 1
                    # Never increase 513500 exposure while premium > 5%:
                    # - If existing 513500 weight exceeds target by > band, trim 513500 to target (and new cash goes to gold).
                    # - Otherwise deploy any cash 100% into gold without buying 513500.
                    if actual_eq_w - w_tgt > tvt_band:
                        pending = ("TVT_REBAL", w_tgt, i)
                    elif cash > 1e-12:
                        pending = ("TVT_INJECT", 0.0, i)
                else:
                    if cash > 1e-12:
                        # Check post-injection equity weight if we only deploy cash at w_tgt
                        proj_eq_w = (eq_val + cash * (1.0 - cost) * w_tgt) / val_now if val_now > 1e-12 else w_tgt
                        if abs(w_tgt - proj_eq_w) > tvt_band:
                            pending = ("TVT_REBAL", w_tgt, i)
                        else:
                            pending = ("TVT_INJECT", w_tgt, i)
                    else:
                        if abs(w_tgt - actual_eq_w) > tvt_band:
                            pending = ("TVT_REBAL", w_tgt, i)

    terminal = float(val_arr[-1])
    x = float(cf.xirr(pd.Series(1.0, index=contrib_dates), terminal, dates[-1]))
    float_ret = val_arr / princ_arr - 1.0
    max_float_loss = float(np.min(float_ret))
    twr_dd = twr_nav / np.maximum.accumulate(twr_nav) - 1.0
    twr_max_dd = float(np.min(twr_dd))

    xirr_to_float = float(x / abs(max_float_loss)) if max_float_loss < -1e-12 else np.nan
    xirr_to_twr_mdd = float(x / abs(twr_max_dd)) if twr_max_dd < -1e-12 else np.nan

    if buy_eq_amounts:
        w_arr = np.asarray(buy_eq_amounts, dtype=float)
        pd_arr = np.asarray(buy_eq_prem_dec, dtype=float)
        pa_arr = np.asarray(buy_eq_prem_after, dtype=float)
        m_d = np.isfinite(pd_arr)
        m_a = np.isfinite(pa_arr)
        avg_prem_dec = float(np.average(pd_arr[m_d], weights=w_arr[m_d])) if m_d.any() else np.nan
        avg_prem_after = float(np.average(pa_arr[m_a], weights=w_arr[m_a])) if m_a.any() else np.nan
    else:
        avg_prem_dec = np.nan
        avg_prem_after = np.nan

    ending_parked_share = float((sh_gold * p_gold[-1] + cash) / terminal) if terminal > 0 else np.nan
    return {
        "n_months": int(len(contrib_dates)),
        "xirr": x,
        "max_float_loss": max_float_loss,
        "twr_max_dd": twr_max_dd,
        "xirr_to_float_loss": xirr_to_float,
        "xirr_to_twr_mdd": xirr_to_twr_mdd,
        "terminal_per_unit": float(terminal / len(contrib_dates)),
        "avg_premium_paid": avg_prem_dec,
        "avg_premium_after_diag": avg_prem_after,
        "delayed_months": int(delayed_months),
        "n_trades": int(n_trades),
        "total_cost_paid": float(total_cost_paid),
        "ending_parked_share": ending_parked_share,
        "max_cash_residual": float(max_cash_resid),
        "min_account_value": float(np.min(val_arr)),
        "order_lag_violations": int(order_lag_violations),
    }


def rolling_dca_parking_windows(
    dates: pd.DatetimeIndex,
    p_eq: np.ndarray,
    p_gold: np.ndarray,
    cash_pos: np.ndarray,
    prem_dec: np.ndarray,
    prem_after: np.ndarray,
    tvt_w_eq: np.ndarray,
    window_months: int,
    cost: float,
) -> pd.DataFrame:
    """Evaluate all 5 real cashflow DCA strategies across every complete N-month rolling window."""
    periods = dates.to_period("M")
    first_pos = np.flatnonzero(np.r_[True, periods[1:] != periods[:-1]])
    # Pre-find valid (start_pos, end_pos) slices
    slices: list[tuple[int, int, str, str]] = []
    for sp in first_pos:
        end_p = periods[sp] + window_months - 1
        end_matches = np.flatnonzero(periods == end_p)
        if len(end_matches) == 0:
            continue
        ep = int(end_matches[-1])
        # Verify exact month count
        sub_p = periods[sp : ep + 1]
        if int(len(np.unique(sub_p))) != window_months:
            continue
        slices.append((int(sp), ep, str(dates[sp].date()), str(dates[ep].date())))

    specs = [
        ("DCA_PLAIN", "DCA_PLAIN", None),
        ("DCA_PREM3_CASH", "DCA_PREM_CASH", 0.03),
        ("DCA_PREM3_GOLD", "DCA_PREM_GOLD", 0.03),
        ("DCA_PREM5_GOLD", "DCA_PREM_GOLD", 0.05),
        ("DCA_TVT50_GOLD", "DCA_TVT50_GOLD", None),
    ]
    rows = []
    for sp, ep, st_str, en_str in slices:
        d_sub = dates[sp : ep + 1]
        pe_sub = p_eq[sp : ep + 1]
        pg_sub = p_gold[sp : ep + 1]
        cp_sub = cash_pos[sp : ep + 1]
        pd_sub = prem_dec[sp : ep + 1]
        pa_sub = prem_after[sp : ep + 1]
        tw_sub = tvt_w_eq[sp : ep + 1]
        plain_res = None
        for label, mode, thr in specs:
            res = simulate_dca_parking_account(
                d_sub, pe_sub, pg_sub, cp_sub, pd_sub, pa_sub,
                mode=mode, cost=cost, prem_threshold=thr, tvt_w_eq=tw_sub,
                tvt_band=CONFIG["part_a_domestic_overlay"]["tvt50_frozen"]["rebalance_band"],
                tvt_prem_park_thr=CONFIG["part_b_domestic_dca_parking"]["tvt_dca_prem_park_threshold"],
            )
            if label == "DCA_PLAIN":
                plain_res = res
            rows.append({
                "window_months": window_months,
                "start": st_str,
                "end": en_str,
                "strategy": label,
                **res,
                "beat_plain_xirr": bool(res["xirr"] > plain_res["xirr"]) if plain_res is not None else False,
                "beat_plain_twr_ratio": bool(res["xirr_to_twr_mdd"] > plain_res["xirr_to_twr_mdd"])
                if (plain_res is not None and np.isfinite(res["xirr_to_twr_mdd"]) and np.isfinite(plain_res["xirr_to_twr_mdd"]))
                else False,
                "beat_plain_float_ratio": bool(res["xirr_to_float_loss"] > plain_res["xirr_to_float_loss"])
                if (plain_res is not None and np.isfinite(res["xirr_to_float_loss"]) and np.isfinite(plain_res["xirr_to_float_loss"]))
                else False,
            })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- SPY Dividend Yield Measurement

def measure_spy_dividend_yield(start: str = lab.US_GLD_START, end: str = lab.US_END) -> dict:
    """Measure SPY 2005-2026 actual historical annual dividend yield from yf_SPY.csv Dividends column.

    Note: ``yf_SPY.csv`` uses yfinance ``auto_adjust=True``, so ``Close`` is total-return adjusted
    while ``Dividends`` are nominal cash dividends per share. We reconstruct the exact unadjusted
    price-only close backwards from the end via Yahoo's standard ex-dividend adjustment identity:
        P_unadj[t] = P_unadj[t+1] * (P_adj[t] / P_adj[t+1]) + D[t+1]
    and compute both the geometric dividend drag ``1 - (1 + CAGR_price) / (1 + CAGR_total)``
    and the annual arithmetic dividend yield ``sum(D_t / P_unadj[t-1])``.
    """
    df = pd.read_csv(lab.US_SECTOR_CACHE / "yf_SPY.csv")
    df["date"] = pd.to_datetime(df["Date"].astype(str).str.slice(0, 10))
    df = df.set_index("date").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    sub = df.loc[start:end].copy()

    c_adj = sub["Close"].to_numpy(float)
    div = sub["Dividends"].to_numpy(float)
    p_unadj = np.empty_like(c_adj)
    p_unadj[-1] = c_adj[-1]
    for i in range(len(c_adj) - 2, -1, -1):
        p_unadj[i] = p_unadj[i + 1] * (c_adj[i] / c_adj[i + 1]) + div[i + 1]

    sub["p_unadj"] = p_unadj
    years = (sub.index[-1] - sub.index[0]).days / 365.25
    cagr_tr = float((c_adj[-1] / c_adj[0]) ** (1.0 / years) - 1.0)
    cagr_price = float((p_unadj[-1] / p_unadj[0]) ** (1.0 / years) - 1.0)
    # Exact annualized multiplicative drag matching run_multi_asset_overlay's (1 - drag)^(days/365.25):
    implied_div_drag = float(1.0 - (1.0 + cagr_price) / (1.0 + cagr_tr))

    daily_div_y = sub["Dividends"] / sub["p_unadj"].shift(1)
    annual_yields = daily_div_y.resample("YE").sum()
    full_years = annual_yields.loc["2005":"2025"]

    return {
        "window": [str(sub.index[0].date()), str(sub.index[-1].date())],
        "years": round(years, 4),
        "n_dividend_events": int((sub["Dividends"] > 0).sum()),
        "cagr_total_return": cagr_tr,
        "cagr_price_only_unadj": cagr_price,
        "cagr_diff_tr_minus_price": float(cagr_tr - cagr_price),
        "implied_annual_div_drag": implied_div_drag,
        "mean_annual_div_yield_2005_2025": float(full_years.mean()),
        "median_annual_div_yield_2005_2025": float(full_years.median()),
        "min_annual_div_yield_2005_2025": float(full_years.min()),
        "max_annual_div_yield_2005_2025": float(full_years.max()),
        "total_div_yield_per_year": float(daily_div_y.sum() / years),
        "reconstructed_unadj_spot_checks": {
            "2005-01-03": round(float(sub.loc["2005-01-03", "p_unadj"]), 4),
            "2015-01-02": round(float(sub.loc["2015-01-02", "p_unadj"]), 4),
            "2020-01-02": round(float(sub.loc["2020-01-02", "p_unadj"]), 4),
            "2026-10-16": round(float(sub.loc["2026-10-16", "p_unadj"]), 4),
        },
        "in_expected_range_1p5_to_1p9pct": bool(0.015 <= implied_div_drag <= 0.019),
    }


# --------------------------------------------------------------------------- Main Research Pipeline

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    checks_summary: dict = {
        "max_cash_residual": 0.0,
        "nav_min": float("inf"),
        "target_weight_min": float("inf"),
        "target_sum_max": 0.0,
    }

    def record_engine_checks(res: lab.MultiEngineResult) -> None:
        checks_summary["max_cash_residual"] = max(checks_summary["max_cash_residual"], res.checks["max_cash_residual"])
        checks_summary["nav_min"] = min(checks_summary["nav_min"], res.checks["nav_min"])
        checks_summary["target_weight_min"] = min(checks_summary["target_weight_min"], res.checks["target_weight_min"])
        checks_summary["target_sum_max"] = max(checks_summary["target_sum_max"], res.checks["target_sum_max"])

    # =========================================================================
    # PART A: Domestic 513500 Stock-Account Enhancements (2014-10-08 ~ 2026-09-30)
    # =========================================================================
    dom = lab.load_domestic_bundle()
    d_dates = dom["dates"]
    d_prices = pd.DataFrame({"c513500": dom["c513500"], "c518880": dom["c518880"]}, index=d_dates)

    # Precompute frozen self-signals on full history, indexed to [2014-10-08, 2026-09-30]
    tvt_cfg = CONFIG["part_a_domestic_overlay"]["tvt50_frozen"]
    prem_cfg = CONFIG["part_a_domestic_overlay"]["prem_trim_frozen"]
    tvtp_cfg = CONFIG["part_a_domestic_overlay"]["tvt50_prem_frozen"]

    vol_513500 = compute_realized_vol(dom["c513500_full"], tvt_cfg["vol_window"]).reindex(d_dates).to_numpy(float)
    trend_513500 = lab.weekly_stage2_state(
        dom["c513500_full"], tvt_cfg["weekly_stage_ma_weeks"], tvt_cfg["weekly_stage_slope_weeks"]
    ).reindex(d_dates).to_numpy(bool)
    trend_518880 = lab.weekly_stage2_state(
        dom["c518880_full"], tvt_cfg["gold_trend_ma_weeks"], tvt_cfg["gold_trend_slope_weeks"]
    ).reindex(d_dates).to_numpy(bool)

    # Strictly use premium_decision (NEVER premium_after)
    prem_dec = dom["premium_decision"].to_numpy(float)
    prem_after = dom["premium_after"].to_numpy(float)

    def make_domestic_builders():
        return {
            "B0_513500": lambda: lab.fixed_weight_signal([1.0, 0.0], d_dates, 0, freq="NONE"),
            "TVT50_CASH": lambda: build_tvt_signal(
                vol_513500, trend_513500, 0, defensive_mode="cash",
                target_vol=tvt_cfg["target_vol"], on_cap=tvt_cfg["on_cap"],
                off_cap=tvt_cfg["off_cap"], band=tvt_cfg["rebalance_band"],
            ),
            "TVT50_GOLD": lambda: build_tvt_signal(
                vol_513500, trend_513500, 0, defensive_mode="gold",
                target_vol=tvt_cfg["target_vol"], on_cap=tvt_cfg["on_cap"],
                off_cap=tvt_cfg["off_cap"], band=tvt_cfg["rebalance_band"],
            ),
            "TVT50_GOLD_TREND": lambda: build_tvt_signal(
                vol_513500, trend_513500, 0, defensive_mode="gold_trend",
                gold_trend_arr=trend_518880,
                target_vol=tvt_cfg["target_vol"], on_cap=tvt_cfg["on_cap"],
                off_cap=tvt_cfg["off_cap"], band=tvt_cfg["rebalance_band"],
            ),
            "TVT50_HALF_GOLD_CASH": lambda: build_tvt_signal(
                vol_513500, trend_513500, 0, defensive_mode="half_gold_cash",
                target_vol=tvt_cfg["target_vol"], on_cap=tvt_cfg["on_cap"],
                off_cap=tvt_cfg["off_cap"], band=tvt_cfg["rebalance_band"],
            ),
            "PREM_TRIM_GOLD": lambda: build_prem_trim_signal(
                prem_dec, 0, defensive_mode="gold",
                trim_above=prem_cfg["trim_above"], restore_below=prem_cfg["restore_below"],
                trimmed_eq_weight=prem_cfg["trimmed_eq_weight"],
            ),
            "PREM_TRIM_CASH": lambda: build_prem_trim_signal(
                prem_dec, 0, defensive_mode="cash",
                trim_above=prem_cfg["trim_above"], restore_below=prem_cfg["restore_below"],
                trimmed_eq_weight=prem_cfg["trimmed_eq_weight"],
            ),
            "TVT50_PREM_GOLD": lambda: build_tvt_signal(
                vol_513500, trend_513500, 0, defensive_mode="gold",
                prem_arr=prem_dec, prem_cap_above=tvtp_cfg["prem_cap_above"],
                target_vol=tvt_cfg["target_vol"], on_cap=tvt_cfg["on_cap"],
                off_cap=tvtp_cfg["prem_cap_weight"], band=tvt_cfg["rebalance_band"],
            ),
            "TVT50_PREM_GOLD_TREND": lambda: build_tvt_signal(
                vol_513500, trend_513500, 0, defensive_mode="gold_trend",
                gold_trend_arr=trend_518880,
                prem_arr=prem_dec, prem_cap_above=tvtp_cfg["prem_cap_above"],
                target_vol=tvt_cfg["target_vol"], on_cap=tvt_cfg["on_cap"],
                off_cap=tvtp_cfg["prem_cap_weight"], band=tvt_cfg["rebalance_band"],
            ),
        }

    dom_builders = make_domestic_builders()
    dom_results: dict[tuple[str, str], lab.MultiEngineResult] = {}
    dom_summary_rows = []

    for cost_label, cost_val in CONFIG["part_a_domestic_overlay"]["costs"].items():
        for name, builder in dom_builders.items():
            res = lab.run_multi_asset_overlay(
                d_prices, builder(), start_i=0, cost=cost_val,
                cash_pos=dom["cash_pos"], cash_neg=dom["cash_neg"],
            )
            record_engine_checks(res)
            dom_results[(cost_label, name)] = res
            for seg_label, (seg_s, seg_e) in CONFIG["part_a_domestic_overlay"]["segments"].items():
                m = lab.summarize_result(res, primary_col="c513500", start=seg_s, end=seg_e)
                dom_summary_rows.append({"cost": cost_label, "segment": seg_label, "strategy": name, **m})

    df_dom_summary = pd.DataFrame(dom_summary_rows)
    df_dom_summary.to_csv(OUT / "summary_domestic_overlay.csv", index=False)

    # Save 10bp domestic daily NAV
    pd.DataFrame(
        {name: dom_results[("10bp", name)].nav for name in dom_builders.keys()}
    ).to_csv(OUT / "nav_domestic_10bp.csv", index_label="date")

    # Key crisis / premium-crash periods (10bp)
    kp_rows = []
    b0_10_nav = dom_results[("10bp", "B0_513500")].nav
    for pinfo in CONFIG["part_a_domestic_overlay"]["key_periods"]:
        b0_kp = key_period_metrics(b0_10_nav, pinfo["start"], pinfo["end"])
        for name in dom_builders.keys():
            kp = key_period_metrics(dom_results[("10bp", name)].nav, pinfo["start"], pinfo["end"])
            kp_rows.append({
                "period": pinfo["label"],
                "start": pinfo["start"],
                "end": pinfo["end"],
                "strategy": name,
                "period_return": kp["period_return"],
                "period_max_dd": kp["period_max_dd"],
                "excess_return_vs_b0": kp["period_return"] - b0_kp["period_return"],
                "dd_improve_vs_b0": kp["period_max_dd"] - b0_kp["period_max_dd"],
            })
    pd.DataFrame(kp_rows).to_csv(OUT / "key_periods_domestic.csv", index=False)

    # Overlay strategy NAV-based DCA comparison (full path + 60m & 120m rolling windows vs B0_513500)
    dca_dom_rows = []
    for cost_label, cost_val in CONFIG["part_a_domestic_overlay"]["costs"].items():
        bench_nav = dom_results[(cost_label, "B0_513500")].nav
        for name in dom_builders.keys():
            nav = dom_results[(cost_label, name)].nav
            full_d = lab.dca_full_path(nav, cost=cost_val)
            w60 = lab.compare_dca_windows(nav, bench_nav, window_months=60, cost=cost_val)
            w120 = lab.compare_dca_windows(nav, bench_nav, window_months=120, cost=cost_val)
            row = {"cost": cost_label, "strategy": name}
            for k, v in full_d.items():
                row[f"full_{k}"] = v
            for k, v in w60.items():
                row[f"w60_{k}"] = v
            for k, v in w120.items():
                row[f"w120_{k}"] = v
            dca_dom_rows.append(row)
    pd.DataFrame(dca_dom_rows).to_csv(OUT / "dca_summary_domestic.csv", index=False)

    # Parameter sensitivity checks at 10bp (validation only, never tuned)
    sens_rows = []
    sens_cfg = CONFIG["part_a_domestic_overlay"]["sensitivity_10bp"]
    for family, mode in [("TVT50_CASH", "cash"), ("TVT50_GOLD", "gold"), ("TVT50_GOLD_TREND", "gold_trend")]:
        for tv in sens_cfg["tvt_target_vols"]:
            for cap in sens_cfg["tvt_off_caps"]:
                sig = build_tvt_signal(
                    vol_513500, trend_513500, 0, defensive_mode=mode,
                    gold_trend_arr=trend_518880 if mode == "gold_trend" else None,
                    target_vol=tv, on_cap=1.0, off_cap=cap, band=tvt_cfg["rebalance_band"],
                )
                r = lab.run_multi_asset_overlay(d_prices, sig, 0, 0.001, dom["cash_pos"], dom["cash_neg"])
                record_engine_checks(r)
                m = lab.summarize_result(r, primary_col="c513500")
                sens_rows.append({
                    "family": family,
                    "param_group": "target_vol_x_off_cap",
                    "variant": f"tv{int(round(tv*100))}_cap{int(round(cap*100))}",
                    "target_vol": tv,
                    "off_cap": cap,
                    "prem_threshold": np.nan,
                    **m,
                })

    for thr in sens_cfg["prem_trim_thresholds"]:
        for family, mode in [("PREM_TRIM_GOLD", "gold"), ("PREM_TRIM_CASH", "cash")]:
            sig = build_prem_trim_signal(
                prem_dec, 0, defensive_mode=mode,
                trim_above=thr, restore_below=sens_cfg["prem_restore_threshold"],
                trimmed_eq_weight=prem_cfg["trimmed_eq_weight"],
            )
            r = lab.run_multi_asset_overlay(d_prices, sig, 0, 0.001, dom["cash_pos"], dom["cash_neg"])
            record_engine_checks(r)
            m = lab.summarize_result(r, primary_col="c513500")
            sens_rows.append({
                "family": family,
                "param_group": "prem_trim_threshold",
                "variant": f"prem_gt_{int(round(thr*100))}pct",
                "target_vol": np.nan,
                "off_cap": prem_cfg["trimmed_eq_weight"],
                "prem_threshold": thr,
                **m,
            })

        sig_tp = build_tvt_signal(
            vol_513500, trend_513500, 0, defensive_mode="gold",
            prem_arr=prem_dec, prem_cap_above=thr,
            target_vol=tvt_cfg["target_vol"], on_cap=1.0, off_cap=tvt_cfg["off_cap"],
            band=tvt_cfg["rebalance_band"],
        )
        r_tp = lab.run_multi_asset_overlay(d_prices, sig_tp, 0, 0.001, dom["cash_pos"], dom["cash_neg"])
        record_engine_checks(r_tp)
        m_tp = lab.summarize_result(r_tp, primary_col="c513500")
        sens_rows.append({
            "family": "TVT50_PREM_GOLD",
            "param_group": "prem_cap_threshold",
            "variant": f"prem_gt_{int(round(thr*100))}pct",
            "target_vol": tvt_cfg["target_vol"],
            "off_cap": tvt_cfg["off_cap"],
            "prem_threshold": thr,
            **m_tp,
        })
    pd.DataFrame(sens_rows).to_csv(OUT / "sensitivity.csv", index=False)

    # =========================================================================
    # PART B: Real Monthly DCA Premium-Parking Cashflow Simulation
    # =========================================================================
    p_eq_arr = dom["c513500"].to_numpy(float)
    p_gold_arr = dom["c518880"].to_numpy(float)
    tvt_cap_arr = np.where(trend_513500, tvt_cfg["on_cap"], tvt_cfg["off_cap"])
    with np.errstate(divide="ignore", invalid="ignore"):
        tvt_raw = np.where(vol_513500 > 0, tvt_cfg["target_vol"] / vol_513500, 1.0)
    tvt_w_eq_arr = np.clip(np.minimum(tvt_cap_arr, tvt_raw), 0.0, 1.0)

    dca_park_specs = [
        ("DCA_PLAIN", "DCA_PLAIN", None),
        ("DCA_PREM3_CASH", "DCA_PREM_CASH", 0.03),
        ("DCA_PREM3_GOLD", "DCA_PREM_GOLD", 0.03),
        ("DCA_PREM5_GOLD", "DCA_PREM_GOLD", 0.05),
        ("DCA_TVT50_GOLD", "DCA_TVT50_GOLD", None),
    ]

    parking_summary_rows = []
    parking_max_resid = 0.0
    parking_min_val = float("inf")
    parking_lag_violations = 0

    for cost_label, cost_val in CONFIG["part_b_domestic_dca_parking"]["costs"].items():
        # Full period
        plain_full = None
        for label, mode, thr in dca_park_specs:
            res = simulate_dca_parking_account(
                d_dates, p_eq_arr, p_gold_arr, dom["cash_pos"], prem_dec, prem_after,
                mode=mode, cost=cost_val, prem_threshold=thr, tvt_w_eq=tvt_w_eq_arr,
                tvt_band=tvt_cfg["rebalance_band"],
                tvt_prem_park_thr=CONFIG["part_b_domestic_dca_parking"]["tvt_dca_prem_park_threshold"],
            )
            parking_max_resid = max(parking_max_resid, res["max_cash_residual"])
            parking_min_val = min(parking_min_val, res["min_account_value"])
            parking_lag_violations += res["order_lag_violations"]
            if label == "DCA_PLAIN":
                plain_full = res
            parking_summary_rows.append({
                "cost": cost_label,
                "horizon": "FULL",
                "strategy": label,
                "n_windows": 1,
                "n_months": res["n_months"],
                "xirr": res["xirr"],
                "worst_xirr": res["xirr"],
                "xirr_vs_plain": res["xirr"] - plain_full["xirr"],
                "max_float_loss": res["max_float_loss"],
                "twr_max_dd": res["twr_max_dd"],
                "xirr_to_float_loss": res["xirr_to_float_loss"],
                "xirr_to_twr_mdd": res["xirr_to_twr_mdd"],
                "terminal_per_unit": res["terminal_per_unit"],
                "avg_premium_paid": res["avg_premium_paid"],
                "avg_premium_after_diag": res["avg_premium_after_diag"],
                "delayed_months": res["delayed_months"],
                "n_trades": res["n_trades"],
                "total_cost_paid": res["total_cost_paid"],
                "ending_parked_share": res["ending_parked_share"],
                "beat_plain_xirr_share": float(res["xirr"] > plain_full["xirr"]),
                "beat_plain_twr_ratio_share": float(res["xirr_to_twr_mdd"] > plain_full["xirr_to_twr_mdd"]),
                "beat_plain_float_ratio_share": float(res["xirr_to_float_loss"] > plain_full["xirr_to_float_loss"]),
            })

        # Rolling 60m and 120m windows
        for win_m in CONFIG["part_b_domestic_dca_parking"]["rolling_windows_months"]:
            wf = rolling_dca_parking_windows(
                d_dates, p_eq_arr, p_gold_arr, dom["cash_pos"], prem_dec, prem_after,
                tvt_w_eq_arr, window_months=win_m, cost=cost_val,
            )
            parking_max_resid = max(parking_max_resid, float(wf["max_cash_residual"].max()))
            parking_min_val = min(parking_min_val, float(wf["min_account_value"].min()))
            parking_lag_violations += int(wf["order_lag_violations"].sum())
            plain_med_xirr = float(wf.loc[wf["strategy"] == "DCA_PLAIN", "xirr"].median())
            for label, _, _ in dca_park_specs:
                sub = wf[wf["strategy"] == label]
                parking_summary_rows.append({
                    "cost": cost_label,
                    "horizon": f"ROLL_{win_m}M",
                    "strategy": label,
                    "n_windows": int(len(sub)),
                    "n_months": int(win_m),
                    "xirr": float(sub["xirr"].median()),
                    "worst_xirr": float(sub["xirr"].min()),
                    "xirr_vs_plain": float(sub["xirr"].median() - plain_med_xirr),
                    "max_float_loss": float(sub["max_float_loss"].median()),
                    "twr_max_dd": float(sub["twr_max_dd"].median()),
                    "xirr_to_float_loss": float(sub["xirr_to_float_loss"].median()),
                    "xirr_to_twr_mdd": float(sub["xirr_to_twr_mdd"].median()),
                    "terminal_per_unit": float(sub["terminal_per_unit"].median()),
                    "avg_premium_paid": float(sub["avg_premium_paid"].median()),
                    "avg_premium_after_diag": float(sub["avg_premium_after_diag"].median()),
                    "delayed_months": float(sub["delayed_months"].median()),
                    "n_trades": float(sub["n_trades"].median()),
                    "total_cost_paid": float(sub["total_cost_paid"].median()),
                    "ending_parked_share": float(sub["ending_parked_share"].median()),
                    "beat_plain_xirr_share": float(sub["beat_plain_xirr"].mean()),
                    "beat_plain_twr_ratio_share": float(sub["beat_plain_twr_ratio"].mean()),
                    "beat_plain_float_ratio_share": float(sub["beat_plain_float_ratio"].mean()),
                })

    pd.DataFrame(parking_summary_rows).to_csv(OUT / "summary_domestic_dca_parking.csv", index=False)

    # =========================================================================
    # PART C: Crypto-Exchange US-Stock Friction Stress Test (2005-01-03 ~ 2026-10-16)
    # =========================================================================
    spy_div_info = measure_spy_dividend_yield(lab.US_GLD_START, lab.US_END)
    measured_div_drag = spy_div_info["implied_annual_div_drag"]

    # Record measured dividend drag in CONFIG before writing config.json
    for sc_item in CONFIG["part_c_crypto_stress"]["scenarios"]:
        if sc_item["spy_drag_mode"] == "measured_spy_dividend_yield":
            sc_item["spy_drag_annual"] = round(measured_div_drag, 6)
    CONFIG["part_c_crypto_stress"]["measured_spy_dividend_stats"] = spy_div_info

    us = lab.load_us_bundle()
    u_dates = us["dates"]
    u_start_i = int(u_dates.searchsorted(pd.Timestamp(lab.US_GLD_START)))
    assert us["gld_real"].iloc[u_start_i:].isna().sum() == 0, "gld_real has NaNs in 2005-2026 window"

    u_prices = pd.DataFrame({"spy": us["spy"], "gld": us["gld_real"]}, index=u_dates)
    u_vol = compute_realized_vol(us["spy"], 21).to_numpy(float)
    u_trend = lab.weekly_stage2_state(us["spy"], 30, 4).to_numpy(bool)

    def make_us_builders():
        return {
            "B0_SPY": lambda: lab.fixed_weight_signal([1.0, 0.0], u_dates, u_start_i, freq="NONE"),
            "GOLD_75_25_Q": lambda: lab.fixed_weight_signal([0.75, 0.25], u_dates, u_start_i, freq="Q"),
            "S2_CASH": lambda: build_s2_signal(u_trend, u_start_i, defensive_mode="cash"),
            "S2_GOLD": lambda: build_s2_signal(u_trend, u_start_i, defensive_mode="gold"),
            "TVT50_CASH": lambda: build_tvt_signal(
                u_vol, u_trend, u_start_i, defensive_mode="cash",
                target_vol=0.15, on_cap=1.0, off_cap=0.50, band=0.10,
            ),
            "TVT50_GOLD": lambda: build_tvt_signal(
                u_vol, u_trend, u_start_i, defensive_mode="gold",
                target_vol=0.15, on_cap=1.0, off_cap=0.50, band=0.10,
            ),
        }

    us_builders = make_us_builders()
    crypto_results: dict[tuple[str, str], lab.MultiEngineResult] = {}
    crypto_rows = []

    for sc_cfg in CONFIG["part_c_crypto_stress"]["scenarios"]:
        sc_name = sc_cfg["scenario"]
        cost_val = float(sc_cfg["cost"])
        drag_val = float(sc_cfg["spy_drag_annual"])
        drag_dict = {"spy": drag_val} if drag_val > 0.0 else None

        for strat_name, builder in us_builders.items():
            res = lab.run_multi_asset_overlay(
                u_prices, builder(), start_i=u_start_i, cost=cost_val,
                cash_pos=us["cash_pos"], cash_neg=us["cash_neg"],
                extra_daily_drag=drag_dict,
            )
            record_engine_checks(res)
            crypto_results[(sc_name, strat_name)] = res

    # Save US base 10bp daily NAV
    pd.DataFrame(
        {name: crypto_results[("US_ETF_10bp", name)].nav for name in us_builders.keys()}
    ).to_csv(OUT / "nav_crypto_base_10bp.csv", index_label="date")

    us_b0_nav = crypto_results[("US_ETF_10bp", "B0_SPY")].nav
    us_b0_metrics = lab.summarize_result(crypto_results[("US_ETF_10bp", "B0_SPY")], primary_col="spy")

    for sc_cfg in CONFIG["part_c_crypto_stress"]["scenarios"]:
        sc_name = sc_cfg["scenario"]
        cost_val = float(sc_cfg["cost"])
        drag_val = float(sc_cfg["spy_drag_annual"])
        sc_b0_nav = crypto_results[(sc_name, "B0_SPY")].nav
        sc_b0_m = lab.summarize_result(crypto_results[(sc_name, "B0_SPY")], primary_col="spy")

        for strat_name in us_builders.keys():
            res = crypto_results[(sc_name, strat_name)]
            m = lab.summarize_result(res, primary_col="spy")
            dca_full = lab.dca_full_path(res.nav, cost=cost_val)
            dca_vs_same_b0 = lab.compare_dca_windows(res.nav, sc_b0_nav, window_months=120, cost=cost_val)
            # Compare against standard US_ETF_10bp B0_SPY (with its own 10bp DCA fee)
            sw = lab.dca_rolling_windows(res.nav, window_months=120, cost=cost_val)
            bw_us = lab.dca_rolling_windows(us_b0_nav, window_months=120, cost=0.001)
            m_us = sw.merge(bw_us, on=["start", "end"], suffixes=("_s", "_us"))

            crypto_rows.append({
                "scenario": sc_name,
                "cost_per_side": cost_val,
                "spy_annual_drag": drag_val,
                "strategy": strat_name,
                **m,
                "cagr_vs_us_b0": m["cagr"] - us_b0_metrics["cagr"],
                "cagr_vs_same_sc_b0": m["cagr"] - sc_b0_m["cagr"],
                "terminal_ratio_to_us_b0": m["terminal_multiple"] / us_b0_metrics["terminal_multiple"],
                "dca_full_xirr": dca_full["xirr"],
                "dca_full_max_float_loss": dca_full["max_float_loss"],
                "dca_full_ratio": dca_full["dca_ratio"],
                "dca_full_terminal_per_unit": dca_full["terminal_per_unit"],
                "dca10y_n_windows": dca_vs_same_b0["n_windows"],
                "dca10y_median_xirr": dca_vs_same_b0["median_xirr"],
                "dca10y_worst_xirr": dca_vs_same_b0["worst_xirr"],
                "dca10y_median_float_loss": dca_vs_same_b0["median_float_loss"],
                "dca10y_median_ratio": dca_vs_same_b0["median_dca_ratio"],
                "dca10y_beat_same_b0_ratio_share": dca_vs_same_b0["ratio_beat_share"],
                "dca10y_beat_same_b0_xirr_share": dca_vs_same_b0["xirr_beat_share"],
                "dca10y_median_xirr_vs_us_b0": float((m_us["xirr_s"] - m_us["xirr_us"]).median()),
                "dca10y_beat_us_b0_xirr_share": float((m_us["xirr_s"] > m_us["xirr_us"]).mean()),
                "dca10y_beat_us_b0_ratio_share": float((m_us["dca_ratio_s"] > m_us["dca_ratio_us"]).mean()),
            })

    pd.DataFrame(crypto_rows).to_csv(OUT / "summary_crypto_stress.csv", index=False)

    # =========================================================================
    # Self-Checks & Anti-Lookahead Audits
    # =========================================================================
    # 1. Verify premium_decision T-2 NAV lag from raw CSV
    prem_raw = pd.read_csv(lab.DOMESTIC_PREMIUM_FILE, parse_dates=["date", "nav_base_date"]).set_index("date").sort_index()
    prem_win = prem_raw.reindex(d_dates)
    all_dom_dates = dom["c513500_full"].index
    pos_trade = all_dom_dates.searchsorted(prem_win.index)
    pos_nav = all_dom_dates.searchsorted(prem_win["nav_base_date"], side="right") - 1
    min_nav_lag_trading_days = int(np.min(pos_trade - pos_nav))

    # 2. Verify premium_decision != premium_after (confirms distinct columns and no accidental swap)
    valid_both = np.isfinite(prem_dec) & np.isfinite(prem_after)
    prem_med_abs_diff = float(np.median(np.abs(prem_dec[valid_both] - prem_after[valid_both])))
    prem_corr = float(np.corrcoef(prem_dec[valid_both], prem_after[valid_both])[0, 1])

    # 3. Truncated-history no-lookahead test on Friday cutoffs for domestic TVT50 + PREM signals
    no_lookahead_ok = True
    cutoff_details = []
    # Pick Friday dates inside [2014-10-08, 2026-09-30]
    fridays = d_dates[d_dates.weekday == 4]
    sample_cutoffs = [
        fridays[fridays.searchsorted(pd.Timestamp(dt), side="right") - 1]
        for dt in ("2016-12-30", "2018-12-28", "2020-03-27", "2022-12-30", "2025-04-25")
    ]
    for cut in sample_cutoffs:
        idx_win = int(d_dates.get_loc(cut))
        c513_trunc = dom["c513500_full"].loc[:cut]
        c518_trunc = dom["c518880_full"].loc[:cut]
        vol_t = compute_realized_vol(c513_trunc, tvt_cfg["vol_window"]).iloc[-1]
        tr513_t = bool(lab.weekly_stage2_state(c513_trunc, 30, 4).iloc[-1])
        tr518_t = bool(lab.weekly_stage2_state(c518_trunc, 30, 4).iloc[-1])
        match = (
            bool(np.isclose(vol_t, vol_513500[idx_win], equal_nan=True))
            and (tr513_t == bool(trend_513500[idx_win]))
            and (tr518_t == bool(trend_518880[idx_win]))
        )
        no_lookahead_ok &= match
        cutoff_details.append({"cutoff": str(cut.date()), "signal_exact_match": match})

    # 4. Verify B0_513500 matches prior frozen 513500 direct-signal benchmark
    prior_b0_path = ROOT / "outputs" / "sp500-513500-direct-signal-2026-11-15" / "summary_q3_q5.csv"
    b0_consistency = None
    if prior_b0_path.exists():
        prior_df = pd.read_csv(prior_b0_path)
        prior_b0 = prior_df[(prior_df["cost"] == "10bp") & (prior_df["strategy"] == "B0")].iloc[0]
        our_b0 = df_dom_summary[
            (df_dom_summary["cost"] == "10bp")
            & (df_dom_summary["segment"] == "FULL")
            & (df_dom_summary["strategy"] == "B0_513500")
        ].iloc[0]
        b0_consistency = {
            "our_cagr": float(our_b0["cagr"]),
            "prior_cagr": float(prior_b0["cagr"]),
            "abs_cagr_diff": float(abs(our_b0["cagr"] - prior_b0["cagr"])),
            "our_max_dd": float(our_b0["max_dd"]),
            "prior_max_dd": float(prior_b0["max_dd"]),
            "abs_mdd_diff": float(abs(our_b0["max_dd"] - prior_b0["max_dd"])),
        }

    overall_max_resid = max(checks_summary["max_cash_residual"], parking_max_resid)
    overall_min_nav = min(checks_summary["nav_min"], parking_min_val)

    self_checks = {
        "all_passed": bool(
            overall_max_resid < 1e-10
            and overall_min_nav > 0.0
            and checks_summary["target_weight_min"] >= -1e-12
            and checks_summary["target_sum_max"] <= 1.0 + 1e-12
            and min_nav_lag_trading_days >= 2
            and int(dom["premium_decision"].isna().sum()) == 0
            and no_lookahead_ok
            and parking_lag_violations == 0
            and spy_div_info["in_expected_range_1p5_to_1p9pct"]
        ),
        "max_cash_residual": float(overall_max_resid),
        "max_cash_residual_lt_1e_10": bool(overall_max_resid < 1e-10),
        "overlay_max_cash_residual": float(checks_summary["max_cash_residual"]),
        "parking_max_cash_residual": float(parking_max_resid),
        "nav_min": float(overall_min_nav),
        "nav_min_gt_0": bool(overall_min_nav > 0.0),
        "target_weight_min": float(checks_summary["target_weight_min"]),
        "target_sum_max": float(checks_summary["target_sum_max"]),
        "anti_lookahead_premium": {
            "only_premium_decision_used_for_signals": True,
            "premium_after_used_for_signals": False,
            "premium_decision_na_count": int(dom["premium_decision"].isna().sum()),
            "min_nav_base_lag_trading_days": min_nav_lag_trading_days,
            "decision_vs_after_median_abs_diff": prem_med_abs_diff,
            "decision_vs_after_corr": prem_corr,
            "dca_parking_order_lag_violations": int(parking_lag_violations),
        },
        "truncated_history_no_lookahead": {
            "all_cutoffs_matched": bool(no_lookahead_ok),
            "cutoffs": cutoff_details,
        },
        "spy_measured_dividend_yield": spy_div_info,
        "b0_513500_prior_benchmark_check": b0_consistency,
    }

    (OUT / "config.json").write_text(json.dumps(CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "self_checks.json").write_text(json.dumps(self_checks, indent=2, ensure_ascii=False), encoding="utf-8")

    # Compact console summary for verification
    pd.set_option("display.width", 240, "display.max_columns", 25, "display.float_format", lambda x: f"{x:.4f}")
    print("=== SELF CHECKS ===")
    print(json.dumps(self_checks, indent=2, ensure_ascii=False))
    print("\n=== PART A: DOMESTIC FULL (10bp) ===")
    print(df_dom_summary[(df_dom_summary["cost"] == "10bp") & (df_dom_summary["segment"] == "FULL")][
        ["strategy", "cagr", "vol", "sharpe", "max_dd", "calmar", "trades_per_year", "annual_turnover", "avg_w_c513500", "avg_w_c518880"]
    ].to_string(index=False))
    print("\n=== PART B: REAL DCA PARKING (10bp) ===")
    df_park = pd.DataFrame(parking_summary_rows)
    print(df_park[df_park["cost"] == "10bp"][
        ["horizon", "strategy", "xirr", "xirr_vs_plain", "max_float_loss", "twr_max_dd", "xirr_to_twr_mdd", "xirr_to_float_loss", "avg_premium_paid", "beat_plain_xirr_share", "beat_plain_twr_ratio_share"]
    ].to_string(index=False))
    print("\n=== PART C: CRYPTO STRESS SUMMARY ===")
    df_cr = pd.DataFrame(crypto_rows)
    print(df_cr[
        ["scenario", "strategy", "cagr", "sharpe", "max_dd", "calmar", "cagr_vs_us_b0", "dca10y_median_xirr", "dca10y_median_ratio", "dca10y_beat_same_b0_ratio_share"]
    ].to_string(index=False))


if __name__ == "__main__":
    main()
