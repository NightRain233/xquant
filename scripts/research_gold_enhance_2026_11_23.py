"""Formal Research Study: Gold Quantitative Enhancement Strategies (2026-11-23).

Comprehensive 9-module empirical study spanning:
1. Market Physics Fingerprint & 55-Year Seasonality Audit (GLD, GC=F, 518880, SLV, GDX vs SPY/BTC)
2. 55-Year Post-Bretton-Woods Long-Cycle Test (1972-2026 monthly, covering 1980-2001 20-year bear market)
3. Pure Gold Single-Asset Strategy Arena (35+ strategies across Trend, Buffered MTF-3, Zero-Lag MA,
   TSMOM, Donchian, Vol-Target, Overheat Brake, Mean-Reversion, 1.5x Trend Leverage, and Real 2x UGL)
   on real GLD (2005-12..2026-11, including the 2026 -35% crash) with 200x circular-shift permutation tests
4. Parameter Plateau Robustness & Annual Rolling-Start Stability Audit
5. Macro Factor Timing (Real Yield proxy TIP, Inflation Expectation TIP/IEF, USD Index DXY: 2005-2021 vs 2022-2026)
6. Precious-Metals Family Rotation (Gold/Silver Ratio mean-reversion vs Dual Momentum; Gold Miners GDX myth check)
7. Gold-Centric Cross-Asset Defensive Shields & Enhancers (Cash vs IEF vs TIP vs TLT vs Trend-SPY; + BTC satellite)
8. 10-Year & 5-Year Rolling Monthly DCA Experience (Plain vs Trend-Shielded vs Budget-Neutral Smart DCA)
9. Domestic RMB Gold ETF (518880 + 511010/511260 + FX decomposition + US-signal strict lag) & Crypto Gold (PAXG/XAUT)

Run (offline sandbox, from repo root):
    .venv/bin/python -I scripts/research_gold_enhance_2026_11_23.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from xquant import indicators as ind  # noqa: E402
from xquant import overlay_rules as ov  # noqa: E402
from xquant import sp500_lab as lab  # noqa: E402

SLUG = "gold-enhance-2026-11-23"
OUT_DIR = ROOT / "outputs" / SLUG
CACHE = OUT_DIR / "cache"
FRED_TB3MS_FALLBACK = ROOT / "outputs" / "sp500-enhance-vs-dca-2026-11-10" / "cache" / "fred_TB3MS" / "fred_TB3MS.csv"

CONFIG: dict[str, Any] = {
    "slug": SLUG,
    "execution_clock": "Signal at close t using data <= t only; order fills at close t+1 with proportional one-way cost.",
    "windows": {
        "long_55y_monthly": ["1972-01-31", "2026-10-31"],
        "gcf_daily": ["2001-09-04", "2026-11-20"],
        "gld_main": ["2005-12-01", "2026-11-20"],
        "gld_bull_05_11": ["2005-12-01", "2011-09-06"],
        "gld_bear_11_19": ["2011-09-06", "2019-05-31"],
        "gld_new_19_26": ["2019-06-03", "2026-11-20"],
        "gld_crash_2026": ["2026-01-29", "2026-11-20"],
        "metals_etf": ["2007-06-01", "2026-11-20"],
        "ugl_2x": ["2009-12-01", "2026-11-20"],
        "btc_gold": ["2015-08-01", "2026-11-20"],
        "domestic_518880": ["2014-08-01", "2026-11-20"],
        "crypto_paxg": ["2020-03-01", "2026-11-20"],
    },
    "costs": {
        "us_primary": 0.001,
        "us_stress": [0.001, 0.003, 0.005],
        "cn_primary": 0.001,
        "cn_stress": 0.003,
        "cn_cash_annual": 0.02,
        "us_margin_spread": 0.015,
        "long_55y_etf_fee": 0.004,
    },
    "circular_shift_trials": 200,
    "pass_bar": {
        "single_asset_defense": [
            "Beats GLD BH on both Sharpe and Calmar at 10bp across 2005-12..2026-11",
            "Cuts GLD MaxDD by >= 25% and materially cuts 2011-2019 underwater pain & 2026 crash loss",
            "Holds on 55-year post-Bretton-Woods cycle (1972-2026 incl. 1980-2001 20Y bear) and 25Y GC=F",
            "Circular-shift permutation p_sharpe <= 0.05 on GLD (or across both 55Y & GLD)",
            "Broad parameter plateau and survives 30bp/50bp slippage",
        ],
        "cross_asset_enhancer": [
            "Beats matched-exposure static allocation on Sharpe and Calmar",
            "Works across multiple regimes (not a single bull-market fluke)",
            "Low practical turnover compatible with retail ETF or crypto-gold accounts",
        ],
    },
}


# --------------------------------------------------------------------------- Loaders
def load_yf_ohlc(name: str) -> pd.DataFrame:
    df = pd.read_csv(CACHE / f"{name}.csv")
    idx = pd.to_datetime(df["Date"].astype(str).str.slice(0, 10))
    out = pd.DataFrame(
        {
            "Open": pd.to_numeric(df["Open"], errors="coerce").to_numpy(float),
            "High": pd.to_numeric(df["High"], errors="coerce").to_numpy(float),
            "Low": pd.to_numeric(df["Low"], errors="coerce").to_numpy(float),
            "Close": pd.to_numeric(df["Close"], errors="coerce").to_numpy(float),
        },
        index=idx,
    ).dropna()
    return out[~out.index.duplicated(keep="last")].sort_index()


def load_monthly_gold_55y() -> tuple[pd.Series, pd.Series]:
    """Load 1970-01..2026-10 monthly spot gold & FRED TB3MS annualized risk-free rate."""
    gm = pd.read_csv(CACHE / "datasets_gold_monthly.csv")
    idx = pd.to_datetime(gm["Date"].astype(str) + "-01") + pd.offsets.MonthEnd(0)
    gold = pd.Series(pd.to_numeric(gm["Price"], errors="coerce").to_numpy(float), index=idx, name="gold_spot").dropna()
    gold = gold[~gold.index.duplicated(keep="last")].sort_index()
    gold = gold[gold.index >= pd.Timestamp("1970-01-31")]

    tb = pd.read_csv(FRED_TB3MS_FALLBACK)
    tb_idx = pd.to_datetime(tb.iloc[:, 0]) + pd.offsets.MonthEnd(0)
    tb_s = pd.Series(pd.to_numeric(tb.iloc[:, 1], errors="coerce").to_numpy(float) / 100.0, index=tb_idx).dropna()
    tb_s = tb_s[~tb_s.index.duplicated(keep="last")].sort_index()
    rf_m = tb_s.reindex(gold.index).ffill().bfill()
    return gold, rf_m


def align_close_to(series: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    return series.reindex(dates.union(series.index)).ffill().reindex(dates)


def weight_to_signal(target_w: np.ndarray, start_i: int, threshold: float = 0.02):
    last_emitted = [np.nan]

    def sig(i: int, _actual: np.ndarray) -> Optional[np.ndarray]:
        w = float(target_w[i])
        if i == start_i:
            last_emitted[0] = w
            return np.array([w])
        if abs(w - last_emitted[0]) >= threshold:
            last_emitted[0] = w
            return np.array([w])
        return None

    return sig


def multi_weight_to_signal(target_w: np.ndarray, start_i: int, threshold: float = 0.02):
    """Emit target weight vector (shape N x M) whenever L1 change from last emitted >= threshold."""
    last_emitted: list[Optional[np.ndarray]] = [None]

    def sig(i: int, _actual: np.ndarray) -> Optional[np.ndarray]:
        w = np.asarray(target_w[i], dtype=float)
        if i == start_i or last_emitted[0] is None:
            last_emitted[0] = w.copy()
            return w
        if float(np.abs(w - last_emitted[0]).sum()) >= threshold:
            last_emitted[0] = w.copy()
            return w
        return None

    return sig


def summarize_nav_ext(
    res: lab.MultiEngineResult,
    primary_col: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    ann_days: int = 252,
) -> dict[str, Any]:
    nav = res.nav
    rf = res.tbill_daily
    wts = res.weights
    trades = res.trades
    if start is not None:
        ts = pd.Timestamp(start)
        nav = nav[nav.index >= ts]
        rf = rf[rf.index >= ts]
        wts = wts[wts.index >= ts]
        if not trades.empty:
            trades = trades[trades["exec_date"] >= ts]
    if end is not None:
        te = pd.Timestamp(end)
        nav = nav[nav.index <= te]
        rf = rf[rf.index <= te]
        wts = wts[wts.index <= te]
        if not trades.empty:
            trades = trades[trades["exec_date"] <= te]

    nav_n = nav / nav.iloc[0]
    days = (nav_n.index[-1] - nav_n.index[0]).days
    years = max(days / 365.25, 1e-6)
    cagr = float(nav_n.iloc[-1] ** (1.0 / years) - 1.0)
    ret = nav_n.pct_change().dropna()
    vol = float(ret.std(ddof=1) * np.sqrt(ann_days)) if len(ret) > 1 else np.nan
    ex = ret - rf.reindex(ret.index).fillna(0.0)
    ex_std = float(ex.std(ddof=1)) if len(ex) > 1 else np.nan
    sharpe = float(ex.mean() / ex_std * np.sqrt(ann_days)) if (ex_std and ex_std > 0) else np.nan
    dd = nav_n / nav_n.cummax() - 1.0
    max_dd = float(dd.min())
    calmar = float(cagr / abs(max_dd)) if max_dd < -1e-9 else np.nan
    uw_y = lab.max_underwater_years(nav_n)
    share_dd20 = float((dd < -0.20).mean())

    # Rolling 3Y and 5Y loss probability
    arr = nav_n.to_numpy(float)
    step3 = int(round(3 * ann_days))
    step5 = int(round(5 * ann_days))
    loss_3y = float(np.mean(arr[step3:] / arr[:-step3] - 1.0 < 0)) if len(arr) > step3 else np.nan
    loss_5y = float(np.mean(arr[step5:] / arr[:-step5] - 1.0 < 0)) if len(arr) > step5 else np.nan

    monthly = nav_n.resample("ME").last().pct_change().dropna()
    yearly = nav_n.resample("YE").last().pct_change().dropna()
    non_init = trades[~trades["is_initial"]] if not trades.empty else trades
    tpy = float(len(non_init) / years)
    turn = float(non_init["traded_frac"].sum() / years) if not non_init.empty else 0.0
    avg_exp = float(wts[primary_col].iloc[1:].mean()) if (primary_col in wts.columns and len(wts) > 1) else 0.0

    return {
        "start": str(nav.index[0].date()),
        "end": str(nav.index[-1].date()),
        "years": round(years, 2),
        "cagr": cagr,
        "total_ret": float(nav_n.iloc[-1] - 1.0),
        "vol": vol,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "calmar": calmar,
        "max_uw_years": uw_y,
        "share_dd20": share_dd20,
        "loss_3y_prob": loss_3y,
        "loss_5y_prob": loss_5y,
        "monthly_win_rate": float((monthly > 0).mean()) if len(monthly) else np.nan,
        "worst_month": float(monthly.min()) if len(monthly) else np.nan,
        "worst_year": float(yearly.min()) if len(yearly) else np.nan,
        "trades_per_year": tpy,
        "annual_turnover": turn,
        "avg_exposure": avg_exp,
        "terminal_multiple": float(nav_n.iloc[-1]),
    }


def fast_xirr(day_offsets: np.ndarray, terminal_val: float, weights: Optional[np.ndarray] = None) -> float:
    yrs = day_offsets / 365.25
    w = np.ones_like(yrs) if weights is None else weights
    lo, hi = -0.95, 5.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        val = float(np.sum(w * ((1.0 + mid) ** yrs)))
        if val > terminal_val:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def fast_dca_rolling(nav: pd.Series, window_months: int, cost: float) -> pd.DataFrame:
    dates = pd.DatetimeIndex(nav.index)
    vals = nav.to_numpy(float)
    ym = dates.year * 12 + dates.month
    first_idx = np.flatnonzero(np.r_[True, ym[1:] != ym[:-1]])
    last_idx = np.r_[first_idx[1:] - 1, len(dates) - 1]
    rows = []
    for k in range(len(first_idx) - window_months + 1):
        i0 = int(first_idx[k])
        i1 = int(last_idx[k + window_months - 1])
        c_idx = first_idx[k : k + window_months]
        if len(c_idx) != window_months:
            continue
        units = float(np.sum((1.0 - cost) / vals[c_idx]))
        end_val = units * float(vals[i1])
        day_off = (dates[i1] - dates[c_idx]).days.to_numpy(float)
        x = fast_xirr(day_off, end_val)
        seg = vals[i0 : i1 + 1]
        u_mdd = float(np.min(seg / np.maximum.accumulate(seg) - 1.0))
        cum_units = np.zeros(len(seg), dtype=float)
        cum_prin = np.zeros(len(seg), dtype=float)
        rel_c = c_idx - i0
        cum_units[rel_c] = (1.0 - cost) / vals[c_idx]
        cum_prin[rel_c] = 1.0
        float_ret = (np.cumsum(cum_units) * seg) / np.maximum(np.cumsum(cum_prin), 1e-12) - 1.0
        rows.append(
            {
                "start": str(dates[i0].date()),
                "end": str(dates[i1].date()),
                "xirr": float(x),
                "unit_max_dd": u_mdd,
                "max_float_loss": float(np.min(float_ret)),
                "dca_ratio": float(x / abs(u_mdd)) if u_mdd < 0 else np.nan,
            }
        )
    return pd.DataFrame(rows)


def circular_shift_perm_single(
    prices: pd.DataFrame,
    weight_arr: np.ndarray,
    start_i: int,
    *,
    cost: float,
    cash_pos: np.ndarray,
    cash_neg: np.ndarray,
    ann_days: int = 252,
    n_trials: int = 200,
    seed: int = 20261123,
    sub_start: Optional[str] = None,
    sub_end: Optional[str] = None,
) -> dict[str, Any]:
    col = prices.columns[0]
    res_obs = lab.run_multi_asset_overlay(
        prices, weight_to_signal(weight_arr, start_i), start_i, cost, cash_pos, cash_neg
    )
    m_obs = summarize_nav_ext(res_obs, primary_col=col, start=sub_start, end=sub_end, ann_days=ann_days)
    obs_sharpe = m_obs["sharpe"]
    obs_cagr = m_obs["cagr"]
    obs_calmar = m_obs["calmar"]

    rng = np.random.default_rng(seed)
    base_eval = weight_arr[start_i:].copy()
    n_eval = len(base_eval)
    min_sh = max(12, n_eval // 15)
    shifts = rng.integers(min_sh, n_eval - min_sh, size=n_trials)
    beat_s = beat_c = beat_cal = 0
    null_s, null_c = [], []
    for sh in shifts:
        cand = weight_arr.copy()
        cand[start_i:] = np.roll(base_eval, int(sh))
        r_sim = lab.run_multi_asset_overlay(
            prices, weight_to_signal(cand, start_i), start_i, cost, cash_pos, cash_neg
        )
        ms = summarize_nav_ext(r_sim, primary_col=col, start=sub_start, end=sub_end, ann_days=ann_days)
        if np.isfinite(ms["sharpe"]):
            null_s.append(ms["sharpe"])
        null_c.append(ms["cagr"])
        if np.isfinite(obs_sharpe) and np.isfinite(ms["sharpe"]) and ms["sharpe"] >= obs_sharpe:
            beat_s += 1
        if ms["cagr"] >= obs_cagr:
            beat_c += 1
        if np.isfinite(obs_calmar) and np.isfinite(ms["calmar"]) and ms["calmar"] >= obs_calmar:
            beat_cal += 1
    return {
        "obs_cagr": obs_cagr,
        "obs_sharpe": obs_sharpe,
        "obs_calmar": obs_calmar,
        "obs_mdd": m_obs["max_dd"],
        "null_median_cagr": float(np.median(null_c)),
        "null_median_sharpe": float(np.median(null_s)) if null_s else np.nan,
        "p_cagr": float((beat_c + 1) / (n_trials + 1)),
        "p_sharpe": float((beat_s + 1) / (n_trials + 1)),
        "p_calmar": float((beat_cal + 1) / (n_trials + 1)),
        "n_trials": n_trials,
    }


# --------------------------------------------------------------------------- Strategy Signal Builders
def build_gold_single_strategies(ohlc: pd.DataFrame, *, ann_days: int = 252) -> dict[str, tuple[str, np.ndarray]]:
    """Build 35 pre-registered single-asset gold strategy weight series (all strictly causal)."""
    close = ohlc["Close"]
    high = ohlc["High"]
    low = ohlc["Low"]
    n = len(close)
    log_ret = np.log(close).diff()
    vol21 = log_ret.rolling(21).std(ddof=1) * np.sqrt(float(ann_days))
    vol63 = log_ret.rolling(63).std(ddof=1) * np.sqrt(float(ann_days))

    out: dict[str, tuple[str, np.ndarray]] = {}

    # 0. Baselines
    out["BH"] = ("Baseline", np.ones(n, dtype=float))
    # Fixed quarterly handled separately or approximated as constant target here? For fairness,
    # fixed quarterly benchmarks are run via lab.fixed_weight_signal in the main runner.

    # 1. Classic Weekly / Monthly Trend
    s2 = lab.weekly_stage2_state(close, ma_weeks=30, slope_weeks=4).to_numpy(bool)
    m10 = lab.monthly_ma_state(close, ma_months=10).to_numpy(bool)
    out["S2_HALF"] = ("Weekly/Monthly", np.where(s2, 1.0, 0.5))
    out["S2_FULL"] = ("Weekly/Monthly", np.where(s2, 1.0, 0.0))
    out["M10_SMA"] = ("Weekly/Monthly", np.where(m10, 1.0, 0.0))
    out["MTF3_CAL"] = ("Weekly/Monthly", np.where(s2 & m10, 1.0, np.where(s2 | m10, 0.5, 0.0)))

    # 2. Daily Buffered MTF-3 & Single MA Hysteresis
    for buf in (0.02, 0.03, 0.05):
        tag = f"MTF3_BUF{int(round(buf * 100))}"
        out[tag] = (
            "Buffered_MTF3",
            lab.daily_buffered_mtf3_equity_weight(close, ma_fast=150, slope_days=20, ma_slow=210, buffer=buf).to_numpy(float),
        )
    # Faster buffered 3-tier (100d rising + 200d)
    f100 = lab.daily_buffered_stage_state(close, ma_days=100, slope_days=15, buffer=0.03).to_numpy(bool)
    s200 = lab.daily_buffered_ma_state(close, ma_days=200, buffer=0.03).to_numpy(bool)
    out["MTF3_100_200_B3"] = ("Buffered_MTF3", np.where(f100 & s200, 1.0, np.where(f100 | s200, 0.5, 0.0)))

    for win, buf in [(100, 0.03), (150, 0.03), (200, 0.03), (200, 0.05)]:
        st = lab.daily_buffered_ma_state(close, ma_days=win, buffer=buf).to_numpy(bool)
        out[f"SMA_{win}_B{int(round(buf * 100))}"] = ("Buffered_Single_MA", np.where(st, 1.0, 0.0))

    # Zero-lag MA + hysteresis buffer (from BTC study)
    for name, ma_s, buf in [
        ("DEMA_150_B3", ind.dema(close, 150), 0.03),
        ("DEMA_150_B5", ind.dema(close, 150), 0.05),
        ("ZLEMA_150_B3", ind.zlema(close, 150), 0.03),
    ]:
        st = ind.hysteresis_ma_state(close, ma_s, buffer=buf).to_numpy(bool)
        out[name] = ("ZeroLag_Buffered", np.where(st, 1.0, 0.0))

    # 3. Dual MA / SuperTrend / Hybrid / Donchian / Institutional TSMOM
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    ema20 = ind.ema(close, 20)
    ema100 = ind.ema(close, 100)
    ema50 = ind.ema(close, 50)
    ema200 = ind.ema(close, 200)
    out["DSMA_50_200"] = ("Dual_MA", (sma50 > sma200).fillna(False).to_numpy(float))
    out["DEMA_X_20_100"] = ("Dual_MA", (ema20 > ema100).fillna(False).to_numpy(float))
    out["DEMA_X_50_200"] = ("Dual_MA", (ema50 > ema200).fillna(False).to_numpy(float))

    st10 = ind.supertrend_direction(high, low, close, atr_window=10, multiplier=3.0).to_numpy(bool)
    st20 = ind.supertrend_direction(high, low, close, atr_window=20, multiplier=3.0).to_numpy(bool)
    ma150_b3 = lab.daily_buffered_ma_state(close, ma_days=150, buffer=0.03).to_numpy(bool)
    ma150_b5 = lab.daily_buffered_ma_state(close, ma_days=150, buffer=0.05).to_numpy(bool)
    out["ST_10_3"] = ("SuperTrend", np.where(st10, 1.0, 0.0))
    out["ST_20_3"] = ("SuperTrend", np.where(st20, 1.0, 0.0))
    out["HYB_ST_MA150_B3"] = ("Hybrid_3Tier", np.where(st10 & ma150_b3, 1.0, np.where(st10 | ma150_b3, 0.5, 0.0)))
    out["HYB_ST_MA150_B5"] = ("Hybrid_3Tier", np.where(st10 & ma150_b5, 1.0, np.where(st10 | ma150_b5, 0.5, 0.0)))

    don55 = ind.donchian_breakout_state(high, low, close, entry_window=55, exit_window=20).to_numpy(bool)
    don100 = ind.donchian_breakout_state(high, low, close, entry_window=100, exit_window=50).to_numpy(bool)
    out["DONCHIAN_55_20"] = ("Breakout", np.where(don55, 1.0, 0.0))
    out["DONCHIAN_100_50"] = ("Breakout", np.where(don100, 1.0, 0.0))

    ts_13612 = ind.tsmom_blend_weight(close, lookbacks=(21, 63, 126, 252), buffer=0.0).to_numpy(float)
    ts_3612_b2 = ind.tsmom_blend_weight(close, lookbacks=(63, 126, 252), buffer=0.02).to_numpy(float)
    ts_13612_b2 = ind.tsmom_blend_weight(close, lookbacks=(21, 63, 126, 252), buffer=0.02).to_numpy(float)
    out["TSMOM_1_3_6_12"] = ("CTA_TSMOM", ts_13612)
    out["TSMOM_1_3_6_12_B2"] = ("CTA_TSMOM", ts_13612_b2)
    out["TSMOM_3_6_12_B2"] = ("CTA_TSMOM", ts_3612_b2)

    # Volatility-scaled CTA TSMOM (capped at 100%, target vol 15%)
    v_scale_15 = np.clip(0.15 / np.where(np.isfinite(vol63) & (vol63 > 1e-4), vol63, 0.15), 0.0, 1.0)
    out["TSMOM_VOL15"] = ("CTA_TSMOM", ts_13612_b2 * v_scale_15)

    # 4. Volatility Management & Overheat Parabolic Brake
    vt12 = np.clip(0.12 / np.where(np.isfinite(vol21) & (vol21 > 1e-4), vol21, 0.12), 0.0, 1.0)
    vt15 = np.clip(0.15 / np.where(np.isfinite(vol21) & (vol21 > 1e-4), vol21, 0.15), 0.0, 1.0)
    out["VT_12"] = ("Vol_Target", vt12)
    out["VT_15"] = ("Vol_Target", vt15)
    out["TVT50_15"] = ("Vol_Target", np.minimum(vt15, np.where(s2, 1.0, 0.5)))

    # Overheat parabolic brake on top of MTF3_BUF3: if close > 1.25 * SMA200 AND vol21 > 25%, cap at 50%
    mtf3_b3 = out["MTF3_BUF3"][1]
    bias200 = (close / sma200 - 1.0).fillna(0.0).to_numpy(float)
    overheat = (bias200 > 0.25) & (vol21.fillna(0.0).to_numpy(float) > 0.25)
    out["MTF3_BUF3_OVERHEAT"] = ("Overheat_Brake", np.where(overheat, np.minimum(mtf3_b3, 0.5), mtf3_b3))

    # 5. Moderate Trend Leverage (strictly charged IRX + 1.5% borrow rate in engine!)
    out["LEV15_MTF3_BUF3"] = ("Trend_Leverage", mtf3_b3 * 1.5)
    out["LEV15_TSMOM"] = ("Trend_Leverage", ts_3612_b2 * 1.5)
    # Volatility-targeted trend leverage (target 18% vol capped at 1.5x, multiplied by MTF3_BUF3)
    v_scale_18_lev = np.clip(0.18 / np.where(np.isfinite(vol63) & (vol63 > 1e-4), vol63, 0.18), 0.0, 1.5)
    out["VT18_CAP150_MTF3"] = ("Trend_Leverage", np.where(mtf3_b3 > 0, mtf3_b3 * v_scale_18_lev, 0.0))

    # 6. Mean-Reversion / Contrarian Controls (hypothesized to fail in gold bull runs)
    rsi14 = ind.rsi_wilder(close, 14).to_numpy(float)
    w_rsi_bin = np.zeros(n, dtype=float)
    w_rsi_core = np.full(n, 0.70, dtype=float)
    st_r = False
    for i in range(n):
        if np.isnan(rsi14[i]):
            continue
        if rsi14[i] < 30.0:
            st_r = True
            w_rsi_core[i] = 1.0
        elif rsi14[i] > 70.0:
            st_r = False
            w_rsi_core[i] = 0.40
        else:
            w_rsi_core[i] = w_rsi_core[i - 1] if i > 0 else 0.70
        w_rsi_bin[i] = 1.0 if st_r else 0.0
    out["RSI14_30_70_BIN"] = ("Mean_Reversion", w_rsi_bin)
    out["RSI14_CORE_70"] = ("Mean_Reversion", w_rsi_core)

    z20 = ind.bollinger_zscore(close, 20).to_numpy(float)
    w_boll = np.full(n, 0.70, dtype=float)
    for i in range(n):
        if np.isnan(z20[i]):
            continue
        if z20[i] < -2.0:
            w_boll[i] = 1.0
        elif z20[i] > 2.0:
            w_boll[i] = 0.40
        else:
            w_boll[i] = w_boll[i - 1] if i > 0 else 0.70
    out["BOLL_D20_CORE"] = ("Mean_Reversion", w_boll)

    rev_ma150 = ~lab.daily_buffered_ma_state(close, ma_days=150, buffer=0.03).to_numpy(bool)
    out["REV_MA150_B3"] = ("Mean_Reversion", np.where(rev_ma150, 1.0, 0.0))

    sma120 = close.rolling(120).mean()
    bias120 = (close / sma120 - 1.0).to_numpy(float)
    w_bias = np.full(n, 0.70, dtype=float)
    for i in range(n):
        if np.isnan(bias120[i]):
            continue
        if bias120[i] < -0.08:
            w_bias[i] = 1.0
        elif bias120[i] > 0.08:
            w_bias[i] = 0.40
        else:
            w_bias[i] = w_bias[i - 1] if i > 0 else 0.70
    out["BIAS_MA120_8PCT_CORE"] = ("Mean_Reversion", w_bias)

    return out


# --------------------------------------------------------------------------- Module 1: Physics & Seasonality
def run_module1_physics_and_seasonality(
    gld_df: pd.DataFrame,
    gcf_df: pd.DataFrame,
    slv_df: pd.DataFrame,
    gdx_df: pd.DataFrame,
    cn_gold_df: pd.DataFrame,
    spy_df: pd.DataFrame,
    btc_df: pd.DataFrame,
    gold_55y: pd.Series,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    phys_rows = []
    specs = [
        ("GLD_2005_2026", gld_df["Close"], "2005-12-01", "2026-11-20", 252),
        ("GLD_2005_2011_Bull", gld_df["Close"], "2005-12-01", "2011-09-06", 252),
        ("GLD_2011_2019_Bear", gld_df["Close"], "2011-09-06", "2019-05-31", 252),
        ("GLD_2019_2026_New", gld_df["Close"], "2019-06-03", "2026-11-20", 252),
        ("GCF_2001_2026", gcf_df["Close"], "2001-09-04", "2026-11-20", 252),
        ("CN_518880_2014_2026", cn_gold_df["Close"], "2014-08-01", "2026-11-20", 252),
        ("SLV_2007_2026", slv_df["Close"], "2007-06-01", "2026-11-20", 252),
        ("GDX_2007_2026", gdx_df["Close"], "2007-06-01", "2026-11-20", 252),
        ("SPY_2005_2026_Ref", spy_df["Close"], "2005-12-01", "2026-11-20", 252),
        ("BTC_2015_2026_Ref", btc_df["Close"], "2015-08-01", "2026-11-20", 365),
    ]
    for label, s_full, s0, s1, ann_days in specs:
        ma150 = s_full.rolling(150).mean()
        ma200 = s_full.rolling(200).mean()
        fwd60 = s_full.shift(-60) / s_full - 1.0
        fwd120 = s_full.shift(-120) / s_full - 1.0
        ret1 = s_full.pct_change()
        mask = (s_full.index >= pd.Timestamp(s0)) & (s_full.index <= pd.Timestamp(s1))
        sub = s_full.loc[mask]
        years = (sub.index[-1] - sub.index[0]).days / 365.25
        cagr = float((sub.iloc[-1] / sub.iloc[0]) ** (1.0 / years) - 1.0)
        vol = float(sub.pct_change().dropna().std(ddof=1) * np.sqrt(ann_days))
        dd = sub / sub.cummax() - 1.0
        max_dd = float(dd.min())
        uw = lab.max_underwater_years(sub)

        above150 = (s_full > ma150).loc[mask]
        above200 = (s_full > ma200).loc[mask]
        f60 = fwd60.loc[mask]
        f120 = fwd120.loc[mask]
        r1 = ret1.loc[mask]
        sp60_150 = float(f60[above150].mean() - f60[~above150].mean())
        sp120_150 = float(f120[above150].mean() - f120[~above150].mean())
        sp60_200 = float(f60[above200].mean() - f60[~above200].mean())
        vol_above = float(r1[above150].std(ddof=1) * np.sqrt(ann_days))
        vol_below = float(r1[~above150].std(ddof=1) * np.sqrt(ann_days))
        # Monthly autocorrelation
        m_rets = sub.resample("ME").last().pct_change().dropna()
        ac1_m = float(m_rets.autocorr(lag=1)) if len(m_rets) > 12 else np.nan
        ac12_m = float(m_rets.rolling(12).sum().dropna().autocorr(lag=1)) if len(m_rets) > 24 else np.nan
        phys_rows.append(
            {
                "asset_window": label,
                "start": str(sub.index[0].date()),
                "end": str(sub.index[-1].date()),
                "years": round(years, 2),
                "cagr": cagr,
                "vol": vol,
                "max_dd": max_dd,
                "max_uw_years": uw,
                "pct_above_ma150": float(above150.mean()),
                "fwd60_above_ma150": float(f60[above150].mean()),
                "fwd60_below_ma150": float(f60[~above150].mean()),
                "trend_spread_60d_ma150": sp60_150,
                "trend_spread_120d_ma150": sp120_150,
                "trend_spread_60d_ma200": sp60_200,
                "vol_above_ma150": vol_above,
                "vol_below_ma150": vol_below,
                "vol_ratio_below_over_above": vol_below / vol_above if vol_above > 0 else np.nan,
                "monthly_autocorr_1m": ac1_m,
            }
        )
    phys_df = pd.DataFrame(phys_rows)

    # Seasonality audit: 55-year monthly gold (1971-01..2026-10) AND GLD (2005-01..2026-10)
    seas_rows = []
    for ds_name, m_series in [
        ("SpotGold_55Y_1971_2026", gold_55y[gold_55y.index >= "1970-12-31"].pct_change().dropna()),
        ("GLD_22Y_2005_2026", gld_df["Close"].resample("ME").last().pct_change().dropna().loc["2005-01-01":"2026-10-31"]),
        ("CN_518880_13Y_2013_2026", cn_gold_df["Close"].resample("ME").last().pct_change().dropna().loc["2013-08-01":"2026-10-31"]),
    ]:
        overall_mean = float(m_series.mean())
        for m in range(1, 13):
            vals = m_series[m_series.index.month == m].to_numpy(float)
            mean_v = float(np.mean(vals))
            sd_v = float(np.std(vals, ddof=1))
            t_stat = float((mean_v - overall_mean) / (sd_v / np.sqrt(len(vals)))) if sd_v > 0 else 0.0
            seas_rows.append(
                {
                    "dataset": ds_name,
                    "month": m,
                    "n_years": int(len(vals)),
                    "mean_ret": mean_v,
                    "median_ret": float(np.median(vals)),
                    "win_rate": float(np.mean(vals > 0)),
                    "excess_vs_avg_month": mean_v - overall_mean,
                    "t_stat_vs_avg": t_stat,
                }
            )
    seas_df = pd.DataFrame(seas_rows)
    return phys_df, seas_df


# --------------------------------------------------------------------------- Module 2: 55-Year Monthly Long-Cycle Test
def run_module2_long_55y(gold_55y: pd.Series, rf_m: pd.Series) -> pd.DataFrame:
    """55-year post-Bretton-Woods monthly backtest (1972-01..2026-10) covering 1980-2001 20Y bear."""
    dates = pd.DatetimeIndex(gold_55y.index)
    prices = pd.DataFrame({"gold": gold_55y.to_numpy(float)}, index=dates)
    start_i = int(dates.searchsorted(pd.Timestamp("1972-01-31")))
    day_diff = np.zeros(len(dates), dtype=float)
    day_diff[1:] = (dates[1:] - dates[:-1]).days.to_numpy(float)
    cash_pos = (1.0 + rf_m.to_numpy(float)) ** (day_diff / 365.25)
    cash_pos[0] = 1.0
    cost = CONFIG["costs"]["us_primary"]
    etf_fee = CONFIG["costs"]["long_55y_etf_fee"]

    # Build monthly causal signals (0% to 100%)
    s = gold_55y
    n = len(s)
    m6 = (s > s.rolling(6).mean()).fillna(False).to_numpy(bool)
    m10 = (s > s.rolling(10).mean()).fillna(False).to_numpy(bool)
    m12 = (s > s.rolling(12).mean()).fillna(False).to_numpy(bool)
    m10_rising = (s.rolling(10).mean() > s.rolling(10).mean().shift(2)).fillna(False).to_numpy(bool)
    m10_b3 = ind.hysteresis_ma_state(s, s.rolling(10).mean(), buffer=0.03).to_numpy(bool)
    m7_b3 = ind.hysteresis_ma_state(s, s.rolling(7).mean(), buffer=0.03, rising_lookback=1).to_numpy(bool)
    tsmom_m = ind.tsmom_blend_weight(s, lookbacks=(1, 3, 6, 12), buffer=0.0).to_numpy(float)
    tsmom_m_3_6_12 = ind.tsmom_blend_weight(s, lookbacks=(3, 6, 12), buffer=0.02).to_numpy(float)

    # Seasonal rule (buy Nov-Feb + Aug-Sep, cash otherwise) vs BH
    months = dates.month.to_numpy()
    seas_w = np.isin(months, [11, 12, 1, 2, 8, 9]).astype(float)

    strats = {
        "BH_GOLD_55Y": np.ones(n, dtype=float),
        "M6_SMA": m6.astype(float),
        "M10_SMA": m10.astype(float),
        "M12_SMA": m12.astype(float),
        "S2_HALF_M10": np.where(m10 & m10_rising, 1.0, 0.5),
        "M10_BUF3": m10_b3.astype(float),
        "MTF3_M7_M10_B3": np.where(m7_b3 & m10_b3, 1.0, np.where(m7_b3 | m10_b3, 0.5, 0.0)),
        "TSMOM_M_1_3_6_12": tsmom_m,
        "TSMOM_M_3_6_12_B2": tsmom_m_3_6_12,
        "SEASONAL_NOV_FEB_AUG_SEP": seas_w,
    }

    sub_periods = [
        ("full_55y", "1972-01-31", "2026-10-31"),
        ("bull_72_80", "1972-01-31", "1980-01-31"),
        ("bear_80_01", "1980-01-31", "2001-03-31"),
        ("bull_01_11", "2001-03-31", "2011-09-30"),
        ("bear_11_19", "2011-09-30", "2019-05-31"),
        ("new_19_26", "2019-05-31", "2026-10-31"),
    ]
    rows = []
    for name, w in strats.items():
        res = lab.run_multi_asset_overlay(
            prices,
            weight_to_signal(w, start_i, threshold=0.02),
            start_i,
            cost,
            cash_pos,
            extra_daily_drag={"gold": etf_fee},
        )
        m_full = summarize_nav_ext(res, primary_col="gold", ann_days=12)
        row: dict[str, Any] = {"strategy": name, **m_full}
        for tag, p0, p1 in sub_periods[1:]:
            ms = summarize_nav_ext(res, primary_col="gold", start=p0, end=p1, ann_days=12)
            row[f"{tag}_cagr"] = ms["cagr"]
            row[f"{tag}_sharpe"] = ms["sharpe"]
            row[f"{tag}_mdd"] = ms["max_dd"]
        # Circular shift permutation on 55Y monthly series (200 trials, fast!)
        if name != "BH_GOLD_55Y":
            rng = np.random.default_rng(20261123)
            base_eval = w[start_i:].copy()
            shifts = rng.integers(12, len(base_eval) - 12, size=CONFIG["circular_shift_trials"])
            beat_s = 0
            for sh in shifts:
                cand = w.copy()
                cand[start_i:] = np.roll(base_eval, int(sh))
                rs = lab.run_multi_asset_overlay(
                    prices,
                    weight_to_signal(cand, start_i, threshold=0.02),
                    start_i,
                    cost,
                    cash_pos,
                    extra_daily_drag={"gold": etf_fee},
                )
                ms = summarize_nav_ext(rs, primary_col="gold", ann_days=12)
                if np.isfinite(ms["sharpe"]) and ms["sharpe"] >= m_full["sharpe"]:
                    beat_s += 1
            row["perm_p_sharpe_55y"] = float((beat_s + 1) / (CONFIG["circular_shift_trials"] + 1))
        else:
            row["perm_p_sharpe_55y"] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- Module 3: GLD Single-Asset Arena + UGL + GC=F
def run_module3_single_asset_arena(
    gld_df: pd.DataFrame,
    iau_df: pd.DataFrame,
    gcf_df: pd.DataFrame,
    ugl_df: pd.DataFrame,
    irx_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, lab.MultiEngineResult]]:
    dates = pd.DatetimeIndex(gld_df.index)
    irx = align_close_to(irx_df["Close"] / 100.0, dates).bfill()
    cash_pos, cash_neg = ov.calendar_cash_factors(dates, irx.to_numpy(float), CONFIG["costs"]["us_margin_spread"])
    prices = pd.DataFrame({"gold": gld_df["Close"].to_numpy(float)}, index=dates)
    start_i = int(dates.searchsorted(pd.Timestamp(CONFIG["windows"]["gld_main"][0])))

    strats = build_gold_single_strategies(gld_df, ann_days=252)

    # Also evaluate IAU low-fee BH & Fixed Quarterly 70%/50% matched-exposure controls
    summary_rows = []
    period_rows = []
    nav_results: dict[str, lab.MultiEngineResult] = {}

    # Run all single-asset strategies on GLD at 10bp, 30bp, 50bp
    for name, (family, w) in strats.items():
        res10 = lab.run_multi_asset_overlay(prices, weight_to_signal(w, start_i), start_i, 0.001, cash_pos, cash_neg)
        res30 = lab.run_multi_asset_overlay(prices, weight_to_signal(w, start_i), start_i, 0.003, cash_pos, cash_neg)
        res50 = lab.run_multi_asset_overlay(prices, weight_to_signal(w, start_i), start_i, 0.005, cash_pos, cash_neg)
        nav_results[name] = res10

        m10 = summarize_nav_ext(res10, primary_col="gold")
        m30 = summarize_nav_ext(res30, primary_col="gold")
        m50 = summarize_nav_ext(res50, primary_col="gold")

        # Matched-exposure fixed quarterly benchmark (exact same avg exposure as strategy, rebalanced quarterly)
        exp_cap = float(np.clip(m10["avg_exposure"], 0.05, 1.5))
        res_match = lab.run_multi_asset_overlay(
            prices,
            lab.fixed_weight_signal([exp_cap], dates, start_i, freq="Q"),
            start_i,
            0.001,
            cash_pos,
            cash_neg,
        )
        m_match = summarize_nav_ext(res_match, primary_col="gold")

        # Sub-periods
        mbull = summarize_nav_ext(res10, primary_col="gold", start="2005-12-01", end="2011-09-06")
        mbear = summarize_nav_ext(res10, primary_col="gold", start="2011-09-06", end="2019-05-31")
        mnew = summarize_nav_ext(res10, primary_col="gold", start="2019-06-03", end="2026-11-20")
        m26 = summarize_nav_ext(res10, primary_col="gold", start="2026-01-29", end="2026-11-20")

        # Find first exit / defense date in 2026 crash (weight drops below 1.0 after 2026-01-29)
        w26 = res10.weights["gold"].loc["2026-01-29":"2026-11-20"]
        dropped = w26[w26 < 0.90]
        first_def_26 = str(dropped.index[0].date()) if len(dropped) else "never"
        w_end_26 = float(w26.iloc[-1])

        summary_rows.append(
            {
                "strategy": name,
                "family": family,
                **m10,
                "sharpe_vs_matched_fix": m10["sharpe"] - m_match["sharpe"],
                "cagr_vs_matched_fix": m10["cagr"] - m_match["cagr"],
                "cagr_30bp": m30["cagr"],
                "sharpe_30bp": m30["sharpe"],
                "cagr_50bp": m50["cagr"],
                "sharpe_50bp": m50["sharpe"],
                "bull_05_11_cagr": mbull["cagr"],
                "bull_05_11_sharpe": mbull["sharpe"],
                "bear_11_19_cagr": mbear["cagr"],
                "bear_11_19_sharpe": mbear["sharpe"],
                "bear_11_19_mdd": mbear["max_dd"],
                "new_19_26_cagr": mnew["cagr"],
                "new_19_26_sharpe": mnew["sharpe"],
                "new_19_26_mdd": mnew["max_dd"],
                "crash_2026_ret": m26["total_ret"],
                "crash_2026_mdd": m26["max_dd"],
                "crash_2026_first_defense_date": first_def_26,
                "weight_2026_11_20": w_end_26,
            }
        )
        for ptag, ps, pe in [
            ("2008_GFC", "2008-03-17", "2008-11-12"),
            ("2011_2015_DeepBear", "2011-09-06", "2015-12-17"),
            ("2016_2018_Chop", "2016-07-06", "2018-09-28"),
            ("2020_COVID_Bull", "2020-01-02", "2020-08-06"),
            ("2022_RateHike", "2022-03-08", "2022-11-03"),
            ("2023_2026_CentralBankBull", "2023-01-03", "2026-01-29"),
            ("2026_Crash", "2026-01-29", "2026-11-20"),
        ]:
            mp = summarize_nav_ext(res10, primary_col="gold", start=ps, end=pe)
            period_rows.append(
                {
                    "strategy": name,
                    "family": family,
                    "period": ptag,
                    "total_ret": mp["total_ret"],
                    "max_dd": mp["max_dd"],
                    "avg_exposure": mp["avg_exposure"],
                }
            )

    # Add IAU low-fee ETF comparison (same 2005-12..2026-11 window)
    iau_c = align_close_to(iau_df["Close"], dates)
    res_iau = lab.run_multi_asset_overlay(
        pd.DataFrame({"gold": iau_c.to_numpy(float)}, index=dates),
        weight_to_signal(np.ones(len(dates)), start_i),
        start_i,
        0.001,
        cash_pos,
        cash_neg,
    )
    m_iau = summarize_nav_ext(res_iau, primary_col="gold")
    summary_rows.append(
        {
            "strategy": "BH_IAU_LowFee",
            "family": "Baseline",
            **m_iau,
            "sharpe_vs_matched_fix": 0.0,
            "cagr_vs_matched_fix": 0.0,
            "cagr_30bp": m_iau["cagr"],
            "sharpe_30bp": m_iau["sharpe"],
            "cagr_50bp": m_iau["cagr"],
            "sharpe_50bp": m_iau["sharpe"],
            "bull_05_11_cagr": summarize_nav_ext(res_iau, "gold", "2005-12-01", "2011-09-06")["cagr"],
            "bull_05_11_sharpe": summarize_nav_ext(res_iau, "gold", "2005-12-01", "2011-09-06")["sharpe"],
            "bear_11_19_cagr": summarize_nav_ext(res_iau, "gold", "2011-09-06", "2019-05-31")["cagr"],
            "bear_11_19_sharpe": summarize_nav_ext(res_iau, "gold", "2011-09-06", "2019-05-31")["sharpe"],
            "bear_11_19_mdd": summarize_nav_ext(res_iau, "gold", "2011-09-06", "2019-05-31")["max_dd"],
            "new_19_26_cagr": summarize_nav_ext(res_iau, "gold", "2019-06-03", "2026-11-20")["cagr"],
            "new_19_26_sharpe": summarize_nav_ext(res_iau, "gold", "2019-06-03", "2026-11-20")["sharpe"],
            "new_19_26_mdd": summarize_nav_ext(res_iau, "gold", "2019-06-03", "2026-11-20")["max_dd"],
            "crash_2026_ret": summarize_nav_ext(res_iau, "gold", "2026-01-29", "2026-11-20")["total_ret"],
            "crash_2026_mdd": summarize_nav_ext(res_iau, "gold", "2026-01-29", "2026-11-20")["max_dd"],
            "crash_2026_first_defense_date": "never",
            "weight_2026_11_20": 1.0,
        }
    )

    # Permutation tests for all representative strategies on GLD (200 trials) AND GC=F 25Y OOS/longer check
    perm_targets = [
        "S2_HALF",
        "S2_FULL",
        "M10_SMA",
        "MTF3_CAL",
        "MTF3_BUF2",
        "MTF3_BUF3",
        "MTF3_BUF5",
        "MTF3_100_200_B3",
        "SMA_100_B3",
        "SMA_150_B3",
        "SMA_200_B3",
        "DEMA_150_B3",
        "DEMA_150_B5",
        "ZLEMA_150_B3",
        "DSMA_50_200",
        "DEMA_X_20_100",
        "ST_10_3",
        "ST_20_3",
        "HYB_ST_MA150_B3",
        "DONCHIAN_55_20",
        "DONCHIAN_100_50",
        "TSMOM_1_3_6_12",
        "TSMOM_1_3_6_12_B2",
        "TSMOM_3_6_12_B2",
        "TSMOM_VOL15",
        "VT_15",
        "TVT50_15",
        "MTF3_BUF3_OVERHEAT",
        "LEV15_MTF3_BUF3",
        "LEV15_TSMOM",
        "RSI14_CORE_70",
        "BIAS_MA120_8PCT_CORE",
        "REV_MA150_B3",
    ]
    perm_rows = []
    # Also prepare 25Y GC=F
    gcf_dates = pd.DatetimeIndex(gcf_df.index)
    gcf_irx = align_close_to(irx_df["Close"] / 100.0, gcf_dates).bfill()
    gcf_cp, gcf_cn = ov.calendar_cash_factors(gcf_dates, gcf_irx.to_numpy(float), CONFIG["costs"]["us_margin_spread"])
    gcf_px = pd.DataFrame({"gold": gcf_df["Close"].to_numpy(float)}, index=gcf_dates)
    gcf_start = int(gcf_dates.searchsorted(pd.Timestamp(CONFIG["windows"]["gcf_daily"][0])))
    gcf_strats = build_gold_single_strategies(gcf_df, ann_days=252)
    gcf_bh = summarize_nav_ext(
        lab.run_multi_asset_overlay(gcf_px, weight_to_signal(np.ones(len(gcf_dates)), gcf_start), gcf_start, 0.001, gcf_cp, gcf_cn),
        "gold",
    )

    for sname in perm_targets:
        p_gld = circular_shift_perm_single(
            prices,
            strats[sname][1],
            start_i,
            cost=0.001,
            cash_pos=cash_pos,
            cash_neg=cash_neg,
            n_trials=CONFIG["circular_shift_trials"],
        )
        # Also evaluate on 25Y GC=F
        rg = lab.run_multi_asset_overlay(
            gcf_px, weight_to_signal(gcf_strats[sname][1], gcf_start), gcf_start, 0.001, gcf_cp, gcf_cn
        )
        mg = summarize_nav_ext(rg, "gold")
        p_gcf = circular_shift_perm_single(
            gcf_px,
            gcf_strats[sname][1],
            gcf_start,
            cost=0.001,
            cash_pos=gcf_cp,
            cash_neg=gcf_cn,
            n_trials=CONFIG["circular_shift_trials"],
        )
        perm_rows.append(
            {
                "strategy": sname,
                "family": strats[sname][0],
                "gld_cagr": p_gld["obs_cagr"],
                "gld_sharpe": p_gld["obs_sharpe"],
                "gld_mdd": p_gld["obs_mdd"],
                "gld_null_sharpe": p_gld["null_median_sharpe"],
                "gld_p_sharpe": p_gld["p_sharpe"],
                "gld_p_cagr": p_gld["p_cagr"],
                "gld_p_calmar": p_gld["p_calmar"],
                "gcf25y_cagr": mg["cagr"],
                "gcf25y_sharpe": mg["sharpe"],
                "gcf25y_mdd": mg["max_dd"],
                "gcf25y_bh_sharpe": gcf_bh["sharpe"],
                "gcf25y_p_sharpe": p_gcf["p_sharpe"],
            }
        )

    # Real 2x Leveraged Gold ETF (UGL, 2009-12..2026-11) vs GLD & synthetic 1.5x
    u_dates = pd.DatetimeIndex(ugl_df.index)
    u_irx = align_close_to(irx_df["Close"] / 100.0, u_dates).bfill()
    u_cp, u_cn = ov.calendar_cash_factors(u_dates, u_irx.to_numpy(float), CONFIG["costs"]["us_margin_spread"])
    u_start = int(u_dates.searchsorted(pd.Timestamp(CONFIG["windows"]["ugl_2x"][0])))
    gld_on_u = align_close_to(gld_df["Close"], u_dates)
    u_px_ugl = pd.DataFrame({"ugl": ugl_df["Close"].to_numpy(float)}, index=u_dates)
    u_px_gld = pd.DataFrame({"gld": gld_on_u.to_numpy(float)}, index=u_dates)

    mtf3_gld_u = lab.daily_buffered_mtf3_equity_weight(gld_on_u, 150, 20, 210, 0.03).to_numpy(float)
    tsmom_gld_u = ind.tsmom_blend_weight(gld_on_u, (63, 126, 252), buffer=0.02).to_numpy(float)
    s2_gld_u = lab.weekly_stage2_state(gld_on_u, 30, 4).to_numpy(bool).astype(float)

    ugl_rows = []
    for label, px_df, col, w_arr in [
        ("GLD_BH_09_26", u_px_gld, "gld", np.ones(len(u_dates))),
        ("GLD_MTF3_BUF3_09_26", u_px_gld, "gld", mtf3_gld_u),
        ("GLD_LEV15_MTF3_SYNTH", u_px_gld, "gld", mtf3_gld_u * 1.5),
        ("UGL_2X_BH", u_px_ugl, "ugl", np.ones(len(u_dates))),
        ("UGL_2X_MTF3_BUF3_SIG_GLD", u_px_ugl, "ugl", mtf3_gld_u),
        ("UGL_2X_HALF_MTF3_EQ1X", u_px_ugl, "ugl", mtf3_gld_u * 0.5),
        ("UGL_2X_TSMOM_SIG_GLD", u_px_ugl, "ugl", tsmom_gld_u),
        ("UGL_2X_S2_FULL_SIG_GLD", u_px_ugl, "ugl", s2_gld_u),
    ]:
        r = lab.run_multi_asset_overlay(px_df, weight_to_signal(w_arr, u_start), u_start, 0.001, u_cp, u_cn)
        m = summarize_nav_ext(r, col)
        m26 = summarize_nav_ext(r, col, start="2026-01-29", end="2026-11-20")
        ugl_rows.append({"strategy": label, **m, "crash_2026_ret": m26["total_ret"]})

    return (
        pd.DataFrame(summary_rows),
        pd.DataFrame(perm_rows),
        pd.DataFrame(period_rows),
        pd.DataFrame(ugl_rows),
        nav_results,
    )


# --------------------------------------------------------------------------- Module 4: Parameter Plateau & Rolling Starts
def run_module4_robustness(
    gld_df: pd.DataFrame,
    irx_df: pd.DataFrame,
    nav_results: dict[str, lab.MultiEngineResult],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.DatetimeIndex(gld_df.index)
    irx = align_close_to(irx_df["Close"] / 100.0, dates).bfill()
    cash_pos, cash_neg = ov.calendar_cash_factors(dates, irx.to_numpy(float), CONFIG["costs"]["us_margin_spread"])
    prices = pd.DataFrame({"gold": gld_df["Close"].to_numpy(float)}, index=dates)
    start_i = int(dates.searchsorted(pd.Timestamp(CONFIG["windows"]["gld_main"][0])))
    close = gld_df["Close"]

    bh_m = summarize_nav_ext(nav_results["BH"], "gold")
    grid_rows = []

    # Grid A: MTF3 Buffered (fast, slow) x buffer
    for fast, slow, slp in [(100, 180, 15), (120, 200, 20), (150, 210, 20), (150, 250, 20), (180, 250, 25)]:
        for buf in (0.0, 0.01, 0.02, 0.03, 0.04, 0.05):
            w = lab.daily_buffered_mtf3_equity_weight(close, fast, slp, slow, buf).to_numpy(float)
            r = lab.run_multi_asset_overlay(prices, weight_to_signal(w, start_i), start_i, 0.001, cash_pos, cash_neg)
            m = summarize_nav_ext(r, "gold")
            grid_rows.append(
                {
                    "family": "MTF3_BUF_GRID",
                    "params": f"{fast}/{slow}_b{int(buf*100)}",
                    "cagr": m["cagr"],
                    "sharpe": m["sharpe"],
                    "max_dd": m["max_dd"],
                    "calmar": m["calmar"],
                    "trades_per_year": m["trades_per_year"],
                    "beats_bh_sharpe": bool(m["sharpe"] > bh_m["sharpe"]),
                    "beats_bh_calmar": bool(m["calmar"] > bh_m["calmar"]),
                }
            )

    # Grid B: Single SMA x buffer
    for win in (50, 100, 120, 150, 200, 250):
        for buf in (0.0, 0.02, 0.03, 0.05):
            w = lab.daily_buffered_ma_state(close, ma_days=win, buffer=buf).to_numpy(float)
            r = lab.run_multi_asset_overlay(prices, weight_to_signal(w, start_i), start_i, 0.001, cash_pos, cash_neg)
            m = summarize_nav_ext(r, "gold")
            grid_rows.append(
                {
                    "family": "SINGLE_SMA_GRID",
                    "params": f"SMA{win}_b{int(buf*100)}",
                    "cagr": m["cagr"],
                    "sharpe": m["sharpe"],
                    "max_dd": m["max_dd"],
                    "calmar": m["calmar"],
                    "trades_per_year": m["trades_per_year"],
                    "beats_bh_sharpe": bool(m["sharpe"] > bh_m["sharpe"]),
                    "beats_bh_calmar": bool(m["calmar"] > bh_m["calmar"]),
                }
            )

    # Grid C: TSMOM lookbacks x buffer
    for lb_name, lbs in [
        ("1_3_6", (21, 63, 126)),
        ("3_6_12", (63, 126, 252)),
        ("1_3_6_12", (21, 63, 126, 252)),
        ("2_6_12", (42, 126, 252)),
        ("3_9_12", (63, 189, 252)),
    ]:
        for buf in (0.0, 0.01, 0.02, 0.03):
            w = ind.tsmom_blend_weight(close, lookbacks=lbs, buffer=buf).to_numpy(float)
            r = lab.run_multi_asset_overlay(prices, weight_to_signal(w, start_i), start_i, 0.001, cash_pos, cash_neg)
            m = summarize_nav_ext(r, "gold")
            grid_rows.append(
                {
                    "family": "TSMOM_GRID",
                    "params": f"TS_{lb_name}_b{int(buf*100)}",
                    "cagr": m["cagr"],
                    "sharpe": m["sharpe"],
                    "max_dd": m["max_dd"],
                    "calmar": m["calmar"],
                    "trades_per_year": m["trades_per_year"],
                    "beats_bh_sharpe": bool(m["sharpe"] > bh_m["sharpe"]),
                    "beats_bh_calmar": bool(m["calmar"] > bh_m["calmar"]),
                }
            )

    # Rolling annual entry starts (2006..2023 -> 2026-11-20)
    start_strats = [
        "BH",
        "S2_HALF",
        "M10_SMA",
        "MTF3_BUF2",
        "MTF3_BUF3",
        "MTF3_100_200_B3",
        "SMA_150_B3",
        "DEMA_150_B3",
        "TSMOM_1_3_6_12_B2",
        "TSMOM_3_6_12_B2",
        "DONCHIAN_55_20",
        "HYB_ST_MA150_B3",
        "VT_15",
        "TVT50_15",
        "LEV15_MTF3_BUF3",
    ]
    roll_rows = []
    for yr in range(2006, 2024):
        s_dt = f"{yr}-01-01"
        bh_sub = summarize_nav_ext(nav_results["BH"], "gold", start=s_dt)
        for sn in start_strats:
            ms = summarize_nav_ext(nav_results[sn], "gold", start=s_dt)
            roll_rows.append(
                {
                    "start_year": yr,
                    "strategy": sn,
                    "cagr": ms["cagr"],
                    "sharpe": ms["sharpe"],
                    "max_dd": ms["max_dd"],
                    "calmar": ms["calmar"],
                    "beats_bh_sharpe": bool(ms["sharpe"] > bh_sub["sharpe"]),
                    "beats_bh_cagr": bool(ms["cagr"] > bh_sub["cagr"]),
                    "beats_bh_calmar": bool(ms["calmar"] > bh_sub["calmar"]),
                }
            )
    return pd.DataFrame(grid_rows), pd.DataFrame(roll_rows)


# --------------------------------------------------------------------------- Module 5: Macro Factors (TIP, TIP/IEF, DXY)
def run_module5_macro_factors(
    gld_df: pd.DataFrame,
    tip_df: pd.DataFrame,
    ief_df: pd.DataFrame,
    dxy_df: pd.DataFrame,
    irx_df: pd.DataFrame,
) -> pd.DataFrame:
    dates = pd.DatetimeIndex(gld_df.index)
    irx = align_close_to(irx_df["Close"] / 100.0, dates).bfill()
    cash_pos, cash_neg = ov.calendar_cash_factors(dates, irx.to_numpy(float), CONFIG["costs"]["us_margin_spread"])
    prices = pd.DataFrame({"gold": gld_df["Close"].to_numpy(float)}, index=dates)
    start_i = int(dates.searchsorted(pd.Timestamp(CONFIG["windows"]["gld_main"][0])))

    gld_c = gld_df["Close"]
    tip_c = align_close_to(tip_df["Close"], dates)
    ief_c = align_close_to(ief_df["Close"], dates)
    dxy_c = align_close_to(dxy_df["Close"], dates)
    be_ratio = tip_c / ief_c  # Rising TIP/IEF = rising breakeven inflation expectations

    # Strictly causal macro states
    # 1) TIP rising (real yield falling -> textbook gold bullish)
    tip_on = ind.hysteresis_ma_state(tip_c, tip_c.rolling(150).mean(), buffer=0.01).to_numpy(bool)
    tip_fast = (tip_c > tip_c.rolling(60).mean()).fillna(False).to_numpy(bool)
    # 2) DXY falling (weak USD -> textbook gold bullish)
    dxy_weak = (~ind.hysteresis_ma_state(dxy_c, dxy_c.rolling(150).mean(), buffer=0.015)).to_numpy(bool)
    dxy_weak_200 = (dxy_c < dxy_c.rolling(200).mean()).fillna(False).to_numpy(bool)
    # 3) Inflation expectations rising (TIP/IEF above 150d MA)
    be_on = (be_ratio > be_ratio.rolling(150).mean()).fillna(False).to_numpy(bool)

    # Pure price trend benchmark
    mtf3_b3 = lab.daily_buffered_mtf3_equity_weight(gld_c, 150, 20, 210, 0.03).to_numpy(float)

    macro_strats = {
        "BH_GLD": np.ones(len(dates)),
        "PRICE_ONLY_MTF3_BUF3": mtf3_b3,
        "MACRO_TIP_REALYIELD_150": tip_on.astype(float),
        "MACRO_TIP_REALYIELD_60": tip_fast.astype(float),
        "MACRO_DXY_WEAK_150": dxy_weak.astype(float),
        "MACRO_DXY_WEAK_200": dxy_weak_200.astype(float),
        "MACRO_BREAKEVEN_TIP_IEF": be_on.astype(float),
        "MACRO_DUAL_TIP_DXY_3TIER": np.where(tip_on & dxy_weak, 1.0, np.where(tip_on | dxy_weak, 0.5, 0.0)),
        "HYBRID_PRICE_AND_TIP": np.where(mtf3_b3 > 0, np.where(tip_on, mtf3_b3, mtf3_b3 * 0.5), 0.0),
        "HYBRID_PRICE_AND_DXY": np.where(mtf3_b3 > 0, np.where(dxy_weak, mtf3_b3, mtf3_b3 * 0.5), 0.0),
        "HYBRID_VOTE_PRICE_TIP_DXY": (0.5 * mtf3_b3 + 0.25 * tip_on.astype(float) + 0.25 * dxy_weak.astype(float)),
    }

    rows = []
    for name, w in macro_strats.items():
        r = lab.run_multi_asset_overlay(prices, weight_to_signal(w, start_i), start_i, 0.001, cash_pos, cash_neg)
        m_full = summarize_nav_ext(r, "gold")
        m_pre22 = summarize_nav_ext(r, "gold", start="2005-12-01", end="2021-12-31")
        m_post22 = summarize_nav_ext(r, "gold", start="2022-01-03", end="2026-11-20")
        m_22_25 = summarize_nav_ext(r, "gold", start="2022-01-03", end="2026-01-29")
        perm = (
            circular_shift_perm_single(prices, w, start_i, cost=0.001, cash_pos=cash_pos, cash_neg=cash_neg, n_trials=200)
            if name != "BH_GLD"
            else {"p_sharpe": np.nan}
        )
        rows.append(
            {
                "strategy": name,
                "full_cagr": m_full["cagr"],
                "full_sharpe": m_full["sharpe"],
                "full_mdd": m_full["max_dd"],
                "full_calmar": m_full["calmar"],
                "avg_exposure": m_full["avg_exposure"],
                "trades_per_year": m_full["trades_per_year"],
                "perm_p_sharpe": perm["p_sharpe"],
                "pre2022_cagr": m_pre22["cagr"],
                "pre2022_sharpe": m_pre22["sharpe"],
                "pre2022_mdd": m_pre22["max_dd"],
                "post2022_cagr": m_post22["cagr"],
                "post2022_sharpe": m_post22["sharpe"],
                "post2022_mdd": m_post22["max_dd"],
                "ratehike_bull_22_26pk_cagr": m_22_25["cagr"],
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- Module 6: Precious Metals Rotation (Silver & Miners)
def run_module6_precious_metals(
    gld_df: pd.DataFrame,
    slv_df: pd.DataFrame,
    gdx_df: pd.DataFrame,
    gcf_df: pd.DataFrame,
    sif_df: pd.DataFrame,
    irx_df: pd.DataFrame,
) -> pd.DataFrame:
    # Common real ETF window: 2007-06-01..2026-11-20 (19.5Y)
    common = gld_df.index.intersection(slv_df.index).intersection(gdx_df.index)
    dates = pd.DatetimeIndex(common.sort_values())
    irx = align_close_to(irx_df["Close"] / 100.0, dates).bfill()
    cash_pos, cash_neg = ov.calendar_cash_factors(dates, irx.to_numpy(float), CONFIG["costs"]["us_margin_spread"])

    gld = gld_df["Close"].reindex(dates)
    slv = slv_df["Close"].reindex(dates)
    gdx = gdx_df["Close"].reindex(dates)
    px = pd.DataFrame({"gld": gld.to_numpy(float), "slv": slv.to_numpy(float), "gdx": gdx.to_numpy(float)}, index=dates)
    start_i = int(dates.searchsorted(pd.Timestamp(CONFIG["windows"]["metals_etf"][0])))
    n = len(dates)

    # True Gold/Silver ounce price ratio using GC=F / SI=F aligned to dates (no scaling distortion)
    gcf_al = align_close_to(gcf_df["Close"], dates)
    sif_al = align_close_to(sif_df["Close"], dates)
    gsr = (gcf_al / sif_al).to_numpy(float)
    gsr_s = pd.Series(gsr, index=dates)
    gsr_z = ((gsr_s - gsr_s.rolling(1260, min_periods=252).mean()) / gsr_s.rolling(1260, min_periods=252).std(ddof=1)).to_numpy(float)

    rows = []

    def eval_multi(name: str, group: str, w_mat: Optional[np.ndarray] = None, sig_fn=None):
        sig = sig_fn if sig_fn is not None else multi_weight_to_signal(w_mat, start_i, threshold=0.02)
        r10 = lab.run_multi_asset_overlay(px, sig, start_i, 0.001, cash_pos, cash_neg)
        r30 = lab.run_multi_asset_overlay(px, sig, start_i, 0.003, cash_pos, cash_neg)
        m = summarize_nav_ext(r10, "gld")
        m30 = summarize_nav_ext(r30, "gld")
        m_pre = summarize_nav_ext(r10, "gld", start="2007-06-01", end="2019-05-31")
        m_post = summarize_nav_ext(r10, "gld", start="2019-06-03", end="2026-11-20")
        m26 = summarize_nav_ext(r10, "gld", start="2026-01-29", end="2026-11-20")
        rows.append(
            {
                "strategy": name,
                "group": group,
                "cagr": m["cagr"],
                "vol": m["vol"],
                "sharpe": m["sharpe"],
                "max_dd": m["max_dd"],
                "calmar": m["calmar"],
                "max_uw_years": m["max_uw_years"],
                "trades_per_year": m["trades_per_year"],
                "annual_turnover": m["annual_turnover"],
                "sharpe_30bp": m30["sharpe"],
                "cagr_07_19": m_pre["cagr"],
                "sharpe_07_19": m_pre["sharpe"],
                "cagr_19_26": m_post["cagr"],
                "sharpe_19_26": m_post["sharpe"],
                "crash_2026_ret": m26["total_ret"],
                "avg_w_gld": float(r10.weights["gld"].iloc[1:].mean()),
                "avg_w_slv": float(r10.weights["slv"].iloc[1:].mean()),
                "avg_w_gdx": float(r10.weights["gdx"].iloc[1:].mean()),
            }
        )

    # Standalone baselines
    eval_multi("BH_GLD", "Baseline", sig_fn=lab.fixed_weight_signal([1.0, 0.0, 0.0], dates, start_i, freq="NONE"))
    eval_multi("BH_SLV", "Baseline", sig_fn=lab.fixed_weight_signal([0.0, 1.0, 0.0], dates, start_i, freq="NONE"))
    eval_multi("BH_GDX", "Baseline", sig_fn=lab.fixed_weight_signal([0.0, 0.0, 1.0], dates, start_i, freq="NONE"))

    # Gold/Silver Ratio (GSR) Mean-Reversion Myths
    # 1) Static 80/60 switch: >80 hold 100% SLV, <60 hold 100% GLD, hold state between
    w_gsr_stat = np.zeros((n, 3))
    in_slv = False
    for i in range(n):
        if gsr[i] > 80.0:
            in_slv = True
        elif gsr[i] < 60.0:
            in_slv = False
        w_gsr_stat[i] = [0.0, 1.0, 0.0] if in_slv else [1.0, 0.0, 0.0]
    eval_multi("GSR_STATIC_80_60", "GSR_MeanRev", w_gsr_stat)

    # 2) Strictly causal rolling 5Y Z-score GSR (> +1.0 -> SLV, < -1.0 -> GLD)
    w_gsr_z = np.zeros((n, 3))
    in_slv = False
    for i in range(n):
        if np.isfinite(gsr_z[i]):
            if gsr_z[i] > 1.0:
                in_slv = True
            elif gsr_z[i] < -1.0:
                in_slv = False
        w_gsr_z[i] = [0.0, 1.0, 0.0] if in_slv else [1.0, 0.0, 0.0]
    eval_multi("GSR_ROLL5Y_Z1", "GSR_MeanRev", w_gsr_z)

    # 3) Core 70% GLD + 30% GSR tilt (30% switches to SLV when GSR Z > +1, else GLD)
    w_gsr_core = np.zeros((n, 3))
    in_slv = False
    for i in range(n):
        if np.isfinite(gsr_z[i]):
            if gsr_z[i] > 1.0:
                in_slv = True
            elif gsr_z[i] < 0.0:
                in_slv = False
        w_gsr_core[i] = [0.7, 0.3, 0.0] if in_slv else [1.0, 0.0, 0.0]
    eval_multi("GSR_CORE70_TILT30", "GSR_MeanRev", w_gsr_core)

    # Gold/Silver Static & Inverse-Vol & Dual Momentum Rotation (monthly rebalance)
    eval_multi("GLD80_SLV20_Q", "Gold_Silver_Mix", sig_fn=lab.fixed_weight_signal([0.8, 0.2, 0.0], dates, start_i, freq="Q"))
    eval_multi("GLD80_GDX20_Q", "Gold_Miner_Mix", sig_fn=lab.fixed_weight_signal([0.8, 0.0, 0.2], dates, start_i, freq="Q"))

    # Monthly Dual Momentum: GLD vs SLV (6M and 12M)
    m_mask = ov.month_end_mask(dates)
    for lb_name, lb in [("6M", 126), ("12M", 252)]:
        r_g = (gld / gld.shift(lb) - 1.0).to_numpy(float)
        r_s = (slv / slv.shift(lb) - 1.0).to_numpy(float)
        r_m = (gdx / gdx.shift(lb) - 1.0).to_numpy(float)
        # Relative momentum GLD vs SLV (always invested)
        w_rel = np.zeros((n, 3))
        w_dual = np.zeros((n, 3))
        w_3way = np.zeros((n, 3))
        cur_rel = np.array([1.0, 0.0, 0.0])
        cur_dual = np.array([0.0, 0.0, 0.0])
        cur_3way = np.array([0.0, 0.0, 0.0])
        for i in range(n):
            if i == start_i or m_mask[i]:
                if np.isfinite(r_g[i]) and np.isfinite(r_s[i]):
                    cur_rel = np.array([1.0, 0.0, 0.0]) if r_g[i] >= r_s[i] else np.array([0.0, 1.0, 0.0])
                    best = max(r_g[i], r_s[i])
                    if best <= 0.0:
                        cur_dual = np.array([0.0, 0.0, 0.0])
                    else:
                        cur_dual = np.array([1.0, 0.0, 0.0]) if r_g[i] >= r_s[i] else np.array([0.0, 1.0, 0.0])
                if np.isfinite(r_g[i]) and np.isfinite(r_s[i]) and np.isfinite(r_m[i]):
                    vals = [r_g[i], r_s[i], r_m[i]]
                    if max(vals) <= 0.0:
                        cur_3way = np.array([0.0, 0.0, 0.0])
                    else:
                        best_j = int(np.argmax(vals))
                        cur_3way = np.zeros(3)
                        cur_3way[best_j] = 1.0
            w_rel[i] = cur_rel
            w_dual[i] = cur_dual
            w_3way[i] = cur_3way
        eval_multi(f"GS_REL_MOM_{lb_name}", "Metals_Momentum", w_rel)
        eval_multi(f"GS_DUAL_MOM_{lb_name}", "Metals_Momentum", w_dual)
        eval_multi(f"GLD_SLV_GDX_DUAL_{lb_name}", "Metals_Momentum", w_3way)

    # Pure GLD / SLV / GDX with MTF3_BUF3 individually for direct comparison
    for idx_j, nm, ser in [(0, "GLD_MTF3_BUF3_07_26", gld), (1, "SLV_MTF3_BUF3_07_26", slv), (2, "GDX_MTF3_BUF3_07_26", gdx)]:
        w_s = lab.daily_buffered_mtf3_equity_weight(ser, 150, 20, 210, 0.03).to_numpy(float)
        mat = np.zeros((n, 3))
        mat[:, idx_j] = w_s
        eval_multi(nm, "Single_Trend_Ref", mat)

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- Module 7: Cross-Asset Defensive Shields & BTC Satellite
def run_module7_cross_asset_shields(
    gld_df: pd.DataFrame,
    ief_df: pd.DataFrame,
    tip_df: pd.DataFrame,
    tlt_df: pd.DataFrame,
    spy_df: pd.DataFrame,
    btc_df: pd.DataFrame,
    irx_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, lab.MultiEngineResult]]:
    dates = pd.DatetimeIndex(gld_df.index)
    irx = align_close_to(irx_df["Close"] / 100.0, dates).bfill()
    cash_pos, cash_neg = ov.calendar_cash_factors(dates, irx.to_numpy(float), CONFIG["costs"]["us_margin_spread"])
    start_i = int(dates.searchsorted(pd.Timestamp(CONFIG["windows"]["gld_main"][0])))

    gld = gld_df["Close"]
    ief = align_close_to(ief_df["Close"], dates)
    tip = align_close_to(tip_df["Close"], dates)
    tlt = align_close_to(tlt_df["Close"], dates)
    spy = align_close_to(spy_df["Close"], dates)
    px = pd.DataFrame(
        {
            "gld": gld.to_numpy(float),
            "ief": ief.to_numpy(float),
            "tip": tip.to_numpy(float),
            "tlt": tlt.to_numpy(float),
            "spy": spy.to_numpy(float),
        },
        index=dates,
    )
    n = len(dates)

    w_gld_mtf3 = lab.daily_buffered_mtf3_equity_weight(gld, 150, 20, 210, 0.03).to_numpy(float)
    w_gld_tsmom = ind.tsmom_blend_weight(gld, (63, 126, 252), buffer=0.02).to_numpy(float)
    w_spy_mtf3 = lab.daily_buffered_mtf3_equity_weight(spy, 150, 20, 210, 0.03).to_numpy(float)
    ief_on = lab.daily_buffered_ma_state(ief, ma_days=150, buffer=0.02).to_numpy(bool)

    rows = []
    shield_res: dict[str, lab.MultiEngineResult] = {}

    def eval_shield(name: str, group: str, w_mat: Optional[np.ndarray] = None, sig_fn=None):
        sig = sig_fn if sig_fn is not None else multi_weight_to_signal(w_mat, start_i, threshold=0.02)
        r10 = lab.run_multi_asset_overlay(px, sig, start_i, 0.001, cash_pos, cash_neg)
        r30 = lab.run_multi_asset_overlay(px, sig, start_i, 0.003, cash_pos, cash_neg)
        shield_res[name] = r10
        m = summarize_nav_ext(r10, "gld")
        m30 = summarize_nav_ext(r30, "gld")
        mbear = summarize_nav_ext(r10, "gld", start="2011-09-06", end="2019-05-31")
        mnew = summarize_nav_ext(r10, "gld", start="2019-06-03", end="2026-11-20")
        m26 = summarize_nav_ext(r10, "gld", start="2026-01-29", end="2026-11-20")
        rows.append(
            {
                "strategy": name,
                "group": group,
                "window": "2005-12..2026-11",
                "cagr": m["cagr"],
                "vol": m["vol"],
                "sharpe": m["sharpe"],
                "max_dd": m["max_dd"],
                "calmar": m["calmar"],
                "max_uw_years": m["max_uw_years"],
                "loss_5y_prob": m["loss_5y_prob"],
                "trades_per_year": m["trades_per_year"],
                "annual_turnover": m["annual_turnover"],
                "sharpe_30bp": m30["sharpe"],
                "bear_11_19_cagr": mbear["cagr"],
                "bear_11_19_sharpe": mbear["sharpe"],
                "bear_11_19_mdd": mbear["max_dd"],
                "new_19_26_cagr": mnew["cagr"],
                "new_19_26_sharpe": mnew["sharpe"],
                "crash_2026_ret": m26["total_ret"],
                "avg_w_gld": float(r10.weights["gld"].iloc[1:].mean()),
                "avg_w_cash": float(r10.weights["cash"].iloc[1:].mean()),
            }
        )

    # Baselines
    eval_shield("BH_GLD", "Baseline", sig_fn=lab.fixed_weight_signal([1, 0, 0, 0, 0], dates, start_i, freq="NONE"))
    eval_shield("BH_SPY_Ref", "Baseline", sig_fn=lab.fixed_weight_signal([0, 0, 0, 0, 1], dates, start_i, freq="NONE"))

    # Gold Trend + Defensive Parking Assets
    for label, w_core in [("MTF3_BUF3", w_gld_mtf3), ("TSMOM_3_6_12", w_gld_tsmom)]:
        # 1) Pure T-bill cash
        m_cash = np.zeros((n, 5))
        m_cash[:, 0] = w_core
        eval_shield(f"GLD_{label}_CASH", "Trend_Plus_Shield", m_cash)
        # 2) Mid-term Treasury IEF
        m_ief = np.zeros((n, 5))
        m_ief[:, 0] = w_core
        m_ief[:, 1] = 1.0 - w_core
        eval_shield(f"GLD_{label}_IEF", "Trend_Plus_Shield", m_ief)
        # 3) Conditional IEF (only park in IEF if IEF > 150d MA, else T-bill cash -> protects against 2022 bond crash!)
        m_cief = np.zeros((n, 5))
        m_cief[:, 0] = w_core
        m_cief[:, 1] = np.where(ief_on, 1.0 - w_core, 0.0)
        eval_shield(f"GLD_{label}_COND_IEF", "Trend_Plus_Shield", m_cief)
        # 4) TIPS (inflation-protected bond)
        m_tip = np.zeros((n, 5))
        m_tip[:, 0] = w_core
        m_tip[:, 2] = 1.0 - w_core
        eval_shield(f"GLD_{label}_TIP", "Trend_Plus_Shield", m_tip)
        # 5) Long-term Treasury TLT
        m_tlt = np.zeros((n, 5))
        m_tlt[:, 0] = w_core
        m_tlt[:, 3] = 1.0 - w_core
        eval_shield(f"GLD_{label}_TLT", "Trend_Plus_Shield", m_tlt)
        # 6) Trend-gated SPY (when gold is OFF, put spare weight into SPY ONLY if SPY trend is ON; else cash!)
        m_spy = np.zeros((n, 5))
        m_spy[:, 0] = w_core
        m_spy[:, 4] = (1.0 - w_core) * w_spy_mtf3
        eval_shield(f"GLD_{label}_SPY_TREND", "Trend_Plus_Equity", m_spy)

    # Static Gold-Centric Diversified Portfolios (low turnover)
    eval_shield("GLD70_IEF30_Q", "Static_Gold_Mix", sig_fn=lab.fixed_weight_signal([0.70, 0.30, 0, 0, 0], dates, start_i, freq="Q"))
    eval_shield("GLD70_TIP30_Q", "Static_Gold_Mix", sig_fn=lab.fixed_weight_signal([0.70, 0, 0.30, 0, 0], dates, start_i, freq="Q"))
    eval_shield("GLD60_SPY40_Q", "Static_Gold_Mix", sig_fn=lab.fixed_weight_signal([0.60, 0, 0, 0, 0.40], dates, start_i, freq="Q"))
    eval_shield("GLD50_SPY50_Q", "Static_Gold_Mix", sig_fn=lab.fixed_weight_signal([0.50, 0, 0, 0, 0.50], dates, start_i, freq="Q"))
    eval_shield("GLD50_IEF25_SPY25_Q", "Static_Gold_Mix", sig_fn=lab.fixed_weight_signal([0.50, 0.25, 0, 0, 0.25], dates, start_i, freq="Q"))

    # Inverse-Vol Gold + IEF (monthly) & Gold + SPY (monthly)
    m_mask = ov.month_end_mask(dates)
    vol_g = gld.pct_change().rolling(60).std(ddof=1).to_numpy(float)
    vol_i = ief.pct_change().rolling(60).std(ddof=1).to_numpy(float)
    vol_s = spy.pct_change().rolling(60).std(ddof=1).to_numpy(float)
    w_iv_gi = np.zeros((n, 5))
    w_iv_gs = np.zeros((n, 5))
    cur_gi = np.array([0.5, 0.5, 0, 0, 0])
    cur_gs = np.array([0.5, 0, 0, 0, 0.5])
    for i in range(n):
        if i == start_i or m_mask[i]:
            if np.isfinite(vol_g[i]) and np.isfinite(vol_i[i]) and vol_g[i] > 0 and vol_i[i] > 0:
                ig, ii = 1.0 / vol_g[i], 1.0 / vol_i[i]
                cur_gi = np.array([ig / (ig + ii), ii / (ig + ii), 0, 0, 0])
            if np.isfinite(vol_g[i]) and np.isfinite(vol_s[i]) and vol_g[i] > 0 and vol_s[i] > 0:
                ig, is_ = 1.0 / vol_g[i], 1.0 / vol_s[i]
                cur_gs = np.array([ig / (ig + is_), 0, 0, 0, is_ / (ig + is_)])
        w_iv_gi[i] = cur_gi
        w_iv_gs[i] = cur_gs
    eval_shield("GLD_IEF_INVVOL_M", "Static_Gold_Mix", w_iv_gi)
    eval_shield("GLD_SPY_INVVOL_M", "Static_Gold_Mix", w_iv_gs)

    # Physical Gold + Digital Gold (BTC) satellite check (2015-08..2026-11)
    b_dates = pd.DatetimeIndex(gld_df.index[gld_df.index >= pd.Timestamp("2014-09-17")])
    b_irx = align_close_to(irx_df["Close"] / 100.0, b_dates).bfill()
    b_cp, b_cn = ov.calendar_cash_factors(b_dates, b_irx.to_numpy(float), CONFIG["costs"]["us_margin_spread"])
    b_start = int(b_dates.searchsorted(pd.Timestamp(CONFIG["windows"]["btc_gold"][0])))
    gld_b = gld_df["Close"].reindex(b_dates)
    btc_c = align_close_to(btc_df["Close"], b_dates)
    btc_h = align_close_to(btc_df["High"], b_dates)
    btc_l = align_close_to(btc_df["Low"], b_dates)
    btc_st = ind.supertrend_direction(btc_h, btc_l, btc_c, atr_window=10, multiplier=3.0).to_numpy(bool)
    gld_b_mtf3 = lab.daily_buffered_mtf3_equity_weight(gld_b, 150, 20, 210, 0.03).to_numpy(float)
    b_px = pd.DataFrame({"gld": gld_b.to_numpy(float), "btc": btc_c.to_numpy(float)}, index=b_dates)

    for bname, bsig in [
        ("GLD_BH_15_26", lab.fixed_weight_signal([1.0, 0.0], b_dates, b_start, freq="NONE")),
        ("GLD_MTF3_BUF3_15_26", multi_weight_to_signal(np.column_stack([gld_b_mtf3, np.zeros(len(b_dates))]), b_start)),
        ("GLD90_BTC10_Q_15_26", lab.fixed_weight_signal([0.90, 0.10], b_dates, b_start, freq="Q")),
        (
            "GLD90_BTC10_ST_15_26",
            multi_weight_to_signal(np.column_stack([np.full(len(b_dates), 0.90), np.where(btc_st, 0.10, 0.0)]), b_start),
        ),
        (
            "GLD_MTF3_90_BTC10_ST_15_26",
            multi_weight_to_signal(np.column_stack([gld_b_mtf3 * 0.90, np.where(btc_st, 0.10, 0.0)]), b_start),
        ),
    ]:
        r = lab.run_multi_asset_overlay(b_px, bsig, b_start, 0.002, b_cp, b_cn)  # 20bp blended cost
        m = summarize_nav_ext(r, "gld")
        m26 = summarize_nav_ext(r, "gld", start="2026-01-29", end="2026-11-20")
        rows.append(
            {
                "strategy": bname,
                "group": "Gold_Plus_DigitalGold",
                "window": "2015-08..2026-11",
                "cagr": m["cagr"],
                "vol": m["vol"],
                "sharpe": m["sharpe"],
                "max_dd": m["max_dd"],
                "calmar": m["calmar"],
                "max_uw_years": m["max_uw_years"],
                "loss_5y_prob": m["loss_5y_prob"],
                "trades_per_year": m["trades_per_year"],
                "annual_turnover": m["annual_turnover"],
                "sharpe_30bp": np.nan,
                "bear_11_19_cagr": np.nan,
                "bear_11_19_sharpe": np.nan,
                "bear_11_19_mdd": np.nan,
                "new_19_26_cagr": summarize_nav_ext(r, "gld", start="2019-06-03", end="2026-11-20")["cagr"],
                "new_19_26_sharpe": summarize_nav_ext(r, "gld", start="2019-06-03", end="2026-11-20")["sharpe"],
                "crash_2026_ret": m26["total_ret"],
                "avg_w_gld": float(r.weights["gld"].iloc[1:].mean()),
                "avg_w_cash": float(r.weights["cash"].iloc[1:].mean()),
            }
        )

    return pd.DataFrame(rows), shield_res


# --------------------------------------------------------------------------- Module 8: Rolling DCA & Budget-Neutral Smart DCA
def run_budget_neutral_smart_dca(
    close: pd.Series,
    cash_pos: np.ndarray,
    start_date: str,
    rule: str,
    cost: float = 0.001,
) -> dict[str, Any]:
    """Strictly budget-neutral monthly DCA (1 unit/month salary).

    Plain: invest 1.0 every month.
    Smart (BIAS_120 or RSI14): invest 0.5 when overbought (save 0.5 into cash pool earning cash_pos),
    invest up to 1.5 when oversold (drawing from saved cash pool only; never borrows!).
    """
    dates = pd.DatetimeIndex(close.index)
    start_i = int(dates.searchsorted(pd.Timestamp(start_date)))
    vals = close.to_numpy(float)
    sma120 = close.rolling(120).mean().to_numpy(float)
    rsi14 = ind.rsi_wilder(close, 14).to_numpy(float)

    sub_dates = dates[start_i:]
    ym = sub_dates.year * 12 + sub_dates.month
    first_rel = set(np.flatnonzero(np.r_[True, ym[1:] != ym[:-1]]).tolist())

    shares = 0.0
    reserve_cash = 0.0
    cum_prin = 0.0
    contrib_days = []
    float_rets = []
    for k, i in enumerate(range(start_i, len(dates))):
        if k > 0:
            reserve_cash *= cash_pos[i]
        if k in first_rel:
            cum_prin += 1.0
            contrib_days.append(dates[i])
            reserve_cash += 1.0  # monthly paycheck arrives
            # Signal uses close[i-1] (strictly prior close before day-i execution)
            prev_i = max(i - 1, 0)
            if rule == "PLAIN":
                want = 1.0
            elif rule == "BIAS120_SMART":
                b = (vals[prev_i] / sma120[prev_i] - 1.0) if np.isfinite(sma120[prev_i]) else 0.0
                want = 1.5 if b < -0.05 else (0.5 if b > 0.08 else 1.0)
            elif rule == "RSI14_SMART":
                rv = rsi14[prev_i] if np.isfinite(rsi14[prev_i]) else 50.0
                want = 1.5 if rv < 35.0 else (0.5 if rv > 68.0 else 1.0)
            else:
                raise ValueError(rule)
            spend = min(want, reserve_cash)
            reserve_cash -= spend
            shares += (spend * (1.0 - cost)) / vals[i]
        total_v = shares * vals[i] + reserve_cash
        if cum_prin > 0:
            float_rets.append(total_v / cum_prin - 1.0)

    end_val = shares * vals[-1] + reserve_cash
    day_off = (dates[-1] - pd.DatetimeIndex(contrib_days)).days.to_numpy(float)
    x = fast_xirr(day_off, end_val)
    return {
        "rule": rule,
        "n_months": len(contrib_days),
        "xirr": float(x),
        "max_float_loss": float(np.min(float_rets)),
        "terminal_per_unit": float(end_val / len(contrib_days)),
        "ending_cash_share": float(reserve_cash / end_val) if end_val > 0 else 0.0,
    }


def run_module8_dca(
    gld_df: pd.DataFrame,
    irx_df: pd.DataFrame,
    nav_results: dict[str, lab.MultiEngineResult],
    shield_res: dict[str, lab.MultiEngineResult],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    # 1) Rolling 10Y (120m) and 5Y (60m) DCA on key GLD strategies
    cand_navs = {
        "BH_GLD": nav_results["BH"].nav,
        "S2_HALF": nav_results["S2_HALF"].nav,
        "M10_SMA": nav_results["M10_SMA"].nav,
        "MTF3_BUF2": nav_results["MTF3_BUF2"].nav,
        "MTF3_BUF3": nav_results["MTF3_BUF3"].nav,
        "MTF3_100_200_B3": nav_results["MTF3_100_200_B3"].nav,
        "SMA_150_B3": nav_results["SMA_150_B3"].nav,
        "DEMA_150_B3": nav_results["DEMA_150_B3"].nav,
        "TSMOM_1_3_6_12_B2": nav_results["TSMOM_1_3_6_12_B2"].nav,
        "TSMOM_3_6_12_B2": nav_results["TSMOM_3_6_12_B2"].nav,
        "HYB_ST_MA150_B3": nav_results["HYB_ST_MA150_B3"].nav,
        "VT_15": nav_results["VT_15"].nav,
        "LEV15_MTF3_BUF3": nav_results["LEV15_MTF3_BUF3"].nav,
        "GLD_MTF3_BUF3_COND_IEF": shield_res["GLD_MTF3_BUF3_COND_IEF"].nav,
        "GLD_MTF3_BUF3_SPY_TREND": shield_res["GLD_MTF3_BUF3_SPY_TREND"].nav,
        "GLD_TSMOM_3_6_12_SPY_TREND": shield_res["GLD_TSMOM_3_6_12_SPY_TREND"].nav,
        "GLD70_IEF30_Q": shield_res["GLD70_IEF30_Q"].nav,
        "GLD50_SPY50_Q": shield_res["GLD50_SPY50_Q"].nav,
    }
    dca_rows = []
    for win_m in (60, 120):
        bench_w = fast_dca_rolling(cand_navs["BH_GLD"], win_m, 0.001)
        for name, nav in cand_navs.items():
            sw = fast_dca_rolling(nav, win_m, 0.001)
            merged = sw.merge(bench_w, on=["start", "end"], suffixes=("_s", "_b"))
            dca_rows.append(
                {
                    "window_months": win_m,
                    "strategy": name,
                    "n_windows": int(len(merged)),
                    "median_xirr": float(merged["xirr_s"].median()),
                    "worst_xirr": float(merged["xirr_s"].min()),
                    "loss_window_share": float((merged["xirr_s"] < 0).mean()),
                    "median_float_loss": float(merged["max_float_loss_s"].median()),
                    "worst_float_loss": float(merged["max_float_loss_s"].min()),
                    "median_dca_ratio": float(merged["dca_ratio_s"].median()),
                    "ratio_beat_bh": float((merged["dca_ratio_s"] > merged["dca_ratio_b"]).mean()),
                    "xirr_beat_bh": float((merged["xirr_s"] > merged["xirr_b"]).mean()),
                }
            )

    # 2) Strictly budget-neutral smart DCA vs plain DCA (full 21Y GLD + 2011-2020 bear-start DCA)
    dates = pd.DatetimeIndex(gld_df.index)
    irx = align_close_to(irx_df["Close"] / 100.0, dates).bfill()
    cash_pos, _ = ov.calendar_cash_factors(dates, irx.to_numpy(float), 0.0)
    smart_rows = []
    for start_tag, s_dt in [("full_21y_2005", "2005-12-01"), ("bear_start_2011", "2011-09-06"), ("recent_2019", "2019-06-03")]:
        for rule in ("PLAIN", "BIAS120_SMART", "RSI14_SMART"):
            d = run_budget_neutral_smart_dca(gld_df["Close"], cash_pos, s_dt, rule, cost=0.001)
            smart_rows.append({"start_cohort": start_tag, **d})
    return pd.DataFrame(dca_rows), pd.DataFrame(smart_rows)


# --------------------------------------------------------------------------- Module 9: Domestic 518880 & Crypto PAXG/XAUT
def run_module9_domestic_and_crypto(
    cn_gold_df: pd.DataFrame,
    cn_bond5_df: pd.DataFrame,
    cn_bond10_df: pd.DataFrame,
    cny_df: pd.DataFrame,
    gld_df: pd.DataFrame,
    iau_df: pd.DataFrame,
    gcf_df: pd.DataFrame,
    paxg_df: pd.DataFrame,
    xaut_df: pd.DataFrame,
    irx_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    # --- Part A: Domestic 518880 + 511010 (2014-08-01..2026-11-20) ---
    common = cn_gold_df.index.intersection(cn_bond5_df.index)
    dates = pd.DatetimeIndex(common.sort_values())
    g_cn = cn_gold_df["Close"].reindex(dates)
    h_cn = cn_gold_df["High"].reindex(dates)
    l_cn = cn_gold_df["Low"].reindex(dates)
    b5 = cn_bond5_df["Close"].reindex(dates)
    start_i = int(dates.searchsorted(pd.Timestamp(CONFIG["windows"]["domestic_518880"][0])))
    cash_pos, cash_neg = ov.calendar_cash_factors(dates, np.full(len(dates), CONFIG["costs"]["cn_cash_annual"]), 0.0)
    px = pd.DataFrame({"gold_cn": g_cn.to_numpy(float), "bond_cn": b5.to_numpy(float)}, index=dates)
    n = len(dates)

    # FX decomposition over 2014-08-01..2026-11-20
    gld_on_cn, min_lag_us = lab.map_us_series_to_cn_strict(gld_df["Close"], dates)
    cny_on_cn = align_close_to(cny_df["Close"], dates).bfill()
    g_eval = g_cn.iloc[start_i:]
    gld_eval = gld_on_cn.iloc[start_i:]
    cny_eval = cny_on_cn.iloc[start_i:]
    synth_rmb_gold = gld_eval * cny_eval
    yrs_cn = (g_eval.index[-1] - g_eval.index[0]).days / 365.25
    fx_decomp = {
        "window": f"{g_eval.index[0].date()}..{g_eval.index[-1].date()}",
        "min_us_to_cn_lag_days": int(min_lag_us),
        "cn_518880_cagr": float((g_eval.iloc[-1] / g_eval.iloc[0]) ** (1 / yrs_cn) - 1),
        "cn_518880_vol": float(g_eval.pct_change().dropna().std(ddof=1) * np.sqrt(252)),
        "cn_518880_mdd": float((g_eval / g_eval.cummax() - 1).min()),
        "us_gld_usd_cagr": float((gld_eval.iloc[-1] / gld_eval.iloc[0]) ** (1 / yrs_cn) - 1),
        "us_gld_usd_vol": float(gld_eval.pct_change().dropna().std(ddof=1) * np.sqrt(252)),
        "us_gld_usd_mdd": float((gld_eval / gld_eval.cummax() - 1).min()),
        "usdcny_cagr": float((cny_eval.iloc[-1] / cny_eval.iloc[0]) ** (1 / yrs_cn) - 1),
        "synth_gld_x_usdcny_cagr": float((synth_rmb_gold.iloc[-1] / synth_rmb_gold.iloc[0]) ** (1 / yrs_cn) - 1),
        "gld_vs_usdcny_daily_corr": float(gld_eval.pct_change().corr(cny_eval.pct_change())),
        "gld_vs_usdcny_monthly_corr": float(
            gld_eval.resample("ME").last().pct_change().corr(cny_eval.resample("ME").last().pct_change())
        ),
    }

    # Build self-signal and strict lagged US-signal weights for 518880
    w_s2_half = np.where(lab.weekly_stage2_state(g_cn, 30, 4).to_numpy(bool), 1.0, 0.5)
    w_m10 = lab.monthly_ma_state(g_cn, 10).to_numpy(float)
    w_mtf3_b2 = lab.daily_buffered_mtf3_equity_weight(g_cn, 150, 20, 210, 0.02).to_numpy(float)
    w_mtf3_b3 = lab.daily_buffered_mtf3_equity_weight(g_cn, 150, 20, 210, 0.03).to_numpy(float)
    w_sma150_b3 = lab.daily_buffered_ma_state(g_cn, 150, 0.03).to_numpy(float)
    w_dema150_b3 = ind.hysteresis_ma_state(g_cn, ind.dema(g_cn, 150), buffer=0.03).to_numpy(float)
    w_tsmom = ind.tsmom_blend_weight(g_cn, (63, 126, 252), buffer=0.02).to_numpy(float)
    w_tsmom4 = ind.tsmom_blend_weight(g_cn, (21, 63, 126, 252), buffer=0.02).to_numpy(float)
    w_hyb_st = lab.daily_buffered_st_ma_weight(h_cn, l_cn, g_cn, 10, 3.0, 150, 0.03).to_numpy(float)
    vol21_cn = np.log(g_cn).diff().rolling(21).std(ddof=1) * np.sqrt(252.0)
    w_vt12 = np.clip(0.12 / np.where(np.isfinite(vol21_cn) & (vol21_cn > 1e-4), vol21_cn, 0.12), 0.0, 1.0)
    w_tvt50 = np.minimum(w_vt12, w_s2_half)

    # Strict lagged US GLD signals (us_date < cn_date)
    us_mtf3_raw = lab.daily_buffered_mtf3_equity_weight(gld_df["Close"], 150, 20, 210, 0.03)
    us_tsmom_raw = ind.tsmom_blend_weight(gld_df["Close"], (63, 126, 252), buffer=0.02)
    w_us_mtf3, lag1 = lab.map_us_series_to_cn_strict(us_mtf3_raw, dates)
    w_us_tsmom, lag2 = lab.map_us_series_to_cn_strict(us_tsmom_raw, dates)
    assert lag1 >= 1 and lag2 >= 1
    w_us_mtf3_arr = w_us_mtf3.to_numpy(float)
    w_us_tsmom_arr = w_us_tsmom.to_numpy(float)

    # Inverse-vol 518880 + 511010 (monthly)
    m_mask = ov.month_end_mask(dates)
    vg = g_cn.pct_change().rolling(60).std(ddof=1).to_numpy(float)
    vb = b5.pct_change().rolling(60).std(ddof=1).to_numpy(float)
    w_iv_cn = np.zeros((n, 2))
    cur_iv = np.array([0.5, 0.5])
    for i in range(n):
        if i == start_i or m_mask[i]:
            if np.isfinite(vg[i]) and np.isfinite(vb[i]) and vg[i] > 0 and vb[i] > 0:
                ig, ib = 1.0 / vg[i], 1.0 / vb[i]
                # Cap bond weight at 75% so gold stays meaningful core (>=25%)
                wg = max(0.25, ig / (ig + ib))
                cur_iv = np.array([wg, 1.0 - wg])
        w_iv_cn[i] = cur_iv

    cn_specs: list[tuple[str, str, Optional[np.ndarray], Optional[Callable], bool]] = [
        ("CN_BH_518880", "Baseline", None, lab.fixed_weight_signal([1.0, 0.0], dates, start_i, freq="NONE"), False),
        ("CN_BH_511010_Ref", "Baseline", None, lab.fixed_weight_signal([0.0, 1.0], dates, start_i, freq="NONE"), False),
        ("CN_S2_HALF_CASH", "Self_Cash", np.column_stack([w_s2_half, np.zeros(n)]), None, True),
        ("CN_M10_CASH", "Self_Cash", np.column_stack([w_m10, np.zeros(n)]), None, True),
        ("CN_MTF3_BUF2_CASH", "Self_Cash", np.column_stack([w_mtf3_b2, np.zeros(n)]), None, True),
        ("CN_MTF3_BUF3_CASH", "Self_Cash", np.column_stack([w_mtf3_b3, np.zeros(n)]), None, True),
        ("CN_SMA150_B3_CASH", "Self_Cash", np.column_stack([w_sma150_b3, np.zeros(n)]), None, True),
        ("CN_DEMA150_B3_CASH", "Self_Cash", np.column_stack([w_dema150_b3, np.zeros(n)]), None, True),
        ("CN_TSMOM_3_6_12_CASH", "Self_Cash", np.column_stack([w_tsmom, np.zeros(n)]), None, True),
        ("CN_TSMOM_1_3_6_12_CASH", "Self_Cash", np.column_stack([w_tsmom4, np.zeros(n)]), None, True),
        ("CN_HYB_ST_MA150_CASH", "Self_Cash", np.column_stack([w_hyb_st, np.zeros(n)]), None, True),
        ("CN_VT12_CASH", "Self_Cash", np.column_stack([w_vt12, np.zeros(n)]), None, True),
        ("CN_TVT50_CASH", "Self_Cash", np.column_stack([w_tvt50, np.zeros(n)]), None, True),
        ("CN_US_SIG_MTF3_CASH", "US_Signal_Cash", np.column_stack([w_us_mtf3_arr, np.zeros(n)]), None, True),
        ("CN_US_SIG_TSMOM_CASH", "US_Signal_Cash", np.column_stack([w_us_tsmom_arr, np.zeros(n)]), None, True),
        # Park spare cash into CN 5Y Treasury ETF 511010!
        ("CN_MTF3_BUF3_BOND511010", "Self_Plus_CNBond", np.column_stack([w_mtf3_b3, 1.0 - w_mtf3_b3]), None, False),
        ("CN_TSMOM_3_6_12_BOND511010", "Self_Plus_CNBond", np.column_stack([w_tsmom, 1.0 - w_tsmom]), None, False),
        ("CN_S2_HALF_BOND511010", "Self_Plus_CNBond", np.column_stack([w_s2_half, 1.0 - w_s2_half]), None, False),
        ("CN_US_SIG_MTF3_BOND511010", "US_Sig_Plus_CNBond", np.column_stack([w_us_mtf3_arr, 1.0 - w_us_mtf3_arr]), None, False),
        # Static Gold + CN Bond mixes
        ("CN_70G_30B_Q", "Static_CN_Mix", None, lab.fixed_weight_signal([0.70, 0.30], dates, start_i, freq="Q"), False),
        ("CN_50G_50B_Q", "Static_CN_Mix", None, lab.fixed_weight_signal([0.50, 0.50], dates, start_i, freq="Q"), False),
        ("CN_INVVOL_GB_M", "Static_CN_Mix", w_iv_cn, None, False),
    ]

    cn_rows = []
    px_gold_only = pd.DataFrame({"gold_cn": g_cn.to_numpy(float)}, index=dates)
    cn_bh_res = lab.run_multi_asset_overlay(
        px, lab.fixed_weight_signal([1.0, 0.0], dates, start_i, freq="NONE"), start_i, 0.001, cash_pos, cash_neg
    )
    cn_bh_dca5 = fast_dca_rolling(cn_bh_res.nav, 60, 0.001)

    for name, grp, w_mat, sig_fn, do_perm in cn_specs:
        sig = sig_fn if sig_fn is not None else multi_weight_to_signal(w_mat, start_i, threshold=0.02)
        r10 = lab.run_multi_asset_overlay(px, sig, start_i, 0.001, cash_pos, cash_neg)
        r30 = lab.run_multi_asset_overlay(px, sig, start_i, 0.003, cash_pos, cash_neg)
        m = summarize_nav_ext(r10, "gold_cn")
        m30 = summarize_nav_ext(r30, "gold_cn")
        m_pre23 = summarize_nav_ext(r10, "gold_cn", start="2014-08-01", end="2022-12-30")
        m_23_26 = summarize_nav_ext(r10, "gold_cn", start="2023-01-03", end="2026-11-20")
        m26 = summarize_nav_ext(r10, "gold_cn", start="2026-01-29", end="2026-11-20")
        dca5 = fast_dca_rolling(r10.nav, 60, 0.001)
        mg5 = dca5.merge(cn_bh_dca5, on=["start", "end"], suffixes=("_s", "_b"))
        p_sh = np.nan
        if do_perm and w_mat is not None:
            p_sh = circular_shift_perm_single(
                px_gold_only, w_mat[:, 0], start_i, cost=0.001, cash_pos=cash_pos, cash_neg=cash_neg, n_trials=200
            )["p_sharpe"]
        cn_rows.append(
            {
                "strategy": name,
                "group": grp,
                "cagr": m["cagr"],
                "vol": m["vol"],
                "sharpe": m["sharpe"],
                "max_dd": m["max_dd"],
                "calmar": m["calmar"],
                "max_uw_years": m["max_uw_years"],
                "trades_per_year": m["trades_per_year"],
                "annual_turnover": m["annual_turnover"],
                "avg_w_gold": float(r10.weights["gold_cn"].iloc[1:].mean()),
                "avg_w_bond": float(r10.weights["bond_cn"].iloc[1:].mean()),
                "sharpe_30bp": m30["sharpe"],
                "perm_p_sharpe": p_sh,
                "pre2023_cagr": m_pre23["cagr"],
                "pre2023_sharpe": m_pre23["sharpe"],
                "pre2023_mdd": m_pre23["max_dd"],
                "post2023_cagr": m_23_26["cagr"],
                "post2023_sharpe": m_23_26["sharpe"],
                "crash_2026_ret": m26["total_ret"],
                "dca5y_med_xirr": float(mg5["xirr_s"].median()),
                "dca5y_worst_float": float(mg5["max_float_loss_s"].min()),
                "dca5y_ratio_beat_bh": float((mg5["dca_ratio_s"] > mg5["dca_ratio_b"]).mean()),
            }
        )

    # --- Part B: Crypto Gold (PAXG / XAUT) vs GLD / IAU / GC=F (2020-03-01..2026-11-20) ---
    # Align onto US trading dates for clean apples-to-apples comparison
    c_dates = pd.DatetimeIndex(gld_df.index[gld_df.index >= pd.Timestamp("2020-03-01")])
    c_yrs = (c_dates[-1] - c_dates[0]).days / 365.25
    paxg_al = align_close_to(paxg_df["Close"], c_dates)
    xaut_al = align_close_to(xaut_df["Close"], c_dates)
    gld_al = gld_df["Close"].reindex(c_dates)
    iau_al = align_close_to(iau_df["Close"], c_dates)
    gcf_al = align_close_to(gcf_df["Close"], c_dates)

    # Compare PAXG vs GCF premium/discount
    paxg_prem = paxg_al / gcf_al - 1.0
    xaut_prem = xaut_al / gcf_al - 1.0
    crypto_rows = []
    for label, ser, prem in [
        ("GLD_ETF_0.40pct_fee", gld_al, None),
        ("IAU_ETF_0.25pct_fee", iau_al, None),
        ("GCF_Futures_Ref", gcf_al, None),
        ("PAXG_CryptoGold_0pct_fee", paxg_al, paxg_prem),
        ("XAUT_CryptoGold_0pct_fee", xaut_al, xaut_prem),
    ]:
        r = ser.pct_change().dropna()
        cagr = float((ser.iloc[-1] / ser.iloc[0]) ** (1.0 / c_yrs) - 1.0)
        vol = float(r.std(ddof=1) * np.sqrt(252))
        mdd = float((ser / ser.cummax() - 1.0).min())
        te = float((r - gcf_al.pct_change().dropna()).std(ddof=1) * np.sqrt(252))
        crypto_rows.append(
            {
                "instrument": label,
                "start": str(c_dates[0].date()),
                "end": str(c_dates[-1].date()),
                "cagr": cagr,
                "vol": vol,
                "max_dd": mdd,
                "tracking_error_vs_gcf": te,
                "worst_1d_ret": float(r.min()),
                "best_1d_ret": float(r.max()),
                "median_prem_vs_gcf": float(prem.median()) if prem is not None else 0.0,
                "max_prem_vs_gcf": float(prem.max()) if prem is not None else 0.0,
                "min_prem_vs_gcf": float(prem.min()) if prem is not None else 0.0,
            }
        )

    # Also test PAXG with 30bp/50bp crypto slippage and 0% USDT cash on top strategies (2020-11..2026-11)
    p_dates = pd.DatetimeIndex(paxg_df.index)
    p_start = int(p_dates.searchsorted(pd.Timestamp("2020-10-01")))
    p_px = pd.DataFrame({"paxg": paxg_df["Close"].to_numpy(float)}, index=p_dates)
    p_cash0 = np.ones(len(p_dates), dtype=float)
    p_close = paxg_df["Close"]
    for pname, pw in [
        ("PAXG_BH_30bp_0cash", np.ones(len(p_dates))),
        ("PAXG_MTF3_BUF3_30bp_0cash", lab.daily_buffered_mtf3_equity_weight(p_close, 150, 20, 210, 0.03).to_numpy(float)),
        ("PAXG_TSMOM_3_6_12_30bp_0cash", ind.tsmom_blend_weight(p_close, (63, 126, 252), buffer=0.02).to_numpy(float)),
        ("PAXG_SMA150_B3_30bp_0cash", lab.daily_buffered_ma_state(p_close, 150, 0.03).to_numpy(float)),
    ]:
        r30 = lab.run_multi_asset_overlay(p_px, weight_to_signal(pw, p_start), p_start, 0.003, p_cash0, p_cash0)
        m = summarize_nav_ext(r30, "paxg", ann_days=365)
        m26 = summarize_nav_ext(r30, "paxg", start="2026-01-29", end="2026-11-20", ann_days=365)
        crypto_rows.append(
            {
                "instrument": pname,
                "start": m["start"],
                "end": m["end"],
                "cagr": m["cagr"],
                "vol": m["vol"],
                "max_dd": m["max_dd"],
                "tracking_error_vs_gcf": m["sharpe"],  # reuse column? Better keep separate!
                "worst_1d_ret": m["trades_per_year"],
                "best_1d_ret": m26["total_ret"],
                "median_prem_vs_gcf": np.nan,
                "max_prem_vs_gcf": np.nan,
                "min_prem_vs_gcf": np.nan,
            }
        )
    # Clean separate table for crypto instruments vs crypto strategies
    crypto_df = pd.DataFrame(crypto_rows[:5])
    paxg_strat_rows = []
    for pname, pw in [
        ("PAXG_BH", np.ones(len(p_dates))),
        ("PAXG_MTF3_BUF3", lab.daily_buffered_mtf3_equity_weight(p_close, 150, 20, 210, 0.03).to_numpy(float)),
        ("PAXG_TSMOM_3_6_12_B2", ind.tsmom_blend_weight(p_close, (63, 126, 252), buffer=0.02).to_numpy(float)),
        ("PAXG_SMA150_B3", lab.daily_buffered_ma_state(p_close, 150, 0.03).to_numpy(float)),
    ]:
        r30 = lab.run_multi_asset_overlay(p_px, weight_to_signal(pw, p_start), p_start, 0.003, p_cash0, p_cash0)
        r50 = lab.run_multi_asset_overlay(p_px, weight_to_signal(pw, p_start), p_start, 0.005, p_cash0, p_cash0)
        m30 = summarize_nav_ext(r30, "paxg", ann_days=365)
        m50 = summarize_nav_ext(r50, "paxg", ann_days=365)
        m26 = summarize_nav_ext(r30, "paxg", start="2026-01-29", end="2026-11-20", ann_days=365)
        paxg_strat_rows.append(
            {
                "strategy": pname,
                "cagr_30bp": m30["cagr"],
                "sharpe_30bp": m30["sharpe"],
                "max_dd_30bp": m30["max_dd"],
                "calmar_30bp": m30["calmar"],
                "trades_per_year": m30["trades_per_year"],
                "cagr_50bp": m50["cagr"],
                "sharpe_50bp": m50["sharpe"],
                "crash_2026_ret": m26["total_ret"],
            }
        )
    fx_decomp["paxg_strategies_30bp_0cash"] = paxg_strat_rows

    return pd.DataFrame(cn_rows), crypto_df, fx_decomp


# --------------------------------------------------------------------------- Anti-Lookahead Self-Checks & Charts
def run_self_checks(
    gld_df: pd.DataFrame,
    nav_results: dict[str, lab.MultiEngineResult],
    shield_res: dict[str, lab.MultiEngineResult],
    fx_decomp: dict[str, Any],
) -> dict[str, Any]:
    # 1. Perturb prices strictly after cut_i and verify EVERY single-asset signal <= cut_i is bit-for-bit identical
    cut_i = len(gld_df) // 2
    orig = build_gold_single_strategies(gld_df)
    pert_df = gld_df.copy()
    pert_df.iloc[cut_i + 1 :] *= 0.25
    pert = build_gold_single_strategies(pert_df)

    max_sig_diff = 0.0
    checked_signals = 0
    for k in orig:
        a = orig[k][1][: cut_i + 1]
        b = pert[k][1][: cut_i + 1]
        diff = float(np.max(np.abs(a - b)))
        max_sig_diff = max(max_sig_diff, diff)
        checked_signals += 1

    # 2. Cash conservation residual across all backtests
    max_resid = 0.0
    min_nav = np.inf
    for d in (nav_results, shield_res):
        for res in d.values():
            max_resid = max(max_resid, float(res.checks["max_cash_residual"]))
            min_nav = min(min_nav, float(res.checks["nav_min"]))

    checks = {
        "checked_signal_count": checked_signals,
        "anti_lookahead_max_diff": max_sig_diff,
        "anti_lookahead_passed": bool(max_sig_diff == 0.0),
        "max_cash_residual": max_resid,
        "cash_conservation_passed": bool(max_resid < 1e-12),
        "min_nav_observed": float(min_nav),
        "cross_market_min_lag_days": int(fx_decomp["min_us_to_cn_lag_days"]),
        "cross_market_lag_passed": bool(fx_decomp["min_us_to_cn_lag_days"] >= 1),
    }
    assert checks["anti_lookahead_passed"], f"Lookahead detected: {checks}"
    assert checks["cash_conservation_passed"], f"Cash residual too high: {checks}"
    assert checks["cross_market_lag_passed"], f"Cross-market lag violation: {checks}"
    return checks


def generate_charts(
    gold_55y: pd.Series,
    rf_m: pd.Series,
    nav_results: dict[str, lab.MultiEngineResult],
    shield_res: dict[str, lab.MultiEngineResult],
    cn_gold_df: pd.DataFrame,
    cn_bond5_df: pd.DataFrame,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["axes.unicode_minus"] = False

    # Chart 1: GLD 21Y NAV & Drawdown Comparison (log scale)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [2.2, 1.0]})
    picks = [
        ("BH", "GLD Buy & Hold", "#888888", "--", 1.8),
        ("MTF3_BUF3", "GLD Daily Buffered MTF-3 (+-3%, Cash)", "#1f77b4", "-", 2.1),
        ("TSMOM_3_6_12_B2", "GLD CTA TSMOM (3/6/12M +-2%, Cash)", "#2ca02c", "-", 1.9),
        ("GLD_MTF3_BUF3_COND_IEF", "GLD MTF-3 +-3% + Cond. Treasury (IEF)", "#ff7f0e", "-", 2.0),
        ("GLD_MTF3_BUF3_SPY_TREND", "GLD MTF-3 +-3% + Trend-Gated SPY", "#d62728", "-", 2.2),
    ]
    for key, label, col, ls, lw in picks:
        res = nav_results[key] if key in nav_results else shield_res[key]
        nav = res.nav / res.nav.iloc[0]
        dd = (nav / nav.cummax() - 1.0) * 100.0
        ax1.plot(nav.index, nav.values, label=label, color=col, linestyle=ls, linewidth=lw)
        ax2.plot(dd.index, dd.values, label=label, color=col, linestyle=ls, linewidth=lw * 0.85)
    ax1.set_yscale("log")
    ax1.set_title("Gold Quantitative Enhancement (GLD 2005-12 to 2026-11, incl. 2026 -35% Crash)", fontsize=13)
    ax1.set_ylabel("Cumulative NAV (Log Scale)")
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="upper left", fontsize=9)
    ax2.set_ylabel("Drawdown (%)")
    ax2.set_ylim(-52, 2)
    ax2.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "gold_gld_21y_nav_dd.png", dpi=150)
    plt.close(fig)

    # Chart 2: 55-Year Post-Bretton-Woods Cycle (1972-2026 Monthly, Log NAV & Drawdown)
    dates = pd.DatetimeIndex(gold_55y.index)
    prices = pd.DataFrame({"gold": gold_55y.to_numpy(float)}, index=dates)
    start_i = int(dates.searchsorted(pd.Timestamp("1972-01-31")))
    day_diff = np.zeros(len(dates), dtype=float)
    day_diff[1:] = (dates[1:] - dates[:-1]).days.to_numpy(float)
    cash_pos = (1.0 + rf_m.to_numpy(float)) ** (day_diff / 365.25)
    cash_pos[0] = 1.0
    w_bh = np.ones(len(dates))
    w_m10 = (gold_55y > gold_55y.rolling(10).mean()).fillna(False).to_numpy(float)
    w_ts = ind.tsmom_blend_weight(gold_55y, (3, 6, 12), buffer=0.02).to_numpy(float)
    m7_b3 = ind.hysteresis_ma_state(gold_55y, gold_55y.rolling(7).mean(), buffer=0.03, rising_lookback=1).to_numpy(bool)
    m10_b3 = ind.hysteresis_ma_state(gold_55y, gold_55y.rolling(10).mean(), buffer=0.03).to_numpy(bool)
    w_mtf = np.where(m7_b3 & m10_b3, 1.0, np.where(m7_b3 | m10_b3, 0.5, 0.0))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [2.2, 1.0]})
    for lbl, w_a, col, ls in [
        ("Spot Gold Buy & Hold (net 0.4% fee)", w_bh, "#888888", "--"),
        ("10-Month SMA + T-Bill", w_m10, "#1f77b4", "-"),
        ("Buffered 3-Tier (7M/10M +-3%) + T-Bill", w_mtf, "#d62728", "-"),
        ("Monthly TSMOM (3/6/12M +-2%) + T-Bill", w_ts, "#2ca02c", "-"),
    ]:
        r = lab.run_multi_asset_overlay(
            prices, weight_to_signal(w_a, start_i), start_i, 0.001, cash_pos, extra_daily_drag={"gold": 0.004}
        )
        nv = r.nav / r.nav.iloc[0]
        dd = (nv / nv.cummax() - 1.0) * 100.0
        ax1.plot(nv.index, nv.values, label=lbl, color=col, linestyle=ls, linewidth=1.9)
        ax2.plot(dd.index, dd.values, label=lbl, color=col, linestyle=ls, linewidth=1.6)
    ax1.axvspan(pd.Timestamp("1980-01-31"), pd.Timestamp("2001-03-31"), color="#ffcccc", alpha=0.25, label="1980-2001 20Y Gold Bear")
    ax1.axvspan(pd.Timestamp("2011-09-30"), pd.Timestamp("2019-05-31"), color="#ffe5cc", alpha=0.35, label="2011-2019 8Y Gold Bear")
    ax1.set_yscale("log")
    ax1.set_title("55-Year Post-Bretton-Woods Gold Stress Test (1972-2026 Monthly, Incl. 1980-2001 -70% Bear)", fontsize=13)
    ax1.set_ylabel("Cumulative NAV (Log Scale)")
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="upper left", fontsize=9)
    ax2.set_ylabel("Drawdown (%)")
    ax2.set_ylim(-75, 2)
    ax2.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "gold_55y_long_cycle.png", dpi=150)
    plt.close(fig)

    # Chart 3: 2026 Crash Zoom (2025-07 to 2026-11-20) on GLD
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for key, label, col, ls in [
        ("BH", "GLD Buy & Hold (-34.9% from peak)", "#888888", "--"),
        ("MTF3_BUF3", "GLD Daily Buffered MTF-3 (+-3%)", "#1f77b4", "-"),
        ("TSMOM_3_6_12_B2", "GLD CTA TSMOM (3/6/12M +-2%)", "#2ca02c", "-"),
        ("MTF3_BUF3_OVERHEAT", "GLD MTF-3 +-3% + Overheat Brake", "#9467bd", "-"),
        ("GLD_MTF3_BUF3_SPY_TREND", "GLD MTF-3 +-3% + Trend SPY", "#d62728", "-"),
    ]:
        res = nav_results[key] if key in nav_results else shield_res[key]
        sub = res.nav.loc["2025-07-01":"2026-11-20"]
        sub = sub / sub.iloc[0]
        ax.plot(sub.index, sub.values, label=label, color=col, linestyle=ls, linewidth=2.0)
    ax.axvline(pd.Timestamp("2026-01-29"), color="#cc0000", linestyle=":", alpha=0.7, label="2026-01-29 Gold Peak ($495.9)")
    ax.set_title("Live Crash Stress Test: 2025-07 to 2026-11-20 Gold Blow-Off & -35% Crash", fontsize=13)
    ax.set_ylabel("Normalized NAV (2025-07-01 = 1.0)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "gold_2026_crash_zoom.png", dpi=150)
    plt.close(fig)


# --------------------------------------------------------------------------- Main
def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading frozen gold & cross-asset cache...", flush=True)
    gld_df = load_yf_ohlc("yf_GLD")
    iau_df = load_yf_ohlc("yf_IAU")
    slv_df = load_yf_ohlc("yf_SLV")
    gdx_df = load_yf_ohlc("yf_GDX")
    ugl_df = load_yf_ohlc("yf_UGL")
    gcf_df = load_yf_ohlc("yf_GCF")
    sif_df = load_yf_ohlc("yf_SIF")
    spy_df = load_yf_ohlc("yf_SPY")
    ief_df = load_yf_ohlc("yf_IEF")
    tlt_df = load_yf_ohlc("yf_TLT")
    tip_df = load_yf_ohlc("yf_TIP")
    dxy_df = load_yf_ohlc("yf_DXY")
    irx_df = load_yf_ohlc("yf_IRX")
    paxg_df = load_yf_ohlc("yf_PAXG")
    xaut_df = load_yf_ohlc("yf_XAUT")
    btc_df = load_yf_ohlc("yf_BTC")
    cn_gold_df = load_yf_ohlc("yf_518880")
    cn_bond5_df = load_yf_ohlc("yf_511010")
    cn_bond10_df = load_yf_ohlc("yf_511260")
    cny_df = load_yf_ohlc("yf_CNY")
    gold_55y, rf_m = load_monthly_gold_55y()

    print("Module 1: Market Physics Fingerprint & 55Y Seasonality...", flush=True)
    phys_df, seas_df = run_module1_physics_and_seasonality(
        gld_df, gcf_df, slv_df, gdx_df, cn_gold_df, spy_df, btc_df, gold_55y
    )
    phys_df.to_csv(OUT_DIR / "gold_physics_fingerprint.csv", index=False)
    seas_df.to_csv(OUT_DIR / "gold_seasonality_audit.csv", index=False)

    print("Module 2: 55-Year Post-Bretton-Woods Long-Cycle Backtest (1972-2026)...", flush=True)
    long55_df = run_module2_long_55y(gold_55y, rf_m)
    long55_df.to_csv(OUT_DIR / "gold_55y_long_cycle.csv", index=False)

    print("Module 3: GLD Single-Asset Strategy Arena (35+ strategies + 200x Permutation + 25Y GC=F + 2x UGL)...", flush=True)
    gld_sum_df, gld_perm_df, gld_per_df, ugl_df_out, nav_results = run_module3_single_asset_arena(
        gld_df, iau_df, gcf_df, ugl_df, irx_df
    )
    gld_sum_df.to_csv(OUT_DIR / "gold_gld_strategies_summary.csv", index=False)
    gld_perm_df.to_csv(OUT_DIR / "gold_gld_permutation.csv", index=False)
    gld_per_df.to_csv(OUT_DIR / "gold_gld_key_periods.csv", index=False)
    ugl_df_out.to_csv(OUT_DIR / "gold_ugl_2x_leverage.csv", index=False)

    print("Module 4: Parameter Plateau & Rolling Annual Starts...", flush=True)
    grid_df, roll_df = run_module4_robustness(gld_df, irx_df, nav_results)
    grid_df.to_csv(OUT_DIR / "gold_param_sensitivity.csv", index=False)
    roll_df.to_csv(OUT_DIR / "gold_rolling_starts.csv", index=False)

    print("Module 5: Macro Factor Timing (Real Yield TIP, Breakeven TIP/IEF, USD DXY)...", flush=True)
    macro_df = run_module5_macro_factors(gld_df, tip_df, ief_df, dxy_df, irx_df)
    macro_df.to_csv(OUT_DIR / "gold_macro_timing.csv", index=False)

    print("Module 6: Precious-Metals Rotation (Gold/Silver Ratio vs Dual Momentum & Gold Miners GDX)...", flush=True)
    metals_df = run_module6_precious_metals(gld_df, slv_df, gdx_df, gcf_df, sif_df, irx_df)
    metals_df.to_csv(OUT_DIR / "gold_precious_metals_rotation.csv", index=False)

    print("Module 7: Gold-Centric Cross-Asset Shields & Digital Gold (BTC) Satellite...", flush=True)
    shields_df, shield_res = run_module7_cross_asset_shields(gld_df, ief_df, tip_df, tlt_df, spy_df, btc_df, irx_df)
    shields_df.to_csv(OUT_DIR / "gold_cross_asset_shields.csv", index=False)

    print("Module 8: Rolling 5Y/10Y DCA & Budget-Neutral Smart DCA...", flush=True)
    dca_roll_df, dca_smart_df = run_module8_dca(gld_df, irx_df, nav_results, shield_res)
    dca_roll_df.to_csv(OUT_DIR / "gold_dca_rolling.csv", index=False)
    dca_smart_df.to_csv(OUT_DIR / "gold_dca_smart_budget_neutral.csv", index=False)

    print("Module 9: Domestic RMB 518880 (FX Decomp + CN Bond 511010 + US Signal) & Crypto PAXG/XAUT...", flush=True)
    cn_df, crypto_df, fx_decomp = run_module9_domestic_and_crypto(
        cn_gold_df, cn_bond5_df, cn_bond10_df, cny_df, gld_df, iau_df, gcf_df, paxg_df, xaut_df, irx_df
    )
    cn_df.to_csv(OUT_DIR / "gold_domestic_518880.csv", index=False)
    crypto_df.to_csv(OUT_DIR / "gold_crypto_paxg_audit.csv", index=False)
    (OUT_DIR / "gold_fx_and_crypto_summary.json").write_text(json.dumps(fx_decomp, ensure_ascii=False, indent=2) + "\n")

    print("Running anti-lookahead & cash-conservation self-checks...", flush=True)
    checks = run_self_checks(gld_df, nav_results, shield_res, fx_decomp)
    (OUT_DIR / "self_checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n")
    (OUT_DIR / "config.json").write_text(json.dumps(CONFIG, ensure_ascii=False, indent=2) + "\n")

    print("Generating charts...", flush=True)
    generate_charts(gold_55y, rf_m, nav_results, shield_res, cn_gold_df, cn_bond5_df)

    # Print crisp executive digest
    print("\n" + "=" * 90)
    print("SELF CHECKS:", json.dumps(checks, ensure_ascii=False))
    print("\n--- MODULE 1: PHYSICS FINGERPRINT ---")
    print(
        phys_df[["asset_window", "cagr", "vol", "max_dd", "max_uw_years", "trend_spread_60d_ma150", "trend_spread_120d_ma150"]].to_string(
            index=False
        )
    )
    print("\n--- MODULE 2: 55-YEAR LONG CYCLE (1972-2026) ---")
    print(
        long55_df[
            ["strategy", "cagr", "sharpe", "max_dd", "calmar", "max_uw_years", "bear_80_01_cagr", "bear_11_19_cagr", "perm_p_sharpe_55y"]
        ].to_string(index=False)
    )
    print("\n--- MODULE 3: TOP GLD SINGLE-ASSET STRATEGIES (sorted by Sharpe) ---")
    print(
        gld_sum_df.sort_values("sharpe", ascending=False)[
            ["strategy", "family", "cagr", "sharpe", "max_dd", "calmar", "max_uw_years", "trades_per_year", "bear_11_19_cagr", "crash_2026_ret"]
        ]
        .head(20)
        .to_string(index=False)
    )
    print("\n--- MODULE 5: MACRO FACTORS ---")
    print(
        macro_df[
            ["strategy", "full_cagr", "full_sharpe", "full_mdd", "pre2022_sharpe", "post2022_sharpe", "ratehike_bull_22_26pk_cagr", "perm_p_sharpe"]
        ].to_string(index=False)
    )
    print("\n--- MODULE 6: PRECIOUS METALS ROTATION (2007-2026) ---")
    print(
        metals_df[["strategy", "group", "cagr", "sharpe", "max_dd", "calmar", "trades_per_year", "crash_2026_ret"]].to_string(
            index=False
        )
    )
    print("\n--- MODULE 7: CROSS-ASSET SHIELDS ---")
    print(
        shields_df[
            ["strategy", "group", "window", "cagr", "sharpe", "max_dd", "calmar", "max_uw_years", "bear_11_19_cagr", "crash_2026_ret"]
        ].to_string(index=False)
    )
    print("\n--- MODULE 9: DOMESTIC 518880 (2014-2026) ---")
    print(
        cn_df[
            ["strategy", "group", "cagr", "sharpe", "max_dd", "calmar", "trades_per_year", "perm_p_sharpe", "crash_2026_ret", "dca5y_ratio_beat_bh"]
        ].to_string(index=False)
    )
    print("\nDONE! All artifacts written to", OUT_DIR)


if __name__ == "__main__":
    main()
