"""Formal Research Study:
1. Track 1 — BTC Long-Only Moving Average Families (Dual SMA vs Dual EMA vs Zero-Lag MA [ZLEMA/DEMA/TEMA/HMA/KAMA])
   head-to-head against Buy-and-Hold, Daily SuperTrend(10,3), and Validated Buffered Three-Tier Strategies
   (BTC 2015-2026, Early vs 2021-2026 Mature, ETH zero-tuning OOS 2018-2026).
2. Track 2 — A-Share Dividend Low-Vol Mean-Reversion & Reverse-MA Strategies (RSI, KDJ, Daily/Weekly Bollinger,
   Reverse Moving Averages, Bias Core-Tilt, Bond-Paired Tilt, and Budget-Neutral Mean-Reversion DCA)
   across H20269 Total Return (2014-2026, Early vs Ex-2015 vs 2020+), real 510880 ETF, real 512890 ETF,
   and cross-index check on H00300 / 510500.

Run (offline sandbox, from repo root):
    .venv/bin/python -I scripts/research_btc_ma_and_dlv_mean_reversion_2026_11_23.py
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

SLUG = "btc-ma-and-dlv-mean-reversion-2026-11-23"
OUT_DIR = ROOT / "outputs" / SLUG

BTC_PQ = ROOT / "outputs" / "btc-satellite-corrected-prices-2026-10-18" / "market_data" / "BTC-USD.parquet"
ETH_PQ = ROOT / "outputs" / "strategy-healthcheck-2026-10-02" / "market_data" / "ETH-USD.parquet"
CSI_CACHE = ROOT / "outputs" / "dividend-lowvol-csi2000-2026-10-18" / "cache"
TF_CACHE = ROOT / "outputs" / "weinstein-etf-stage-2026-10-18" / "cache"
BOND_CN_PQ = ROOT / "outputs" / "strategy-healthcheck-2026-10-02" / "market_data" / "511010.SS.parquet"

CONFIG: dict[str, Any] = {
    "slug": SLUG,
    "execution_clock": "Signal at close t using data <= t; fills at close t+1 with proportional one-way cost.",
    "track1_btc": {
        "btc_window": ["2015-08-01", "2026-10-01"],
        "btc_early": ["2015-08-01", "2020-12-31"],
        "btc_mature": ["2021-01-01", "2026-10-01"],
        "eth_window": ["2018-09-01", "2026-10-01"],
        "primary_cost": 0.003,
        "stress_costs": [0.001, 0.003, 0.005],
        "cash_annual": 0.0,
        "ann_days": 365,
        "pass_bar": [
            "Beats BTC BH on Sharpe and Calmar at 30bp with 0% USDT cash",
            "Holds up in 2021-2026 mature institutional era (beats BH Sharpe)",
            "Generalizes zero-tuning to ETH-USD (beats ETH BH Sharpe & MaxDD)",
            "Circular-shift permutation p_sharpe <= 0.05 on BTC and ETH",
            "Broad parameter plateau (not an isolated lucky pair)",
        ],
    },
    "track2_dlv_mr": {
        "h20269_window": ["2014-08-01", "2026-10-15"],
        "early_window": ["2014-08-01", "2019-12-31"],
        "ex15_window": ["2016-01-04", "2026-10-15"],
        "modern_window": ["2020-01-02", "2026-10-15"],
        "window_512890": ["2020-01-02", "2026-10-15"],
        "primary_cost": 0.001,
        "stress_cost": 0.003,
        "cash_annual": 0.02,
        "ann_days": 252,
        "pass_bar": [
            "Beats matched-exposure fixed quarterly portfolio on Sharpe AND CAGR across full window",
            "Passes circular-shift permutation test (p_sharpe <= 0.05) on full 2014-2026 AND Ex-2015 / 512890",
            "Does not blow up in 2015 crash / 2018 bear (falling-knife audit) and survives 30bp cost",
            "Works consistently in BOTH 2014-2019 AND 2020-2026 (not a single-regime fluke)",
        ],
    },
    "circular_shift_trials": 200,
}


# --------------------------------------------------------------------------- Loaders & Core Helpers
def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_parquet_ohlc(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df.columns = [str(c).capitalize() for c in df.columns]
    idx = pd.to_datetime(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    return df[~df.index.duplicated(keep="last")].sort_index()[["Open", "High", "Low", "Close"]].astype(float)


def load_tickflow_json(path: Path, symbol: str) -> pd.DataFrame:
    doc = json.loads(path.read_text())["data"][symbol]
    dates = (
        pd.to_datetime(doc["timestamp"], unit="ms", utc=True)
        .tz_convert("Asia/Shanghai")
        .tz_localize(None)
        .normalize()
    )
    df = pd.DataFrame(
        {
            "Open": np.asarray(doc["open"], float),
            "High": np.asarray(doc["high"], float),
            "Low": np.asarray(doc["low"], float),
            "Close": np.asarray(doc["close"], float),
        },
        index=dates,
    )
    return df[~df.index.duplicated(keep="last")].sort_index()


def load_csindex_ohlc(code: str) -> pd.DataFrame:
    p = CSI_CACHE / f"csindex_{code}.csv"
    df = pd.read_csv(p, parse_dates=["日期"]).drop_duplicates("日期", keep="last").set_index("日期").sort_index()
    close = pd.to_numeric(df["收盘"], errors="coerce")
    # CSI TR files leave Open/High/Low blank; fall back to Close cleanly where missing
    high = pd.to_numeric(df["最高"], errors="coerce").fillna(close) if "最高" in df else close
    low = pd.to_numeric(df["最低"], errors="coerce").fillna(close) if "最低" in df else close
    opn = pd.to_numeric(df["开盘"], errors="coerce").fillna(close) if "开盘" in df else close
    return pd.DataFrame({"Open": opn, "High": high, "Low": low, "Close": close}, index=df.index).dropna()


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


def two_asset_signal(w_a: np.ndarray, start_i: int, threshold: float = 0.02):
    """Allocate w_a to asset 0 and (1 - w_a) to defensive asset 1 (e.g., CN bond 511010)."""
    last_emitted = [np.nan]

    def sig(i: int, _actual: np.ndarray) -> Optional[np.ndarray]:
        w = float(w_a[i])
        if i == start_i:
            last_emitted[0] = w
            return np.array([w, 1.0 - w])
        if abs(w - last_emitted[0]) >= threshold:
            last_emitted[0] = w
            return np.array([w, 1.0 - w])
        return None

    return sig


def summarize_nav(
    res: lab.MultiEngineResult,
    *,
    primary_col: str,
    ann_days: int,
    start: Optional[str] = None,
    end: Optional[str] = None,
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
    years = days / 365.25
    cagr = float(nav_n.iloc[-1] ** (1.0 / years) - 1.0)
    ret = nav_n.pct_change().dropna()
    vol = float(ret.std(ddof=1) * np.sqrt(ann_days))
    ex = ret - rf.reindex(ret.index).fillna(0.0)
    ex_std = float(ex.std(ddof=1))
    sharpe = float(ex.mean() / ex_std * np.sqrt(ann_days)) if ex_std > 0 else np.nan
    dd = nav_n / nav_n.cummax() - 1.0
    max_dd = float(dd.min())
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else np.nan
    uw = lab.max_underwater_years(nav_n)
    monthly = nav_n.resample("ME").last().pct_change().dropna()
    yearly = nav_n.resample("YE").last().pct_change().dropna()
    non_init = trades[~trades["is_initial"]] if not trades.empty else trades
    tpy = float(len(non_init) / years) if years > 0 else 0.0
    turn = float(non_init["traded_frac"].sum() / years) if (not non_init.empty and years > 0) else 0.0
    avg_exp = float(wts[primary_col].iloc[1:].mean()) if len(wts) > 1 else 0.0
    return {
        "start": str(nav.index[0].date()),
        "end": str(nav.index[-1].date()),
        "years": round(years, 2),
        "cagr": cagr,
        "vol": vol,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "calmar": calmar,
        "max_underwater_years": uw,
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
    lo, hi = -0.95, 10.0
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
        # Also compute max floating loss of principal along the DCA path
        cum_units = np.zeros(len(seg), dtype=float)
        cum_prin = np.zeros(len(seg), dtype=float)
        rel_c = c_idx - i0
        cum_units[rel_c] = (1.0 - cost) / vals[c_idx]
        cum_prin[rel_c] = 1.0
        cum_units = np.cumsum(cum_units)
        cum_prin = np.cumsum(cum_prin)
        float_ret = (cum_units * seg) / np.maximum(cum_prin, 1e-12) - 1.0
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


def circular_shift_perm(
    prices: pd.DataFrame,
    weight_arr: np.ndarray,
    start_i: int,
    *,
    cost: float,
    cash_pos: np.ndarray,
    cash_neg: np.ndarray,
    ann_days: int,
    n_trials: int = 200,
    seed: int = 20261123,
    sub_start: Optional[str] = None,
    sub_end: Optional[str] = None,
) -> dict[str, Any]:
    col = prices.columns[0]
    res_obs = lab.run_multi_asset_overlay(
        prices, weight_to_signal(weight_arr, start_i), start_i, cost, cash_pos, cash_neg
    )
    m_obs = summarize_nav(res_obs, primary_col=col, ann_days=ann_days, start=sub_start, end=sub_end)
    obs_sharpe = m_obs["sharpe"]
    obs_cagr = m_obs["cagr"]

    rng = np.random.default_rng(seed)
    base_eval = weight_arr[start_i:].copy()
    n_eval = len(base_eval)
    min_sh = max(20, n_eval // 15)
    shifts = rng.integers(min_sh, n_eval - min_sh, size=n_trials)
    beat_s = 0
    beat_c = 0
    null_s = []
    null_c = []
    for sh in shifts:
        cand = weight_arr.copy()
        cand[start_i:] = np.roll(base_eval, int(sh))
        r_sim = lab.run_multi_asset_overlay(
            prices, weight_to_signal(cand, start_i), start_i, cost, cash_pos, cash_neg
        )
        ms = summarize_nav(r_sim, primary_col=col, ann_days=ann_days, start=sub_start, end=sub_end)
        if np.isfinite(ms["sharpe"]):
            null_s.append(ms["sharpe"])
        null_c.append(ms["cagr"])
        if np.isfinite(obs_sharpe) and np.isfinite(ms["sharpe"]) and ms["sharpe"] >= obs_sharpe:
            beat_s += 1
        if ms["cagr"] >= obs_cagr:
            beat_c += 1
    return {
        "obs_cagr": obs_cagr,
        "obs_sharpe": obs_sharpe,
        "obs_mdd": m_obs["max_dd"],
        "null_median_cagr": float(np.median(null_c)),
        "null_median_sharpe": float(np.median(null_s)) if null_s else np.nan,
        "p_cagr": float((beat_c + 1) / (n_trials + 1)),
        "p_sharpe": float((beat_s + 1) / (n_trials + 1)),
        "n_trials": n_trials,
    }


def hysteresis_cross_state(fast: pd.Series, slow: pd.Series, buf: float = 0.0) -> np.ndarray:
    f = fast.to_numpy(float)
    s = slow.to_numpy(float)
    out = np.zeros(len(f), dtype=bool)
    on = False
    for i in range(len(f)):
        if np.isnan(f[i]) or np.isnan(s[i]):
            continue
        if buf <= 0.0:
            on = bool(f[i] > s[i])
        else:
            if f[i] < s[i] * (1.0 - buf):
                on = False
            elif f[i] > s[i] * (1.0 + buf):
                on = True
        out[i] = on
    return out


def hysteresis_price_vs_ma(close: pd.Series, ma: pd.Series, buf: float = 0.0) -> np.ndarray:
    return hysteresis_cross_state(close, ma, buf=buf)


def tier3_buffered_ma_family(
    close: pd.Series,
    ma_fn: Callable[[pd.Series, int], pd.Series],
    fast_n: int,
    slow_n: int,
    slope_days: int = 20,
    buf: float = 0.05,
) -> np.ndarray:
    """Three-tier buffered rule (100/50/0) using any MA family (SMA / EMA / ZLEMA / DEMA / HMA)."""
    mf = ma_fn(close, fast_n)
    ms = ma_fn(close, slow_n)
    rising = (mf > mf.shift(slope_days)).fillna(False).to_numpy(bool)
    c = close.to_numpy(float)
    mf_v = mf.to_numpy(float)
    ms_v = ms.to_numpy(float)
    l1 = np.zeros(len(c), dtype=bool)
    l2 = np.zeros(len(c), dtype=bool)
    on1 = False
    on2 = False
    for i in range(len(c)):
        if not np.isnan(mf_v[i]):
            if c[i] < mf_v[i] * (1.0 - buf):
                on1 = False
            elif c[i] > mf_v[i] * (1.0 + buf) and rising[i]:
                on1 = True
        if not np.isnan(ms_v[i]):
            if c[i] < ms_v[i] * (1.0 - buf):
                on2 = False
            elif c[i] > ms_v[i] * (1.0 + buf):
                on2 = True
        l1[i] = on1
        l2[i] = on2
    score = l1.astype(int) + l2.astype(int)
    return np.where(score == 2, 1.0, np.where(score == 1, 0.5, 0.0))


# --------------------------------------------------------------------------- Track 1: BTC MA Families
def build_btc_ma_strategies(ohlc: pd.DataFrame) -> list[tuple[str, str, np.ndarray]]:
    """Pre-registered catalog of BTC long-only MA families + validated baselines."""
    c = ohlc["Close"]
    h = ohlc["High"]
    l = ohlc["Low"]
    sma_fn = lambda s, n: s.rolling(n, min_periods=n).mean()

    strats: list[tuple[str, str, np.ndarray]] = []
    # Baselines
    strats.append(("Baseline", "BH", np.ones(len(c), dtype=float)))
    st_dir = ind.supertrend_direction(h, l, c, atr_window=10, multiplier=3.0).to_numpy(float)
    strats.append(("Baseline", "ST_10_3", st_dir))
    strats.append(("Validated_3Tier", "HYB_ST_MA150_B5", lab.daily_buffered_st_ma_weight(h, l, c, 10, 3.0, 150, 0.05).to_numpy(float)))
    strats.append(("Validated_3Tier", "MTF3_100_200_B5", lab.daily_buffered_mtf3_equity_weight(c, 100, 20, 200, 0.05).to_numpy(float)))

    # Family 1: Plain Dual SMA & Single SMA
    for f_n, s_n in [(20, 50), (20, 100), (30, 100), (50, 150), (50, 200)]:
        w = hysteresis_cross_state(sma_fn(c, f_n), sma_fn(c, s_n), buf=0.0).astype(float)
        strats.append(("Dual_SMA", f"DSMA_{f_n}_{s_n}", w))
    strats.append(("Dual_SMA", "DSMA_20_100_B3", hysteresis_cross_state(sma_fn(c, 20), sma_fn(c, 100), buf=0.03).astype(float)))
    for n in (50, 100, 150, 200):
        strats.append(("Single_SMA", f"SMA_{n}", hysteresis_price_vs_ma(c, sma_fn(c, n), 0.0).astype(float)))
    strats.append(("Single_SMA", "SMA_100_B5", hysteresis_price_vs_ma(c, sma_fn(c, 100), 0.05).astype(float)))

    # Family 2: Dual EMA & Single EMA & Buffered 3-Tier EMA
    for f_n, s_n in [(12, 26), (20, 50), (20, 100), (30, 100), (50, 150), (50, 200)]:
        w = hysteresis_cross_state(ind.ema(c, f_n), ind.ema(c, s_n), buf=0.0).astype(float)
        strats.append(("Dual_EMA", f"DEMA_X_{f_n}_{s_n}", w))
    strats.append(("Dual_EMA", "DEMA_X_20_100_B3", hysteresis_cross_state(ind.ema(c, 20), ind.ema(c, 100), buf=0.03).astype(float)))
    strats.append(("Dual_EMA", "DEMA_X_20_50_B3", hysteresis_cross_state(ind.ema(c, 20), ind.ema(c, 50), buf=0.03).astype(float)))
    for n in (50, 100, 150):
        strats.append(("Single_EMA", f"EMA_{n}", hysteresis_price_vs_ma(c, ind.ema(c, n), 0.0).astype(float)))
    strats.append(("Single_EMA", "EMA_100_B5", hysteresis_price_vs_ma(c, ind.ema(c, 100), 0.05).astype(float)))
    strats.append(("EMA_3Tier", "TIER3_EMA_50_150_B5", tier3_buffered_ma_family(c, ind.ema, 50, 150, 20, 0.05)))
    strats.append(("EMA_3Tier", "TIER3_EMA_100_200_B5", tier3_buffered_ma_family(c, ind.ema, 100, 200, 20, 0.05)))

    # Family 3A: Zero-Lag EMA (ZLEMA) — single, buffered, dual, and 3-tier
    for n in (50, 100, 150, 200):
        strats.append(("ZLEMA", f"ZLEMA_{n}", hysteresis_price_vs_ma(c, ind.zlema(c, n), 0.0).astype(float)))
    strats.append(("ZLEMA", "ZLEMA_100_B5", hysteresis_price_vs_ma(c, ind.zlema(c, 100), 0.05).astype(float)))
    strats.append(("ZLEMA", "ZLEMA_150_B5", hysteresis_price_vs_ma(c, ind.zlema(c, 150), 0.05).astype(float)))
    for f_n, s_n in [(20, 50), (20, 100), (30, 100), (50, 150), (50, 200)]:
        strats.append(("Dual_ZLEMA", f"DZLEMA_{f_n}_{s_n}", hysteresis_cross_state(ind.zlema(c, f_n), ind.zlema(c, s_n), 0.0).astype(float)))
    strats.append(("Dual_ZLEMA", "DZLEMA_30_100_B3", hysteresis_cross_state(ind.zlema(c, 30), ind.zlema(c, 100), 0.03).astype(float)))
    strats.append(("Dual_ZLEMA", "DZLEMA_50_150_B3", hysteresis_cross_state(ind.zlema(c, 50), ind.zlema(c, 150), 0.03).astype(float)))
    strats.append(("ZLEMA_3Tier", "TIER3_ZLEMA_50_150_B5", tier3_buffered_ma_family(c, ind.zlema, 50, 150, 20, 0.05)))
    strats.append(("ZLEMA_3Tier", "TIER3_ZLEMA_100_200_B5", tier3_buffered_ma_family(c, ind.zlema, 100, 200, 20, 0.05)))

    # Family 3B: DEMA / TEMA / HMA / KAMA (other Zero-Lag & Adaptive MAs)
    strats.append(("ZeroLag_Other", "DEMA_100", hysteresis_price_vs_ma(c, ind.dema(c, 100), 0.0).astype(float)))
    strats.append(("ZeroLag_Other", "DEMA_150_B5", hysteresis_price_vs_ma(c, ind.dema(c, 150), 0.05).astype(float)))
    strats.append(("ZeroLag_Other", "DDEMA_20_100", hysteresis_cross_state(ind.dema(c, 20), ind.dema(c, 100), 0.0).astype(float)))
    strats.append(("ZeroLag_Other", "DDEMA_50_150", hysteresis_cross_state(ind.dema(c, 50), ind.dema(c, 150), 0.0).astype(float)))
    strats.append(("ZeroLag_Other", "TEMA_150", hysteresis_price_vs_ma(c, ind.tema(c, 150), 0.0).astype(float)))
    strats.append(("ZeroLag_Other", "TEMA_150_B5", hysteresis_price_vs_ma(c, ind.tema(c, 150), 0.05).astype(float)))
    strats.append(("ZeroLag_Other", "DTEMA_30_100", hysteresis_cross_state(ind.tema(c, 30), ind.tema(c, 100), 0.0).astype(float)))
    strats.append(("ZeroLag_Other", "HMA_100", hysteresis_price_vs_ma(c, ind.hma(c, 100), 0.0).astype(float)))
    hma100 = ind.hma(c, 100)
    strats.append(("ZeroLag_Other", "HMA_100_SLOPE", (hma100 > hma100.shift(1)).fillna(False).to_numpy(float)))
    strats.append(("ZeroLag_Other", "HMA_150_B5", hysteresis_price_vs_ma(c, ind.hma(c, 150), 0.05).astype(float)))
    strats.append(("ZeroLag_Other", "KAMA_20", hysteresis_price_vs_ma(c, ind.kama(c, 20, 2, 30), 0.0).astype(float)))
    strats.append(("ZeroLag_Other", "KAMA_50_B5", hysteresis_price_vs_ma(c, ind.kama(c, 50, 2, 30), 0.05).astype(float)))
    strats.append(("ZeroLag_Other", "HYB_ST_ZLEMA150_B5", np.where(
        st_dir.astype(int) + hysteresis_price_vs_ma(c, ind.zlema(c, 150), 0.05).astype(int) == 2, 1.0,
        np.where(st_dir.astype(int) + hysteresis_price_vs_ma(c, ind.zlema(c, 150), 0.05).astype(int) == 1, 0.5, 0.0)
    )))
    strats.append(("ZeroLag_Other", "HYB_ST_EMA150_B5", np.where(
        st_dir.astype(int) + hysteresis_price_vs_ma(c, ind.ema(c, 150), 0.05).astype(int) == 2, 1.0,
        np.where(st_dir.astype(int) + hysteresis_price_vs_ma(c, ind.ema(c, 150), 0.05).astype(int) == 1, 0.5, 0.0)
    )))
    return strats


# --------------------------------------------------------------------------- Track 2: Dividend Low-Vol Mean Reversion
def state_machine_oscillator(
    osc: pd.Series,
    *,
    buy_th: float,
    sell_th: float,
    w_low: float,
    w_mid: float,
    w_high: float,
    mid_reset: Optional[tuple[float, float]] = None,
    start_w: float = 0.7,
) -> np.ndarray:
    """Strictly causal mean-reversion state machine: oversold -> w_high, overbought -> w_low."""
    vals = osc.to_numpy(float)
    out = np.full(len(vals), start_w, dtype=float)
    cur = start_w
    for i, v in enumerate(vals):
        if np.isnan(v):
            out[i] = cur
            continue
        if v <= buy_th:
            cur = w_high
        elif v >= sell_th:
            cur = w_low
        elif mid_reset is not None and mid_reset[0] <= v <= mid_reset[1]:
            cur = w_mid
        out[i] = cur
    return out


def build_dlv_mean_reversion_strategies(ohlc: pd.DataFrame) -> list[tuple[str, str, np.ndarray]]:
    """Pre-registered mean-reversion & reverse-MA strategies for A-share Dividend Low-Vol."""
    c = ohlc["Close"]
    h = ohlc["High"]
    l = ohlc["Low"]

    rsi2 = ind.rsi_wilder(c, 2)
    rsi6 = ind.rsi_wilder(c, 6)
    rsi14 = ind.rsi_wilder(c, 14)
    kdf = ind.kdj(h, l, c, n=9, m1=3, m2=3)
    bz20 = ind.bollinger_zscore(c, 20)
    bz60 = ind.bollinger_zscore(c, 60)

    # Weekly Bollinger z-score forward-filled cleanly on week-end closes (no lookahead)
    wk_close = c.resample("W-FRI").last().dropna()
    wk_bz = ind.bollinger_zscore(wk_close, 20).reindex(c.index, method="ffill")

    sma20 = c.rolling(20, min_periods=20).mean()
    sma60 = c.rolling(60, min_periods=60).mean()
    sma120 = c.rolling(120, min_periods=120).mean()
    sma150 = c.rolling(150, min_periods=150).mean()

    bias60 = c / sma60 - 1.0
    bias120 = c / sma120 - 1.0
    bias150 = c / sma150 - 1.0

    # Connors RSI(2): buy <10, exit >70 or close > 5d SMA
    sma5 = c.rolling(5, min_periods=5).mean().to_numpy(float)
    r2_v = rsi2.to_numpy(float)
    c_v = c.to_numpy(float)
    w_rsi2 = np.zeros(len(c), dtype=float)
    cur = 0.0
    for i in range(len(c)):
        if not np.isnan(r2_v[i]) and not np.isnan(sma5[i]):
            if r2_v[i] < 10.0:
                cur = 1.0
            elif c_v[i] > sma5[i] or r2_v[i] > 85.0:
                cur = 0.0
        w_rsi2[i] = cur

    strats: list[tuple[str, str, np.ndarray]] = [
        ("Baseline", "BH", np.ones(len(c), dtype=float)),
        # Family A: RSI
        ("RSI", "RSI2_CONNORS_BIN", w_rsi2),
        ("RSI", "RSI6_20_80_BIN", state_machine_oscillator(rsi6, buy_th=20, sell_th=80, w_low=0.0, w_mid=0.0, w_high=1.0, start_w=1.0)),
        ("RSI", "RSI14_30_70_BIN", state_machine_oscillator(rsi14, buy_th=30, sell_th=70, w_low=0.0, w_mid=0.0, w_high=1.0, start_w=1.0)),
        ("RSI", "RSI6_CORE_70", state_machine_oscillator(rsi6, buy_th=20, sell_th=80, w_low=0.40, w_mid=0.70, w_high=1.0, mid_reset=(45, 55), start_w=0.70)),
        ("RSI", "RSI14_CORE_70", state_machine_oscillator(rsi14, buy_th=35, sell_th=70, w_low=0.40, w_mid=0.70, w_high=1.0, mid_reset=(48, 52), start_w=0.70)),
        # Family B: KDJ
        ("KDJ", "KDJ_J_10_90_BIN", state_machine_oscillator(kdf["J"], buy_th=10, sell_th=90, w_low=0.0, w_mid=0.0, w_high=1.0, start_w=1.0)),
        ("KDJ", "KDJ_K_20_80_BIN", state_machine_oscillator(kdf["K"], buy_th=20, sell_th=80, w_low=0.0, w_mid=0.0, w_high=1.0, start_w=1.0)),
        ("KDJ", "KDJ_J_CORE_70", state_machine_oscillator(kdf["J"], buy_th=10, sell_th=90, w_low=0.40, w_mid=0.70, w_high=1.0, mid_reset=(40, 60), start_w=0.70)),
        # Family C: Bollinger Bands (Daily 20, Daily 60, Weekly 20)
        ("Bollinger", "BOLL_D20_BIN", state_machine_oscillator(bz20, buy_th=-1.8, sell_th=1.8, w_low=0.0, w_mid=0.0, w_high=1.0, start_w=1.0)),
        ("Bollinger", "BOLL_D20_CORE_70", state_machine_oscillator(bz20, buy_th=-1.5, sell_th=1.5, w_low=0.40, w_mid=0.70, w_high=1.0, mid_reset=(-0.2, 0.2), start_w=0.70)),
        ("Bollinger", "BOLL_D60_CORE_70", state_machine_oscillator(bz60, buy_th=-1.5, sell_th=1.5, w_low=0.40, w_mid=0.70, w_high=1.0, mid_reset=(-0.2, 0.2), start_w=0.70)),
        ("Bollinger", "BOLL_W20_CORE_70", state_machine_oscillator(wk_bz, buy_th=-1.8, sell_th=1.8, w_low=0.50, w_mid=0.70, w_high=1.0, mid_reset=(-0.2, 0.2), start_w=0.70)),
        # Family D: Reverse Moving Averages & Bias Core-Tilt ("均线反策略")
        ("Reverse_MA", "REV_MA20_BIN", (c < sma20).fillna(True).to_numpy(float)),
        ("Reverse_MA", "REV_MA60_BIN", (c < sma60).fillna(True).to_numpy(float)),
        ("Reverse_MA", "REV_MA120_BIN", (c < sma120).fillna(True).to_numpy(float)),
        ("Reverse_MA", "REV_MA150_BIN", (c < sma150).fillna(True).to_numpy(float)),
        ("Reverse_MA", "REV_MA60_B3_BIN", (~hysteresis_price_vs_ma(c, sma60, 0.03)).astype(float)),
        ("Reverse_MA", "REV_MA150_B5_BIN", (~hysteresis_price_vs_ma(c, sma150, 0.05)).astype(float)),
        ("Reverse_MA", "REV_MA120_CORE_70", np.where((c < sma120).fillna(True), 1.0, 0.50)),
        ("Reverse_MA", "REV_MA150_CORE_70", np.where((c < sma150).fillna(True), 1.0, 0.50)),
        ("Bias_Core", "BIAS_MA60_5PCT_CORE", state_machine_oscillator(bias60, buy_th=-0.05, sell_th=0.05, w_low=0.40, w_mid=0.70, w_high=1.0, mid_reset=(-0.01, 0.01), start_w=0.70)),
        ("Bias_Core", "BIAS_MA120_6PCT_CORE", state_machine_oscillator(bias120, buy_th=-0.06, sell_th=0.06, w_low=0.40, w_mid=0.70, w_high=1.0, mid_reset=(-0.01, 0.01), start_w=0.70)),
        ("Bias_Core", "BIAS_MA150_8PCT_CORE", state_machine_oscillator(bias150, buy_th=-0.08, sell_th=0.08, w_low=0.40, w_mid=0.70, w_high=1.0, mid_reset=(-0.01, 0.01), start_w=0.70)),
    ]
    return strats


def compute_mr_conditional_returns(name: str, ohlc: pd.DataFrame, start: str, end: str) -> list[dict[str, Any]]:
    """Measure conditional forward 5d/20d/60d/120d returns for oversold vs overbought zones."""
    c = ohlc["Close"]
    h = ohlc["High"]
    l = ohlc["Low"]
    rsi6 = ind.rsi_wilder(c, 6)
    rsi14 = ind.rsi_wilder(c, 14)
    kdj_j = ind.kdj(h, l, c, 9, 3, 3)["J"]
    bz20 = ind.bollinger_zscore(c, 20)
    bias120 = c / c.rolling(120).mean() - 1.0
    bias150 = c / c.rolling(150).mean() - 1.0

    fwd5 = c.shift(-5) / c - 1.0
    fwd20 = c.shift(-20) / c - 1.0
    fwd60 = c.shift(-60) / c - 1.0
    fwd120 = c.shift(-120) / c - 1.0

    sl = (c.index >= pd.Timestamp(start)) & (c.index <= pd.Timestamp(end))
    specs = [
        ("ALL", "全部交易日", pd.Series(True, index=c.index)),
        ("RSI6", "超卖 RSI(6)<20", rsi6 < 20),
        ("RSI6", "超买 RSI(6)>80", rsi6 > 80),
        ("RSI14", "超卖 RSI(14)<30", rsi14 < 30),
        ("RSI14", "超买 RSI(14)>70", rsi14 > 70),
        ("KDJ_J", "超卖 J<10", kdj_j < 10),
        ("KDJ_J", "超买 J>90", kdj_j > 90),
        ("BOLL20", "下轨 Z<-1.5", bz20 < -1.5),
        ("BOLL20", "上轨 Z>+1.5", bz20 > 1.5),
        ("MA120", "低于120日线", bias120 < 0),
        ("MA120", "高于120日线", bias120 > 0),
        ("BIAS120", "深跌乖离<-6%", bias120 < -0.06),
        ("BIAS120", "过热乖离>+6%", bias120 > 0.06),
        ("BIAS150", "深跌乖离<-8%", bias150 < -0.08),
        ("BIAS150", "过热乖离>+8%", bias150 > 0.08),
    ]
    rows = []
    for ind_nm, zone_nm, mask in specs:
        m = mask.fillna(False) & sl
        idx = c.index[m]
        rows.append(
            {
                "asset": name,
                "window": f"{start}..{end}",
                "indicator": ind_nm,
                "zone": zone_nm,
                "days": int(len(idx)),
                "share": float(len(idx) / max(int(sl.sum()), 1)),
                "fwd5_mean": float(fwd5.loc[idx].mean()),
                "fwd20_mean": float(fwd20.loc[idx].mean()),
                "fwd60_mean": float(fwd60.loc[idx].mean()),
                "fwd120_mean": float(fwd120.loc[idx].mean()),
                "fwd60_win_rate": float((fwd60.loc[idx].dropna() > 0).mean()) if fwd60.loc[idx].notna().any() else np.nan,
                "fwd120_win_rate": float((fwd120.loc[idx].dropna() > 0).mean()) if fwd120.loc[idx].notna().any() else np.nan,
            }
        )
    return rows


def run_budget_neutral_mr_dca(
    ohlc: pd.DataFrame,
    start: str,
    end: str,
    *,
    cost: float = 0.001,
    cash_annual: float = 0.02,
) -> list[dict[str, Any]]:
    """Budget-neutral monthly DCA (exact same 1.0/month salary inflow!) comparing plain vs MR-timed deployment."""
    c_full = ohlc["Close"]
    rsi14 = ind.rsi_wilder(c_full, 14)
    bz20 = ind.bollinger_zscore(c_full, 20)
    bias120 = c_full / c_full.rolling(120).mean() - 1.0
    kdj_j = ind.kdj(ohlc["High"], ohlc["Low"], c_full, 9, 3, 3)["J"]

    sl = c_full.loc[start:end]
    dates = pd.DatetimeIndex(sl.index)
    vals = sl.to_numpy(float)
    ym = dates.year * 12 + dates.month
    first_idx = np.flatnonzero(np.r_[True, ym[1:] != ym[:-1]])
    day_diff = np.zeros(len(dates), dtype=float)
    day_diff[1:] = (dates[1:] - dates[:-1]).days.to_numpy(float)
    cash_fac = (1.0 + cash_annual) ** (day_diff / 365.25)

    # Pre-aligned signal series (strictly using prior close t-1 when deciding on month-start day t!)
    r14_s = rsi14.shift(1).reindex(dates).to_numpy(float)
    bz_s = bz20.shift(1).reindex(dates).to_numpy(float)
    b120_s = bias120.shift(1).reindex(dates).to_numpy(float)
    j_s = kdj_j.shift(1).reindex(dates).to_numpy(float)

    def sim_dca(name: str, mult_fn: Callable[[int], float]) -> dict[str, Any]:
        # Each month investor receives 1.0 cash into DCA reserve, deploys mult_fn(i) capped by available cash
        # (if mult > 1 and reserve allows, deploys extra saved cash; if mult < 1, saves remainder in 2% cash!)
        units = 0.0
        reserve = 0.0
        total_in = 0.0
        first_set = set(int(x) for x in first_idx)
        max_fl = 0.0
        nav_path = np.zeros(len(dates), dtype=float)
        for i in range(len(dates)):
            if i > 0:
                reserve *= cash_fac[i]
            if i in first_set:
                reserve += 1.0
                total_in += 1.0
                want = mult_fn(i)
                spend = min(reserve, want)
                if spend > 0:
                    units += spend * (1.0 - cost) / vals[i]
                    reserve -= spend
            val = units * vals[i] + reserve
            nav_path[i] = val
            if total_in > 0:
                max_fl = min(max_fl, val / total_in - 1.0)
        end_val = float(nav_path[-1])
        day_off = (dates[-1] - dates[first_idx]).days.to_numpy(float)
        x = fast_xirr(day_off, end_val)
        return {
            "strategy": name,
            "n_months": int(len(first_idx)),
            "total_inflow": float(total_in),
            "terminal_value": end_val,
            "terminal_multiple": float(end_val / total_in),
            "xirr": float(x),
            "max_float_loss": float(max_fl),
            "ending_cash_share": float(reserve / end_val) if end_val > 0 else 0.0,
        }

    return [
        sim_dca("DCA_PLAIN (每月定投1份)", lambda i: 1.0),
        sim_dca("DCA_REV_MA120 (均线下1.5x/上+5%投0.5x)", lambda i: 1.5 if b120_s[i] < 0 else (0.5 if b120_s[i] > 0.05 else 1.0)),
        sim_dca("DCA_RSI14 (RSI<40投1.5x/>65投0.5x)", lambda i: 1.5 if r14_s[i] < 40 else (0.5 if r14_s[i] > 65 else 1.0)),
        sim_dca("DCA_BOLL20 (Z<-1投1.5x/>+1投0.5x)", lambda i: 1.5 if bz_s[i] < -1.0 else (0.5 if bz_s[i] > 1.0 else 1.0)),
        sim_dca("DCA_KDJ_J (J<20投1.5x/>80投0.5x)", lambda i: 1.5 if j_s[i] < 20 else (0.5 if j_s[i] > 80 else 1.0)),
    ]


# --------------------------------------------------------------------------- Main Execution
def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"=== Running {SLUG} ===")

    # ----------------------------------------------------------------------- TRACK 1: BTC & ETH MA FAMILIES
    print("[1/6] Track 1: Evaluating BTC (2015-2026) & zero-tuning ETH (2018-2026) across 42 MA strategies...")
    btc_ohlc = load_parquet_ohlc(BTC_PQ).loc["2014-09-17":"2026-10-01"]
    eth_ohlc = load_parquet_ohlc(ETH_PQ).loc["2017-11-09":"2026-10-01"]
    btc_px = pd.DataFrame({"btc": btc_ohlc["Close"]}, index=btc_ohlc.index)
    eth_px = pd.DataFrame({"eth": eth_ohlc["Close"]}, index=eth_ohlc.index)
    btc_cp = np.ones(len(btc_ohlc), dtype=float)
    eth_cp = np.ones(len(eth_ohlc), dtype=float)
    btc_si = int(btc_ohlc.index.searchsorted(pd.Timestamp("2015-08-01")))
    eth_si = int(eth_ohlc.index.searchsorted(pd.Timestamp("2018-09-01")))

    btc_strats = build_btc_ma_strategies(btc_ohlc)
    eth_strats = build_btc_ma_strategies(eth_ohlc)

    btc_rows = []
    btc_res_map: dict[str, lab.MultiEngineResult] = {}
    for fam, name, w_arr in btc_strats:
        r30 = lab.run_multi_asset_overlay(btc_px, weight_to_signal(w_arr, btc_si), btc_si, 0.003, btc_cp, btc_cp)
        r10 = lab.run_multi_asset_overlay(btc_px, weight_to_signal(w_arr, btc_si), btc_si, 0.001, btc_cp, btc_cp)
        r50 = lab.run_multi_asset_overlay(btc_px, weight_to_signal(w_arr, btc_si), btc_si, 0.005, btc_cp, btc_cp)
        btc_res_map[name] = r30
        mf = summarize_nav(r30, primary_col="btc", ann_days=365)
        me = summarize_nav(r30, primary_col="btc", ann_days=365, start="2015-08-01", end="2020-12-31")
        mm = summarize_nav(r30, primary_col="btc", ann_days=365, start="2021-01-01", end="2026-10-01")
        m10 = summarize_nav(r10, primary_col="btc", ann_days=365)
        m50 = summarize_nav(r50, primary_col="btc", ann_days=365)
        btc_rows.append(
            {
                "family": fam,
                "strategy": name,
                **mf,
                "early_cagr": me["cagr"],
                "early_sharpe": me["sharpe"],
                "early_mdd": me["max_dd"],
                "mature_cagr": mm["cagr"],
                "mature_sharpe": mm["sharpe"],
                "mature_mdd": mm["max_dd"],
                "cagr_10bp": m10["cagr"],
                "sharpe_10bp": m10["sharpe"],
                "cagr_50bp": m50["cagr"],
                "sharpe_50bp": m50["sharpe"],
            }
        )
    btc_df = pd.DataFrame(btc_rows)
    btc_df.to_csv(OUT_DIR / "track1_btc_ma_families.csv", index=False)

    eth_rows = []
    eth_res_map: dict[str, lab.MultiEngineResult] = {}
    for fam, name, w_arr in eth_strats:
        r30 = lab.run_multi_asset_overlay(eth_px, weight_to_signal(w_arr, eth_si), eth_si, 0.003, eth_cp, eth_cp)
        eth_res_map[name] = r30
        mf = summarize_nav(r30, primary_col="eth", ann_days=365)
        mm = summarize_nav(r30, primary_col="eth", ann_days=365, start="2021-01-01", end="2026-10-01")
        eth_rows.append(
            {
                "family": fam,
                "strategy": name,
                **mf,
                "mature_cagr": mm["cagr"],
                "mature_sharpe": mm["sharpe"],
                "mature_mdd": mm["max_dd"],
            }
        )
    eth_df = pd.DataFrame(eth_rows)
    eth_df.to_csv(OUT_DIR / "track1_eth_oos_ma_families.csv", index=False)

    # Track 1 Parameter Neighborhood Grid (Dual SMA vs Dual EMA vs Dual ZLEMA on BTC & ETH)
    print("[2/6] Track 1: Running Dual-MA parameter grids, permutation tests (200 trials), 5Y DCA & annual starts...")
    grid_rows = []
    c_btc = btc_ohlc["Close"]
    c_eth = eth_ohlc["Close"]
    ma_makers = {
        "SMA": lambda s, n: s.rolling(n, min_periods=n).mean(),
        "EMA": ind.ema,
        "ZLEMA": ind.zlema,
        "DEMA": ind.dema,
    }
    for ma_type, fn in ma_makers.items():
        for f_n in [15, 20, 30, 50]:
            for s_n in [50, 100, 150, 200]:
                if f_n >= s_n:
                    continue
                wb = hysteresis_cross_state(fn(c_btc, f_n), fn(c_btc, s_n), 0.0).astype(float)
                we = hysteresis_cross_state(fn(c_eth, f_n), fn(c_eth, s_n), 0.0).astype(float)
                rb = lab.run_multi_asset_overlay(btc_px, weight_to_signal(wb, btc_si), btc_si, 0.003, btc_cp, btc_cp)
                re = lab.run_multi_asset_overlay(eth_px, weight_to_signal(we, eth_si), eth_si, 0.003, eth_cp, eth_cp)
                mb = summarize_nav(rb, primary_col="btc", ann_days=365)
                mbm = summarize_nav(rb, primary_col="btc", ann_days=365, start="2021-01-01", end="2026-10-01")
                me = summarize_nav(re, primary_col="eth", ann_days=365)
                grid_rows.append(
                    {
                        "ma_type": ma_type,
                        "fast": f_n,
                        "slow": s_n,
                        "btc_cagr": mb["cagr"],
                        "btc_sharpe": mb["sharpe"],
                        "btc_mdd": mb["max_dd"],
                        "btc_tpy": mb["trades_per_year"],
                        "btc_mature_cagr": mbm["cagr"],
                        "btc_mature_sharpe": mbm["sharpe"],
                        "eth_cagr": me["cagr"],
                        "eth_sharpe": me["sharpe"],
                        "eth_mdd": me["max_dd"],
                    }
                )
    pd.DataFrame(grid_rows).to_csv(OUT_DIR / "track1_btc_ma_param_grid.csv", index=False)

    # Track 1 Permutation Tests on Top Representatives of Each Family (BTC + ETH)
    btc_w_dict = {nm: w for _, nm, w in btc_strats}
    eth_w_dict = {nm: w for _, nm, w in eth_strats}
    t1_perm_keys = [
        "HYB_ST_MA150_B5",
        "MTF3_100_200_B5",
        "SMA_100_B5",
        "DSMA_20_100",
        "DSMA_30_100",
        "DSMA_50_200",
        "DEMA_X_20_50",
        "DEMA_X_20_100",
        "DEMA_X_30_100",
        "DEMA_X_20_100_B3",
        "TIER3_EMA_50_150_B5",
        "TIER3_EMA_100_200_B5",
        "ZLEMA_100",
        "ZLEMA_100_B5",
        "ZLEMA_150_B5",
        "DZLEMA_30_100",
        "DZLEMA_50_150",
        "TIER3_ZLEMA_50_150_B5",
        "TIER3_ZLEMA_100_200_B5",
        "DEMA_150_B5",
        "DDEMA_50_150",
        "TEMA_150_B5",
        "HMA_150_B5",
        "KAMA_50_B5",
        "HYB_ST_EMA150_B5",
        "HYB_ST_ZLEMA150_B5",
    ]
    t1_perm_rows = []
    for k_i, strat in enumerate(t1_perm_keys):
        pb = circular_shift_perm(btc_px, btc_w_dict[strat], btc_si, cost=0.003, cash_pos=btc_cp, cash_neg=btc_cp, ann_days=365, n_trials=200, seed=1000 + k_i)
        pbm = circular_shift_perm(btc_px, btc_w_dict[strat], btc_si, cost=0.003, cash_pos=btc_cp, cash_neg=btc_cp, ann_days=365, n_trials=200, seed=2000 + k_i, sub_start="2021-01-01", sub_end="2026-10-01")
        pe = circular_shift_perm(eth_px, eth_w_dict[strat], eth_si, cost=0.003, cash_pos=eth_cp, cash_neg=eth_cp, ann_days=365, n_trials=200, seed=3000 + k_i)
        t1_perm_rows.append(
            {
                "strategy": strat,
                "btc_sharpe": pb["obs_sharpe"],
                "btc_p_sharpe": pb["p_sharpe"],
                "btc_mature_sharpe": pbm["obs_sharpe"],
                "btc_mature_p_sharpe": pbm["p_sharpe"],
                "eth_sharpe": pe["obs_sharpe"],
                "eth_p_sharpe": pe["p_sharpe"],
            }
        )
    pd.DataFrame(t1_perm_rows).to_csv(OUT_DIR / "track1_btc_eth_permutation.csv", index=False)

    # Track 1 Rolling 5Y DCA & Annual Starting Years (Top Candidates vs Validated Baselines)
    t1_dca_keys = [
        "BH", "ST_10_3", "HYB_ST_MA150_B5", "MTF3_100_200_B5", "SMA_100_B5",
        "DSMA_20_100", "DSMA_50_200", "DEMA_X_20_100", "DEMA_X_20_50", "DEMA_X_20_100_B3",
        "TIER3_EMA_100_200_B5", "ZLEMA_100_B5", "ZLEMA_150_B5", "DZLEMA_30_100", "TIER3_ZLEMA_100_200_B5",
        "DEMA_150_B5", "DDEMA_50_150", "TEMA_150_B5",
        "HYB_ST_EMA150_B5", "HYB_ST_ZLEMA150_B5", "HMA_150_B5", "KAMA_50_B5",
    ]
    bh_dca = fast_dca_rolling(btc_res_map["BH"].nav, 60, cost=0.003)
    hyb_dca = fast_dca_rolling(btc_res_map["HYB_ST_MA150_B5"].nav, 60, cost=0.003)
    t1_dca_rows = []
    for strat in t1_dca_keys:
        sd = fast_dca_rolling(btc_res_map[strat].nav, 60, cost=0.003)
        m_bh = sd.merge(bh_dca, on=["start", "end"], suffixes=("_s", "_bh"))
        m_hyb = sd.merge(hyb_dca, on=["start", "end"], suffixes=("_s", "_hyb"))
        t1_dca_rows.append(
            {
                "strategy": strat,
                "n_windows": int(len(sd)),
                "median_xirr": float(sd["xirr"].median()),
                "worst_xirr": float(sd["xirr"].min()),
                "median_float_loss": float(sd["max_float_loss"].median()),
                "worst_float_loss": float(sd["max_float_loss"].min()),
                "median_unit_mdd": float(sd["unit_max_dd"].median()),
                "median_dca_ratio": float(sd["dca_ratio"].median()),
                "ratio_beat_bh_share": float((m_bh["dca_ratio_s"] > m_bh["dca_ratio_bh"]).mean()),
                "ratio_beat_hyb_share": float((m_hyb["dca_ratio_s"] > m_hyb["dca_ratio_hyb"]).mean()),
            }
        )
    pd.DataFrame(t1_dca_rows).to_csv(OUT_DIR / "track1_btc_rolling_dca_5y.csv", index=False)

    # ----------------------------------------------------------------------- TRACK 2: DIVIDEND LOW-VOL MEAN REVERSION
    print("[3/6] Track 2: Computing conditional oversold/overbought forward returns on H20269, 510880, 512890...")
    h20269_ohlc = load_csindex_ohlc("H20269").loc["2013-01-01":"2026-10-15"]
    etf510880_ohlc = load_tickflow_json(TF_CACHE / "tickflow_forward_588000_588080_510880.json", "510880.SH").loc["2013-01-01":"2026-10-15"]
    etf512890_ohlc = load_tickflow_json(TF_CACHE / "tickflow_forward_512890_512040_513010.json", "512890.SH").loc["2019-01-01":"2026-10-15"]
    h00300_ohlc = load_csindex_ohlc("H00300").loc["2013-01-01":"2026-10-15"]
    etf510500_ohlc = load_tickflow_json(TF_CACHE / "tickflow_forward_510050_510300_510500.json", "510500.SH").loc["2013-01-01":"2026-10-15"]
    bond_s = load_parquet_ohlc(BOND_CN_PQ)["Close"]

    cond_rows = []
    cond_rows.extend(compute_mr_conditional_returns("H20269_全期", h20269_ohlc, "2014-08-01", "2026-10-15"))
    cond_rows.extend(compute_mr_conditional_returns("H20269_前期14_19", h20269_ohlc, "2014-08-01", "2019-12-31"))
    cond_rows.extend(compute_mr_conditional_returns("H20269_后期20_26", h20269_ohlc, "2020-01-02", "2026-10-15"))
    cond_rows.extend(compute_mr_conditional_returns("510880_红利ETF", etf510880_ohlc, "2014-08-01", "2026-10-15"))
    cond_rows.extend(compute_mr_conditional_returns("512890_红利低波ETF", etf512890_ohlc, "2020-01-02", "2026-10-15"))
    pd.DataFrame(cond_rows).to_csv(OUT_DIR / "track2_dlv_conditional_returns.csv", index=False)

    print("[4/6] Track 2: Backtesting 24 Mean-Reversion & Reverse-MA strategies + matched-exposure controls...")
    t2_rows = []
    h20269_res_map: dict[str, lab.MultiEngineResult] = {}
    h20269_w_map: dict[str, np.ndarray] = {}
    etf510880_w_map: dict[str, np.ndarray] = {}
    etf512890_w_map: dict[str, np.ndarray] = {}

    for asset_label, ohlc_df, win_start, has_early in [
        ("H20269_红利低波全收益", h20269_ohlc, "2014-08-01", True),
        ("510880_红利ETF实盘", etf510880_ohlc, "2014-08-01", True),
        ("512890_红利低波ETF实盘", etf512890_ohlc, "2020-01-02", False),
        ("H00300_沪深300对照", h00300_ohlc, "2014-08-01", True),
        ("510500_中证500对照", etf510500_ohlc, "2014-08-01", True),
    ]:
        px_df = pd.DataFrame({"a": ohlc_df["Close"]}, index=ohlc_df.index)
        s_i = int(ohlc_df.index.searchsorted(pd.Timestamp(win_start)))
        cp, cn = ov.calendar_cash_factors(ohlc_df.index, np.full(len(ohlc_df), 0.02), 0.0)
        strats = build_dlv_mean_reversion_strategies(ohlc_df)

        # Also add fixed 50% and 70% benchmarks
        for fix_w, fix_nm in [(0.50, "FIX_50_Q"), (0.70, "FIX_70_Q")]:
            r_fix = lab.run_multi_asset_overlay(
                px_df, lab.fixed_weight_signal([fix_w], ohlc_df.index, s_i, freq="Q"), s_i, 0.001, cp, cn
            )
            mf = summarize_nav(r_fix, primary_col="a", ann_days=252)
            row = {
                "asset": asset_label, "family": "Fixed_Control", "strategy": fix_nm, **mf,
                "matched_fixed_cagr": mf["cagr"], "matched_fixed_sharpe": mf["sharpe"], "matched_fixed_mdd": mf["max_dd"],
                "delta_cagr_vs_matched": 0.0, "delta_sharpe_vs_matched": 0.0,
                "cagr_30bp": np.nan, "sharpe_30bp": np.nan,
            }
            if has_early:
                m_er = summarize_nav(r_fix, primary_col="a", ann_days=252, start="2014-08-01", end="2019-12-31")
                m_ex = summarize_nav(r_fix, primary_col="a", ann_days=252, start="2016-01-04", end="2026-10-15")
                m_mo = summarize_nav(r_fix, primary_col="a", ann_days=252, start="2020-01-02", end="2026-10-15")
                m_15 = summarize_nav(r_fix, primary_col="a", ann_days=252, start="2015-06-01", end="2015-09-30")
                m_18 = summarize_nav(r_fix, primary_col="a", ann_days=252, start="2018-01-02", end="2018-12-28")
                row.update({
                    "early14_19_cagr": m_er["cagr"], "early14_19_sharpe": m_er["sharpe"], "early14_19_mdd": m_er["max_dd"],
                    "ex15_cagr": m_ex["cagr"], "ex15_sharpe": m_ex["sharpe"], "ex15_mdd": m_ex["max_dd"],
                    "mod20_26_cagr": m_mo["cagr"], "mod20_26_sharpe": m_mo["sharpe"], "mod20_26_mdd": m_mo["max_dd"],
                    "crash2015_ret": m_15["terminal_multiple"] - 1.0, "crash2015_mdd": m_15["max_dd"],
                    "bear2018_ret": m_18["terminal_multiple"] - 1.0, "bear2018_mdd": m_18["max_dd"],
                })
            t2_rows.append(row)

        for fam, nm, w_arr in strats:
            r10 = lab.run_multi_asset_overlay(px_df, weight_to_signal(w_arr, s_i), s_i, 0.001, cp, cn)
            r30 = lab.run_multi_asset_overlay(px_df, weight_to_signal(w_arr, s_i), s_i, 0.003, cp, cn)
            if asset_label == "H20269_红利低波全收益":
                h20269_res_map[nm] = r10
                h20269_w_map[nm] = w_arr
            elif asset_label == "510880_红利ETF实盘":
                etf510880_w_map[nm] = w_arr
            elif asset_label == "512890_红利低波ETF实盘":
                etf512890_w_map[nm] = w_arr

            mf = summarize_nav(r10, primary_col="a", ann_days=252)
            m30 = summarize_nav(r30, primary_col="a", ann_days=252)
            # Fair matched-exposure fixed quarterly benchmark!
            exp_w = max(0.0, min(1.0, mf["avg_exposure"]))
            r_match = lab.run_multi_asset_overlay(
                px_df, lab.fixed_weight_signal([exp_w], ohlc_df.index, s_i, freq="Q"), s_i, 0.001, cp, cn
            )
            mm_fix = summarize_nav(r_match, primary_col="a", ann_days=252)
            row = {
                "asset": asset_label,
                "family": fam,
                "strategy": nm,
                **mf,
                "matched_fixed_cagr": mm_fix["cagr"],
                "matched_fixed_sharpe": mm_fix["sharpe"],
                "matched_fixed_mdd": mm_fix["max_dd"],
                "delta_cagr_vs_matched": mf["cagr"] - mm_fix["cagr"],
                "delta_sharpe_vs_matched": mf["sharpe"] - mm_fix["sharpe"],
                "cagr_30bp": m30["cagr"],
                "sharpe_30bp": m30["sharpe"],
            }
            if has_early:
                m_er = summarize_nav(r10, primary_col="a", ann_days=252, start="2014-08-01", end="2019-12-31")
                m_ex = summarize_nav(r10, primary_col="a", ann_days=252, start="2016-01-04", end="2026-10-15")
                m_mo = summarize_nav(r10, primary_col="a", ann_days=252, start="2020-01-02", end="2026-10-15")
                m_15 = summarize_nav(r10, primary_col="a", ann_days=252, start="2015-06-01", end="2015-09-30")
                m_18 = summarize_nav(r10, primary_col="a", ann_days=252, start="2018-01-02", end="2018-12-28")
                row.update({
                    "early14_19_cagr": m_er["cagr"], "early14_19_sharpe": m_er["sharpe"], "early14_19_mdd": m_er["max_dd"],
                    "ex15_cagr": m_ex["cagr"], "ex15_sharpe": m_ex["sharpe"], "ex15_mdd": m_ex["max_dd"],
                    "mod20_26_cagr": m_mo["cagr"], "mod20_26_sharpe": m_mo["sharpe"], "mod20_26_mdd": m_mo["max_dd"],
                    "crash2015_ret": m_15["terminal_multiple"] - 1.0, "crash2015_mdd": m_15["max_dd"],
                    "bear2018_ret": m_18["terminal_multiple"] - 1.0, "bear2018_mdd": m_18["max_dd"],
                })
            t2_rows.append(row)
    t2_df = pd.DataFrame(t2_rows)
    t2_df.to_csv(OUT_DIR / "track2_dlv_mean_reversion_summary.csv", index=False)

    # Track 2 Bond-Paired Mean Reversion vs Fixed 70/30 & 50/50 Bond Portfolio (2014-08..2026-09)
    print("[5/6] Track 2: Testing Bond-paired MR tilt, permutation tests (200 trials), param grid & MR-DCA...")
    common_b_idx = h20269_ohlc.index.intersection(bond_s.index)
    bond_px = pd.DataFrame(
        {"dlv": h20269_ohlc["Close"].reindex(common_b_idx), "bond": bond_s.reindex(common_b_idx)},
        index=common_b_idx,
    )
    b_si = int(common_b_idx.searchsorted(pd.Timestamp("2014-08-01")))
    b_cp, b_cn = ov.calendar_cash_factors(common_b_idx, np.full(len(common_b_idx), 0.02), 0.0)
    bond_compare_rows = []
    for nm, sig_fn in [
        ("DLV_BH (100%红利低波)", lab.fixed_weight_signal([1.0, 0.0], common_b_idx, b_si, freq="NONE")),
        ("DLV70_BOND30_Q (固定70%红利+30%国债季调)", lab.fixed_weight_signal([0.70, 0.30], common_b_idx, b_si, freq="Q")),
        ("DLV50_BOND50_Q (固定50%红利+50%国债季调)", lab.fixed_weight_signal([0.50, 0.50], common_b_idx, b_si, freq="Q")),
        ("RSI14_CORE_BOND (RSI底仓70%余仓换国债)", two_asset_signal(pd.Series(h20269_w_map["RSI14_CORE_70"], index=h20269_ohlc.index).reindex(common_b_idx).to_numpy(float), b_si)),
        ("BOLL_D20_CORE_BOND (布林底仓70%余仓换国债)", two_asset_signal(pd.Series(h20269_w_map["BOLL_D20_CORE_70"], index=h20269_ohlc.index).reindex(common_b_idx).to_numpy(float), b_si)),
        ("BIAS_MA120_CORE_BOND (120日乖离底仓余仓换国债)", two_asset_signal(pd.Series(h20269_w_map["BIAS_MA120_6PCT_CORE"], index=h20269_ohlc.index).reindex(common_b_idx).to_numpy(float), b_si)),
        ("REV_MA120_CORE_BOND (120日反均线100/50余仓换国债)", two_asset_signal(pd.Series(h20269_w_map["REV_MA120_CORE_70"], index=h20269_ohlc.index).reindex(common_b_idx).to_numpy(float), b_si)),
    ]:
        rb = lab.run_multi_asset_overlay(bond_px, sig_fn, b_si, 0.001, b_cp, b_cn)
        mf = summarize_nav(rb, primary_col="dlv", ann_days=252)
        mer = summarize_nav(rb, primary_col="dlv", ann_days=252, start="2014-08-01", end="2019-12-31")
        mmo = summarize_nav(rb, primary_col="dlv", ann_days=252, start="2020-01-02", end="2026-09-30")
        bond_compare_rows.append(
            {
                "strategy": nm,
                **mf,
                "early14_19_cagr": mer["cagr"],
                "early14_19_sharpe": mer["sharpe"],
                "early14_19_mdd": mer["max_dd"],
                "mod20_26_cagr": mmo["cagr"],
                "mod20_26_sharpe": mmo["sharpe"],
                "mod20_26_mdd": mmo["max_dd"],
            }
        )
    pd.DataFrame(bond_compare_rows).to_csv(OUT_DIR / "track2_dlv_bond_paired.csv", index=False)

    # Track 2 Circular-Shift Permutation Tests (Full, Early 14-19, Ex-15, Modern 20-26, 510880, 512890)
    t2_perm_keys = [
        "RSI6_20_80_BIN",
        "RSI14_30_70_BIN",
        "RSI14_CORE_70",
        "KDJ_J_10_90_BIN",
        "KDJ_J_CORE_70",
        "BOLL_D20_BIN",
        "BOLL_D20_CORE_70",
        "BOLL_W20_CORE_70",
        "REV_MA60_BIN",
        "REV_MA120_BIN",
        "REV_MA150_B5_BIN",
        "REV_MA120_CORE_70",
        "BIAS_MA60_5PCT_CORE",
        "BIAS_MA120_6PCT_CORE",
        "BIAS_MA150_8PCT_CORE",
    ]
    h_px = pd.DataFrame({"a": h20269_ohlc["Close"]}, index=h20269_ohlc.index)
    h_si = int(h20269_ohlc.index.searchsorted(pd.Timestamp("2014-08-01")))
    h_cp, h_cn = ov.calendar_cash_factors(h20269_ohlc.index, np.full(len(h20269_ohlc), 0.02), 0.0)

    e510_px = pd.DataFrame({"a": etf510880_ohlc["Close"]}, index=etf510880_ohlc.index)
    e510_si = int(etf510880_ohlc.index.searchsorted(pd.Timestamp("2014-08-01")))
    e510_cp, e510_cn = ov.calendar_cash_factors(etf510880_ohlc.index, np.full(len(etf510880_ohlc), 0.02), 0.0)

    e512_px = pd.DataFrame({"a": etf512890_ohlc["Close"]}, index=etf512890_ohlc.index)
    e512_si = int(etf512890_ohlc.index.searchsorted(pd.Timestamp("2020-01-02")))
    e512_cp, e512_cn = ov.calendar_cash_factors(etf512890_ohlc.index, np.full(len(etf512890_ohlc), 0.02), 0.0)

    t2_perm_rows = []
    for k_i, strat in enumerate(t2_perm_keys):
        p_full = circular_shift_perm(h_px, h20269_w_map[strat], h_si, cost=0.001, cash_pos=h_cp, cash_neg=h_cn, ann_days=252, n_trials=200, seed=4000 + k_i)
        p_er = circular_shift_perm(h_px, h20269_w_map[strat], h_si, cost=0.001, cash_pos=h_cp, cash_neg=h_cn, ann_days=252, n_trials=200, seed=4500 + k_i, sub_start="2014-08-01", sub_end="2019-12-31")
        p_ex = circular_shift_perm(h_px, h20269_w_map[strat], h_si, cost=0.001, cash_pos=h_cp, cash_neg=h_cn, ann_days=252, n_trials=200, seed=5000 + k_i, sub_start="2016-01-04", sub_end="2026-10-15")
        p_510 = circular_shift_perm(e510_px, etf510880_w_map[strat], e510_si, cost=0.001, cash_pos=e510_cp, cash_neg=e510_cn, ann_days=252, n_trials=200, seed=5500 + k_i)
        p_512 = circular_shift_perm(e512_px, etf512890_w_map[strat], e512_si, cost=0.001, cash_pos=e512_cp, cash_neg=e512_cn, ann_days=252, n_trials=200, seed=6000 + k_i)
        t2_perm_rows.append(
            {
                "strategy": strat,
                "h20269_full_sharpe": p_full["obs_sharpe"],
                "h20269_full_p": p_full["p_sharpe"],
                "h20269_early_sharpe": p_er["obs_sharpe"],
                "h20269_early_p": p_er["p_sharpe"],
                "h20269_ex15_sharpe": p_ex["obs_sharpe"],
                "h20269_ex15_p": p_ex["p_sharpe"],
                "etf510880_sharpe": p_510["obs_sharpe"],
                "etf510880_p": p_510["p_sharpe"],
                "etf512890_sharpe": p_512["obs_sharpe"],
                "etf512890_p": p_512["p_sharpe"],
            }
        )
    pd.DataFrame(t2_perm_rows).to_csv(OUT_DIR / "track2_dlv_permutation.csv", index=False)

    # Track 2 Budget-Neutral Mean-Reversion DCA across H20269, 510880, and 512890
    dca_mr_rows = []
    for label, df_o, s_dt, e_dt in [
        ("H20269_14_26", h20269_ohlc, "2014-08-01", "2026-10-15"),
        ("510880_14_26", etf510880_ohlc, "2014-08-01", "2026-10-15"),
        ("512890_20_26", etf512890_ohlc, "2020-01-02", "2026-10-15"),
    ]:
        for row in run_budget_neutral_mr_dca(df_o, s_dt, e_dt, cost=0.001, cash_annual=0.02):
            dca_mr_rows.append({"asset": label, **row})
    pd.DataFrame(dca_mr_rows).to_csv(OUT_DIR / "track2_dlv_mr_dca.csv", index=False)

    # ----------------------------------------------------------------------- Self-Checks & Manifests
    print("[6/6] Running strict anti-lookahead & cash conservation self-checks...")
    pert_btc = btc_ohlc.copy()
    cut_b = 2000
    pert_btc.iloc[cut_b + 1 :] *= 0.25
    orig_t1 = dict((n, w) for _, n, w in btc_strats)
    pert_t1 = dict((n, w) for _, n, w in build_btc_ma_strategies(pert_btc))
    t1_no_lookahead = all(np.array_equal(orig_t1[k][: cut_b + 1], pert_t1[k][: cut_b + 1]) for k in orig_t1)

    pert_dlv = etf510880_ohlc.copy()
    cut_d = 1500
    pert_dlv.iloc[cut_d + 1 :] *= 0.25
    orig_t2 = dict((n, w) for _, n, w in build_dlv_mean_reversion_strategies(etf510880_ohlc))
    pert_t2 = dict((n, w) for _, n, w in build_dlv_mean_reversion_strategies(pert_dlv))
    # Note: BOLL_W20_CORE_70 resamples to W-FRI, so check strictly before the week containing cut_d
    cut_d_wk = cut_d - 10
    t2_no_lookahead = all(np.array_equal(orig_t2[k][:cut_d_wk], pert_t2[k][:cut_d_wk]) for k in orig_t2)

    max_resid = max(
        max(r.checks["max_cash_residual"] for r in btc_res_map.values()),
        max(r.checks["max_cash_residual"] for r in eth_res_map.values()),
        max(r.checks["max_cash_residual"] for r in h20269_res_map.values()),
    )

    self_checks = {
        "track1_all_42_strategies_no_lookahead_passed": bool(t1_no_lookahead),
        "track2_all_24_strategies_no_lookahead_passed": bool(t2_no_lookahead),
        "max_cash_residual": float(max_resid),
        "cash_conservation_passed": bool(max_resid < 1e-12),
        "data_hashes": {
            "BTC-USD.parquet": sha256_file(BTC_PQ),
            "ETH-USD.parquet": sha256_file(ETH_PQ),
            "csindex_H20269.csv": sha256_file(CSI_CACHE / "csindex_H20269.csv"),
            "tickflow_forward_588000_588080_510880.json": sha256_file(TF_CACHE / "tickflow_forward_588000_588080_510880.json"),
            "tickflow_forward_512890_512040_513010.json": sha256_file(TF_CACHE / "tickflow_forward_512890_512040_513010.json"),
            "511010.SS.parquet": sha256_file(BOND_CN_PQ),
        },
    }
    assert self_checks["track1_all_42_strategies_no_lookahead_passed"]
    assert self_checks["track2_all_24_strategies_no_lookahead_passed"]
    assert self_checks["cash_conservation_passed"]

    (OUT_DIR / "config.json").write_text(json.dumps(CONFIG, ensure_ascii=False, indent=2) + "\n")
    (OUT_DIR / "self_checks.json").write_text(json.dumps(self_checks, ensure_ascii=False, indent=2) + "\n")

    # Print executive summaries
    print("\n=== TRACK 1: BTC MA FAMILIES (30bp, 0% Cash) — SORTED BY SHARPE ===")
    print(
        btc_df.sort_values("sharpe", ascending=False)[
            ["family", "strategy", "cagr", "sharpe", "max_dd", "trades_per_year", "early_sharpe", "mature_cagr", "mature_sharpe", "mature_mdd", "sharpe_50bp"]
        ].head(25).to_string(index=False)
    )
    print("\n=== TRACK 1: ETH ZERO-TUNING OOS (TOP 20 BY SHARPE) ===")
    print(
        eth_df.sort_values("sharpe", ascending=False)[
            ["family", "strategy", "cagr", "sharpe", "max_dd", "trades_per_year", "mature_cagr", "mature_sharpe"]
        ].head(20).to_string(index=False)
    )
    print("\n=== TRACK 1: BTC + ETH PERMUTATION TESTS ===")
    print(pd.DataFrame(t1_perm_rows).to_string(index=False))
    print("\n=== TRACK 1: BTC 5Y ROLLING DCA ===")
    print(pd.DataFrame(t1_dca_rows).to_string(index=False))

    print("\n=== TRACK 2: H20269 CONDITIONAL FORWARD RETURNS (FULL 2014-2026) ===")
    cond_df = pd.DataFrame(cond_rows)
    print(cond_df[cond_df["asset"] == "H20269_全期"][["indicator", "zone", "days", "share", "fwd5_mean", "fwd20_mean", "fwd60_mean", "fwd120_mean", "fwd60_win_rate"]].to_string(index=False))

    print("\n=== TRACK 2: H20269 MEAN REVERSION & REVERSE-MA (10bp, 2% Cash) ===")
    print(
        t2_df[t2_df["asset"] == "H20269_红利低波全收益"][
            ["family", "strategy", "cagr", "sharpe", "max_dd", "avg_exposure", "delta_cagr_vs_matched", "delta_sharpe_vs_matched", "early14_19_sharpe", "ex15_sharpe", "mod20_26_sharpe", "crash2015_ret", "bear2018_ret", "trades_per_year"]
        ].to_string(index=False)
    )
    print("\n=== TRACK 2: REAL 510880 & 512890 TOP STRATEGIES ===")
    print(
        t2_df[t2_df["asset"] == "512890_红利低波ETF实盘"].sort_values("sharpe", ascending=False)[
            ["family", "strategy", "cagr", "sharpe", "max_dd", "avg_exposure", "delta_cagr_vs_matched", "delta_sharpe_vs_matched", "trades_per_year"]
        ].head(15).to_string(index=False)
    )
    print("\n=== TRACK 2: BOND-PAIRED MR TILT VS FIXED BOND PORTFOLIO ===")
    print(pd.DataFrame(bond_compare_rows)[["strategy", "cagr", "sharpe", "max_dd", "early14_19_sharpe", "mod20_26_sharpe", "trades_per_year"]].to_string(index=False))
    print("\n=== TRACK 2: PERMUTATION TESTS (H20269 FULL / EARLY / EX15 / 510880 / 512890) ===")
    print(pd.DataFrame(t2_perm_rows).to_string(index=False))
    print("\n=== TRACK 2: BUDGET-NEUTRAL MR DCA ===")
    print(pd.DataFrame(dca_mr_rows).to_string(index=False))
    print(f"\nAll outputs written to {OUT_DIR}")


if __name__ == "__main__":
    main()
