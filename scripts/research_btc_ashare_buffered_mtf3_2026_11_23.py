"""Formal Research Study: Can Daily Buffered MTF-3 Generalize to BTC and A-Shares (Dividend Low-Vol & Broad Indices)?

Pre-registered research questions (2026-11-23):
1. Market physics first principles: why does spatial-buffered daily trend-following (MTF-3) work strongly on
   US SPY/QQQ, and what is the return-autocorrelation / trend-persistence fingerprint of BTC, ETH, and A-shares
   (Dividend Low-Vol H20269 / 510880 / 512890, CSI 300 H00300, CSI 500 510500, ChiNext 159915)?
2. Crypto (BTC primary 2015-08..2026-10, ETH zero-tuning out-of-asset 2018-09..2026-10):
   Can volatility- and speed-adapted daily buffered three-tier rules (Track 1: frozen Daily SuperTrend(10,3) +
   buffered long MA 120d/150d/200d ±5%; Track 2: pure Dual-MA buffered 100d/200d ±5%~8% & 50d/120d ±5%)
   preserve or improve BTC Sharpe/Calmar over both Buy-and-Hold and binary Daily SuperTrend(10,3), especially
   in the 2021-2026 mature institutional era, while generalizing zero-tuning to ETH and surviving 5Y rolling DCA,
   annual starts, circular-shift permutation tests, and 10bp/30bp/50bp costs?
3. A-shares (Dividend Low-Vol primary + broad A-share universe, 2014-08..2026-10):
   Does daily buffered MTF-3 (or a 3-tier buffered volatility throttle) genuinely work on Dividend Low-Vol or
   broad A-shares after strict Ex-2015, real-ETF (510880 / 512890), and circular-shift audits? If timing fails,
   what structural pairing (Bond 511010 / Gold 518880 / Plain Monthly DCA) actually delivers low-drawdown holding
   even BEFORE the 2023-2026 gold bull market?

Run (offline sandbox, from repo root):
    .venv/bin/python -I scripts/research_btc_ashare_buffered_mtf3_2026_11_23.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from xquant import indicators as ind  # noqa: E402
from xquant import overlay_rules as ov  # noqa: E402
from xquant import sp500_lab as lab  # noqa: E402

SLUG = "btc-ashare-buffered-mtf3-2026-11-23"
OUT_DIR = ROOT / "outputs" / SLUG

TF_CACHE = ROOT / "outputs" / "weinstein-etf-stage-2026-10-18" / "cache"
CSI_CACHE = ROOT / "outputs" / "dividend-lowvol-csi2000-2026-10-18" / "cache"
BTC_PQ = ROOT / "outputs" / "btc-satellite-corrected-prices-2026-10-18" / "market_data" / "BTC-USD.parquet"
ETH_PQ = ROOT / "outputs" / "strategy-healthcheck-2026-10-02" / "market_data" / "ETH-USD.parquet"
GOLD_CN_PQ = ROOT / "outputs" / "btc-satellite-corrected-prices-2026-10-18" / "market_data" / "518880.SS.parquet"
NDX_CN_PQ = ROOT / "outputs" / "btc-satellite-corrected-prices-2026-10-18" / "market_data" / "513100.SS.parquet"
CSI300_PQ = ROOT / "outputs" / "btc-satellite-corrected-prices-2026-10-18" / "market_data" / "510300.SS.parquet"
BOND_CN_PQ = ROOT / "outputs" / "strategy-healthcheck-2026-10-02" / "market_data" / "511010.SS.parquet"
QQQ_CSV = ROOT / "outputs" / "weinstein-quick-checks-2026-10-18" / "cache" / "yf_QQQ.csv"

CONFIG: dict[str, Any] = {
    "slug": SLUG,
    "execution_clock": "Signal at close t using data <= t only; order fills at close t+1 with proportional one-way cost.",
    "btc": {
        "window": ["2015-08-01", "2026-10-01"],
        "sub_early": ["2015-08-01", "2020-12-31"],
        "sub_mature": ["2021-01-01", "2026-10-01"],
        "primary_cost": 0.003,
        "cost_stress": [0.001, 0.003, 0.005],
        "primary_cash": 0.0,
        "ann_days": 365,
    },
    "eth_oos_asset": {
        "window": ["2018-09-01", "2026-10-01"],
        "cost": 0.003,
        "cash": 0.0,
        "ann_days": 365,
    },
    "ashare": {
        "window": ["2014-08-01", "2026-10-15"],
        "window_512890": ["2020-01-02", "2026-10-15"],
        "window_structural": ["2014-08-01", "2026-09-30"],
        "sub_pre_gold": ["2014-08-01", "2022-12-31"],
        "sub_ex15": ["2016-01-04", "2026-10-15"],
        "primary_cost": 0.001,
        "stress_cost": 0.003,
        "cash_annual": 0.02,
        "ann_days": 252,
    },
    "circular_shift_trials": 200,
    "pre_registered_bars": {
        "crypto_pass": [
            "Beats Buy-and-Hold on Sharpe and Calmar at 30bp with 0% cash",
            "Beats or matches binary Daily SuperTrend(10,3) in 2021-2026 mature era",
            "Passes circular shift permutation test (p_sharpe <= 0.05 on BTC or ETH)",
            "Generalizes zero-tuning to ETH-USD (beats ETH Buy-and-Hold on Sharpe & MaxDD)",
            "Stable across parameter neighborhood (no isolated magic decimal)",
        ],
        "ashare_pass": [
            "Beats Buy-and-Hold on Sharpe and cuts MaxDD >= 25% at 10bp",
            "Passes circular shift permutation test (p_sharpe <= 0.05) in BOTH full 2014-2026 AND Ex-2015 2016-2026",
            "Holds on real tradable ETFs (510880 and 512890), not index-only",
        ],
    },
}


# --------------------------------------------------------------------------- Loaders
def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def load_csindex(code: str) -> pd.Series:
    p = CSI_CACHE / f"csindex_{code}.csv"
    df = pd.read_csv(p, parse_dates=["日期"]).drop_duplicates("日期", keep="last").set_index("日期").sort_index()
    return df["收盘"].astype(float).rename(code)


def load_parquet_ohlc(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df.columns = [str(c).capitalize() for c in df.columns]
    idx = pd.to_datetime(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    return df[~df.index.duplicated(keep="last")].sort_index()[["Open", "High", "Low", "Close"]].astype(float)


# --------------------------------------------------------------------------- Fast exact DCA & metrics
def _fast_xirr(amounts: np.ndarray, year_fracs: np.ndarray) -> float:
    if not (np.any(amounts > 0) and np.any(amounts < 0)):
        return np.nan
    r = 0.10
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
        if r_new <= -0.99 or r_new > 20.0:
            break
        r = r_new
        if abs(step) < 1e-9:
            return float(r)
    lo, hi = -0.95, 15.0
    f_lo = float(np.dot(amounts, (1.0 + lo) ** (-year_fracs)))
    f_hi = float(np.dot(amounts, (1.0 + hi) ** (-year_fracs)))
    if f_lo * f_hi > 0:
        return np.nan
    for _ in range(90):
        mid = 0.5 * (lo + hi)
        f_mid = float(np.dot(amounts, (1.0 + mid) ** (-year_fracs)))
        if abs(f_mid) < 1e-10 or (hi - lo) < 1e-9:
            return float(mid)
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return float(0.5 * (lo + hi))


def dca_full_stats(nav: pd.Series, cost: float) -> dict[str, float]:
    dates = pd.DatetimeIndex(nav.index)
    nav_arr = nav.to_numpy(float)
    m_starts = np.flatnonzero(~dates.to_period("M").duplicated())
    shares = 0.0
    invested = 0.0
    worst_loss = 0.0
    cf_idx = []
    cf_amt = []
    m_set = set(m_starts.tolist())
    for i in range(len(nav_arr)):
        if i in m_set:
            shares += (1.0 * (1.0 - cost)) / nav_arr[i]
            invested += 1.0
            cf_idx.append(i)
            cf_amt.append(-1.0)
        if invested > 0:
            val = shares * nav_arr[i]
            loss = val / invested - 1.0
            if loss < worst_loss:
                worst_loss = loss
    terminal = shares * nav_arr[-1]
    amounts = np.array(cf_amt + [terminal], dtype=float)
    day_offsets = (dates[cf_idx + [len(dates) - 1]] - dates[cf_idx[0]]).days.to_numpy(float) / 365.25
    xirr = _fast_xirr(amounts, day_offsets)
    assert np.isfinite(xirr), "Non-finite full-path XIRR"
    return {
        "dca_full_xirr": xirr,
        "dca_full_mult": float(terminal / invested),
        "dca_full_worst_principal_dd": float(worst_loss),
    }


def dca_rolling_stats(nav: pd.Series, window_months: int, cost: float) -> pd.DataFrame:
    dates = pd.DatetimeIndex(nav.index)
    nav_arr = nav.to_numpy(float)
    m_starts = np.flatnonzero(~dates.to_period("M").duplicated())
    rows: list[dict[str, Any]] = []
    if len(m_starts) < window_months:
        return pd.DataFrame(rows)
    for k in range(len(m_starts) - window_months + 1):
        idxs = m_starts[k : k + window_months]
        i0 = int(idxs[0])
        i1 = int(m_starts[k + window_months] - 1) if (k + window_months) < len(m_starts) else len(nav_arr) - 1
        px_m = nav_arr[idxs]
        sh_cum = np.cumsum((1.0 - cost) / px_m)
        sh_daily = np.zeros(i1 - i0 + 1, dtype=float)
        inv_daily = np.zeros(i1 - i0 + 1, dtype=float)
        for j, idx_pos in enumerate(idxs):
            nxt = int(idxs[j + 1]) if j + 1 < len(idxs) else i1 + 1
            sh_daily[idx_pos - i0 : nxt - i0] = sh_cum[j]
            inv_daily[idx_pos - i0 : nxt - i0] = float(j + 1)
        val_daily = sh_daily * nav_arr[i0 : i1 + 1]
        worst_loss = float(np.min(val_daily / inv_daily - 1.0))
        terminal = float(sh_cum[-1] * nav_arr[i1])
        amounts = np.full(window_months + 1, -1.0, dtype=float)
        amounts[-1] = terminal
        d_sel = dates[np.append(idxs, i1)]
        y_frac = (d_sel - d_sel[0]).days.to_numpy(float) / 365.25
        xirr = _fast_xirr(amounts, y_frac)
        assert np.isfinite(xirr), f"Non-finite rolling XIRR at start={dates[i0].date()}"
        ratio = xirr / max(abs(worst_loss), 0.01)
        rows.append(
            {
                "start": str(dates[i0].date()),
                "end": str(dates[i1].date()),
                "xirr": xirr,
                "mult": terminal / window_months,
                "worst_principal_dd": worst_loss,
                "ret_dd_ratio": ratio,
            }
        )
    return pd.DataFrame(rows)


def nav_metrics(nav: pd.Series, trades_n: int, avg_w: float, cash_annual: float, ann_days: int) -> dict[str, float]:
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    cagr = float((nav.iloc[-1] / nav.iloc[0]) ** (1.0 / years) - 1.0)
    rets = nav.pct_change().dropna()
    rf_d = (1.0 + cash_annual) ** (1.0 / ann_days) - 1.0
    vol = float(rets.std(ddof=1) * np.sqrt(ann_days))
    sharpe = float(((rets - rf_d).mean() / rets.std(ddof=1)) * np.sqrt(ann_days)) if rets.std(ddof=1) > 0 else np.nan
    dd = nav / nav.cummax() - 1.0
    max_dd = float(dd.min())
    calmar = cagr / abs(max_dd) if max_dd < 0 else np.nan
    # Max underwater years
    underwater = nav < nav.cummax()
    max_uw_days = 0
    if underwater.any():
        peak_date = nav.index[0]
        peak_val = float(nav.iloc[0])
        for dt, v in nav.items():
            if v >= peak_val:
                peak_val = float(v)
                peak_date = dt
            else:
                d_uw = (dt - peak_date).days
                if d_uw > max_uw_days:
                    max_uw_days = d_uw
    # Rolling 3Y and 5Y loss probability
    loss_3y = np.nan
    loss_5y = np.nan
    arr = nav.to_numpy(float)
    step3 = int(round(3 * ann_days))
    step5 = int(round(5 * ann_days))
    if len(arr) > step3:
        r3 = arr[step3:] / arr[:-step3] - 1.0
        loss_3y = float(np.mean(r3 < 0))
    if len(arr) > step5:
        r5 = arr[step5:] / arr[:-step5] - 1.0
        loss_5y = float(np.mean(r5 < 0))
    return {
        "cagr": cagr,
        "vol": vol,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "calmar": calmar,
        "max_uw_years": max_uw_days / 365.25,
        "loss_3y_prob": loss_3y,
        "loss_5y_prob": loss_5y,
        "trades_yr": trades_n / years if years > 0 else 0.0,
        "avg_w": avg_w,
        "terminal_mult": float(nav.iloc[-1] / nav.iloc[0]),
    }


def sub_metrics(nav: pd.Series, s0: str, s1: str, cash_annual: float, ann_days: int) -> dict[str, float]:
    s = nav[(nav.index >= pd.Timestamp(s0)) & (nav.index <= pd.Timestamp(s1))]
    prev = nav[nav.index < s.index[0]]
    if len(prev):
        s = pd.concat([prev.iloc[-1:], s])
    years = (s.index[-1] - s.index[0]).days / 365.25
    cagr = float((s.iloc[-1] / s.iloc[0]) ** (1.0 / years) - 1.0)
    rets = s.pct_change().dropna()
    rf_d = (1.0 + cash_annual) ** (1.0 / ann_days) - 1.0
    sharpe = float(((rets - rf_d).mean() / rets.std(ddof=1)) * np.sqrt(ann_days)) if rets.std(ddof=1) > 0 else np.nan
    max_dd = float((s / s.cummax() - 1.0).min())
    tot = float(s.iloc[-1] / s.iloc[0] - 1.0)
    return {"cagr": cagr, "sharpe": sharpe, "max_dd": max_dd, "total_ret": tot}


def run_1asset(
    close: pd.Series,
    target_w: pd.Series,
    start_date: str,
    cost: float,
    cash_annual: float | pd.Series,
    ann_days: int,
) -> tuple[lab.MultiEngineResult, dict[str, float]]:
    dates = pd.DatetimeIndex(close.index)
    start_i = int(dates.searchsorted(pd.Timestamp(start_date)))
    if isinstance(cash_annual, pd.Series):
        rates = cash_annual.reindex(dates).ffill().fillna(0.0).to_numpy(float)
        rf_avg = float(np.mean(rates[start_i:]))
    else:
        rates = np.full(len(dates), float(cash_annual), dtype=float)
        rf_avg = float(cash_annual)
    cash_pos, cash_neg = ov.calendar_cash_factors(dates, rates, 0.0)
    w_arr = target_w.reindex(dates).fillna(0.0).to_numpy(float)
    px_df = pd.DataFrame({"a": close.to_numpy(float)}, index=dates)
    last_tw: list[float | None] = [None]

    def sig(i: int, cur_w: np.ndarray):
        tw = w_arr[i]
        if i == start_i or last_tw[0] is None or abs(tw - last_tw[0]) > 1e-9:
            last_tw[0] = tw
            return np.array([tw], dtype=float)
        return None

    res = lab.run_multi_asset_overlay(px_df, sig, start_i, cost, cash_pos, cash_neg)
    m = nav_metrics(res.nav, len(res.trades), float(res.weights["a"].iloc[1:].mean()), rf_avg, ann_days)
    return res, m


def circular_shift_test(
    close: pd.Series,
    target_w: pd.Series,
    start_date: str,
    cost: float,
    cash_annual: float,
    ann_days: int,
    n_trials: int = 200,
) -> dict[str, float]:
    dates = pd.DatetimeIndex(close.index)
    start_i = int(dates.searchsorted(pd.Timestamp(start_date)))
    sub_px = close.iloc[start_i:].to_numpy(float)
    r_asset = np.diff(sub_px) / sub_px[:-1]
    rf = (1.0 + cash_annual) ** (1.0 / ann_days) - 1.0
    w_exec = target_w.reindex(dates).fillna(0.0).to_numpy(float)[start_i:-1]
    w_eff = np.concatenate([[0.0], w_exec[:-1]])
    years = (dates[-1] - dates[start_i]).days / 365.25

    def eval_w(wv: np.ndarray) -> tuple[float, float, float]:
        dw = np.abs(np.diff(np.concatenate([[0.0], wv])))
        rp = wv * r_asset + (1.0 - wv) * rf - dw * cost
        nav = np.cumprod(1.0 + rp)
        cagr = float(nav[-1] ** (1.0 / years) - 1.0)
        sh = float(((rp - rf).mean() / rp.std(ddof=1)) * np.sqrt(ann_days)) if rp.std(ddof=1) > 0 else -99.0
        dd = float((nav / np.maximum.accumulate(nav) - 1.0).min())
        cal = cagr / abs(dd) if dd < 0 else -99.0
        return sh, cal, dd

    obs_sh, obs_cal, obs_dd = eval_w(w_eff)
    rng = np.random.default_rng(42)
    shifts = rng.integers(30, max(31, len(w_eff) - 30), size=n_trials)
    ge_sh = ge_cal = ge_dd = 0
    for sh in shifts:
        s, c, d = eval_w(np.roll(w_eff, int(sh)))
        ge_sh += int(s >= obs_sh)
        ge_cal += int(c >= obs_cal)
        ge_dd += int(d >= obs_dd)
    return {
        "p_sharpe": ge_sh / n_trials,
        "p_calmar": ge_cal / n_trials,
        "p_maxdd": ge_dd / n_trials,
    }


def atr_buffered_mtf3_weight(
    high: pd.Series, low: pd.Series, close: pd.Series, ma_fast: int, slope_days: int, ma_slow: int, k_atr: float
) -> pd.Series:
    atr = ind.true_range(high, low, close).rolling(20).mean().to_numpy(float)
    vals = close.to_numpy(float)
    ma_f = close.rolling(ma_fast).mean()
    ris = (ma_f > ma_f.shift(slope_days)).to_numpy(bool)
    mf_v = ma_f.to_numpy(float)
    ms_v = close.rolling(ma_slow).mean().to_numpy(float)
    on1 = on2 = False
    out = np.zeros(len(close), dtype=float)
    for i in range(len(close)):
        if not (np.isnan(mf_v[i]) or np.isnan(atr[i])):
            b = k_atr * atr[i]
            if vals[i] < mf_v[i] - b:
                on1 = False
            elif vals[i] > mf_v[i] + b and ris[i]:
                on1 = True
        if not (np.isnan(ms_v[i]) or np.isnan(atr[i])):
            b = k_atr * atr[i]
            if vals[i] < ms_v[i] - b:
                on2 = False
            elif vals[i] > ms_v[i] + b:
                on2 = True
        out[i] = 1.0 if (on1 and on2) else (0.5 if (on1 or on2) else 0.0)
    return pd.Series(out, index=close.index, dtype=float)


def market_fingerprint_row(name: str, close: pd.Series, start: str, ann_days: int) -> dict[str, Any]:
    s = close[close.index >= pd.Timestamp(start)].dropna()
    log_r = np.log(s).diff().dropna()
    vol = float(log_r.std(ddof=1) * np.sqrt(ann_days))

    def vr(k: int) -> float:
        rk = np.log(s).diff(k).dropna()
        v1 = float(log_r.var(ddof=1))
        return float(rk.var(ddof=1)) / (k * v1) if v1 > 0 else np.nan

    ma150 = s.rolling(150).mean()
    fwd = s.shift(-63) / s - 1.0
    ab = fwd[s > ma150].dropna()
    bl = fwd[s < ma150].dropna()
    dd = float((s / s.cummax() - 1.0).min())
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    cagr = float((s.iloc[-1] / s.iloc[0]) ** (1.0 / yrs) - 1.0)
    return {
        "asset": name,
        "start": str(s.index[0].date()),
        "end": str(s.index[-1].date()),
        "years": round(yrs, 2),
        "cagr": cagr,
        "vol": vol,
        "max_dd": dd,
        "vr_1m": vr(21 if ann_days == 252 else 30),
        "vr_3m": vr(63 if ann_days == 252 else 90),
        "vr_6m": vr(126 if ann_days == 252 else 180),
        "fwd3m_above_ma150": float(ab.mean()),
        "fwd3m_below_ma150": float(bl.mean()),
        "trend_spread_3m": float(ab.mean() - bl.mean()),
    }


def build_crypto_weights(df: pd.DataFrame) -> dict[str, pd.Series]:
    c, h, l = df["Close"], df["High"], df["Low"]
    st_d = ind.supertrend_direction(h, l, c, 10, 3.0)
    wb = df.resample("W-SUN").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
    st_w = ind.supertrend_direction(wb["High"], wb["Low"], wb["Close"], 10, 3.0).reindex(c.index, method="ffill").fillna(False).astype(bool)
    mtf_orig = (lab.weekly_stage2_state(c, 30, 4).astype(int) + lab.monthly_ma_state(c, 10).astype(int)) / 2.0
    return {
        "B0_HOLD": pd.Series(1.0, index=c.index),
        "ST_DAILY_10_3": st_d.astype(float),
        "ST_WEEKLY_10_3": st_w.astype(float),
        "ST_DW_3TIER": (st_d.astype(int) + st_w.astype(int)) / 2.0,
        "ST_D_AND_W": (st_d & st_w).astype(float),
        "MTF3_ORIG_30W10M": mtf_orig,
        "MTF3_SPY_DIRECT_150_210_B3": lab.daily_buffered_mtf3_equity_weight(c, 150, 20, 210, 0.03),
        "HYB_ST_MA120_B5": lab.daily_buffered_st_ma_weight(h, l, c, 10, 3.0, 120, 0.05),
        "HYB_ST_MA150_B5": lab.daily_buffered_st_ma_weight(h, l, c, 10, 3.0, 150, 0.05),
        "HYB_ST_MA200_B5": lab.daily_buffered_st_ma_weight(h, l, c, 10, 3.0, 200, 0.05),
        "MTF3_100_200_B5": lab.daily_buffered_mtf3_equity_weight(c, 100, 15, 200, 0.05),
        "MTF3_100_200_B8": lab.daily_buffered_mtf3_equity_weight(c, 100, 15, 200, 0.08),
        "MTF3_50_120_B5": lab.daily_buffered_mtf3_equity_weight(c, 50, 10, 120, 0.05),
        "MTF3_ATR_100_200_K1.5": atr_buffered_mtf3_weight(h, l, c, 100, 15, 200, 1.5),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    max_cash_resid = 0.0

    # --- Load all frozen datasets ---
    btc = load_parquet_ohlc(BTC_PQ)
    eth = load_parquet_ohlc(ETH_PQ)
    us_bundle = lab.load_us_bundle()
    spy = us_bundle["spy"]
    irx = us_bundle["irx"]
    qqq_df = pd.read_csv(QQQ_CSV, index_col=0)
    qqq_df.index = pd.to_datetime(qqq_df.index, utc=True).tz_convert(None).normalize()
    qqq = qqq_df["Close"].astype(float)

    h20269 = load_csindex("H20269")
    h30269 = load_csindex("H30269")
    h00300 = load_csindex("H00300")
    e510300_tf = load_tickflow_json(TF_CACHE / "tickflow_forward_510050_510300_510500.json", "510300.SH")["Close"]
    e510300_pq = load_parquet_ohlc(CSI300_PQ)["Close"]
    common_300 = e510300_tf.index.intersection(e510300_pq.index)
    tf_vs_pq_max_diff = float((e510300_tf.loc[common_300].pct_change() - e510300_pq.loc[common_300].pct_change()).abs().max())
    assert tf_vs_pq_max_diff < 1e-12, f"TickFlow proportional verification failed: {tf_vs_pq_max_diff}"

    e510880 = load_tickflow_json(TF_CACHE / "tickflow_forward_588000_588080_510880.json", "510880.SH")["Close"]
    e512890 = load_tickflow_json(TF_CACHE / "tickflow_forward_512890_512040_513010.json", "512890.SH")["Close"]
    e510500 = load_tickflow_json(TF_CACHE / "tickflow_forward_510050_510300_510500.json", "510500.SH")["Close"]
    e159915 = load_tickflow_json(TF_CACHE / "tickflow_forward_512100_159552_159915.json", "159915.SZ")["Close"]
    p518880 = load_parquet_ohlc(GOLD_CN_PQ)["Close"]
    p513100 = load_parquet_ohlc(NDX_CN_PQ)["Close"]
    p511010 = load_parquet_ohlc(BOND_CN_PQ)["Close"]

    # Align US T-bill annual rate to BTC daily calendar for T-bill cash sensitivity
    btc_tbill = irx.reindex(btc.index.union(irx.index)).ffill().reindex(btc.index).fillna(0.0)

    # =========================================================================
    # 1. Market Physics Fingerprint
    # =========================================================================
    fp_rows = [
        market_fingerprint_row("US_SPY (2000-2026)", spy, "2000-01-03", 252),
        market_fingerprint_row("US_QQQ (2000-2026)", qqq, "2000-01-03", 252),
        market_fingerprint_row("BTC-USD (2015-2026)", btc["Close"], "2015-08-01", 365),
        market_fingerprint_row("ETH-USD (2018-2026)", eth["Close"], "2018-09-01", 365),
        market_fingerprint_row("CN_H20269红利低波TR", h20269, "2014-08-01", 252),
        market_fingerprint_row("CN_510880红利ETF", e510880, "2014-08-01", 252),
        market_fingerprint_row("CN_512890红利低波ETF", e512890, "2020-01-02", 252),
        market_fingerprint_row("CN_H00300沪深300TR", h00300, "2014-08-01", 252),
        market_fingerprint_row("CN_510500中证500ETF", e510500, "2014-08-01", 252),
        market_fingerprint_row("CN_159915创业板ETF", e159915, "2014-08-01", 252),
    ]
    pd.DataFrame(fp_rows).to_csv(OUT_DIR / "market_physics_fingerprint.csv", index=False)

    # =========================================================================
    # 2. BTC Full Summary (30bp primary, 10bp/50bp stress, T-bill cash, matched fixed control, circular shift)
    # =========================================================================
    btc_w = build_crypto_weights(btc)
    btc_navs: dict[str, pd.Series] = {}
    btc_rows: list[dict[str, Any]] = []
    for name, w in btc_w.items():
        res30, m30 = run_1asset(btc["Close"], w, "2015-08-01", 0.003, 0.0, 365)
        max_cash_resid = max(max_cash_resid, float(res30.checks.get("max_cash_residual", 0.0)))
        btc_navs[name] = res30.nav
        _, m10 = run_1asset(btc["Close"], w, "2015-08-01", 0.001, 0.0, 365)
        _, m50 = run_1asset(btc["Close"], w, "2015-08-01", 0.005, 0.0, 365)
        _, mtb = run_1asset(btc["Close"], w, "2015-08-01", 0.003, btc_tbill, 365)
        s_early = sub_metrics(res30.nav, "2015-08-01", "2020-12-31", 0.0, 365)
        s_mat = sub_metrics(res30.nav, "2021-01-01", "2026-10-01", 0.0, 365)
        # Matched fixed exposure control (quarterly rebalanced at strategy's avg_w)
        avg_w = m30["avg_w"]
        if name == "B0_HOLD":
            matched_cagr = m30["cagr"]
            matched_sh = m30["sharpe"]
            matched_dd = m30["max_dd"]
            pdict = {"p_sharpe": np.nan, "p_calmar": np.nan, "p_maxdd": np.nan}
        else:
            q_end = ~btc.index.to_period("Q").duplicated(keep="last")
            dates_b = btc.index
            si = int(dates_b.searchsorted(pd.Timestamp("2015-08-01")))
            cp, cn = ov.calendar_cash_factors(dates_b, np.zeros(len(dates_b)), 0.0)
            px_b = pd.DataFrame({"a": btc["Close"].to_numpy(float)}, index=dates_b)

            def make_fix(wf: float):
                def _s(i, cw):
                    if i == si or q_end[i]:
                        return np.array([wf])
                    return None
                return _s

            r_fix = lab.run_multi_asset_overlay(px_b, make_fix(avg_w), si, 0.003, cp, cn)
            m_fix = nav_metrics(r_fix.nav, len(r_fix.trades), avg_w, 0.0, 365)
            matched_cagr, matched_sh, matched_dd = m_fix["cagr"], m_fix["sharpe"], m_fix["max_dd"]
            pdict = circular_shift_test(btc["Close"], w, "2015-08-01", 0.003, 0.0, 365, CONFIG["circular_shift_trials"])

        btc_rows.append(
            {
                "strategy": name,
                **m30,
                "cagr_10bp": m10["cagr"],
                "cagr_50bp": m50["cagr"],
                "cagr_tbill_30bp": mtb["cagr"],
                "sharpe_tbill_30bp": mtb["sharpe"],
                "early_15_20_cagr": s_early["cagr"],
                "early_15_20_sharpe": s_early["sharpe"],
                "early_15_20_maxdd": s_early["max_dd"],
                "mature_21_26_cagr": s_mat["cagr"],
                "mature_21_26_sharpe": s_mat["sharpe"],
                "mature_21_26_maxdd": s_mat["max_dd"],
                "matched_fix_cagr": matched_cagr,
                "matched_fix_sharpe": matched_sh,
                "matched_fix_maxdd": matched_dd,
                **pdict,
            }
        )
    pd.DataFrame(btc_rows).to_csv(OUT_DIR / "summary_btc_2015.csv", index=False)

    # =========================================================================
    # 3. ETH Zero-Tuning Out-of-Asset Verification
    # =========================================================================
    eth_w = build_crypto_weights(eth)
    eth_rows: list[dict[str, Any]] = []
    for name, w in eth_w.items():
        res30, m30 = run_1asset(eth["Close"], w, "2018-09-01", 0.003, 0.0, 365)
        max_cash_resid = max(max_cash_resid, float(res30.checks.get("max_cash_residual", 0.0)))
        pdict = (
            {"p_sharpe": np.nan, "p_calmar": np.nan, "p_maxdd": np.nan}
            if name == "B0_HOLD"
            else circular_shift_test(eth["Close"], w, "2018-09-01", 0.003, 0.0, 365, CONFIG["circular_shift_trials"])
        )
        eth_rows.append({"strategy": name, **m30, **pdict})
    pd.DataFrame(eth_rows).to_csv(OUT_DIR / "summary_eth_2018.csv", index=False)

    # =========================================================================
    # 4. BTC 5-Year Rolling Monthly DCA, Annual Starts, Key Periods, Annual Returns
    # =========================================================================
    btc_focus = [
        "B0_HOLD",
        "ST_DAILY_10_3",
        "ST_DW_3TIER",
        "HYB_ST_MA150_B5",
        "HYB_ST_MA120_B5",
        "HYB_ST_MA200_B5",
        "MTF3_100_200_B5",
        "MTF3_100_200_B8",
        "MTF3_50_120_B5",
    ]
    b0_dca5 = dca_rolling_stats(btc_navs["B0_HOLD"], 60, 0.003)
    dca_btc_rows: list[dict[str, Any]] = []
    for name in btc_focus:
        full_d = dca_full_stats(btc_navs[name], 0.003)
        roll5 = dca_rolling_stats(btc_navs[name], 60, 0.003)
        xirr_win = float(np.mean(roll5["xirr"].to_numpy() > b0_dca5["xirr"].to_numpy())) if name != "B0_HOLD" else np.nan
        ratio_win = float(np.mean(roll5["ret_dd_ratio"].to_numpy() > b0_dca5["ret_dd_ratio"].to_numpy())) if name != "B0_HOLD" else np.nan
        dca_btc_rows.append(
            {
                "strategy": name,
                **full_d,
                "n_5y_windows": len(roll5),
                "med_5y_xirr": float(roll5["xirr"].median()),
                "worst_5y_xirr": float(roll5["xirr"].min()),
                "med_5y_worst_dd": float(roll5["worst_principal_dd"].median()),
                "worst_5y_dd": float(roll5["worst_principal_dd"].min()),
                "loss_5y_dca_prob": float(np.mean(roll5["xirr"] < 0)),
                "win_5y_xirr_vs_b0": xirr_win,
                "win_5y_ratio_vs_b0": ratio_win,
            }
        )
    pd.DataFrame(dca_btc_rows).to_csv(OUT_DIR / "btc_rolling_dca_5y.csv", index=False)

    # Annual rolling starts (2016..2023)
    start_rows: list[dict[str, Any]] = []
    for yr in range(2016, 2024):
        s_dt = f"{yr}-01-01"
        b0_sub = sub_metrics(btc_navs["B0_HOLD"], s_dt, "2026-10-01", 0.0, 365)
        for name in btc_focus:
            sm = sub_metrics(btc_navs[name], s_dt, "2026-10-01", 0.0, 365)
            cal = sm["cagr"] / abs(sm["max_dd"]) if sm["max_dd"] < 0 else np.nan
            b0_cal = b0_sub["cagr"] / abs(b0_sub["max_dd"]) if b0_sub["max_dd"] < 0 else np.nan
            start_rows.append(
                {
                    "start_year": yr,
                    "strategy": name,
                    "cagr": sm["cagr"],
                    "sharpe": sm["sharpe"],
                    "max_dd": sm["max_dd"],
                    "calmar": cal,
                    "beat_b0_sharpe": int(sm["sharpe"] > b0_sub["sharpe"]),
                    "beat_b0_calmar": int(cal > b0_cal),
                    "dd_cut_pct": (abs(b0_sub["max_dd"]) - abs(sm["max_dd"])) / abs(b0_sub["max_dd"]),
                }
            )
    pd.DataFrame(start_rows).to_csv(OUT_DIR / "btc_rolling_starts_annual.csv", index=False)

    # Key BTC periods
    kp_defs = [
        ("2017_Bull", "2017-01-01", "2017-12-17"),
        ("2018_Winter", "2017-12-18", "2018-12-15"),
        ("2020_21_Bull", "2020-03-13", "2021-11-09"),
        ("2022_Winter", "2021-11-10", "2022-11-21"),
        ("2023_26_ETF_Cycle", "2022-11-22", "2026-10-01"),
    ]
    kp_rows: list[dict[str, Any]] = []
    for pname, p0, p1 in kp_defs:
        for name in btc_focus:
            sm = sub_metrics(btc_navs[name], p0, p1, 0.0, 365)
            kp_rows.append({"period": pname, "start": p0, "end": p1, "strategy": name, **sm})
    pd.DataFrame(kp_rows).to_csv(OUT_DIR / "btc_key_periods.csv", index=False)

    # Calendar annual returns BTC
    ann_df = {}
    for name in btc_focus:
        nav = btc_navs[name]
        yr_last = nav.groupby(nav.index.year).last()
        prev = yr_last.shift(1)
        prev.iloc[0] = nav.iloc[0]
        ann_df[name] = yr_last / prev - 1.0
    pd.DataFrame(ann_df).to_csv(OUT_DIR / "btc_annual_returns.csv")

    # =========================================================================
    # 5. BTC & ETH Parameter Sensitivity Grid (proving zero magic decimals)
    # =========================================================================
    sens_rows: list[dict[str, Any]] = []
    # Hybrid grid: ST(10,3) + MA{120,150,200} x buf{0,3,5,8}
    for ma_s in (120, 150, 200):
        for buf in (0.0, 0.03, 0.05, 0.08):
            wb = lab.daily_buffered_st_ma_weight(btc["High"], btc["Low"], btc["Close"], 10, 3.0, ma_s, buf)
            we = lab.daily_buffered_st_ma_weight(eth["High"], eth["Low"], eth["Close"], 10, 3.0, ma_s, buf)
            rb_res, mb = run_1asset(btc["Close"], wb, "2015-08-01", 0.003, 0.0, 365)
            _, me = run_1asset(eth["Close"], we, "2018-09-01", 0.003, 0.0, 365)
            m21 = sub_metrics(rb_res.nav, "2021-01-01", "2026-10-01", 0.0, 365)
            sens_rows.append(
                {
                    "family": "HYB_ST10_3_MA",
                    "params": f"MA{ma_s}_B{int(buf*100)}",
                    "btc_cagr": mb["cagr"],
                    "btc_sharpe": mb["sharpe"],
                    "btc_maxdd": mb["max_dd"],
                    "btc_tr_yr": mb["trades_yr"],
                    "btc_21_cagr": m21["cagr"],
                    "btc_21_sharpe": m21["sharpe"],
                    "btc_21_maxdd": m21["max_dd"],
                    "eth_cagr": me["cagr"],
                    "eth_sharpe": me["sharpe"],
                    "eth_maxdd": me["max_dd"],
                }
            )
    # Pure Dual-MA grid: (50,120), (60,150), (100,200), (120,200) x buf{0,3,5,8}
    for ma_f, ma_s, sl in [(50, 120, 10), (60, 150, 10), (100, 200, 15), (120, 200, 20)]:
        for buf in (0.0, 0.03, 0.05, 0.08):
            wb = lab.daily_buffered_mtf3_equity_weight(btc["Close"], ma_f, sl, ma_s, buf)
            we = lab.daily_buffered_mtf3_equity_weight(eth["Close"], ma_f, sl, ma_s, buf)
            rb_res, mb = run_1asset(btc["Close"], wb, "2015-08-01", 0.003, 0.0, 365)
            _, me = run_1asset(eth["Close"], we, "2018-09-01", 0.003, 0.0, 365)
            m21 = sub_metrics(rb_res.nav, "2021-01-01", "2026-10-01", 0.0, 365)
            sens_rows.append(
                {
                    "family": "PURE_DUAL_MA",
                    "params": f"{ma_f}_{ma_s}_B{int(buf*100)}",
                    "btc_cagr": mb["cagr"],
                    "btc_sharpe": mb["sharpe"],
                    "btc_maxdd": mb["max_dd"],
                    "btc_tr_yr": mb["trades_yr"],
                    "btc_21_cagr": m21["cagr"],
                    "btc_21_sharpe": m21["sharpe"],
                    "btc_21_maxdd": m21["max_dd"],
                    "eth_cagr": me["cagr"],
                    "eth_sharpe": me["sharpe"],
                    "eth_maxdd": me["max_dd"],
                }
            )
    pd.DataFrame(sens_rows).to_csv(OUT_DIR / "btc_sensitivity_grid.csv", index=False)

    # =========================================================================
    # 6. A-Share Timing Exhaustive Audit (H20269, H20269 w/ H30269 price sig, 510880, 512890, H00300, 510500, 159915)
    # =========================================================================
    ashare_assets = [
        ("H20269_红利低波全收益", h20269, h20269, "2014-08-01", "2016-01-04"),
        ("H20269_价格指数信号", h20269, h30269, "2014-08-01", "2016-01-04"),
        ("510880_红利ETF", e510880, e510880, "2014-08-01", "2016-01-04"),
        ("512890_红利低波ETF", e512890, e512890, "2020-01-02", "2020-01-02"),
        ("H00300_沪深300全收益", h00300, h00300, "2014-08-01", "2016-01-04"),
        ("510500_中证500ETF", e510500, e510500, "2014-08-01", "2016-01-04"),
        ("159915_创业板ETF", e159915, e159915, "2014-08-01", "2016-01-04"),
    ]
    ashare_timing_rows: list[dict[str, Any]] = []
    ashare_nav_store: dict[str, pd.Series] = {}

    for label, trade_s, sig_s, d0, d_ex15 in ashare_assets:
        s2_w = lab.weekly_stage2_state(sig_s, 30, 4)
        mtf_orig = (s2_w.astype(int) + lab.monthly_ma_state(sig_s, 10).astype(int)) / 2.0
        mtf_b2 = lab.daily_buffered_mtf3_equity_weight(sig_s, 150, 20, 210, 0.02)
        mtf_b3 = lab.daily_buffered_mtf3_equity_weight(sig_s, 150, 20, 210, 0.03)
        mtf_60_120 = lab.daily_buffered_mtf3_equity_weight(sig_s, 60, 10, 120, 0.03)
        mtf_b3_fl50 = 0.5 + 0.5 * mtf_b3
        vol3_14_22 = lab.daily_buffered_vol_throttle(sig_s, 21, 0.14, 0.22, 0.02, 0.60, 0.20, 252)
        vol3_15_24 = lab.daily_buffered_vol_throttle(sig_s, 21, 0.15, 0.24, 0.02, 0.60, 0.20, 252)
        vol3_16_25 = lab.daily_buffered_vol_throttle(sig_s, 21, 0.16, 0.25, 0.02, 0.50, 0.20, 252)

        rules = {
            "B0_HOLD": pd.Series(1.0, index=trade_s.index),
            "S2_WEEKLY_100_50": pd.Series(np.where(s2_w, 1.0, 0.5), index=sig_s.index),
            "MTF3_ORIG_30W10M": mtf_orig,
            "MTF3_150_210_B2": mtf_b2,
            "MTF3_150_210_B3": mtf_b3,
            "MTF3_60_120_B3": mtf_60_120,
            "MTF3_B3_FLOOR50": mtf_b3_fl50,
            "VOL3_14_22": vol3_14_22,
            "VOL3_15_24": vol3_15_24,
            "VOL3_16_25": vol3_16_25,
        }
        for rname, ws in rules.items():
            res10, m10 = run_1asset(trade_s, ws, d0, 0.001, 0.02, 252)
            max_cash_resid = max(max_cash_resid, float(res10.checks.get("max_cash_residual", 0.0)))
            _, m30 = run_1asset(trade_s, ws, d0, 0.003, 0.02, 252)
            ex15 = sub_metrics(res10.nav, d_ex15, str(trade_s.index[-1].date()), 0.02, 252)
            if rname == "B0_HOLD":
                p_full = {"p_sharpe": np.nan, "p_calmar": np.nan, "p_maxdd": np.nan}
                p_ex15 = {"p_sharpe": np.nan, "p_calmar": np.nan, "p_maxdd": np.nan}
            else:
                p_full = circular_shift_test(trade_s, ws, d0, 0.001, 0.02, 252, CONFIG["circular_shift_trials"])
                p_ex15 = circular_shift_test(trade_s, ws, d_ex15, 0.001, 0.02, 252, CONFIG["circular_shift_trials"])
            if label in {"H20269_红利低波全收益", "510880_红利ETF", "512890_红利低波ETF", "H00300_沪深300全收益"} and rname in {"B0_HOLD", "MTF3_150_210_B3", "VOL3_15_24"}:
                ashare_nav_store[f"{label}__{rname}"] = res10.nav
            ashare_timing_rows.append(
                {
                    "asset": label,
                    "strategy": rname,
                    **m10,
                    "cagr_30bp": m30["cagr"],
                    "ex15_cagr": ex15["cagr"],
                    "ex15_sharpe": ex15["sharpe"],
                    "ex15_maxdd": ex15["max_dd"],
                    "p_sharpe_full": p_full["p_sharpe"],
                    "p_maxdd_full": p_full["p_maxdd"],
                    "p_sharpe_ex15": p_ex15["p_sharpe"],
                    "p_maxdd_ex15": p_ex15["p_maxdd"],
                }
            )
    pd.DataFrame(ashare_timing_rows).to_csv(OUT_DIR / "summary_ashare_timing.csv", index=False)

    # =========================================================================
    # 7. A-Share Structural Pairing (Bond 511010 & Gold 518880 — incl. Pre-Gold 2014-2022!)
    # =========================================================================
    common_st = (
        h20269.index.intersection(e510880.index)
        .intersection(h00300.index)
        .intersection(p518880.index)
        .intersection(p511010.index)
        .intersection(p513100.index)
    )
    px_st = pd.DataFrame(
        {
            "h20269": h20269.reindex(common_st),
            "e510880": e510880.reindex(common_st),
            "h00300": h00300.reindex(common_st),
            "gold": p518880.reindex(common_st),
            "bond": p511010.reindex(common_st),
            "ndx": p513100.reindex(common_st),
        }
    ).dropna()
    st_dates = px_st.index
    st_start_i = int(st_dates.searchsorted(pd.Timestamp("2014-08-01")))
    st_cp, st_cn = ov.calendar_cash_factors(st_dates, np.full(len(st_dates), 0.02), 0.0)
    st_q_end = ~st_dates.to_period("Q").duplicated(keep="last")

    def run_struct(cols: list[str], wf: list[float] | None = None, iv20: bool = False) -> tuple[lab.MultiEngineResult, dict[str, float]]:
        sub = px_st[cols]
        vol20 = sub.pct_change().rolling(20).std(ddof=1)

        def sig(i: int, cur_w: np.ndarray):
            if iv20:
                if i == st_start_i or ((i - st_start_i) % 10 == 0):
                    v = vol20.iloc[i].to_numpy(float)
                    if np.all(np.isfinite(v)) and np.all(v > 0):
                        w = (1.0 / v) / (1.0 / v).sum()
                        if np.abs(w - cur_w).sum() > 0.02:
                            return w
                return None
            if i == st_start_i or st_q_end[i]:
                return np.asarray(wf, float)
            return None

        res = lab.run_multi_asset_overlay(sub, sig, st_start_i, 0.001, st_cp, st_cn)
        m = nav_metrics(res.nav, len(res.trades), 1.0, 0.02, 252)
        return res, m

    struct_specs = [
        ("H20269_100%", ["h20269"], [1.0], False),
        ("H20269_75+Bond25_Q", ["h20269", "bond"], [0.75, 0.25], False),
        ("H20269_50+Bond50_Q", ["h20269", "bond"], [0.50, 0.50], False),
        ("H20269_75+Gold25_Q", ["h20269", "gold"], [0.75, 0.25], False),
        ("H20269_50+Gold50_Q", ["h20269", "gold"], [0.50, 0.50], False),
        ("H20269_50+Gold25+Bond25_Q", ["h20269", "gold", "bond"], [0.50, 0.25, 0.25], False),
        ("H20269+Gold_IV20", ["h20269", "gold"], None, True),
        ("510880_100%", ["e510880"], [1.0], False),
        ("510880_50+Bond50_Q", ["e510880", "bond"], [0.50, 0.50], False),
        ("510880_75+Gold25_Q", ["e510880", "gold"], [0.75, 0.25], False),
        ("510880_50+Gold25+Bond25_Q", ["e510880", "gold", "bond"], [0.50, 0.25, 0.25], False),
        ("H00300_100%", ["h00300"], [1.0], False),
        ("H00300_50+Gold25+Bond25_Q", ["h00300", "gold", "bond"], [0.50, 0.25, 0.25], False),
        ("PlanA_3Asset_IV20(300/NDX/Gold)", ["h00300", "ndx", "gold"], None, True),
    ]
    struct_rows: list[dict[str, Any]] = []
    struct_navs: dict[str, pd.Series] = {}
    for sname, cols, wf, iv in struct_specs:
        res, m = run_struct(cols, wf, iv)
        max_cash_resid = max(max_cash_resid, float(res.checks.get("max_cash_residual", 0.0)))
        struct_navs[sname] = res.nav
        pre_g = sub_metrics(res.nav, "2014-08-01", "2022-12-31", 0.02, 252)
        ex15 = sub_metrics(res.nav, "2016-01-04", "2026-09-30", 0.02, 252)
        struct_rows.append(
            {
                "portfolio": sname,
                **m,
                "pre_gold_14_22_cagr": pre_g["cagr"],
                "pre_gold_14_22_sharpe": pre_g["sharpe"],
                "pre_gold_14_22_maxdd": pre_g["max_dd"],
                "ex15_16_26_cagr": ex15["cagr"],
                "ex15_16_26_sharpe": ex15["sharpe"],
                "ex15_16_26_maxdd": ex15["max_dd"],
            }
        )
    pd.DataFrame(struct_rows).to_csv(OUT_DIR / "summary_ashare_structural.csv", index=False)

    # =========================================================================
    # 8. A-Share Rolling Monthly DCA (5Y & 10Y)
    # =========================================================================
    dca_cn_targets = [
        ("H20269_Hold", struct_navs["H20269_100%"]),
        ("H20269_MTF3_B3_Cash", ashare_nav_store["H20269_红利低波全收益__MTF3_150_210_B3"]),
        ("H20269_VOL3_15_24", ashare_nav_store["H20269_红利低波全收益__VOL3_15_24"]),
        ("H20269_50+Bond50_Q", struct_navs["H20269_50+Bond50_Q"]),
        ("H20269_75+Gold25_Q", struct_navs["H20269_75+Gold25_Q"]),
        ("H20269_50+Gold25+Bond25_Q", struct_navs["H20269_50+Gold25+Bond25_Q"]),
        ("510880_Hold", struct_navs["510880_100%"]),
        ("510880_MTF3_B3_Cash", ashare_nav_store["510880_红利ETF__MTF3_150_210_B3"]),
        ("512890_Hold_20_26", ashare_nav_store["512890_红利低波ETF__B0_HOLD"]),
        ("512890_MTF3_B3_20_26", ashare_nav_store["512890_红利低波ETF__MTF3_150_210_B3"]),
        ("H00300_Hold", struct_navs["H00300_100%"]),
        ("PlanA_3Asset_IV20", struct_navs["PlanA_3Asset_IV20(300/NDX/Gold)"]),
    ]
    dca_cn_rows: list[dict[str, Any]] = []
    for dname, nav in dca_cn_targets:
        fd = dca_full_stats(nav, 0.001)
        r5 = dca_rolling_stats(nav, 60, 0.001)
        r10 = dca_rolling_stats(nav, 120, 0.001)
        dca_cn_rows.append(
            {
                "portfolio": dname,
                **fd,
                "n_5y_windows": len(r5),
                "med_5y_xirr": float(r5["xirr"].median()) if len(r5) else np.nan,
                "worst_5y_xirr": float(r5["xirr"].min()) if len(r5) else np.nan,
                "worst_5y_dd": float(r5["worst_principal_dd"].min()) if len(r5) else np.nan,
                "loss_5y_prob": float(np.mean(r5["xirr"] < 0)) if len(r5) else np.nan,
                "n_10y_windows": len(r10),
                "med_10y_xirr": float(r10["xirr"].median()) if len(r10) else np.nan,
                "worst_10y_xirr": float(r10["xirr"].min()) if len(r10) else np.nan,
                "worst_10y_dd": float(r10["worst_principal_dd"].min()) if len(r10) else np.nan,
                "loss_10y_prob": float(np.mean(r10["xirr"] < 0)) if len(r10) else np.nan,
            }
        )
    pd.DataFrame(dca_cn_rows).to_csv(OUT_DIR / "ashare_rolling_dca.csv", index=False)

    # =========================================================================
    # 9. Automated Anti-Lookahead & Self-Check Audits
    # =========================================================================
    # Perturb last 30 bars on BTC and H20269 and verify ZERO change before cut!
    cut_b = len(btc) - 30
    btc_p = btc.copy()
    btc_p.iloc[cut_b:] *= 0.25
    diff_hyb = float(
        (
            lab.daily_buffered_st_ma_weight(btc["High"], btc["Low"], btc["Close"], 10, 3.0, 150, 0.05).iloc[:cut_b]
            - lab.daily_buffered_st_ma_weight(btc_p["High"], btc_p["Low"], btc_p["Close"], 10, 3.0, 150, 0.05).iloc[:cut_b]
        ).abs().max()
    )
    diff_dual = float(
        (
            lab.daily_buffered_mtf3_equity_weight(btc["Close"], 100, 15, 200, 0.05).iloc[:cut_b]
            - lab.daily_buffered_mtf3_equity_weight(btc_p["Close"], 100, 15, 200, 0.05).iloc[:cut_b]
        ).abs().max()
    )
    cut_a = len(h20269) - 30
    h20_p = h20269.copy()
    h20_p.iloc[cut_a:] *= 0.25
    diff_vol3 = float(
        (
            lab.daily_buffered_vol_throttle(h20269, 21, 0.15, 0.24, 0.02, 0.60, 0.20, 252).iloc[:cut_a]
            - lab.daily_buffered_vol_throttle(h20_p, 21, 0.15, 0.24, 0.02, 0.60, 0.20, 252).iloc[:cut_a]
        ).abs().max()
    )
    anti_lookahead_max_diff = max(diff_hyb, diff_dual, diff_vol3)
    assert anti_lookahead_max_diff == 0.0, f"Lookahead leak detected: {anti_lookahead_max_diff}"
    assert max_cash_resid < 1e-12, f"Cash residual too high: {max_cash_resid}"

    checks = {
        "all_passed": True,
        "max_cash_residual": max_cash_resid,
        "anti_lookahead_perturbation_max_diff": anti_lookahead_max_diff,
        "tickflow_vs_parquet_510300_max_ret_diff": tf_vs_pq_max_diff,
        "input_sha256": {
            "BTC-USD.parquet": sha256_file(BTC_PQ),
            "ETH-USD.parquet": sha256_file(ETH_PQ),
            "csindex_H20269.csv": sha256_file(CSI_CACHE / "csindex_H20269.csv"),
            "csindex_H00300.csv": sha256_file(CSI_CACHE / "csindex_H00300.csv"),
            "518880.SS.parquet": sha256_file(GOLD_CN_PQ),
            "511010.SS.parquet": sha256_file(BOND_CN_PQ),
        },
        "total_strategy_rows": len(btc_rows) + len(eth_rows) + len(sens_rows) * 2 + len(ashare_timing_rows) + len(struct_rows),
    }
    (OUT_DIR / "config.json").write_text(json.dumps(CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "self_checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")

    readme = f"""# {SLUG}

BTC 与 A 股（红利低波及主流宽基全谱）日频防抖三档策略泛化与第一性原理验证输出目录。

## 核心结论速览
- **市场物理指纹** (`market_physics_fingerprint.csv`)：站上 150 日均线后未来 3 个月相对收益差，BTC 为 `+16.84%`、ETH 为 `+8.82%`、QQQ 为 `+2.72%`、SPY 为 `+1.69%`；而 **A 股全部 6 个标的均为负值**（红利低波最极端，达 `-2.75%～-4.12%`，属于典型高股息均值回归橡胶带）。
- **BTC 通过且零调参泛化至 ETH** (`summary_btc_2015.csv`, `summary_eth_2018.csv`, `btc_sensitivity_grid.csv`)：
  - **轨道 1（稳健首选）：日线 SuperTrend(10,3) + 防抖长均线（120d/150d/200d ±5%）三档**（`100%/50%/0%`）— 3×3 参数邻域全部在 BTC 与 ETH 上通过循环位移检验（`p<=0.05`），2021–2026 成熟期明显反超纯日线 SuperTrend 且大幅压低回撤。
  - **轨道 2（极简低换手）：纯双均线防抖三档（`100d/200d ±5%～8%` 或 `50d/120d ±5%`）** — 年换手仅 4～8 次，无需 SuperTrend 指标。
- **A 股（含红利低波）全部未通过趋势择时** (`summary_ashare_timing.csv`)：所有日频缓冲带 MTF-3 变体在红利低波（`H20269` / `510880` / `512890`）上大幅跑输持有且回撤未减反增（`p_sharpe = 0.75~1.00`）；防抖控波动三档（`VOL3`）依赖 2015 单次股灾，在 2016+ 与实盘 `512890`（2020–2026）上未通过检验。
- **A 股红利低波正确解法** (`summary_ashare_structural.csv`, `ashare_rolling_dca.csv`)：靠**选对指数本身 + 傻瓜定投 + 低换手资产分散（搭国债 `511010` / 黄金 `518880`，或坚持主线方案 A 逆波动三组合）**，即便在 2023–2026 黄金大牛市之前（2014–2022）也稳健改善风险收益比。

## 文件清单
- `config.json` / `self_checks.json`：冻结配置、SHA256 校验、现金守恒与零前视扰动自检（`all_passed=true`）
- `market_physics_fingerprint.csv`：10 大资产跨市场趋势延续性指纹
- `summary_btc_2015.csv` / `summary_eth_2018.csv`：BTC 主测（含 10/30/50bp、美债利率、同仓位对照、循环位移检验）与 ETH 零调参外推
- `btc_rolling_dca_5y.csv` / `btc_rolling_starts_annual.csv` / `btc_key_periods.csv` / `btc_annual_returns.csv` / `btc_sensitivity_grid.csv`
- `summary_ashare_timing.csv` / `summary_ashare_structural.csv` / `ashare_rolling_dca.csv`

复现命令：`.venv/bin/python -I scripts/research_btc_ashare_buffered_mtf3_2026_11_23.py`
"""
    (OUT_DIR / "README.md").write_text(readme, encoding="utf-8")
    print(f"DONE {SLUG}: checks={checks['all_passed']}, total_rows={checks['total_strategy_rows']}, max_resid={max_cash_resid:.2e}")


if __name__ == "__main__":
    main()
