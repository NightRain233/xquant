"""Round-2 Deep-Dive Verification for Gold Quantitative Enhancement Study (2026-11-23).

Targets 5 critical follow-up questions surfaced by Round 1:
1. Low-turnover practical TVT-50 / Vol-Target variants (Weekly / 10% deadband / 3-tier vol / +Bond / +Trend-SPY)
   + full parameter plateau (target_vol x bear_cap) + 200x circular-shift permutation on GLD (21Y), GC=F (25Y),
   and domestic 518880 (12.3Y) + 50bp slippage stress + 10Y rolling DCA.
2. 55-Year Decade-by-Decade Rate Regime Decomposition (explaining why pure trend shines in 1980-2001 high-rate bear
   and 2022-2026, yet suffered whipsaw in 2011-2019 ZIRP chop).
3. Gold/Silver Ratio (GSR) Stress Audit over 25Y GC=F/SI=F (2001-2026): threshold grid, Ex-2020 split,
   200x permutation test, and trend-filtered GSR (avoiding -65% silver crashes).
4. Physical Gold + Digital Gold (BTC) split into 2015-2020 Early vs 2021-2026 Mature institutional era.
5. Domestic 518880 low-turnover TVT50 + 511010/511260 bond shields + 2026-11-20 live signal snapshot.

Run (offline sandbox, from repo root):
    .venv/bin/python -I scripts/research_gold_enhance_deepdive_2026_11_23.py
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
sys.path.insert(0, str(ROOT / "scripts"))

from xquant import indicators as ind  # noqa: E402
from xquant import overlay_rules as ov  # noqa: E402
from xquant import sp500_lab as lab  # noqa: E402
import research_gold_enhance_2026_11_23 as r1  # noqa: E402

OUT_DIR = r1.OUT_DIR


def build_tvt_weight(
    close: pd.Series,
    *,
    vol_window: int = 21,
    target_vol: float = 0.15,
    bear_cap: float = 0.50,
    rebalance_freq: str = "D",
    weight_deadband: float = 0.02,
    use_buffered_trend: bool = False,
    ann_days: int = 252,
) -> tuple[np.ndarray, float]:
    """Strictly causal TVT (Trend + Vol-Target) target weight array with optional weekly/monthly schedule."""
    dates = pd.DatetimeIndex(close.index)
    vol = np.log(close).diff().rolling(vol_window).std(ddof=1) * np.sqrt(float(ann_days))
    v_arr = vol.to_numpy(float)
    raw = np.clip(target_vol / np.where(np.isfinite(v_arr) & (v_arr > 1e-4), v_arr, target_vol), 0.0, 1.0)
    if use_buffered_trend:
        tr_on = lab.daily_buffered_stage_state(close, ma_days=150, slope_days=20, buffer=0.03).to_numpy(bool)
    else:
        tr_on = lab.weekly_stage2_state(close, ma_weeks=30, slope_weeks=4).to_numpy(bool)
    desired = np.minimum(raw, np.where(tr_on, 1.0, bear_cap))

    if rebalance_freq == "W":
        mask = np.zeros(len(dates), dtype=bool)
        if len(dates) > 1:
            mask[:-1] = dates[:-1].to_period("W-SUN") != dates[1:].to_period("W-SUN")
        mask[-1] = True
    elif rebalance_freq == "M":
        mask = ov.month_end_mask(dates)
    else:
        mask = np.ones(len(dates), dtype=bool)

    out = np.zeros(len(dates), dtype=float)
    cur = desired[0]
    for i in range(len(dates)):
        if mask[i] and abs(desired[i] - cur) >= weight_deadband:
            cur = desired[i]
        out[i] = cur
    return out, weight_deadband


def run_deepdive1_low_turnover_tvt(
    gld_df: pd.DataFrame,
    gcf_df: pd.DataFrame,
    ief_df: pd.DataFrame,
    spy_df: pd.DataFrame,
    irx_df: pd.DataFrame,
    cn_gold_df: pd.DataFrame,
    cn_bond5_df: pd.DataFrame,
    cn_bond10_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # --- A. GLD Low-Turnover TVT Variants & Cross-Asset Shields ---
    dates = pd.DatetimeIndex(gld_df.index)
    irx = r1.align_close_to(irx_df["Close"] / 100.0, dates).bfill()
    cp, cn = ov.calendar_cash_factors(dates, irx.to_numpy(float), r1.CONFIG["costs"]["us_margin_spread"])
    start_i = int(dates.searchsorted(pd.Timestamp(r1.CONFIG["windows"]["gld_main"][0])))
    gld_c = gld_df["Close"]
    ief_c = r1.align_close_to(ief_df["Close"], dates)
    spy_c = r1.align_close_to(spy_df["Close"], dates)
    ief_on = lab.daily_buffered_ma_state(ief_c, 150, 0.02).to_numpy(bool)
    spy_on = lab.daily_buffered_mtf3_equity_weight(spy_c, 150, 20, 210, 0.03).to_numpy(float)

    px1 = pd.DataFrame({"gold": gld_c.to_numpy(float)}, index=dates)
    px3 = pd.DataFrame(
        {"gold": gld_c.to_numpy(float), "ief": ief_c.to_numpy(float), "spy": spy_c.to_numpy(float)}, index=dates
    )

    # Also prepare 25Y GC=F
    g_dates = pd.DatetimeIndex(gcf_df.index)
    g_irx = r1.align_close_to(irx_df["Close"] / 100.0, g_dates).bfill()
    g_cp, g_cn = ov.calendar_cash_factors(g_dates, g_irx.to_numpy(float), r1.CONFIG["costs"]["us_margin_spread"])
    g_start = int(g_dates.searchsorted(pd.Timestamp(r1.CONFIG["windows"]["gcf_daily"][0])))
    g_px = pd.DataFrame({"gold": gcf_df["Close"].to_numpy(float)}, index=g_dates)

    bh_res = lab.run_multi_asset_overlay(px1, r1.weight_to_signal(np.ones(len(dates)), start_i), start_i, 0.001, cp, cn)
    bh_dca10 = r1.fast_dca_rolling(bh_res.nav, 120, 0.001)
    bh_dca5 = r1.fast_dca_rolling(bh_res.nav, 60, 0.001)

    variants = [
        ("BH_GLD", dict(target_vol=9.9, bear_cap=1.0, rebalance_freq="M", weight_deadband=0.99, use_buffered_trend=False), "CASH"),
        ("TVT50_15_DAILY_RAW", dict(target_vol=0.15, bear_cap=0.50, rebalance_freq="D", weight_deadband=0.02, use_buffered_trend=False), "CASH"),
        ("TVT50_15_DAILY_DB10", dict(target_vol=0.15, bear_cap=0.50, rebalance_freq="D", weight_deadband=0.10, use_buffered_trend=False), "CASH"),
        ("TVT50_15_WEEKLY_DB10", dict(target_vol=0.15, bear_cap=0.50, rebalance_freq="W", weight_deadband=0.10, use_buffered_trend=False), "CASH"),
        ("TVT50_15_WEEKLY_DB15", dict(target_vol=0.15, bear_cap=0.50, rebalance_freq="W", weight_deadband=0.15, use_buffered_trend=False), "CASH"),
        ("TVT50_15_MONTHLY_DB10", dict(target_vol=0.15, bear_cap=0.50, rebalance_freq="M", weight_deadband=0.10, use_buffered_trend=False), "CASH"),
        ("TVT50_15_BUF3_WEEKLY_DB10", dict(target_vol=0.15, bear_cap=0.50, rebalance_freq="W", weight_deadband=0.10, use_buffered_trend=True), "CASH"),
        ("TVT0_15_WEEKLY_DB10", dict(target_vol=0.15, bear_cap=0.0, rebalance_freq="W", weight_deadband=0.10, use_buffered_trend=False), "CASH"),
        ("VT_15_WEEKLY_DB10", dict(target_vol=0.15, bear_cap=1.0, rebalance_freq="W", weight_deadband=0.10, use_buffered_trend=False), "CASH"),
        ("VT_15_MONTHLY_DB10", dict(target_vol=0.15, bear_cap=1.0, rebalance_freq="M", weight_deadband=0.10, use_buffered_trend=False), "CASH"),
        # 3-Tier discrete buffered vol throttle + S2 (super simple for retail!)
        ("VOL3_S2_DISCRETE", None, "CASH"),
        # Cross-asset parking on top of low-turnover TVT50_15_WEEKLY_DB10
        ("TVT50_15_W_DB10_COND_IEF", dict(target_vol=0.15, bear_cap=0.50, rebalance_freq="W", weight_deadband=0.10, use_buffered_trend=False), "COND_IEF"),
        ("TVT50_15_W_DB10_SPY_TREND", dict(target_vol=0.15, bear_cap=0.50, rebalance_freq="W", weight_deadband=0.10, use_buffered_trend=False), "SPY_TREND"),
    ]

    # Discrete 3-tier vol throttle + S2 helper
    def discrete_vol3_s2(c_ser: pd.Series) -> np.ndarray:
        vt3 = lab.daily_buffered_vol_throttle(
            c_ser, vol_window=21, low_vol=0.16, high_vol=0.24, hysteresis=0.02, mid_weight=0.70, high_weight=0.40
        ).to_numpy(float)
        s2 = lab.weekly_stage2_state(c_ser, 30, 4).to_numpy(bool)
        return np.minimum(vt3, np.where(s2, 1.0, 0.50))

    tvt_rows = []
    for name, kw, park in variants:
        if name == "BH_GLD":
            w_g = np.ones(len(dates))
            w_gcf = np.ones(len(g_dates))
        elif name == "VOL3_S2_DISCRETE":
            w_g = discrete_vol3_s2(gld_c)
            w_gcf = discrete_vol3_s2(gcf_df["Close"])
        else:
            w_g, _ = build_tvt_weight(gld_c, **kw)
            w_gcf, _ = build_tvt_weight(gcf_df["Close"], **kw)

        if park == "CASH":
            r10 = lab.run_multi_asset_overlay(px1, r1.weight_to_signal(w_g, start_i, 0.01), start_i, 0.001, cp, cn)
            r30 = lab.run_multi_asset_overlay(px1, r1.weight_to_signal(w_g, start_i, 0.01), start_i, 0.003, cp, cn)
            r50 = lab.run_multi_asset_overlay(px1, r1.weight_to_signal(w_g, start_i, 0.01), start_i, 0.005, cp, cn)
            perm_gld = (
                r1.circular_shift_perm_single(px1, w_g, start_i, cost=0.001, cash_pos=cp, cash_neg=cn, n_trials=200)["p_sharpe"]
                if name != "BH_GLD"
                else np.nan
            )
            r_gcf = lab.run_multi_asset_overlay(g_px, r1.weight_to_signal(w_gcf, g_start, 0.01), g_start, 0.001, g_cp, g_cn)
            m_gcf = r1.summarize_nav_ext(r_gcf, "gold")
            perm_gcf = (
                r1.circular_shift_perm_single(g_px, w_gcf, g_start, cost=0.001, cash_pos=g_cp, cash_neg=g_cn, n_trials=200)["p_sharpe"]
                if name != "BH_GLD"
                else np.nan
            )
        else:
            mat = np.zeros((len(dates), 3))
            mat[:, 0] = w_g
            if park == "COND_IEF":
                mat[:, 1] = np.where(ief_on, 1.0 - w_g, 0.0)
            elif park == "SPY_TREND":
                mat[:, 2] = (1.0 - w_g) * spy_on
            r10 = lab.run_multi_asset_overlay(px3, r1.multi_weight_to_signal(mat, start_i, 0.02), start_i, 0.001, cp, cn)
            r30 = lab.run_multi_asset_overlay(px3, r1.multi_weight_to_signal(mat, start_i, 0.02), start_i, 0.003, cp, cn)
            r50 = lab.run_multi_asset_overlay(px3, r1.multi_weight_to_signal(mat, start_i, 0.02), start_i, 0.005, cp, cn)
            perm_gld = np.nan
            m_gcf = {"cagr": np.nan, "sharpe": np.nan, "max_dd": np.nan}
            perm_gcf = np.nan

        m10 = r1.summarize_nav_ext(r10, "gold")
        m30 = r1.summarize_nav_ext(r30, "gold")
        m50 = r1.summarize_nav_ext(r50, "gold")
        m26 = r1.summarize_nav_ext(r10, "gold", start="2026-01-29", end="2026-11-20")
        mbear = r1.summarize_nav_ext(r10, "gold", start="2011-09-06", end="2019-05-31")
        mnew = r1.summarize_nav_ext(r10, "gold", start="2019-06-03", end="2026-11-20")

        d10 = r1.fast_dca_rolling(r10.nav, 120, 0.001).merge(bh_dca10, on=["start", "end"], suffixes=("_s", "_b"))
        d5 = r1.fast_dca_rolling(r10.nav, 60, 0.001).merge(bh_dca5, on=["start", "end"], suffixes=("_s", "_b"))
        tvt_rows.append(
            {
                "strategy": name,
                "park": park,
                "cagr": m10["cagr"],
                "vol": m10["vol"],
                "sharpe": m10["sharpe"],
                "max_dd": m10["max_dd"],
                "calmar": m10["calmar"],
                "max_uw_years": m10["max_uw_years"],
                "trades_per_year": m10["trades_per_year"],
                "annual_turnover": m10["annual_turnover"],
                "avg_w_gold": m10["avg_exposure"],
                "sharpe_30bp": m30["sharpe"],
                "cagr_50bp": m50["cagr"],
                "sharpe_50bp": m50["sharpe"],
                "perm_p_gld": perm_gld,
                "gcf25y_sharpe": m_gcf["sharpe"],
                "perm_p_gcf25y": perm_gcf,
                "bear_11_19_cagr": mbear["cagr"],
                "bear_11_19_mdd": mbear["max_dd"],
                "new_19_26_cagr": mnew["cagr"],
                "new_19_26_sharpe": mnew["sharpe"],
                "crash_2026_ret": m26["total_ret"],
                "dca5y_med_xirr": float(d5["xirr_s"].median()),
                "dca5y_worst_float": float(d5["max_float_loss_s"].min()),
                "dca5y_ratio_beat_bh": float((d5["dca_ratio_s"] > d5["dca_ratio_b"]).mean()),
                "dca10y_med_xirr": float(d10["xirr_s"].median()),
                "dca10y_worst_float": float(d10["max_float_loss_s"].min()),
                "dca10y_ratio_beat_bh": float((d10["dca_ratio_s"] > d10["dca_ratio_b"]).mean()),
            }
        )

    # --- B. TVT Parameter Plateau Grid (target_vol x bear_cap x vol_window) on Weekly DB10 ---
    bh_sharpe = r1.summarize_nav_ext(bh_res, "gold")["sharpe"]
    bh_calmar = r1.summarize_nav_ext(bh_res, "gold")["calmar"]
    grid_rows = []
    for vw in (15, 21, 30, 42):
        for tv in (0.10, 0.12, 0.14, 0.15, 0.16, 0.18, 0.20):
            for cap in (0.0, 0.30, 0.50, 0.70, 1.0):
                w, _ = build_tvt_weight(
                    gld_c, vol_window=vw, target_vol=tv, bear_cap=cap, rebalance_freq="W", weight_deadband=0.10
                )
                r = lab.run_multi_asset_overlay(px1, r1.weight_to_signal(w, start_i, 0.01), start_i, 0.001, cp, cn)
                m = r1.summarize_nav_ext(r, "gold")
                grid_rows.append(
                    {
                        "vol_window": vw,
                        "target_vol": tv,
                        "bear_cap": cap,
                        "cagr": m["cagr"],
                        "sharpe": m["sharpe"],
                        "max_dd": m["max_dd"],
                        "calmar": m["calmar"],
                        "trades_per_year": m["trades_per_year"],
                        "beats_bh_sharpe": bool(m["sharpe"] > bh_sharpe),
                        "beats_bh_calmar": bool(m["calmar"] > bh_calmar),
                    }
                )

    # --- C. Domestic 518880 Low-Turnover TVT + Bond Shields (511010 full 2014-2026 & 511260 2018-2026) ---
    common_cn = cn_gold_df.index.intersection(cn_bond5_df.index)
    c_dates = pd.DatetimeIndex(common_cn.sort_values())
    c_start = int(c_dates.searchsorted(pd.Timestamp(r1.CONFIG["windows"]["domestic_518880"][0])))
    g_cn = cn_gold_df["Close"].reindex(c_dates)
    b5 = cn_bond5_df["Close"].reindex(c_dates)
    c_cp, c_cn = ov.calendar_cash_factors(c_dates, np.full(len(c_dates), 0.02), 0.0)
    c_px = pd.DataFrame({"gold_cn": g_cn.to_numpy(float), "bond_cn": b5.to_numpy(float)}, index=c_dates)
    c_px1 = pd.DataFrame({"gold_cn": g_cn.to_numpy(float)}, index=c_dates)

    cn_tvt_rows = []
    cn_bh = lab.run_multi_asset_overlay(c_px1, r1.weight_to_signal(np.ones(len(c_dates)), c_start), c_start, 0.001, c_cp, c_cn)
    cn_bh_d5 = r1.fast_dca_rolling(cn_bh.nav, 60, 0.001)
    for cname, kw, use_bond in [
        ("CN_BH_518880", None, False),
        ("CN_TVT50_12_W_DB10_CASH", dict(target_vol=0.12, bear_cap=0.50, rebalance_freq="W", weight_deadband=0.10), False),
        ("CN_TVT50_15_W_DB10_CASH", dict(target_vol=0.15, bear_cap=0.50, rebalance_freq="W", weight_deadband=0.10), False),
        ("CN_TVT50_12_W_DB10_BOND511010", dict(target_vol=0.12, bear_cap=0.50, rebalance_freq="W", weight_deadband=0.10), True),
        ("CN_TVT50_15_W_DB10_BOND511010", dict(target_vol=0.15, bear_cap=0.50, rebalance_freq="W", weight_deadband=0.10), True),
        ("CN_VOL3_S2_DISCRETE_CASH", "VOL3", False),
        ("CN_VOL3_S2_DISCRETE_BOND511010", "VOL3", True),
        ("CN_MTF3_BUF2_BOND511010", "MTF3_B2", True),
        ("CN_MTF3_BUF3_BOND511010", "MTF3_B3", True),
    ]:
        if kw is None:
            wc = np.ones(len(c_dates))
        elif kw == "VOL3":
            vt3 = lab.daily_buffered_vol_throttle(
                g_cn, vol_window=21, low_vol=0.14, high_vol=0.22, hysteresis=0.02, mid_weight=0.70, high_weight=0.40
            ).to_numpy(float)
            s2 = lab.weekly_stage2_state(g_cn, 30, 4).to_numpy(bool)
            wc = np.minimum(vt3, np.where(s2, 1.0, 0.50))
        elif kw == "MTF3_B2":
            wc = lab.daily_buffered_mtf3_equity_weight(g_cn, 150, 20, 210, 0.02).to_numpy(float)
        elif kw == "MTF3_B3":
            wc = lab.daily_buffered_mtf3_equity_weight(g_cn, 150, 20, 210, 0.03).to_numpy(float)
        else:
            wc, _ = build_tvt_weight(g_cn, **kw)

        if use_bond:
            mat = np.column_stack([wc, 1.0 - wc])
            r10 = lab.run_multi_asset_overlay(c_px, r1.multi_weight_to_signal(mat, c_start, 0.01), c_start, 0.001, c_cp, c_cn)
            r30 = lab.run_multi_asset_overlay(c_px, r1.multi_weight_to_signal(mat, c_start, 0.01), c_start, 0.003, c_cp, c_cn)
            p_sh = np.nan
        else:
            r10 = lab.run_multi_asset_overlay(c_px1, r1.weight_to_signal(wc, c_start, 0.01), c_start, 0.001, c_cp, c_cn)
            r30 = lab.run_multi_asset_overlay(c_px1, r1.weight_to_signal(wc, c_start, 0.01), c_start, 0.003, c_cp, c_cn)
            p_sh = (
                r1.circular_shift_perm_single(c_px1, wc, c_start, cost=0.001, cash_pos=c_cp, cash_neg=c_cn, n_trials=200)["p_sharpe"]
                if cname != "CN_BH_518880"
                else np.nan
            )
        m = r1.summarize_nav_ext(r10, "gold_cn")
        m30 = r1.summarize_nav_ext(r30, "gold_cn")
        m_pre = r1.summarize_nav_ext(r10, "gold_cn", start="2014-08-01", end="2022-12-30")
        m_post = r1.summarize_nav_ext(r10, "gold_cn", start="2023-01-03", end="2026-11-20")
        m26 = r1.summarize_nav_ext(r10, "gold_cn", start="2026-01-29", end="2026-11-20")
        d5 = r1.fast_dca_rolling(r10.nav, 60, 0.001).merge(cn_bh_d5, on=["start", "end"], suffixes=("_s", "_b"))
        cn_tvt_rows.append(
            {
                "strategy": cname,
                "cagr": m["cagr"],
                "vol": m["vol"],
                "sharpe": m["sharpe"],
                "max_dd": m["max_dd"],
                "calmar": m["calmar"],
                "trades_per_year": m["trades_per_year"],
                "annual_turnover": m["annual_turnover"],
                "sharpe_30bp": m30["sharpe"],
                "perm_p_sharpe": p_sh,
                "pre2023_cagr": m_pre["cagr"],
                "pre2023_sharpe": m_pre["sharpe"],
                "pre2023_mdd": m_pre["max_dd"],
                "post2023_cagr": m_post["cagr"],
                "post2023_sharpe": m_post["sharpe"],
                "crash_2026_ret": m26["total_ret"],
                "dca5y_med_xirr": float(d5["xirr_s"].median()),
                "dca5y_worst_float": float(d5["max_float_loss_s"].min()),
                "dca5y_ratio_beat_bh": float((d5["dca_ratio_s"] > d5["dca_ratio_b"]).mean()),
            }
        )

    return pd.DataFrame(tvt_rows), pd.DataFrame(grid_rows), pd.DataFrame(cn_tvt_rows)


def run_deepdive2_rate_regime_55y(gold_55y: pd.Series, rf_m: pd.Series) -> pd.DataFrame:
    """Decompose 55-year monthly gold trend performance across interest-rate regimes."""
    dates = pd.DatetimeIndex(gold_55y.index)
    prices = pd.DataFrame({"gold": gold_55y.to_numpy(float)}, index=dates)
    start_i = int(dates.searchsorted(pd.Timestamp("1972-01-31")))
    day_diff = np.zeros(len(dates), dtype=float)
    day_diff[1:] = (dates[1:] - dates[:-1]).days.to_numpy(float)
    cash_pos = (1.0 + rf_m.to_numpy(float)) ** (day_diff / 365.25)
    cash_pos[0] = 1.0

    w_bh = np.ones(len(dates))
    w_m10 = (gold_55y > gold_55y.rolling(10).mean()).fillna(False).to_numpy(float)
    w_m12 = (gold_55y > gold_55y.rolling(12).mean()).fillna(False).to_numpy(float)
    vol6m = np.log(gold_55y).diff().rolling(6).std(ddof=1) * np.sqrt(12.0)
    w_vt = np.clip(0.15 / np.where(np.isfinite(vol6m) & (vol6m > 1e-4), vol6m, 0.15), 0.0, 1.0)
    w_tvt = np.minimum(w_vt, np.where(w_m10 > 0.5, 1.0, 0.5))

    res_map = {}
    for nm, wa in [("BH", w_bh), ("M10_SMA", w_m10), ("M12_SMA", w_m12), ("TVT50_M", w_tvt)]:
        res_map[nm] = lab.run_multi_asset_overlay(
            prices, r1.weight_to_signal(wa, start_i), start_i, 0.001, cash_pos, extra_daily_drag={"gold": 0.004}
        )

    regimes = [
        ("1972-1980 High-Inflation Bull", "1972-01-31", "1980-01-31"),
        ("1980-1990 Volcker High-Rate Bear", "1980-01-31", "1990-12-31"),
        ("1991-2001 Mod-Rate Grind Bear", "1990-12-31", "2001-03-31"),
        ("2001-2011 Secular Gold Bull", "2001-03-31", "2011-09-30"),
        ("2011-2019 ZIRP Choppy Bear", "2011-09-30", "2019-05-31"),
        ("2019-2026 Modern Cycle + Crash", "2019-05-31", "2026-10-31"),
    ]
    rows = []
    for label, s0, s1 in regimes:
        avg_rf = float(rf_m.loc[s0:s1].mean())
        row: dict[str, Any] = {"regime": label, "avg_tbill_rate": avg_rf}
        for nm, r in res_map.items():
            m = r1.summarize_nav_ext(r, "gold", start=s0, end=s1, ann_days=12)
            row[f"{nm}_cagr"] = m["cagr"]
            row[f"{nm}_sharpe"] = m["sharpe"]
            row[f"{nm}_mdd"] = m["max_dd"]
        rows.append(row)
    return pd.DataFrame(rows)


def run_deepdive3_gsr_audit_25y(gcf_df: pd.DataFrame, sif_df: pd.DataFrame, irx_df: pd.DataFrame) -> pd.DataFrame:
    """Strict 25-year (2001-09..2026-11) audit of Gold/Silver Ratio (GSR) switching."""
    common = gcf_df.index.intersection(sif_df.index)
    dates = pd.DatetimeIndex(common.sort_values())
    g = gcf_df["Close"].reindex(dates)
    s = sif_df["Close"].reindex(dates)
    irx = r1.align_close_to(irx_df["Close"] / 100.0, dates).bfill()
    cp, cn = ov.calendar_cash_factors(dates, irx.to_numpy(float), r1.CONFIG["costs"]["us_margin_spread"])
    px = pd.DataFrame({"gold": g.to_numpy(float), "silver": s.to_numpy(float)}, index=dates)
    start_i = int(dates.searchsorted(pd.Timestamp("2001-09-04")))
    gsr = (g / s).to_numpy(float)
    s_above150 = lab.daily_buffered_ma_state(s, 150, 0.03).to_numpy(bool)
    n = len(dates)

    rows = []

    def eval_gsr(name: str, w_mat: np.ndarray, do_perm: bool = True):
        r = lab.run_multi_asset_overlay(px, r1.multi_weight_to_signal(w_mat, start_i, 0.02), start_i, 0.001, cp, cn)
        m = r1.summarize_nav_ext(r, "gold")
        m_pre20 = r1.summarize_nav_ext(r, "gold", start="2001-09-04", end="2019-12-31")
        m_post20 = r1.summarize_nav_ext(r, "gold", start="2020-01-02", end="2026-11-20")
        m26 = r1.summarize_nav_ext(r, "gold", start="2026-01-29", end="2026-11-20")
        p_sh = np.nan
        if do_perm:
            rng = np.random.default_rng(20261123)
            base_eval = w_mat[start_i:].copy()
            shifts = rng.integers(60, len(base_eval) - 60, size=200)
            beat = 0
            for sh in shifts:
                cand = w_mat.copy()
                cand[start_i:] = np.roll(base_eval, int(sh), axis=0)
                rs = lab.run_multi_asset_overlay(px, r1.multi_weight_to_signal(cand, start_i, 0.02), start_i, 0.001, cp, cn)
                ms = r1.summarize_nav_ext(rs, "gold")
                if np.isfinite(ms["sharpe"]) and ms["sharpe"] >= m["sharpe"]:
                    beat += 1
            p_sh = float((beat + 1) / 201)
        rows.append(
            {
                "strategy": name,
                "cagr": m["cagr"],
                "vol": m["vol"],
                "sharpe": m["sharpe"],
                "max_dd": m["max_dd"],
                "calmar": m["calmar"],
                "trades_total": int((~r.trades["is_initial"]).sum()) if not r.trades.empty else 0,
                "avg_w_silver": float(r.weights["silver"].iloc[1:].mean()),
                "perm_p_sharpe_25y": p_sh,
                "pre2020_cagr": m_pre20["cagr"],
                "pre2020_sharpe": m_pre20["sharpe"],
                "pre2020_mdd": m_pre20["max_dd"],
                "post2020_cagr": m_post20["cagr"],
                "post2020_sharpe": m_post20["sharpe"],
                "crash_2026_ret": m26["total_ret"],
            }
        )

    eval_gsr("BH_GCF_25Y", np.column_stack([np.ones(n), np.zeros(n)]), do_perm=False)
    eval_gsr("BH_SIF_25Y", np.column_stack([np.zeros(n), np.ones(n)]), do_perm=False)

    # Static threshold grid
    for hi, lo in [(75, 55), (80, 55), (80, 60), (80, 65), (85, 60), (85, 65), (90, 65)]:
        wm = np.zeros((n, 2))
        in_s = False
        for i in range(n):
            if gsr[i] > hi:
                in_s = True
            elif gsr[i] < lo:
                in_s = False
            wm[i] = [0.0, 1.0] if in_s else [1.0, 0.0]
        eval_gsr(f"GSR_100PCT_{hi}_{lo}", wm, do_perm=(hi == 80 and lo == 60))

    # Trend-gated & capped GSR (only put 30% or 50% in silver when GSR > 80 AND silver > 150d MA)
    for cap_s in (0.30, 0.50, 1.0):
        wm = np.zeros((n, 2))
        in_s = False
        for i in range(n):
            if gsr[i] > 80.0:
                in_s = True
            elif gsr[i] < 60.0:
                in_s = False
            w_s = cap_s if (in_s and s_above150[i]) else 0.0
            wm[i] = [1.0 - w_s, w_s]
        eval_gsr(f"GSR_80_60_TREND_CAP{int(cap_s*100)}", wm, do_perm=True)

    return pd.DataFrame(rows)


def run_deepdive4_gold_btc_regimes(gld_df: pd.DataFrame, btc_df: pd.DataFrame, irx_df: pd.DataFrame) -> pd.DataFrame:
    """Test Physical Gold + 5%/10% Digital Gold (BTC) split across 2015-2020 Early vs 2021-2026 Mature."""
    dates = pd.DatetimeIndex(gld_df.index[gld_df.index >= pd.Timestamp("2014-09-17")])
    irx = r1.align_close_to(irx_df["Close"] / 100.0, dates).bfill()
    cp, cn = ov.calendar_cash_factors(dates, irx.to_numpy(float), r1.CONFIG["costs"]["us_margin_spread"])
    start_i = int(dates.searchsorted(pd.Timestamp("2015-08-01")))
    gld = gld_df["Close"].reindex(dates)
    btc_c = r1.align_close_to(btc_df["Close"], dates)
    btc_h = r1.align_close_to(btc_df["High"], dates)
    btc_l = r1.align_close_to(btc_df["Low"], dates)
    btc_st = ind.supertrend_direction(btc_h, btc_l, btc_c, 10, 3.0).to_numpy(bool)
    btc_hyb = lab.daily_buffered_st_ma_weight(btc_h, btc_l, btc_c, 10, 3.0, 150, 0.05).to_numpy(float)
    gld_tvt, _ = build_tvt_weight(gld, target_vol=0.15, bear_cap=0.50, rebalance_freq="W", weight_deadband=0.10)
    px = pd.DataFrame({"gld": gld.to_numpy(float), "btc": btc_c.to_numpy(float)}, index=dates)

    specs = [
        ("GLD_BH", lab.fixed_weight_signal([1.0, 0.0], dates, start_i, freq="NONE")),
        ("GLD_TVT50_W_DB10", r1.multi_weight_to_signal(np.column_stack([gld_tvt, np.zeros(len(dates))]), start_i, 0.01)),
        ("GLD95_BTC5_Q", lab.fixed_weight_signal([0.95, 0.05], dates, start_i, freq="Q")),
        ("GLD90_BTC10_Q", lab.fixed_weight_signal([0.90, 0.10], dates, start_i, freq="Q")),
        (
            "GLD90_BTC10_ST",
            r1.multi_weight_to_signal(np.column_stack([np.full(len(dates), 0.90), np.where(btc_st, 0.10, 0.0)]), start_i, 0.02),
        ),
        (
            "GLD90_BTC10_HYB3",
            r1.multi_weight_to_signal(np.column_stack([np.full(len(dates), 0.90), btc_hyb * 0.10]), start_i, 0.02),
        ),
        (
            "GLD_TVT50_90_BTC10_HYB3",
            r1.multi_weight_to_signal(np.column_stack([gld_tvt * 0.90, btc_hyb * 0.10]), start_i, 0.02),
        ),
    ]
    rows = []
    for name, sig in specs:
        r = lab.run_multi_asset_overlay(px, sig, start_i, 0.002, cp, cn)
        m_full = r1.summarize_nav_ext(r, "gld")
        m_e = r1.summarize_nav_ext(r, "gld", start="2015-08-01", end="2020-12-31")
        m_m = r1.summarize_nav_ext(r, "gld", start="2021-01-04", end="2026-11-20")
        m26 = r1.summarize_nav_ext(r, "gld", start="2026-01-29", end="2026-11-20")
        rows.append(
            {
                "strategy": name,
                "full_cagr": m_full["cagr"],
                "full_sharpe": m_full["sharpe"],
                "full_mdd": m_full["max_dd"],
                "full_calmar": m_full["calmar"],
                "early_15_20_cagr": m_e["cagr"],
                "early_15_20_sharpe": m_e["sharpe"],
                "mature_21_26_cagr": m_m["cagr"],
                "mature_21_26_sharpe": m_m["sharpe"],
                "mature_21_26_mdd": m_m["max_dd"],
                "crash_2026_ret": m26["total_ret"],
            }
        )
    return pd.DataFrame(rows)


def compute_live_snapshot_2026_11_20(
    gld_df: pd.DataFrame, cn_gold_df: pd.DataFrame, paxg_df: pd.DataFrame, gcf_df: pd.DataFrame, sif_df: pd.DataFrame
) -> dict[str, Any]:
    snap: dict[str, Any] = {"as_of": "2026-11-20"}
    for label, df in [("GLD", gld_df), ("518880", cn_gold_df), ("PAXG", paxg_df)]:
        c = df["Close"]
        ann = 365.0 if label == "PAXG" else 252.0
        vol21 = float(np.log(c).diff().tail(21).std(ddof=1) * np.sqrt(ann))
        s2_on = bool(lab.weekly_stage2_state(c, 30, 4).iloc[-1])
        mtf3_b3 = float(lab.daily_buffered_mtf3_equity_weight(c, 150, 20, 210, 0.03).iloc[-1])
        tv_tgt = 0.12 if label == "518880" else 0.15
        tvt_w = min(1.0 if s2_on else 0.50, min(1.0, tv_tgt / vol21)) if vol21 > 0 else 0.5
        ma150 = float(c.rolling(150).mean().iloc[-1])
        ma210 = float(c.rolling(210).mean().iloc[-1])
        last_px = float(c.iloc[-1])
        pk26 = float(c[c.index >= "2026-01-01"].max())
        snap[label] = {
            "close": round(last_px, 2),
            "peak_2026": round(pk26, 2),
            "dd_from_2026_peak": round(last_px / pk26 - 1.0, 4),
            "ma150": round(ma150, 2),
            "ma210": round(ma210, 2),
            "vol21_ann": round(vol21, 4),
            "s2_30w_on": s2_on,
            "tvt50_target_w": round(tvt_w, 4),
            "mtf3_buf3_target_w": mtf3_b3,
        }
    snap["gold_silver_ratio_2026_11_20"] = round(float(gcf_df["Close"].iloc[-1] / sif_df["Close"].iloc[-1]), 2)
    return snap


def main() -> None:
    gld_df = r1.load_yf_ohlc("yf_GLD")
    gcf_df = r1.load_yf_ohlc("yf_GCF")
    sif_df = r1.load_yf_ohlc("yf_SIF")
    ief_df = r1.load_yf_ohlc("yf_IEF")
    spy_df = r1.load_yf_ohlc("yf_SPY")
    irx_df = r1.load_yf_ohlc("yf_IRX")
    btc_df = r1.load_yf_ohlc("yf_BTC")
    paxg_df = r1.load_yf_ohlc("yf_PAXG")
    cn_gold_df = r1.load_yf_ohlc("yf_518880")
    cn_bond5_df = r1.load_yf_ohlc("yf_511010")
    cn_bond10_df = r1.load_yf_ohlc("yf_511260")
    gold_55y, rf_m = r1.load_monthly_gold_55y()

    print("DeepDive 1: Low-Turnover TVT50 + Parameter Plateau + Domestic 518880...", flush=True)
    tvt_df, tvt_grid_df, cn_tvt_df = run_deepdive1_low_turnover_tvt(
        gld_df, gcf_df, ief_df, spy_df, irx_df, cn_gold_df, cn_bond5_df, cn_bond10_df
    )
    tvt_df.to_csv(OUT_DIR / "dd1_tvt_low_turnover_gld.csv", index=False)
    tvt_grid_df.to_csv(OUT_DIR / "dd1_tvt_param_plateau.csv", index=False)
    cn_tvt_df.to_csv(OUT_DIR / "dd1_tvt_low_turnover_cn518880.csv", index=False)

    print("DeepDive 2: 55-Year Rate Regime Decomposition...", flush=True)
    reg_df = run_deepdive2_rate_regime_55y(gold_55y, rf_m)
    reg_df.to_csv(OUT_DIR / "dd2_55y_rate_regimes.csv", index=False)

    print("DeepDive 3: 25-Year Gold/Silver Ratio (GSR) Stress Audit...", flush=True)
    gsr_df = run_deepdive3_gsr_audit_25y(gcf_df, sif_df, irx_df)
    gsr_df.to_csv(OUT_DIR / "dd3_gsr_25y_audit.csv", index=False)

    print("DeepDive 4: Physical Gold + BTC Early vs 2021-2026 Mature...", flush=True)
    btc_g_df = run_deepdive4_gold_btc_regimes(gld_df, btc_df, irx_df)
    btc_g_df.to_csv(OUT_DIR / "dd4_gold_btc_regimes.csv", index=False)

    snap = compute_live_snapshot_2026_11_20(gld_df, cn_gold_df, paxg_df, gcf_df, sif_df)
    (OUT_DIR / "gold_live_snapshot_2026_11_20.json").write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n")

    print("\n=== DD1: LOW-TURNOVER TVT ON GLD (21Y) ===")
    print(
        tvt_df[
            ["strategy", "cagr", "sharpe", "max_dd", "calmar", "trades_per_year", "sharpe_50bp", "perm_p_gld", "perm_p_gcf25y", "crash_2026_ret", "dca10y_ratio_beat_bh"]
        ].to_string(index=False)
    )
    print("\n=== DD1: TVT PARAMETER PLATEAU (140 combos) ===")
    print(
        f"Beats BH Sharpe: {tvt_grid_df['beats_bh_sharpe'].mean()*100:.1f}% ({tvt_grid_df['beats_bh_sharpe'].sum()}/{len(tvt_grid_df)}) | "
        f"Beats BH Calmar: {tvt_grid_df['beats_bh_calmar'].mean()*100:.1f}% ({tvt_grid_df['beats_bh_calmar'].sum()}/{len(tvt_grid_df)}) | "
        f"Median Sharpe: {tvt_grid_df['sharpe'].median():.3f} (BH=0.480)"
    )
    print(tvt_grid_df.groupby("bear_cap")[["cagr", "sharpe", "max_dd", "calmar", "beats_bh_sharpe"]].mean().to_string())

    print("\n=== DD1: DOMESTIC 518880 LOW-TURNOVER TVT + BOND ===")
    print(
        cn_tvt_df[
            ["strategy", "cagr", "sharpe", "max_dd", "calmar", "trades_per_year", "perm_p_sharpe", "pre2023_sharpe", "post2023_sharpe", "crash_2026_ret", "dca5y_ratio_beat_bh"]
        ].to_string(index=False)
    )
    print("\n=== DD2: 55-YEAR RATE REGIMES ===")
    print(reg_df[["regime", "avg_tbill_rate", "BH_cagr", "M10_SMA_cagr", "M12_SMA_cagr", "TVT50_M_cagr", "BH_mdd", "M10_SMA_mdd", "TVT50_M_mdd"]].to_string(index=False))
    print("\n=== DD3: 25-YEAR GSR AUDIT ===")
    print(
        gsr_df[
            ["strategy", "cagr", "sharpe", "max_dd", "trades_total", "perm_p_sharpe_25y", "pre2020_cagr", "pre2020_sharpe", "post2020_cagr", "crash_2026_ret"]
        ].to_string(index=False)
    )
    print("\n=== DD4: GOLD + BTC MATURE REGIME CHECK ===")
    print(btc_g_df.to_string(index=False))
    print("\n=== LIVE SNAPSHOT 2026-11-20 ===")
    print(json.dumps(snap, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
