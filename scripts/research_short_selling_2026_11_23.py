"""Formal Research Study: The Short-Selling Challenge (US Equities, Crypto, and A-Shares).

Pre-registered research questions (2026-11-23):
1. First-principles short-selling physics:
   - Why is shorting structurally harder than going long? Quantify secular upward drift,
     bear-market violent short-squeeze concentration (% of biggest rallies occurring below 200d SMA),
     and conditional bear-regime gross edge vs real-world shorting friction across SPY, QQQ, BTC,
     ETH, CSI 300 (H00300), and ChiNext (159915).
2. Track A — Standalone Short-Only Strategies:
   - Can any simple trend-short rule (plain bear-regime short, slope-confirmed short, fast-ST-gated
     short, or volatility-capped bear short) generate positive risk-adjusted returns after realistic
     costs across a full multi-decade cycle?
3. Track B — Adding a Short Leg to Validated Daily Buffered Three-Tier Strategies:
   - When SPY/QQQ daily buffered MTF-3 (150d rising + 210d ±3%) or BTC HYB_ST_MA150_B5 (ST(10,3) +
     150d ±5%) drops to the 0% defensive tier, does flipping mildly/moderately short (-25% / -50% /
     -100% / slope-confirmed / fast-ST-gated / vol-capped) genuinely beat staying in 0% Cash (or
     Gold / Bond+Gold shields on US equities) after separating long-leg profits from incremental
     short-leg alpha?
4. Strict execution realism & anti-overfitting audit:
   - Model 3 distinct US shorting wrappers: (a) Retail margin (0% short-proceeds rebate + 0.5% borrow),
     (b) 1x Inverse ETF (SH/PSQ daily-reset + 1.0% fee/spread + swap rebate), (c) Institutional futures
     (100% rebate + 0.5% borrow).
   - Model crypto borrow/funding stress (+6% / +3% / 0% / -3% annualized) and 30bp/50bp costs.
   - Run 200-trial circular-shift permutation tests specifically on the INCREMENTAL SHORT LEG (holding
     the long leg fixed), crisis-by-crisis anatomy (including V-bottom squeeze traps like 2020 & 2025),
     zero-tuning ETH out-of-asset generalization, rolling annual starts, 5Y/10Y DCA, and parameter grid.

Run (offline sandbox, from repo root):
    .venv/bin/python -I scripts/research_short_selling_2026_11_23.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from xquant import indicators as ind  # noqa: E402
from xquant import overlay_rules as ov  # noqa: E402
from xquant import sp500_lab as lab  # noqa: E402

SLUG = "short-selling-challenge-2026-11-23"
OUT_DIR = ROOT / "outputs" / SLUG

US_SECTOR_CACHE = ROOT / "outputs" / "weinstein-us-sector-2026-10-18" / "cache"
QQQ_CSV = ROOT / "outputs" / "weinstein-quick-checks-2026-10-18" / "cache" / "yf_QQQ.csv"
BTC_PQ = ROOT / "outputs" / "btc-satellite-corrected-prices-2026-10-18" / "market_data" / "BTC-USD.parquet"
ETH_PQ = ROOT / "outputs" / "strategy-healthcheck-2026-10-02" / "market_data" / "ETH-USD.parquet"
TF_CACHE = ROOT / "outputs" / "weinstein-etf-stage-2026-10-18" / "cache"
CSI_CACHE = ROOT / "outputs" / "dividend-lowvol-csi2000-2026-10-18" / "cache"

CONFIG: dict[str, Any] = {
    "slug": SLUG,
    "execution_clock": "Signal at close t using data <= t; fills at close t+1 with proportional one-way cost.",
    "us": {
        "window_main": ["2000-01-03", "2026-10-16"],
        "window_early": ["2000-01-03", "2012-12-31"],
        "window_modern": ["2013-01-02", "2026-10-16"],
        "window_gld": ["2005-01-03", "2026-10-16"],
        "cost": 0.001,
        "wrappers": {
            "retail_margin": {"short_rebate_ratio": 0.0, "short_annual_cost": 0.005, "daily_reset_short": False},
            "inverse_etf": {"short_rebate_ratio": 1.0, "short_annual_cost": 0.010, "daily_reset_short": True},
            "pro_futures": {"short_rebate_ratio": 1.0, "short_annual_cost": 0.005, "daily_reset_short": False},
        },
        "ann_days": 252,
    },
    "crypto": {
        "btc_window": ["2015-08-01", "2026-10-01"],
        "btc_early": ["2015-08-01", "2020-12-31"],
        "btc_mature": ["2021-01-01", "2026-10-01"],
        "eth_window": ["2018-09-01", "2026-10-01"],
        "primary_cost": 0.003,
        "stress_costs": [0.001, 0.003, 0.005],
        "primary_borrow_annual": 0.03,
        "funding_stress_annual": [0.06, 0.03, 0.00, -0.03],
        "ann_days": 365,
    },
    "ashare": {
        "window": ["2014-08-01", "2026-10-15"],
        "cost": 0.001,
        "retail_margin_borrow": 0.085,
        "cash_annual": 0.02,
        "ann_days": 252,
    },
    "circular_shift_trials": 200,
    "pre_registered_pass_bar": [
        "Incremental short leg MUST produce positive cumulative alpha over cash (short_vs_cash_cum_diff > 0)",
        "Long/Short MUST improve Sharpe over the Cash baseline in BOTH early and modern sub-periods",
        "Incremental short-leg circular shift p-value <= 0.05 (not random noise)",
        "Worst 20-day short-squeeze loss must stay survivable (no liquidation, no catastrophic squeeze)",
        "Must survive realistic retail friction (not dependent on zero-cost or institutional-only rebates)",
    ],
}


# --------------------------------------------------------------------------- Loaders
def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_yf_ohlc(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    date_col = df.columns[0]
    idx = pd.to_datetime(df[date_col].astype(str).str.slice(0, 10))
    cols = {c.lower(): c for c in df.columns}
    out = pd.DataFrame(
        {
            "Open": pd.to_numeric(df[cols["open"]], errors="coerce").to_numpy(float),
            "High": pd.to_numeric(df[cols["high"]], errors="coerce").to_numpy(float),
            "Low": pd.to_numeric(df[cols["low"]], errors="coerce").to_numpy(float),
            "Close": pd.to_numeric(df[cols["close"]], errors="coerce").to_numpy(float),
        },
        index=idx,
    ).dropna()
    return out[~out.index.duplicated(keep="last")].sort_index()


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


def load_csindex(code: str) -> pd.Series:
    p = CSI_CACHE / f"csindex_{code}.csv"
    df = pd.read_csv(p, parse_dates=["日期"]).drop_duplicates("日期", keep="last").set_index("日期").sort_index()
    return df["收盘"].astype(float).rename(code)


# --------------------------------------------------------------------------- Metrics & DCA
def summarize_ls(
    res: lab.MultiEngineResult,
    *,
    primary_col: str,
    ann_days: int = 252,
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

    days = (nav.index[-1] - nav.index[0]).days
    years = days / 365.25
    start_val = float(nav.iloc[0])
    end_val = float(nav.iloc[-1])
    liquidated = bool(end_val <= 1e-9 or (nav <= 1e-9).any())

    if start_val <= 1e-9 or liquidated:
        nav_norm = nav / max(start_val, 1e-9)
        cagr = -1.0
        vol = np.nan
        sharpe = np.nan
        max_dd = -1.0
        calmar = np.nan
        worst_month = -1.0
        worst_year = -1.0
        monthly_win = np.nan
        underwater_y = years
    else:
        nav_norm = nav / start_val
        cagr = float(nav_norm.iloc[-1] ** (1.0 / years) - 1.0)
        ret = nav_norm.pct_change().dropna()
        vol = float(ret.std(ddof=1) * np.sqrt(ann_days))
        ex = ret - rf.reindex(ret.index).fillna(0.0)
        ex_std = float(ex.std(ddof=1))
        sharpe = float(ex.mean() / ex_std * np.sqrt(ann_days)) if ex_std > 0 else np.nan
        dd = nav_norm / nav_norm.cummax() - 1.0
        max_dd = float(dd.min())
        calmar = float(cagr / abs(max_dd)) if max_dd < 0 else np.nan
        underwater_y = lab.max_underwater_years(nav_norm)
        monthly = nav_norm.resample("ME").last().pct_change().dropna()
        yearly = nav_norm.resample("YE").last().pct_change().dropna()
        monthly_win = float((monthly > 0).mean()) if len(monthly) else np.nan
        worst_month = float(monthly.min()) if len(monthly) else np.nan
        worst_year = float(yearly.min()) if len(yearly) else np.nan

    non_init = trades[~trades["is_initial"]] if not trades.empty else trades
    trades_per_year = float(len(non_init) / years) if years > 0 else 0.0
    annual_turnover = float(non_init["traded_frac"].sum() / years) if (not non_init.empty and years > 0) else 0.0
    w_prim = wts[primary_col].iloc[1:]
    short_share = float((w_prim < -1e-6).mean()) if len(w_prim) else 0.0
    long_share = float((w_prim > 1e-6).mean()) if len(w_prim) else 0.0
    avg_net_w = float(w_prim.mean()) if len(w_prim) else 0.0
    avg_gross_w = float(w_prim.abs().mean()) if len(w_prim) else 0.0

    # Window-specific short attribution via res.nav and weights (full-sample checks attached too)
    out = {
        "start": str(nav.index[0].date()),
        "end": str(nav.index[-1].date()),
        "years": round(years, 2),
        "cagr": cagr,
        "vol": vol,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "calmar": calmar,
        "max_underwater_years": underwater_y,
        "monthly_win_rate": monthly_win,
        "worst_month": worst_month,
        "worst_year": worst_year,
        "trades_per_year": trades_per_year,
        "annual_turnover": annual_turnover,
        "terminal_multiple": float(end_val / max(start_val, 1e-9)),
        "long_time_share": long_share,
        "short_time_share": short_share,
        "avg_net_weight": avg_net_w,
        "avg_gross_weight": avg_gross_w,
        "liquidated": liquidated,
    }
    if start is None and end is None:
        out["short_cum_alpha"] = float(res.checks.get("short_cum_alpha", 0.0))
        out["short_vs_cash_cum_diff"] = float(res.checks.get("short_vs_cash_cum_diff", 0.0))
        out["short_win_day_rate"] = float(res.checks.get("short_win_day_rate", np.nan))
        out["worst_1d_squeeze"] = float(res.checks.get("worst_1d_squeeze", 0.0))
        out["worst_5d_squeeze"] = float(res.checks.get("worst_5d_squeeze", 0.0))
        out["worst_20d_squeeze"] = float(res.checks.get("worst_20d_squeeze", 0.0))
    return out


def fast_xirr(day_offsets: np.ndarray, terminal_val: float) -> float:
    """Exact monotone bisection XIRR matching cashflow_research.xirr."""
    yrs = day_offsets / 365.25
    lo, hi = -0.95, 10.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        val = float(np.sum((1.0 + mid) ** yrs))
        if val > terminal_val:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def fast_dca_rolling(nav: pd.Series, window_months: int, cost: float = 0.001) -> pd.DataFrame:
    if (nav <= 1e-9).any():
        return pd.DataFrame()
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
        rows.append(
            {
                "start": str(dates[i0].date()),
                "end": str(dates[i1].date()),
                "xirr": float(x),
                "unit_max_dd": u_mdd,
                "dca_ratio": float(x / abs(u_mdd)) if u_mdd < 0 else np.nan,
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- Signal Builders
def weight_array_to_signal(target_w: np.ndarray, start_i: int, threshold: float = 0.02):
    """Emit target weight [w] on start_i and whenever target changes by >= threshold."""
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


def multi_weight_to_signal(target_mat: np.ndarray, start_i: int, threshold: float = 0.02):
    last_emitted: list[Optional[np.ndarray]] = [None]

    def sig(i: int, _actual: np.ndarray) -> Optional[np.ndarray]:
        w = target_mat[i]
        if i == start_i or last_emitted[0] is None:
            last_emitted[0] = w.copy()
            return w.copy()
        if float(np.abs(w - last_emitted[0]).sum()) >= threshold:
            last_emitted[0] = w.copy()
            return w.copy()
        return None

    return sig


def build_us_short_signals(ohlc: pd.DataFrame, *, buf: float = 0.03) -> dict[str, np.ndarray]:
    """Pre-registered US short-only and long/short weight trajectories on SPY/QQQ."""
    close = ohlc["Close"]
    high = ohlc["High"]
    low = ohlc["Low"]

    base_long = lab.daily_buffered_mtf3_equity_weight(
        close, ma_fast=150, slope_days=20, ma_slow=210, buffer=buf
    ).to_numpy(float)
    bear_mask = base_long < 1e-9  # Both lamps OFF (0% tier)

    ma210 = close.rolling(210).mean()
    ma210_falling = (ma210 < ma210.shift(20)).fillna(False).to_numpy(bool)
    st_down = (~ind.supertrend_direction(high, low, close, atr_window=10, multiplier=3.0)).to_numpy(bool)

    rv21 = (np.log(close).diff().rolling(21).std(ddof=1) * np.sqrt(252.0)).bfill().clip(lower=0.05).to_numpy(float)
    # Vol-capped short size targeting 10% annualized vol, capped at 50% (shrinks automatically in panics!)
    vol_cap_50 = np.clip(0.10 / rv21, 0.0, 0.50)
    # Quantize to 5% steps so daily micro-rebalancing doesn't create noise turnover
    vol_cap_50_q = np.round(vol_cap_50 * 20.0) / 20.0

    # Bear-regime masks for different confirmation gates
    m_all = bear_mask
    m_slope = bear_mask & ma210_falling
    m_st = bear_mask & st_down

    # Track C: Fast Tactical Short (independent of slow 210d MA — enters crashes early, covers instantly on ST flip)
    ma50 = close.rolling(50).mean()
    m_tactical = ((close < ma50) & (ma50 < ma50.shift(10))).fillna(False).to_numpy(bool) & st_down

    return {
        # Baselines
        "BH": np.ones(len(close), dtype=float),
        "MTF3_BUF3_CASH": base_long,
        # Track A: Standalone Short-Only (0% when not shorting)
        "SHORT_HOLD_100": np.full(len(close), -1.0, dtype=float),
        "SHORT_MTF3_50": np.where(m_all, -0.50, 0.0),
        "SHORT_MTF3_100": np.where(m_all, -1.00, 0.0),
        "SHORT_SLOPE_50": np.where(m_slope, -0.50, 0.0),
        "SHORT_FAST_ST_50": np.where(m_st, -0.50, 0.0),
        "SHORT_VOLCAP_50": np.where(m_all, -vol_cap_50_q, 0.0),
        "SHORT_TACTICAL_ST50": np.where(m_tactical, -0.50, 0.0),
        # Track B: Long/Short upgrades to MTF3_BUF3_CASH (100% / 50% / short)
        "LS_MTF3_25": np.where(m_all, -0.25, base_long),
        "LS_MTF3_50": np.where(m_all, -0.50, base_long),
        "LS_MTF3_100": np.where(m_all, -1.00, base_long),
        "LS_SLOPE_50": np.where(m_slope, -0.50, base_long),
        "LS_FAST_ST_50": np.where(m_st, -0.50, base_long),
        "LS_VOLCAP_50": np.where(m_all, -vol_cap_50_q, base_long),
    }


def build_crypto_short_signals(ohlc: pd.DataFrame, *, buf: float = 0.05) -> dict[str, np.ndarray]:
    """Pre-registered Crypto short-only and long/short weight trajectories (BTC primary, ETH zero-tuning)."""
    close = ohlc["Close"]
    high = ohlc["High"]
    low = ohlc["Low"]

    base_hyb = lab.daily_buffered_st_ma_weight(
        high, low, close, atr_window=10, multiplier=3.0, ma_days=150, buffer=buf
    ).to_numpy(float)
    bear_hyb = base_hyb < 1e-9  # Both ST(10,3) OFF and 150d SMA ±5% OFF

    base_mtf = lab.daily_buffered_mtf3_equity_weight(
        close, ma_fast=100, slope_days=20, ma_slow=200, buffer=buf
    ).to_numpy(float)
    bear_mtf = base_mtf < 1e-9

    ma150 = close.rolling(150).mean()
    ma150_falling = (ma150 < ma150.shift(20)).fillna(False).to_numpy(bool)
    bear_hyb_slope = bear_hyb & ma150_falling

    rv21 = (np.log(close).diff().rolling(21).std(ddof=1) * np.sqrt(365.0)).bfill().clip(lower=0.15).to_numpy(float)
    vol_cap_50_q = np.round(np.clip(0.25 / rv21, 0.0, 0.50) * 20.0) / 20.0

    # Track C: Fast Tactical Short (close < 50d falling SMA AND daily ST(10,3) DOWN)
    st_down = (~ind.supertrend_direction(high, low, close, atr_window=10, multiplier=3.0)).to_numpy(bool)
    ma50 = close.rolling(50).mean()
    m_tactical = ((close < ma50) & (ma50 < ma50.shift(10))).fillna(False).to_numpy(bool) & st_down

    return {
        # Baselines
        "BH": np.ones(len(close), dtype=float),
        "HYB_ST_MA150_CASH": base_hyb,
        "MTF3_100_200_CASH": base_mtf,
        # Track A: Standalone Short-Only
        "SHORT_HOLD_100": np.full(len(close), -1.0, dtype=float),
        "SHORT_HYB_50": np.where(bear_hyb, -0.50, 0.0),
        "SHORT_HYB_100": np.where(bear_hyb, -1.00, 0.0),
        "SHORT_HYB_SLOPE_50": np.where(bear_hyb_slope, -0.50, 0.0),
        "SHORT_HYB_VOLCAP_50": np.where(bear_hyb, -vol_cap_50_q, 0.0),
        "SHORT_TACTICAL_ST50": np.where(m_tactical, -0.50, 0.0),
        "SHORT_MTF_50": np.where(bear_mtf, -0.50, 0.0),
        # Track B: Long/Short upgrades
        "LS_HYB_25": np.where(bear_hyb, -0.25, base_hyb),
        "LS_HYB_50": np.where(bear_hyb, -0.50, base_hyb),
        "LS_HYB_100": np.where(bear_hyb, -1.00, base_hyb),
        "LS_HYB_SLOPE_50": np.where(bear_hyb_slope, -0.50, base_hyb),
        "LS_HYB_VOLCAP_50": np.where(bear_hyb, -vol_cap_50_q, base_hyb),
        "LS_MTF_50": np.where(bear_mtf, -0.50, base_mtf),
        "LS_MTF_100": np.where(bear_mtf, -1.00, base_mtf),
    }


# --------------------------------------------------------------------------- Physics & Permutation Tests
def compute_short_physics(
    name: str,
    close: pd.Series,
    bear_mask: np.ndarray,
    *,
    start: str,
    end: str,
    ann_days: int,
    real_short_friction: float,
) -> dict[str, Any]:
    """Quantify first-principles short-selling physics: drift, squeeze asymmetry, conditional bear edge."""
    s = close.loc[start:end]
    bm = pd.Series(bear_mask, index=close.index).loc[s.index].to_numpy(bool)
    ret = s.pct_change().dropna()
    ret5 = s.pct_change(5).dropna()
    bm_prev = pd.Series(bm, index=s.index).shift(1, fill_value=False).loc[ret.index].to_numpy(bool)
    ma200 = close.rolling(200).mean().loc[s.index]
    below200_prev = (s < ma200).shift(1, fill_value=False).loc[ret.index].to_numpy(bool)

    years = (s.index[-1] - s.index[0]).days / 365.25
    bh_cagr = float((s.iloc[-1] / s.iloc[0]) ** (1.0 / years) - 1.0)
    roll_1y = s.pct_change(ann_days).dropna()
    roll_3y = s.pct_change(ann_days * 3).dropna()

    # Where do the top-20 biggest 1-day and 5-day rallies happen?
    top20_1d_idx = ret.nlargest(20).index
    pct_top20_1d_below200 = float(pd.Series(below200_prev, index=ret.index).loc[top20_1d_idx].mean())
    pct_top20_1d_in_bear = float(pd.Series(bm_prev, index=ret.index).loc[top20_1d_idx].mean())

    below200_5d = (s < ma200).shift(5, fill_value=False).loc[ret5.index]
    top20_5d_idx = ret5.nlargest(20).index
    pct_top20_5d_below200 = float(below200_5d.loc[top20_5d_idx].mean())

    bear_rets = ret.to_numpy(float)[bm_prev]
    bull_rets = ret.to_numpy(float)[~bm_prev]
    bear_ann_ret = float(np.mean(bear_rets) * ann_days) if len(bear_rets) > 10 else np.nan
    bear_ann_vol = float(np.std(bear_rets, ddof=1) * np.sqrt(ann_days)) if len(bear_rets) > 10 else np.nan
    bull_ann_ret = float(np.mean(bull_rets) * ann_days) if len(bull_rets) > 10 else np.nan
    bull_ann_vol = float(np.std(bull_rets, ddof=1) * np.sqrt(ann_days)) if len(bull_rets) > 10 else np.nan
    # Gross annualized edge of being -1x short during bear_mask (before borrow/trading costs)
    gross_short_edge = -bear_ann_ret if np.isfinite(bear_ann_ret) else np.nan
    net_short_edge_est = gross_short_edge - real_short_friction if np.isfinite(gross_short_edge) else np.nan
    max_1d_rally_in_bear = float(np.max(bear_rets)) if len(bear_rets) else np.nan

    return {
        "asset": name,
        "window": f"{s.index[0].date()}..{s.index[-1].date()}",
        "years": round(years, 2),
        "bh_cagr": bh_cagr,
        "pos_1y_share": float((roll_1y > 0).mean()) if len(roll_1y) else np.nan,
        "pos_3y_share": float((roll_3y > 0).mean()) if len(roll_3y) else np.nan,
        "bear_time_share": float(bm_prev.mean()),
        "bull_ann_ret": bull_ann_ret,
        "bull_ann_vol": bull_ann_vol,
        "bear_ann_ret": bear_ann_ret,
        "bear_ann_vol": bear_ann_vol,
        "vol_ratio_bear_to_bull": bear_ann_vol / bull_ann_vol if (bull_ann_vol and bull_ann_vol > 0) else np.nan,
        "gross_short_edge_ann": gross_short_edge,
        "assumed_short_friction_ann": real_short_friction,
        "est_net_short_edge_ann": net_short_edge_est,
        "pct_top20_1d_rallies_below200": pct_top20_1d_below200,
        "pct_top20_1d_rallies_in_bear": pct_top20_1d_in_bear,
        "pct_top20_5d_rallies_below200": pct_top20_5d_below200,
        "worst_1d_bear_rally_squeeze": max_1d_rally_in_bear,
    }


def short_leg_circular_shift_pvalue(
    prices: pd.DataFrame,
    long_weights: np.ndarray,
    short_weights: np.ndarray,
    start_i: int,
    *,
    cost: float,
    cash_pos: np.ndarray,
    cash_neg: np.ndarray,
    short_rebate_ratio: float,
    short_annual_cost: float,
    daily_reset_short: bool,
    ann_days: int,
    n_trials: int = 200,
    seed: int = 20261123,
) -> dict[str, Any]:
    """Test whether the SHORT LEG specifically beats random circularly-shifted shorting.

    * For standalone short-only (long_weights == 0 everywhere): circularly shift ``short_weights``
      over [start_i:] and compare Sharpe & CAGR against observed.
    * For long/short (long_weights > 0 on long days): keep ``long_weights`` FIXED, and circularly
      shift the short-weight sequence across [start_i:] (applying shifted short only where the
      fixed long leg is not long, OR shifting the raw short series over the exact cash-period days
      to preserve total short-day exposure!). Shifting within the exact defensive/cash days directly
      isolates: "among days when MTF-3 isn't long, does timing the short beat random shorting?"
      AND we ALSO run a full-sample short-mask circular shift for standalone short-only!
    """
    col = prices.columns[0]
    obs_total = np.where(long_weights > 1e-9, long_weights, short_weights)
    res_obs = lab.run_long_short_overlay(
        prices,
        weight_array_to_signal(obs_total, start_i),
        start_i,
        cost,
        cash_pos,
        cash_neg,
        short_rebate_ratio=short_rebate_ratio,
        short_annual_cost=short_annual_cost,
        daily_reset_short=daily_reset_short,
    )
    obs_m = summarize_ls(res_obs, primary_col=col, ann_days=ann_days)
    obs_sharpe = obs_m["sharpe"]
    obs_cagr = obs_m["cagr"]
    obs_short_alpha = float(res_obs.checks["short_vs_cash_cum_diff"])

    rng = np.random.default_rng(seed)
    n = len(prices)
    n_eval = n - start_i
    # Pure standalone short-only: shift across entire evaluation window
    is_short_only = bool(np.all(long_weights[start_i:] <= 1e-9))
    min_shift = max(20, n_eval // 15)
    shifts = rng.integers(min_shift, n_eval - min_shift, size=n_trials)

    beat_sharpe = 0
    beat_cagr = 0
    beat_short_alpha = 0
    null_sharpes = []
    null_short_alphas = []

    base_s = short_weights[start_i:].copy()
    base_l = long_weights[start_i:].copy()
    for sh in shifts:
        sh_i = int(sh)
        shifted_s = np.roll(base_s, sh_i)
        if is_short_only:
            cand_eval = shifted_s
        else:
            # Keep long leg fixed; apply shifted short mask only when long leg == 0? Wait: that
            # changes short_time_share if long leg covers it. Better: roll the ENTIRE short-only
            # return timing across the full sample by replacing short leg with rolled short mask
            # on full sample while keeping long_weights untouched -> no, if long_w > 0 it overlaps.
            # Instead, test the exact standalone short-only contribution directly on shifted_s!
            cand_eval = np.where(base_l > 1e-9, base_l, shifted_s)
        cand_full = obs_total.copy()
        cand_full[start_i:] = cand_eval
        r_sim = lab.run_long_short_overlay(
            prices,
            weight_array_to_signal(cand_full, start_i),
            start_i,
            cost,
            cash_pos,
            cash_neg,
            short_rebate_ratio=short_rebate_ratio,
            short_annual_cost=short_annual_cost,
            daily_reset_short=daily_reset_short,
        )
        sm = summarize_ls(r_sim, primary_col=col, ann_days=ann_days)
        sa = float(r_sim.checks["short_vs_cash_cum_diff"])
        if np.isfinite(sm["sharpe"]):
            null_sharpes.append(sm["sharpe"])
        null_short_alphas.append(sa)
        if np.isfinite(obs_sharpe) and np.isfinite(sm["sharpe"]) and sm["sharpe"] >= obs_sharpe:
            beat_sharpe += 1
        if sm["cagr"] >= obs_cagr:
            beat_cagr += 1
        if sa >= obs_short_alpha:
            beat_short_alpha += 1

    return {
        "obs_sharpe": obs_sharpe,
        "obs_cagr": obs_cagr,
        "obs_short_vs_cash": obs_short_alpha,
        "null_median_sharpe": float(np.median(null_sharpes)) if null_sharpes else np.nan,
        "null_median_short_vs_cash": float(np.median(null_short_alphas)) if null_short_alphas else np.nan,
        "p_sharpe": float((beat_sharpe + 1) / (n_trials + 1)),
        "p_cagr": float((beat_cagr + 1) / (n_trials + 1)),
        "p_short_alpha": float((beat_short_alpha + 1) / (n_trials + 1)),
        "n_trials": n_trials,
    }


def crisis_table_rows(
    results_map: dict[str, lab.MultiEngineResult],
    episodes: list[tuple[str, str, str]],
    market_label: str,
) -> list[dict[str, Any]]:
    rows = []
    for ep_name, s_date, e_date in episodes:
        row: dict[str, Any] = {"market": market_label, "episode": ep_name, "start": s_date, "end": e_date}
        for strat, res in results_map.items():
            sub = res.nav.loc[s_date:e_date]
            if len(sub) < 5 or float(sub.iloc[0]) <= 1e-9:
                row[f"{strat}_ret"] = np.nan
                row[f"{strat}_mdd"] = np.nan
            else:
                norm = sub / sub.iloc[0]
                row[f"{strat}_ret"] = float(norm.iloc[-1] - 1.0)
                row[f"{strat}_mdd"] = float((norm / norm.cummax() - 1.0).min())
        rows.append(row)
    return rows


# --------------------------------------------------------------------------- Main Study
def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"=== Running {SLUG} ===")

    # 1. Load all frozen datasets
    us_bundle = lab.load_us_bundle()
    spy_ohlc = load_yf_ohlc(US_SECTOR_CACHE / "yf_SPY.csv").loc["1998-12-01":"2026-10-16"]
    qqq_ohlc = load_yf_ohlc(QQQ_CSV).loc["1999-03-10":"2026-10-16"]
    btc_ohlc = load_parquet_ohlc(BTC_PQ).loc["2014-09-17":"2026-10-01"]
    eth_ohlc = load_parquet_ohlc(ETH_PQ).loc["2017-11-09":"2026-10-01"]

    # Align IRX T-bill daily factors to SPY and QQQ
    irx_full = us_bundle["irx"]
    spy_irx = irx_full.reindex(spy_ohlc.index).ffill().bfill()
    spy_cp, spy_cn = ov.calendar_cash_factors(spy_ohlc.index, spy_irx.to_numpy(float), 0.015)

    qqq_irx = irx_full.reindex(qqq_ohlc.index).ffill().bfill()
    qqq_cp, qqq_cn = ov.calendar_cash_factors(qqq_ohlc.index, qqq_irx.to_numpy(float), 0.015)

    # Crypto cash = 0% (USDT margin earns 0%)
    btc_cp = np.ones(len(btc_ohlc), dtype=float)
    eth_cp = np.ones(len(eth_ohlc), dtype=float)

    # A-shares (CSI 300 H00300 total-return + ChiNext 159915 + CSI 500 510500)
    h00300_s = load_csindex("H00300")
    csi500_df = load_tickflow_json(TF_CACHE / "tickflow_forward_510050_510300_510500.json", "510500.SH")
    chinext_df = load_tickflow_json(TF_CACHE / "tickflow_forward_512100_159552_159915.json", "159915.SZ")

    # ------------------------------------------------------------------ Part 1: Short-Selling Physics
    print("[1/7] Computing first-principles short-selling physics across 6 assets...")
    spy_sigs = build_us_short_signals(spy_ohlc, buf=0.03)
    qqq_sigs = build_us_short_signals(qqq_ohlc, buf=0.03)
    btc_sigs = build_crypto_short_signals(btc_ohlc, buf=0.05)
    eth_sigs = build_crypto_short_signals(eth_ohlc, buf=0.05)

    h300_bear = lab.daily_buffered_mtf3_equity_weight(h00300_s, 150, 20, 210, 0.03).to_numpy(float) < 1e-9
    chi_bear = lab.daily_buffered_mtf3_equity_weight(chinext_df["Close"], 150, 20, 210, 0.03).to_numpy(float) < 1e-9

    physics_rows = [
        compute_short_physics("SPY (US Large Cap)", spy_ohlc["Close"], spy_sigs["MTF3_BUF3_CASH"] < 1e-9,
                              start="2000-01-03", end="2026-10-16", ann_days=252, real_short_friction=0.010),
        compute_short_physics("SPY Modern (2013-2026)", spy_ohlc["Close"], spy_sigs["MTF3_BUF3_CASH"] < 1e-9,
                              start="2013-01-02", end="2026-10-16", ann_days=252, real_short_friction=0.010),
        compute_short_physics("QQQ (US Nasdaq-100)", qqq_ohlc["Close"], qqq_sigs["MTF3_BUF3_CASH"] < 1e-9,
                              start="2000-03-01", end="2026-10-16", ann_days=252, real_short_friction=0.010),
        compute_short_physics("QQQ Modern (2013-2026)", qqq_ohlc["Close"], qqq_sigs["MTF3_BUF3_CASH"] < 1e-9,
                              start="2013-01-02", end="2026-10-16", ann_days=252, real_short_friction=0.010),
        compute_short_physics("BTC-USD (2015-2026)", btc_ohlc["Close"], btc_sigs["HYB_ST_MA150_CASH"] < 1e-9,
                              start="2015-08-01", end="2026-10-01", ann_days=365, real_short_friction=0.030),
        compute_short_physics("BTC-USD Mature (2021-2026)", btc_ohlc["Close"], btc_sigs["HYB_ST_MA150_CASH"] < 1e-9,
                              start="2021-01-01", end="2026-10-01", ann_days=365, real_short_friction=0.030),
        compute_short_physics("ETH-USD (2018-2026 OOS)", eth_ohlc["Close"], eth_sigs["HYB_ST_MA150_CASH"] < 1e-9,
                              start="2018-09-01", end="2026-10-01", ann_days=365, real_short_friction=0.030),
        compute_short_physics("H00300 (A-Share CSI300 TR)", h00300_s, h300_bear,
                              start="2014-08-01", end="2026-10-15", ann_days=252, real_short_friction=0.085),
        compute_short_physics("159915 (A-Share ChiNext)", chinext_df["Close"], chi_bear,
                              start="2014-08-01", end="2026-10-15", ann_days=252, real_short_friction=0.085),
    ]
    physics_df = pd.DataFrame(physics_rows)
    physics_df.to_csv(OUT_DIR / "short_market_physics.csv", index=False)

    # ------------------------------------------------------------------ Part 2: US SPY & QQQ (All Wrappers + Shields)
    print("[2/7] Backtesting US SPY & QQQ short-only & long/short strategies across 3 execution wrappers...")
    us_rows = []
    spy_res_retail: dict[str, lab.MultiEngineResult] = {}
    qqq_res_retail: dict[str, lab.MultiEngineResult] = {}

    for asset_name, ohlc, sigs, cp, cn, win_start in [
        ("SPY", spy_ohlc, spy_sigs, spy_cp, spy_cn, "2000-01-03"),
        ("QQQ", qqq_ohlc, qqq_sigs, qqq_cp, qqq_cn, "2000-03-01"),
    ]:
        px_df = pd.DataFrame({asset_name.lower(): ohlc["Close"]}, index=ohlc.index)
        start_i = int(ohlc.index.searchsorted(pd.Timestamp(win_start)))
        col = asset_name.lower()

        # Run across 3 wrappers: retail_margin (primary), inverse_etf (SH/PSQ), pro_futures
        for wrap_name, wrap_cfg in CONFIG["us"]["wrappers"].items():
            # For non-retail wrappers, only need to run key strategies to keep table crisp
            strat_keys = (
                list(sigs.keys())
                if wrap_name == "retail_margin"
                else ["BH", "MTF3_BUF3_CASH", "SHORT_MTF3_50", "SHORT_MTF3_100", "LS_MTF3_25", "LS_MTF3_50", "LS_MTF3_100", "LS_SLOPE_50", "LS_FAST_ST_50", "LS_VOLCAP_50"]
            )
            cash_base_res = None
            for strat in strat_keys:
                w_arr = sigs[strat]
                res = lab.run_long_short_overlay(
                    px_df,
                    weight_array_to_signal(w_arr, start_i),
                    start_i,
                    CONFIG["us"]["cost"],
                    cp,
                    cn,
                    **wrap_cfg,
                )
                if strat == "MTF3_BUF3_CASH":
                    cash_base_res = res
                if wrap_name == "retail_margin":
                    if asset_name == "SPY":
                        spy_res_retail[strat] = res
                    else:
                        qqq_res_retail[strat] = res

                m_full = summarize_ls(res, primary_col=col, ann_days=252)
                m_early = summarize_ls(res, primary_col=col, ann_days=252, start=win_start, end="2012-12-31")
                m_mod = summarize_ls(res, primary_col=col, ann_days=252, start="2013-01-02", end="2026-10-16")
                us_rows.append(
                    {
                        "asset": asset_name,
                        "wrapper": wrap_name,
                        "strategy": strat,
                        **m_full,
                        "early_cagr": m_early["cagr"],
                        "early_sharpe": m_early["sharpe"],
                        "early_mdd": m_early["max_dd"],
                        "modern_cagr": m_mod["cagr"],
                        "modern_sharpe": m_mod["sharpe"],
                        "modern_mdd": m_mod["max_dd"],
                    }
                )

    # Also compare SPY Long/Short head-to-head against MTF3_BUF3_GOLD and MTF3_BUF3_BOND_GOLD on 2005-2026 (real GLD)
    print("[3/7] Comparing SPY Long/Short vs Cash / Gold / Bond+Gold defensive shields (2005-2026 real GLD)...")
    gld = us_bundle["gld_real"].reindex(spy_ohlc.index).ffill()
    ief = us_bundle["ief"].reindex(spy_ohlc.index).ffill()
    shield_px = pd.DataFrame({"spy": spy_ohlc["Close"], "gld": gld, "ief": ief}, index=spy_ohlc.index)
    gld_start_i = int(spy_ohlc.index.searchsorted(pd.Timestamp("2005-01-03")))
    eq_w = spy_sigs["MTF3_BUF3_CASH"]
    def_w = 1.0 - eq_w
    gold_mat = np.column_stack([eq_w, def_w, np.zeros_like(eq_w)])
    bg_mat = np.column_stack([eq_w, 0.5 * def_w, 0.5 * def_w])

    res_spy_gold = lab.run_multi_asset_overlay(
        shield_px, multi_weight_to_signal(gold_mat, gld_start_i), gld_start_i, 0.001, spy_cp, spy_cn
    )
    res_spy_bg = lab.run_multi_asset_overlay(
        shield_px, multi_weight_to_signal(bg_mat, gld_start_i), gld_start_i, 0.001, spy_cp, spy_cn
    )
    shield_compare_rows = []
    for label, res_obj, pcol in [
        ("SPY_BH", spy_res_retail["BH"], "spy"),
        ("MTF3_BUF3_CASH", spy_res_retail["MTF3_BUF3_CASH"], "spy"),
        ("MTF3_BUF3_GOLD", res_spy_gold, "spy"),
        ("MTF3_BUF3_BOND_GOLD", res_spy_bg, "spy"),
        ("LS_MTF3_25 (Retail)", spy_res_retail["LS_MTF3_25"], "spy"),
        ("LS_MTF3_50 (Retail)", spy_res_retail["LS_MTF3_50"], "spy"),
        ("LS_MTF3_100 (Retail)", spy_res_retail["LS_MTF3_100"], "spy"),
        ("LS_SLOPE_50 (Retail)", spy_res_retail["LS_SLOPE_50"], "spy"),
        ("LS_FAST_ST_50 (Retail)", spy_res_retail["LS_FAST_ST_50"], "spy"),
        ("LS_VOLCAP_50 (Retail)", spy_res_retail["LS_VOLCAP_50"], "spy"),
    ]:
        m_05 = summarize_ls(res_obj, primary_col=pcol, ann_days=252, start="2005-01-03", end="2026-10-16")
        m_13 = summarize_ls(res_obj, primary_col=pcol, ann_days=252, start="2013-01-02", end="2026-10-16")
        shield_compare_rows.append(
            {
                "strategy": label,
                **m_05,
                "modern_2013_cagr": m_13["cagr"],
                "modern_2013_sharpe": m_13["sharpe"],
                "modern_2013_mdd": m_13["max_dd"],
            }
        )
    pd.DataFrame(us_rows).to_csv(OUT_DIR / "summary_us_short.csv", index=False)
    pd.DataFrame(shield_compare_rows).to_csv(OUT_DIR / "us_short_vs_shields_2005.csv", index=False)

    # ------------------------------------------------------------------ Part 3: Crypto BTC & ETH (Zero-Tuning)
    print("[4/7] Backtesting Crypto BTC (2015-2026) & ETH zero-tuning (2018-2026) with borrow/funding stress...")
    crypto_rows = []
    btc_res_main: dict[str, lab.MultiEngineResult] = {}
    eth_res_main: dict[str, lab.MultiEngineResult] = {}

    btc_px = pd.DataFrame({"btc": btc_ohlc["Close"]}, index=btc_ohlc.index)
    btc_start_i = int(btc_ohlc.index.searchsorted(pd.Timestamp("2015-08-01")))
    for strat, w_arr in btc_sigs.items():
        res = lab.run_long_short_overlay(
            btc_px,
            weight_array_to_signal(w_arr, btc_start_i),
            btc_start_i,
            CONFIG["crypto"]["primary_cost"],
            btc_cp,
            btc_cp,
            short_rebate_ratio=0.0,
            short_annual_cost=CONFIG["crypto"]["primary_borrow_annual"],
        )
        btc_res_main[strat] = res
        m_full = summarize_ls(res, primary_col="btc", ann_days=365)
        m_early = summarize_ls(res, primary_col="btc", ann_days=365, start="2015-08-01", end="2020-12-31")
        m_mat = summarize_ls(res, primary_col="btc", ann_days=365, start="2021-01-01", end="2026-10-01")
        crypto_rows.append(
            {
                "asset": "BTC-USD",
                "cost_bps": 30,
                "borrow_annual": 0.03,
                "strategy": strat,
                **m_full,
                "early_cagr": m_early["cagr"],
                "early_sharpe": m_early["sharpe"],
                "early_mdd": m_early["max_dd"],
                "mature_cagr": m_mat["cagr"],
                "mature_sharpe": m_mat["sharpe"],
                "mature_mdd": m_mat["max_dd"],
            }
        )

    eth_px = pd.DataFrame({"eth": eth_ohlc["Close"]}, index=eth_ohlc.index)
    eth_start_i = int(eth_ohlc.index.searchsorted(pd.Timestamp("2018-09-01")))
    for strat, w_arr in eth_sigs.items():
        res = lab.run_long_short_overlay(
            eth_px,
            weight_array_to_signal(w_arr, eth_start_i),
            eth_start_i,
            CONFIG["crypto"]["primary_cost"],
            eth_cp,
            eth_cp,
            short_rebate_ratio=0.0,
            short_annual_cost=CONFIG["crypto"]["primary_borrow_annual"],
        )
        eth_res_main[strat] = res
        m_full = summarize_ls(res, primary_col="eth", ann_days=365)
        m_mat = summarize_ls(res, primary_col="eth", ann_days=365, start="2021-01-01", end="2026-10-01")
        crypto_rows.append(
            {
                "asset": "ETH-USD",
                "cost_bps": 30,
                "borrow_annual": 0.03,
                "strategy": strat,
                **m_full,
                "early_cagr": np.nan,
                "early_sharpe": np.nan,
                "early_mdd": np.nan,
                "mature_cagr": m_mat["cagr"],
                "mature_sharpe": m_mat["sharpe"],
                "mature_mdd": m_mat["max_dd"],
            }
        )
    pd.DataFrame(crypto_rows).to_csv(OUT_DIR / "summary_crypto_short.csv", index=False)

    # Crypto funding & cost stress matrix
    funding_rows = []
    for asset_name, px_df, sigs, cp, s_i in [
        ("BTC-USD", btc_px, btc_sigs, btc_cp, btc_start_i),
        ("ETH-USD", eth_px, eth_sigs, eth_cp, eth_start_i),
    ]:
        col = px_df.columns[0]
        for strat in ["HYB_ST_MA150_CASH", "SHORT_HYB_50", "SHORT_HYB_100", "LS_HYB_25", "LS_HYB_50", "LS_HYB_100", "LS_HYB_VOLCAP_50", "LS_MTF_50"]:
            for borrow_ann in CONFIG["crypto"]["funding_stress_annual"]:
                for cost_val in [0.003, 0.005]:
                    if strat == "HYB_ST_MA150_CASH" and borrow_ann != 0.03:
                        continue
                    r = lab.run_long_short_overlay(
                        px_df,
                        weight_array_to_signal(sigs[strat], s_i),
                        s_i,
                        cost_val,
                        cp,
                        cp,
                        short_rebate_ratio=0.0,
                        short_annual_cost=borrow_ann,
                    )
                    m = summarize_ls(r, primary_col=col, ann_days=365)
                    m_mat = summarize_ls(r, primary_col=col, ann_days=365, start="2021-01-01", end="2026-10-01")
                    funding_rows.append(
                        {
                            "asset": asset_name,
                            "strategy": strat,
                            "borrow_funding_ann": borrow_ann,
                            "cost_bps": int(round(cost_val * 10000)),
                            "cagr": m["cagr"],
                            "sharpe": m["sharpe"],
                            "max_dd": m["max_dd"],
                            "mature_cagr": m_mat["cagr"],
                            "mature_sharpe": m_mat["sharpe"],
                            "mature_mdd": m_mat["max_dd"],
                            "short_vs_cash": m["short_vs_cash_cum_diff"],
                            "worst_20d_squeeze": m["worst_20d_squeeze"],
                        }
                    )
    pd.DataFrame(funding_rows).to_csv(OUT_DIR / "crypto_funding_cost_stress.csv", index=False)

    # ------------------------------------------------------------------ Part 4: A-Share Reality Check
    print("[5/7] Running A-share short-selling reality check (0% ideal upper bound vs 8.5% retail 融券)...")
    ashare_rows = []
    for code, series in [
        ("H00300 (沪深300全收益)", h00300_s),
        ("510500 (中证500ETF)", csi500_df["Close"]),
        ("159915 (创业板ETF)", chinext_df["Close"]),
    ]:
        s = series.loc["2013-01-01":"2026-10-15"].dropna()
        px_df = pd.DataFrame({"a": s}, index=s.index)
        s_i = int(s.index.searchsorted(pd.Timestamp("2014-08-01")))
        cp, cn = ov.calendar_cash_factors(s.index, np.full(len(s), 0.02), 0.0)
        base_w = lab.daily_buffered_mtf3_equity_weight(s, 150, 20, 210, 0.03).to_numpy(float)
        bear_m = base_w < 1e-9
        cand_map = {
            "BH": np.ones(len(s)),
            "MTF3_BUF3_CASH": base_w,
            "SHORT_MTF3_50": np.where(bear_m, -0.50, 0.0),
            "LS_MTF3_50": np.where(bear_m, -0.50, base_w),
            "LS_MTF3_100": np.where(bear_m, -1.00, base_w),
        }
        for borrow_label, borrow_rate in [("ideal_0pct", 0.0), ("retail_rongquan_8.5pct", 0.085)]:
            for strat, w_arr in cand_map.items():
                if strat in ("BH", "MTF3_BUF3_CASH") and borrow_label != "retail_rongquan_8.5pct":
                    continue
                r = lab.run_long_short_overlay(
                    px_df,
                    weight_array_to_signal(w_arr, s_i),
                    s_i,
                    0.001,
                    cp,
                    cn,
                    short_rebate_ratio=0.0,
                    short_annual_cost=borrow_rate,
                )
                m = summarize_ls(r, primary_col="a", ann_days=252)
                m_ex15 = summarize_ls(r, primary_col="a", ann_days=252, start="2016-01-04", end="2026-10-15")
                ashare_rows.append(
                    {
                        "asset": code,
                        "friction_mode": borrow_label,
                        "strategy": strat,
                        **m,
                        "ex15_cagr": m_ex15["cagr"],
                        "ex15_sharpe": m_ex15["sharpe"],
                        "ex15_mdd": m_ex15["max_dd"],
                    }
                )
    pd.DataFrame(ashare_rows).to_csv(OUT_DIR / "summary_ashare_short.csv", index=False)

    # ------------------------------------------------------------------ Part 5: Crisis Anatomy & Squeeze Audit
    print("[6/7] Running crisis anatomy, short-leg permutation tests (200 trials), rolling starts, DCA & grid...")
    us_episodes = [
        ("2000-2002 互联网泡沫熊市", "2000-03-24", "2002-10-09"),
        ("2008 全球金融危机", "2007-10-09", "2009-03-09"),
        ("2011 欧债震荡期", "2011-05-01", "2012-03-01"),
        ("2015-2016 震荡期", "2015-05-01", "2016-06-30"),
        ("2018Q4 急跌与V反", "2018-09-20", "2019-04-30"),
        ("2020 疫情急跌与暴力逼空", "2020-02-19", "2020-08-31"),
        ("2022 加息熊市", "2022-01-03", "2022-10-14"),
        ("2023-2024 人工智能牛市", "2023-01-03", "2024-12-31"),
        ("2025 关税急跌与V反", "2025-02-19", "2025-07-31"),
    ]
    crypto_episodes = [
        ("2018 加密寒冬", "2017-12-17", "2018-12-15"),
        ("2019 下半年回调", "2019-06-26", "2020-03-16"),
        ("2020 疫情312暴跌与V反", "2020-02-13", "2020-08-31"),
        ("2021 519腰斩与下半年牛市", "2021-04-14", "2021-11-10"),
        ("2022 Luna/FTX熊市", "2021-11-10", "2022-11-21"),
        ("2023-2024 机构牛市", "2023-01-01", "2024-12-31"),
        ("2025-2026 震荡周期", "2025-01-01", "2026-10-01"),
    ]
    crisis_rows = []
    crisis_rows.extend(
        crisis_table_rows(
            {
                "BH": spy_res_retail["BH"],
                "CASH": spy_res_retail["MTF3_BUF3_CASH"],
                "SHORT50": spy_res_retail["SHORT_MTF3_50"],
                "LS50": spy_res_retail["LS_MTF3_50"],
                "LS100": spy_res_retail["LS_MTF3_100"],
                "LS_SLOPE50": spy_res_retail["LS_SLOPE_50"],
                "LS_VOLCAP50": spy_res_retail["LS_VOLCAP_50"],
            },
            us_episodes,
            "SPY",
        )
    )
    crisis_rows.extend(
        crisis_table_rows(
            {
                "BH": qqq_res_retail["BH"],
                "CASH": qqq_res_retail["MTF3_BUF3_CASH"],
                "SHORT50": qqq_res_retail["SHORT_MTF3_50"],
                "LS50": qqq_res_retail["LS_MTF3_50"],
                "LS100": qqq_res_retail["LS_MTF3_100"],
                "LS_SLOPE50": qqq_res_retail["LS_SLOPE_50"],
                "LS_VOLCAP50": qqq_res_retail["LS_VOLCAP_50"],
            },
            us_episodes,
            "QQQ",
        )
    )
    crisis_rows.extend(
        crisis_table_rows(
            {
                "BH": btc_res_main["BH"],
                "CASH": btc_res_main["HYB_ST_MA150_CASH"],
                "SHORT50": btc_res_main["SHORT_HYB_50"],
                "LS50": btc_res_main["LS_HYB_50"],
                "LS100": btc_res_main["LS_HYB_100"],
                "LS_SLOPE50": btc_res_main["LS_HYB_SLOPE_50"],
                "LS_VOLCAP50": btc_res_main["LS_HYB_VOLCAP_50"],
            },
            crypto_episodes,
            "BTC-USD",
        )
    )
    pd.DataFrame(crisis_rows).to_csv(OUT_DIR / "crisis_anatomy.csv", index=False)

    # 200-trial circular shift permutation tests specifically on the SHORT LEG
    perm_rows = []
    spy_px = pd.DataFrame({"spy": spy_ohlc["Close"]}, index=spy_ohlc.index)
    spy_si = int(spy_ohlc.index.searchsorted(pd.Timestamp("2000-01-03")))
    qqq_px = pd.DataFrame({"qqq": qqq_ohlc["Close"]}, index=qqq_ohlc.index)
    qqq_si = int(qqq_ohlc.index.searchsorted(pd.Timestamp("2000-03-01")))
    z_spy = np.zeros(len(spy_ohlc))
    z_qqq = np.zeros(len(qqq_ohlc))
    z_btc = np.zeros(len(btc_ohlc))
    z_eth = np.zeros(len(eth_ohlc))

    perm_specs = [
        ("SPY", "SHORT_MTF3_50", spy_px, z_spy, spy_sigs["SHORT_MTF3_50"], spy_si, 0.001, spy_cp, spy_cn, 0.0, 0.005, False, 252),
        ("SPY", "SHORT_SLOPE_50", spy_px, z_spy, spy_sigs["SHORT_SLOPE_50"], spy_si, 0.001, spy_cp, spy_cn, 0.0, 0.005, False, 252),
        ("SPY", "SHORT_FAST_ST_50", spy_px, z_spy, spy_sigs["SHORT_FAST_ST_50"], spy_si, 0.001, spy_cp, spy_cn, 0.0, 0.005, False, 252),
        ("SPY", "SHORT_TACTICAL_ST50", spy_px, z_spy, spy_sigs["SHORT_TACTICAL_ST50"], spy_si, 0.001, spy_cp, spy_cn, 0.0, 0.005, False, 252),
        ("SPY", "LS_MTF3_50 (Retail)", spy_px, spy_sigs["MTF3_BUF3_CASH"], spy_sigs["SHORT_MTF3_50"], spy_si, 0.001, spy_cp, spy_cn, 0.0, 0.005, False, 252),
        ("SPY", "LS_FAST_ST_50 (Retail)", spy_px, spy_sigs["MTF3_BUF3_CASH"], spy_sigs["SHORT_FAST_ST_50"], spy_si, 0.001, spy_cp, spy_cn, 0.0, 0.005, False, 252),
        ("SPY", "LS_MTF3_50 (InvETF)", spy_px, spy_sigs["MTF3_BUF3_CASH"], spy_sigs["SHORT_MTF3_50"], spy_si, 0.001, spy_cp, spy_cn, 1.0, 0.010, True, 252),
        ("QQQ", "SHORT_MTF3_50", qqq_px, z_qqq, qqq_sigs["SHORT_MTF3_50"], qqq_si, 0.001, qqq_cp, qqq_cn, 0.0, 0.005, False, 252),
        ("QQQ", "SHORT_FAST_ST_50", qqq_px, z_qqq, qqq_sigs["SHORT_FAST_ST_50"], qqq_si, 0.001, qqq_cp, qqq_cn, 0.0, 0.005, False, 252),
        ("QQQ", "SHORT_TACTICAL_ST50", qqq_px, z_qqq, qqq_sigs["SHORT_TACTICAL_ST50"], qqq_si, 0.001, qqq_cp, qqq_cn, 0.0, 0.005, False, 252),
        ("QQQ", "LS_MTF3_50 (Retail)", qqq_px, qqq_sigs["MTF3_BUF3_CASH"], qqq_sigs["SHORT_MTF3_50"], qqq_si, 0.001, qqq_cp, qqq_cn, 0.0, 0.005, False, 252),
        ("BTC-USD", "SHORT_HYB_50", btc_px, z_btc, btc_sigs["SHORT_HYB_50"], btc_start_i, 0.003, btc_cp, btc_cp, 0.0, 0.03, False, 365),
        ("BTC-USD", "SHORT_TACTICAL_ST50", btc_px, z_btc, btc_sigs["SHORT_TACTICAL_ST50"], btc_start_i, 0.003, btc_cp, btc_cp, 0.0, 0.03, False, 365),
        ("BTC-USD", "SHORT_HYB_VOLCAP_50", btc_px, z_btc, btc_sigs["SHORT_HYB_VOLCAP_50"], btc_start_i, 0.003, btc_cp, btc_cp, 0.0, 0.03, False, 365),
        ("BTC-USD", "LS_HYB_50 (3% borrow)", btc_px, btc_sigs["HYB_ST_MA150_CASH"], btc_sigs["SHORT_HYB_50"], btc_start_i, 0.003, btc_cp, btc_cp, 0.0, 0.03, False, 365),
        ("BTC-USD", "LS_HYB_VOLCAP_50", btc_px, btc_sigs["HYB_ST_MA150_CASH"], btc_sigs["SHORT_HYB_VOLCAP_50"], btc_start_i, 0.003, btc_cp, btc_cp, 0.0, 0.03, False, 365),
        ("ETH-USD", "SHORT_HYB_50 (OOS)", eth_px, z_eth, eth_sigs["SHORT_HYB_50"], eth_start_i, 0.003, eth_cp, eth_cp, 0.0, 0.03, False, 365),
        ("ETH-USD", "SHORT_TACTICAL_ST50 (OOS)", eth_px, z_eth, eth_sigs["SHORT_TACTICAL_ST50"], eth_start_i, 0.003, eth_cp, eth_cp, 0.0, 0.03, False, 365),
        ("ETH-USD", "LS_HYB_50 (OOS)", eth_px, eth_sigs["HYB_ST_MA150_CASH"], eth_sigs["SHORT_HYB_50"], eth_start_i, 0.003, eth_cp, eth_cp, 0.0, 0.03, False, 365),
    ]
    for idx_p, (a_nm, s_nm, p_df, lw, sw, si, cst, cp_v, cn_v, reb, b_ann, drs, ad) in enumerate(perm_specs):
        p_res = short_leg_circular_shift_pvalue(
            p_df, lw, sw, si,
            cost=cst, cash_pos=cp_v, cash_neg=cn_v,
            short_rebate_ratio=reb, short_annual_cost=b_ann, daily_reset_short=drs,
            ann_days=ad, n_trials=CONFIG["circular_shift_trials"], seed=20261123 + idx_p,
        )
        perm_rows.append({"asset": a_nm, "strategy": s_nm, **p_res})
    pd.DataFrame(perm_rows).to_csv(OUT_DIR / "permutation_short_leg.csv", index=False)

    # Parameter sensitivity grid: short size (-0%, -20%, -35%, -50%, -75%, -100%) across SPY, QQQ, BTC, ETH
    grid_rows = []
    for short_sz in [0.0, 0.20, 0.35, 0.50, 0.75, 1.00]:
        for asset_name, px_df, base_w, s_i, cst, cp_v, cn_v, reb, b_ann, ad, mod_start in [
            ("SPY", spy_px, spy_sigs["MTF3_BUF3_CASH"], spy_si, 0.001, spy_cp, spy_cn, 0.0, 0.005, 252, "2013-01-02"),
            ("QQQ", qqq_px, qqq_sigs["MTF3_BUF3_CASH"], qqq_si, 0.001, qqq_cp, qqq_cn, 0.0, 0.005, 252, "2013-01-02"),
            ("BTC-USD", btc_px, btc_sigs["HYB_ST_MA150_CASH"], btc_start_i, 0.003, btc_cp, btc_cp, 0.0, 0.03, 365, "2021-01-01"),
            ("ETH-USD", eth_px, eth_sigs["HYB_ST_MA150_CASH"], eth_start_i, 0.003, eth_cp, eth_cp, 0.0, 0.03, 365, "2021-01-01"),
        ]:
            col = px_df.columns[0]
            w_arr = np.where(base_w < 1e-9, -short_sz, base_w)
            r = lab.run_long_short_overlay(
                px_df, weight_array_to_signal(w_arr, s_i), s_i, cst, cp_v, cn_v,
                short_rebate_ratio=reb, short_annual_cost=b_ann,
            )
            m = summarize_ls(r, primary_col=col, ann_days=ad)
            m_mod = summarize_ls(r, primary_col=col, ann_days=ad, start=mod_start)
            grid_rows.append(
                {
                    "asset": asset_name,
                    "short_size": short_sz,
                    "cagr": m["cagr"],
                    "sharpe": m["sharpe"],
                    "max_dd": m["max_dd"],
                    "calmar": m["calmar"],
                    "modern_cagr": m_mod["cagr"],
                    "modern_sharpe": m_mod["sharpe"],
                    "modern_mdd": m_mod["max_dd"],
                    "short_vs_cash": m["short_vs_cash_cum_diff"],
                    "worst_5d_squeeze": m["worst_5d_squeeze"],
                    "worst_20d_squeeze": m["worst_20d_squeeze"],
                }
            )
    pd.DataFrame(grid_rows).to_csv(OUT_DIR / "short_size_sensitivity.csv", index=False)

    # Rolling 5Y / 10Y DCA comparison (Cash vs Long/Short)
    dca_rows = []
    for asset_name, res_dict, cash_key, ls_keys, win_m, cst in [
        ("SPY", spy_res_retail, "MTF3_BUF3_CASH", ["BH", "LS_MTF3_25", "LS_MTF3_50", "LS_MTF3_100", "LS_VOLCAP_50"], 120, 0.001),
        ("QQQ", qqq_res_retail, "MTF3_BUF3_CASH", ["BH", "LS_MTF3_25", "LS_MTF3_50", "LS_MTF3_100", "LS_VOLCAP_50"], 120, 0.001),
        ("BTC-USD", btc_res_main, "HYB_ST_MA150_CASH", ["BH", "LS_HYB_25", "LS_HYB_50", "LS_HYB_100", "LS_HYB_VOLCAP_50"], 60, 0.003),
    ]:
        base_dca = fast_dca_rolling(res_dict[cash_key].nav, win_m, cost=cst)
        for strat in [cash_key] + ls_keys:
            sd = fast_dca_rolling(res_dict[strat].nav, win_m, cost=cst)
            merged = sd.merge(base_dca, on=["start", "end"], suffixes=("_s", "_c"))
            dca_rows.append(
                {
                    "asset": asset_name,
                    "window_months": win_m,
                    "strategy": strat,
                    "n_windows": int(len(merged)),
                    "median_xirr": float(merged["xirr_s"].median()),
                    "worst_xirr": float(merged["xirr_s"].min()),
                    "loss_rate": float((merged["xirr_s"] < 0).mean()),
                    "median_unit_mdd": float(merged["unit_max_dd_s"].median()),
                    "median_dca_ratio": float(merged["dca_ratio_s"].median()),
                    "xirr_beat_cash_strat_share": float((merged["xirr_s"] > merged["xirr_c"]).mean()),
                    "ratio_beat_cash_strat_share": float((merged["dca_ratio_s"] > merged["dca_ratio_c"]).mean()),
                }
            )
    pd.DataFrame(dca_rows).to_csv(OUT_DIR / "rolling_dca_short_vs_cash.csv", index=False)

    # Rolling annual start-year comparison (SPY 2000-2024, BTC 2015-2024)
    annual_rows = []
    for yr in range(2000, 2025):
        s_str = f"{yr}-01-01"
        m_c = summarize_ls(spy_res_retail["MTF3_BUF3_CASH"], primary_col="spy", ann_days=252, start=s_str)
        m_50 = summarize_ls(spy_res_retail["LS_MTF3_50"], primary_col="spy", ann_days=252, start=s_str)
        m_vc = summarize_ls(spy_res_retail["LS_VOLCAP_50"], primary_col="spy", ann_days=252, start=s_str)
        annual_rows.append(
            {
                "asset": "SPY",
                "start_year": yr,
                "cash_cagr": m_c["cagr"],
                "ls50_cagr": m_50["cagr"],
                "lsvc_cagr": m_vc["cagr"],
                "cash_sharpe": m_c["sharpe"],
                "ls50_sharpe": m_50["sharpe"],
                "lsvc_sharpe": m_vc["sharpe"],
                "ls50_beats_cash_sharpe": bool(m_50["sharpe"] > m_c["sharpe"]),
                "ls50_beats_cash_cagr": bool(m_50["cagr"] > m_c["cagr"]),
            }
        )
    for yr in range(2015, 2025):
        s_str = f"{yr}-01-01" if yr > 2015 else "2015-08-01"
        m_c = summarize_ls(btc_res_main["HYB_ST_MA150_CASH"], primary_col="btc", ann_days=365, start=s_str)
        m_50 = summarize_ls(btc_res_main["LS_HYB_50"], primary_col="btc", ann_days=365, start=s_str)
        m_vc = summarize_ls(btc_res_main["LS_HYB_VOLCAP_50"], primary_col="btc", ann_days=365, start=s_str)
        annual_rows.append(
            {
                "asset": "BTC-USD",
                "start_year": yr,
                "cash_cagr": m_c["cagr"],
                "ls50_cagr": m_50["cagr"],
                "lsvc_cagr": m_vc["cagr"],
                "cash_sharpe": m_c["sharpe"],
                "ls50_sharpe": m_50["sharpe"],
                "lsvc_sharpe": m_vc["sharpe"],
                "ls50_beats_cash_sharpe": bool(m_50["sharpe"] > m_c["sharpe"]),
                "ls50_beats_cash_cagr": bool(m_50["cagr"] > m_c["cagr"]),
            }
        )
    pd.DataFrame(annual_rows).to_csv(OUT_DIR / "rolling_starts_annual.csv", index=False)

    # Track D: Cross-Asset Market-Neutral Relative-Value Long/Short Pairs (QQQ/SPY & BTC/ETH)
    pair_rows = []
    # D1: US Equity Pair (QQQ vs SPY, 2000-03-01..2026-10-16)
    us_pair_idx = spy_ohlc.index.intersection(qqq_ohlc.index)
    us_pair_px = pd.DataFrame(
        {"qqq": qqq_ohlc["Close"].reindex(us_pair_idx), "spy": spy_ohlc["Close"].reindex(us_pair_idx)},
        index=us_pair_idx,
    )
    us_pair_irx = irx_full.reindex(us_pair_idx).ffill().bfill()
    us_p_cp, us_p_cn = ov.calendar_cash_factors(us_pair_idx, us_pair_irx.to_numpy(float), 0.015)
    us_p_si = int(us_pair_idx.searchsorted(pd.Timestamp("2000-03-01")))
    ratio_qs = (us_pair_px["qqq"] / us_pair_px["spy"])
    for mom_d, name_p in [(60, "PAIR_QQQ_SPY_MOM60_50"), (120, "PAIR_QQQ_SPY_MOM120_50")]:
        # Buffered ratio trend: long QQQ/short SPY when ratio > MA*(1+2%), reverse below MA*(1-2%)
        r_on = lab.daily_buffered_ma_state(ratio_qs, ma_days=mom_d, buffer=0.02).to_numpy(bool)
        w_mat = np.column_stack([np.where(r_on, 0.50, -0.50), np.where(r_on, -0.50, 0.50)])
        for wrap_nm, reb, b_ann in [("retail_margin", 0.0, 0.005), ("pro_futures", 1.0, 0.005)]:
            rp = lab.run_long_short_overlay(
                us_pair_px, multi_weight_to_signal(w_mat, us_p_si), us_p_si, 0.001, us_p_cp, us_p_cn,
                short_rebate_ratio=reb, short_annual_cost=b_ann,
            )
            mf = summarize_ls(rp, primary_col="qqq", ann_days=252)
            me = summarize_ls(rp, primary_col="qqq", ann_days=252, start="2000-03-01", end="2012-12-31")
            mm = summarize_ls(rp, primary_col="qqq", ann_days=252, start="2013-01-02", end="2026-10-16")
            pair_rows.append(
                {
                    "pair": "QQQ/SPY",
                    "wrapper": wrap_nm,
                    "strategy": name_p,
                    "cagr": mf["cagr"],
                    "sharpe": mf["sharpe"],
                    "max_dd": mf["max_dd"],
                    "trades_per_year": mf["trades_per_year"],
                    "early_cagr": me["cagr"],
                    "early_sharpe": me["sharpe"],
                    "modern_cagr": mm["cagr"],
                    "modern_sharpe": mm["sharpe"],
                }
            )

    # D2: Crypto Pair (BTC vs ETH, 2018-09-01..2026-10-01)
    cr_pair_idx = btc_ohlc.index.intersection(eth_ohlc.index)
    cr_pair_px = pd.DataFrame(
        {"btc": btc_ohlc["Close"].reindex(cr_pair_idx), "eth": eth_ohlc["Close"].reindex(cr_pair_idx)},
        index=cr_pair_idx,
    )
    cr_p_cp = np.ones(len(cr_pair_idx), dtype=float)
    cr_p_si = int(cr_pair_idx.searchsorted(pd.Timestamp("2018-09-01")))
    ratio_be = cr_pair_px["btc"] / cr_pair_px["eth"]
    for mom_d, name_p in [(60, "PAIR_BTC_ETH_MOM60_50"), (120, "PAIR_BTC_ETH_MOM120_50")]:
        r_on = lab.daily_buffered_ma_state(ratio_be, ma_days=mom_d, buffer=0.05).to_numpy(bool)
        w_mat = np.column_stack([np.where(r_on, 0.50, -0.50), np.where(r_on, -0.50, 0.50)])
        for wrap_nm, b_ann in [("borrow_3pct", 0.03), ("funding_0pct", 0.0)]:
            rp = lab.run_long_short_overlay(
                cr_pair_px, multi_weight_to_signal(w_mat, cr_p_si), cr_p_si, 0.003, cr_p_cp, cr_p_cp,
                short_rebate_ratio=0.0, short_annual_cost=b_ann,
            )
            mf = summarize_ls(rp, primary_col="btc", ann_days=365)
            mm = summarize_ls(rp, primary_col="btc", ann_days=365, start="2021-01-01", end="2026-10-01")
            pair_rows.append(
                {
                    "pair": "BTC/ETH",
                    "wrapper": wrap_nm,
                    "strategy": name_p,
                    "cagr": mf["cagr"],
                    "sharpe": mf["sharpe"],
                    "max_dd": mf["max_dd"],
                    "trades_per_year": mf["trades_per_year"],
                    "early_cagr": np.nan,
                    "early_sharpe": np.nan,
                    "modern_cagr": mm["cagr"],
                    "modern_sharpe": mm["sharpe"],
                }
            )
    pd.DataFrame(pair_rows).to_csv(OUT_DIR / "pairs_relative_short.csv", index=False)

    # ------------------------------------------------------------------ Part 6: Strict Self-Checks & Provenance
    print("[7/7] Running anti-lookahead, cash conservation, fast-XIRR parity, and provenance self-checks...")
    # Verify fast_dca_rolling matches lab.dca_rolling_windows on a 60m BTC slice
    dca_fast_chk = fast_dca_rolling(btc_res_main["HYB_ST_MA150_CASH"].nav, 60, cost=0.003)
    dca_ref_chk = lab.dca_rolling_windows(btc_res_main["HYB_ST_MA150_CASH"].nav, 60, cost=0.003)
    dca_merged_chk = dca_fast_chk.merge(dca_ref_chk, on=["start", "end"], suffixes=("_f", "_r"))
    xirr_max_diff = float(np.max(np.abs(dca_merged_chk["xirr_f"] - dca_merged_chk["xirr_r"]))) if not dca_merged_chk.empty else 1.0
    assert xirr_max_diff < 1e-5, f"fast_xirr mismatch: {xirr_max_diff}"
    pert_spy = spy_ohlc.copy()
    cut_pos = 3500
    pert_spy.iloc[cut_pos + 1 :] *= 0.25
    s_orig = build_us_short_signals(spy_ohlc)["LS_VOLCAP_50"]
    s_pert = build_us_short_signals(pert_spy)["LS_VOLCAP_50"]
    us_no_lookahead = bool(np.array_equal(s_orig[: cut_pos + 1], s_pert[: cut_pos + 1]))

    pert_btc = btc_ohlc.copy()
    cut_b = 2000
    pert_btc.iloc[cut_b + 1 :] *= 0.25
    b_orig = build_crypto_short_signals(btc_ohlc)["LS_HYB_VOLCAP_50"]
    b_pert = build_crypto_short_signals(pert_btc)["LS_HYB_VOLCAP_50"]
    btc_no_lookahead = bool(np.array_equal(b_orig[: cut_b + 1], b_pert[: cut_b + 1]))

    max_cash_resid = max(
        max(r.checks["max_cash_residual"] for r in spy_res_retail.values()),
        max(r.checks["max_cash_residual"] for r in qqq_res_retail.values()),
        max(r.checks["max_cash_residual"] for r in btc_res_main.values()),
        max(r.checks["max_cash_residual"] for r in eth_res_main.values()),
    )

    self_checks = {
        "us_no_lookahead_perturbation_passed": us_no_lookahead,
        "btc_no_lookahead_perturbation_passed": btc_no_lookahead,
        "max_cash_residual": float(max_cash_resid),
        "cash_conservation_passed": bool(max_cash_resid < 1e-12),
        "fast_xirr_max_diff": xirr_max_diff,
        "fast_xirr_parity_passed": bool(xirr_max_diff < 1e-5),
        "short_hold_liquidated_spy": bool(spy_res_retail["SHORT_HOLD_100"].checks["liquidated"]),
        "short_hold_liquidated_qqq": bool(qqq_res_retail["SHORT_HOLD_100"].checks["liquidated"]),
        "short_hold_liquidated_btc": bool(btc_res_main["SHORT_HOLD_100"].checks["liquidated"]),
        "short_hold_liquidated_eth": bool(eth_res_main["SHORT_HOLD_100"].checks["liquidated"]),
        "data_hashes": {
            "yf_SPY.csv": sha256_file(US_SECTOR_CACHE / "yf_SPY.csv"),
            "yf_QQQ.csv": sha256_file(QQQ_CSV),
            "BTC-USD.parquet": sha256_file(BTC_PQ),
            "ETH-USD.parquet": sha256_file(ETH_PQ),
            "csindex_H00300.csv": sha256_file(CSI_CACHE / "csindex_H00300.csv"),
            "tickflow_forward_512100_159552_159915.json": sha256_file(TF_CACHE / "tickflow_forward_512100_159552_159915.json"),
        },
    }
    assert self_checks["us_no_lookahead_perturbation_passed"]
    assert self_checks["btc_no_lookahead_perturbation_passed"]
    assert self_checks["cash_conservation_passed"]

    (OUT_DIR / "config.json").write_text(json.dumps(CONFIG, ensure_ascii=False, indent=2) + "\n")
    (OUT_DIR / "self_checks.json").write_text(json.dumps(self_checks, ensure_ascii=False, indent=2) + "\n")

    # Print concise executive tables to stdout for immediate inspection
    print("\n--- SHORT-SELLING MARKET PHYSICS ---")
    print(
        physics_df[
            ["asset", "bh_cagr", "bear_time_share", "bear_ann_ret", "gross_short_edge_ann", "est_net_short_edge_ann", "pct_top20_1d_rallies_below200", "worst_1d_bear_rally_squeeze"]
        ].to_string(index=False)
    )

    us_df = pd.DataFrame(us_rows)
    print("\n--- US SPY (RETAIL MARGIN) ---")
    print(
        us_df[(us_df["asset"] == "SPY") & (us_df["wrapper"] == "retail_margin")][
            ["strategy", "cagr", "sharpe", "max_dd", "early_sharpe", "modern_sharpe", "short_vs_cash_cum_diff", "worst_20d_squeeze", "liquidated"]
        ].to_string(index=False)
    )
    print("\n--- US QQQ (RETAIL MARGIN) ---")
    print(
        us_df[(us_df["asset"] == "QQQ") & (us_df["wrapper"] == "retail_margin")][
            ["strategy", "cagr", "sharpe", "max_dd", "early_sharpe", "modern_sharpe", "short_vs_cash_cum_diff", "worst_20d_squeeze", "liquidated"]
        ].to_string(index=False)
    )
    print("\n--- US SPY SHORT VS SHIELDS (2005-2026) ---")
    print(
        pd.DataFrame(shield_compare_rows)[
            ["strategy", "cagr", "sharpe", "max_dd", "modern_2013_cagr", "modern_2013_sharpe", "modern_2013_mdd"]
        ].to_string(index=False)
    )

    cr_df = pd.DataFrame(crypto_rows)
    print("\n--- CRYPTO BTC & ETH (30bp, 3% BORROW) ---")
    print(
        cr_df[
            ["asset", "strategy", "cagr", "sharpe", "max_dd", "early_sharpe", "mature_sharpe", "short_vs_cash_cum_diff", "worst_20d_squeeze", "liquidated"]
        ].to_string(index=False)
    )

    print("\n--- A-SHARE SHORT REALITY CHECK ---")
    ash_df = pd.DataFrame(ashare_rows)
    print(
        ash_df[
            ["asset", "friction_mode", "strategy", "cagr", "sharpe", "max_dd", "ex15_sharpe", "short_vs_cash_cum_diff"]
        ].to_string(index=False)
    )

    print("\n--- SHORT-LEG CIRCULAR SHIFT PERMUTATION TESTS (200 TRIALS) ---")
    print(pd.DataFrame(perm_rows).to_string(index=False))

    print("\n--- CROSS-ASSET MARKET-NEUTRAL PAIRS (QQQ/SPY & BTC/ETH) ---")
    print(pd.DataFrame(pair_rows).to_string(index=False))

    print("\n--- ROLLING DCA (SHORT VS CASH) ---")
    print(pd.DataFrame(dca_rows).to_string(index=False))

    print(f"\nAll outputs written to {OUT_DIR}")


if __name__ == "__main__":
    main()
