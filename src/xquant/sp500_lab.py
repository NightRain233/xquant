"""Shared backtest engine, metrics, DCA evaluator, and frozen data loaders for S&P 500 4-direction research.

All four parallel strategy research scripts import this module so that every
candidate strategy is evaluated on identical data, identical execution clocks
(signal at close t, fill at close t+1), identical transaction-cost math, and
identical Sharpe/Calmar/DCA definitions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Sequence

import numpy as np
import pandas as pd

from xquant import cashflow_research as cf
from xquant import indicators as ind
from xquant import overlay_rules as ov
from xquant import position_rules as pr
from xquant import style_combo as sc
from xquant.weinstein_stage import load_yfinance_csv

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "outputs" / "sp500-four-directions-2026-11-22" / "cache"
US_SECTOR_CACHE = ROOT / "outputs" / "weinstein-us-sector-2026-10-18" / "cache"
SP500_DCA_CACHE = ROOT / "outputs" / "sp500-enhance-vs-dca-2026-11-10" / "cache"
BTC_MARKET_DIR = ROOT / "outputs" / "btc-satellite-corrected-prices-2026-10-18" / "market_data"
DOMESTIC_PREMIUM_FILE = ROOT / "outputs" / "qdii-premium-2026-11-10" / "premium_daily_513500.csv"
DOMESTIC_RAW_FILE = (
    ROOT / "outputs" / "domestic-etf-small-account-2026-10-04" / "evidence" / "raw_510300.SH.json"
)
DOMESTIC_RAW_SHA = "ace18b4e70d3029e959b7c72e77c6c6300a90ecd673fa1dcaf3c085c8d1ca8b6"

TRADING_DAYS = 252
US_MAIN_START = "2000-01-03"
US_GOLD_SPLICED_START = "2001-01-02"
US_GLD_START = "2005-01-03"
US_VIX3M_START = "2006-08-01"
US_END = "2026-10-16"
DOMESTIC_START = "2014-10-08"
DOMESTIC_END = "2026-09-30"

MultiSignal = Callable[[int, np.ndarray], Optional[np.ndarray]]


@dataclass
class MultiEngineResult:
    nav: pd.Series
    weights: pd.DataFrame
    trades: pd.DataFrame
    tbill_daily: pd.Series
    checks: dict = field(default_factory=dict)


def run_multi_asset_overlay(
    prices: pd.DataFrame,
    signal: MultiSignal,
    start_i: int,
    cost: float,
    cash_pos: np.ndarray,
    cash_neg: Optional[np.ndarray] = None,
    extra_daily_drag: Optional[dict[str, float]] = None,
) -> MultiEngineResult:
    """Close-to-close N-asset backtest matching ``overlay_rules.run_overlay`` exactly.

    Conventions:
    * Signal decides at close ``i`` using only data up to close ``i`` (passed ``actual_weights``).
    * Order fills at close ``i + 1`` with proportional cost ``cost`` per side on traded notional.
    * Uninvested cash earns ``cash_pos[i]``; negative cash borrows at ``cash_neg[i]``.
    * ``extra_daily_drag`` (optional): annualized fee/dividend/funding drag per asset column
      applied smoothly per calendar day to that asset's mark-to-market price factor.
    """
    cols = list(prices.columns)
    m = len(cols)
    dates = pd.DatetimeIndex(prices.index)
    px = prices[cols].to_numpy(float).copy()
    n = len(dates)

    if cash_neg is None:
        cash_neg = cash_pos

    if extra_daily_drag:
        day_diff = np.zeros(n, dtype=float)
        day_diff[1:] = (dates[1:] - dates[:-1]).days.to_numpy(float)
        for j, col in enumerate(cols):
            drag = float(extra_daily_drag.get(col, 0.0))
            if drag != 0.0:
                # Apply smooth multiplicative annualized drag from start_i onward
                factors = np.ones(n, dtype=float)
                factors[start_i + 1 :] = (1.0 - drag) ** (day_diff[start_i + 1 :] / 365.25)
                px[:, j] = px[:, j] * np.cumprod(factors)

    shares = np.zeros(m, dtype=float)
    cash = 1.0
    pending: Optional[np.ndarray] = None
    nav_list: list[float] = []
    wts_list: list[np.ndarray] = []
    trades_list: list[dict] = []
    max_resid = 0.0
    target_min = np.inf
    target_max = -np.inf

    for i in range(start_i, n):
        if i > start_i:
            cash *= cash_neg[i] if cash < 0 else cash_pos[i]
        if pending is not None:
            hold = shares * px[i]
            total = float(hold.sum() + cash)
            c_est = 0.0
            for _ in range(8):
                tgt = pending * (total - c_est)
                c_est = float(cost * np.abs(tgt - hold).sum())
            tgt = pending * (total - c_est)
            traded = float(np.abs(tgt - hold).sum())
            new_cash = float(total - c_est - tgt.sum())
            max_resid = max(max_resid, abs((float(tgt.sum()) + new_cash + c_est) - total))
            shares = tgt / px[i]
            cash = new_cash
            trades_list.append(
                {
                    "exec_date": dates[i],
                    "traded_frac": traded / total if total > 0 else 0.0,
                    "cost": c_est,
                    "is_initial": len(trades_list) == 0,
                }
            )
            pending = None

        hold = shares * px[i]
        v = float(hold.sum() + cash)
        w_now = hold / v if v > 0 else np.zeros(m, dtype=float)
        nav_list.append(v)
        wts_list.append(w_now)

        if i < n - 1:
            dec = signal(i, w_now)
            if dec is not None:
                arr = np.asarray(dec, dtype=float)
                if arr.shape != (m,):
                    raise ValueError(f"signal returned shape {arr.shape}, expected ({m},)")
                if not np.all(np.isfinite(arr)):
                    raise ValueError(f"non-finite target weights at {dates[i]}: {arr}")
                target_min = min(target_min, float(arr.min()))
                target_max = max(target_max, float(arr.sum()))
                pending = arr

    idx = dates[start_i:]
    nav = pd.Series(nav_list, index=idx, name="nav")
    weights = pd.DataFrame(wts_list, index=idx, columns=cols)
    weights["cash"] = 1.0 - weights[cols].sum(axis=1)
    trades = (
        pd.DataFrame(trades_list)
        if trades_list
        else pd.DataFrame(columns=["exec_date", "traded_frac", "cost", "is_initial"])
    )
    rf = pd.Series(cash_pos[start_i:] - 1.0, index=idx, name="tbill_daily")
    rf.iloc[0] = 0.0
    checks = {
        "max_cash_residual": float(max_resid),
        "nav_min": float(nav.min()),
        "target_weight_min": float(target_min) if np.isfinite(target_min) else 0.0,
        "target_sum_max": float(target_max) if np.isfinite(target_max) else 0.0,
    }
    return MultiEngineResult(nav=nav, weights=weights, trades=trades, tbill_daily=rf, checks=checks)


def fixed_weight_signal(target_weights: Sequence[float], dates: pd.DatetimeIndex, start_i: int, freq: str = "M"):
    """Fixed weights rebalanced on each period end (M / Q / Y), or buy-and-hold if freq=='NONE'."""
    w = np.asarray(target_weights, dtype=float)
    if freq == "NONE":
        return lambda i, _actual: w if i == start_i else None

    if freq == "M":
        mask = ov.month_end_mask(dates)
    else:
        mask = np.zeros(len(dates), dtype=bool)
        if len(dates) > 1:
            mask[:-1] = dates[:-1].to_period(freq) != dates[1:].to_period(freq)

    def sig(i: int, _actual: np.ndarray):
        if i == start_i or mask[i]:
            return w
        return None

    return sig


def max_underwater_years(nav: pd.Series) -> float:
    """Longest time (in years) spent below a prior running peak."""
    dd = nav / nav.cummax() - 1.0
    dates = pd.DatetimeIndex(nav.index)
    peak_date = dates[0]
    longest_days = 0
    for d, val in zip(dates, dd.to_numpy(float)):
        if val >= -1e-12:
            peak_date = d
        else:
            longest_days = max(longest_days, int((d - peak_date).days))
    return longest_days / 365.25


def summarize_result(
    res: MultiEngineResult,
    primary_col: str = "spy",
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> dict:
    """Compute standardized Q3 + Q5 metrics on a slice of a MultiEngineResult."""
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

    if len(nav) < 20:
        raise ValueError(f"slice too short: {len(nav)} rows")

    nav_norm = nav / nav.iloc[0]
    days = (nav_norm.index[-1] - nav_norm.index[0]).days
    years = days / 365.25
    cagr = float(nav_norm.iloc[-1] ** (1.0 / years) - 1.0)
    ret = nav_norm.pct_change().dropna()
    vol = float(ret.std(ddof=1) * np.sqrt(TRADING_DAYS))
    ex = ret - rf.reindex(ret.index).fillna(0.0)
    ex_std = float(ex.std(ddof=1))
    sharpe = float(ex.mean() / ex_std * np.sqrt(TRADING_DAYS)) if ex_std > 0 else np.nan
    sharpe_rf0 = float(ret.mean() / ret.std(ddof=1) * np.sqrt(TRADING_DAYS)) if ret.std(ddof=1) > 0 else np.nan

    dd = nav_norm / nav_norm.cummax() - 1.0
    max_dd = float(dd.min())
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else np.nan
    share_dd20 = float((dd < -0.20).mean())
    underwater_y = max_underwater_years(nav_norm)

    # Monthly and calendar-year Q5 metrics
    monthly = nav_norm.resample("ME").last().pct_change().dropna()
    yearly = nav_norm.resample("YE").last().pct_change().dropna()
    monthly_win = float((monthly > 0).mean()) if len(monthly) else np.nan
    worst_month = float(monthly.min()) if len(monthly) else np.nan
    worst_year = float(yearly.min()) if len(yearly) else np.nan

    non_init_trades = trades[~trades["is_initial"]] if not trades.empty else trades
    trades_per_year = float(len(non_init_trades) / years) if years > 0 else 0.0
    annual_turnover = float(non_init_trades["traded_frac"].sum() / years) if (not non_init_trades.empty and years > 0) else 0.0

    out = {
        "start": str(nav.index[0].date()),
        "end": str(nav.index[-1].date()),
        "years": round(years, 2),
        "cagr": cagr,
        "vol": vol,
        "sharpe": sharpe,
        "sharpe_rf0": sharpe_rf0,
        "max_dd": max_dd,
        "calmar": calmar,
        "share_dd_below_20": share_dd20,
        "max_underwater_years": underwater_y,
        "monthly_win_rate": monthly_win,
        "worst_month": worst_month,
        "worst_year": worst_year,
        "trades_per_year": trades_per_year,
        "annual_turnover": annual_turnover,
        "terminal_multiple": float(nav_norm.iloc[-1]),
    }
    if primary_col in wts.columns:
        out["avg_primary_weight"] = float(wts[primary_col].iloc[1:].mean())
    for col in wts.columns:
        out[f"avg_w_{col}"] = float(wts[col].iloc[1:].mean())
    return out


def dca_full_path(nav: pd.Series, cost: float = 0.001) -> dict:
    """Monthly first-trading-day DCA of 1 unit into strategy NAV."""
    dates = pd.DatetimeIndex(nav.index)
    contrib_mask = ~dates.to_period("M").duplicated()
    contrib_dates = dates[contrib_mask]
    buys = pd.Series(0.0, index=dates)
    buys.loc[contrib_dates] = (1.0 - cost) / nav.loc[contrib_dates]
    units = buys.cumsum()
    principal = pd.Series(0.0, index=dates)
    principal.loc[contrib_dates] = 1.0
    principal = principal.cumsum()
    value = units * nav
    float_ret = value / principal.replace(0.0, np.nan) - 1.0
    unit_dd = nav / nav.cummax() - 1.0
    val_end = float(value.iloc[-1])
    x = float(cf.xirr(pd.Series(1.0, index=contrib_dates), val_end, dates[-1]))
    u_mdd = float(unit_dd.min())
    return {
        "n_months": int(len(contrib_dates)),
        "xirr": x,
        "max_float_loss": float(float_ret.dropna().min()),
        "unit_max_dd": u_mdd,
        "dca_ratio": float(x / abs(u_mdd)) if u_mdd < 0 else np.nan,
        "terminal_per_unit": float(val_end / len(contrib_dates)),
    }


def dca_rolling_windows(nav: pd.Series, window_months: int = 120, cost: float = 0.001) -> pd.DataFrame:
    """Complete rolling N-month DCA windows starting on each month's first trading day."""
    dates = pd.DatetimeIndex(nav.index)
    first_days = dates[~dates.to_period("M").duplicated()]
    periods = dates.to_period("M")
    rows = []
    for day in first_days:
        end_p = day.to_period("M") + window_months - 1
        part = nav[(dates >= day) & (periods <= end_p)]
        if part.empty or part.index[-1].to_period("M") != end_p:
            continue
        # Ensure the end month is complete (not truncated mid-month before the last available date unless last day of month)
        stats = dca_full_path(part, cost=cost)
        if stats["n_months"] != window_months:
            continue
        rows.append({"start": str(day.date()), "end": str(part.index[-1].date()), **stats})
    return pd.DataFrame(rows)


def compare_dca_windows(strat_nav: pd.Series, bench_nav: pd.Series, window_months: int = 120, cost: float = 0.001) -> dict:
    sw = dca_rolling_windows(strat_nav, window_months=window_months, cost=cost)
    bw = dca_rolling_windows(bench_nav, window_months=window_months, cost=cost)
    if sw.empty or bw.empty:
        return {"n_windows": 0}
    merged = sw.merge(bw, on=["start", "end"], suffixes=("_s", "_b"))
    return {
        "n_windows": int(len(merged)),
        "median_xirr": float(merged["xirr_s"].median()),
        "bench_median_xirr": float(merged["xirr_b"].median()),
        "worst_xirr": float(merged["xirr_s"].min()),
        "bench_worst_xirr": float(merged["xirr_b"].min()),
        "median_float_loss": float(merged["max_float_loss_s"].median()),
        "bench_median_float_loss": float(merged["max_float_loss_b"].median()),
        "median_dca_ratio": float(merged["dca_ratio_s"].median()),
        "bench_median_dca_ratio": float(merged["dca_ratio_b"].median()),
        "ratio_beat_share": float((merged["dca_ratio_s"] > merged["dca_ratio_b"]).mean()),
        "xirr_beat_share": float((merged["xirr_s"] > merged["xirr_b"]).mean()),
    }


def load_close_csv(path: Path, col: str = "Close") -> pd.Series:
    df = pd.read_csv(path)
    date_col = df.columns[0]
    # Slice YYYY-MM-DD directly so exchange-local trading dates never shift across UTC boundaries
    idx = pd.to_datetime(df[date_col].astype(str).str.slice(0, 10))
    s = pd.to_numeric(df[col], errors="coerce")
    out = pd.Series(s.to_numpy(float), index=idx, name=path.stem).dropna()
    return out[~out.index.duplicated(keep="last")].sort_index()


def load_fred_csv(path: Path) -> pd.Series:
    df = pd.read_csv(path)
    idx = pd.DatetimeIndex(pd.to_datetime(df.iloc[:, 0])).normalize()
    val = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    out = pd.Series(val.to_numpy(float), index=idx, name=path.stem).dropna()
    return out[~out.index.duplicated(keep="last")].sort_index()


def load_synthetic_ief(spy_index: pd.DatetimeIndex) -> pd.Series:
    """Real IEF from 2002-07-30, spliced backward with duration-7 synthetic bond from FRED DGS10."""
    ief = load_close_csv(SP500_DCA_CACHE / "yf_IEF" / "yf_IEF.csv")
    dgs10 = load_fred_csv(SP500_DCA_CACHE / "fred_DGS10" / "fred_DGS10.csv") / 100.0
    y = dgs10.reindex(spy_index).ffill().bfill()
    dy = y.diff().fillna(0.0)
    # Approximate daily total return of 7-10y Treasury (matching research_sp500_enhance_vs_dca.py)
    dt = spy_index.to_series().diff().dt.days.fillna(1.0) / 365.25
    synth_ret = y.shift(1).fillna(y.iloc[0]) * dt - 7.0 * dy
    synth = (1.0 + synth_ret.clip(-0.15, 0.15)).cumprod()
    first_ief = ief.index[0]
    ief_aligned = ief.reindex(spy_index).ffill()
    scale = float(ief.iloc[0] / synth.loc[:first_ief].iloc[-1])
    combined = synth * scale
    combined.loc[first_ief:] = ief_aligned.loc[first_ief:]
    return combined.rename("ief")


def load_gold_series(spy_index: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series, dict]:
    """Return (gld_real, gold_spliced, diagnostics).

    ``gld_real`` is pure GLD ETF (auto-adjusted, starting 2004-11-18).
    ``gold_spliced`` uses real GLD from 2004-11-18 onward, and splices backward to 1998-12
    using stooq XAUUSD (or Yahoo GC=F if stooq unavailable), deducting GLD's 0.40%/yr fee on the
    spliced pre-2004 segment. Overlap correlation & annual drift are reported in diagnostics.
    """
    gld = load_close_csv(CACHE_DIR / "yf_GLD.csv")
    gld_aligned = gld.reindex(spy_index).ffill()

    xau_path = CACHE_DIR / "stooq_xauusd.csv"
    gcf_path = CACHE_DIR / "yf_GCF.csv"
    proxy_name = None
    proxy = None
    if xau_path.exists():
        proxy = load_close_csv(xau_path, col="Close")
        proxy_name = "stooq_xauusd"
    elif gcf_path.exists():
        proxy = load_close_csv(gcf_path, col="Close")
        proxy_name = "yf_GCF"

    if proxy is None:
        return gld_aligned.rename("gld"), gld_aligned.rename("gold"), {"proxy": None}

    proxy_aligned = proxy.reindex(spy_index).ffill()
    first_gld = gld.index[0]
    # Validate overlap between GLD and proxy
    ov_idx = gld.index.intersection(proxy.index)
    r_gld = gld.loc[ov_idx].pct_change().dropna()
    r_prx = proxy.loc[ov_idx].pct_change().dropna()
    common = r_gld.index.intersection(r_prx.index)
    corr = float(r_gld.loc[common].corr(r_prx.loc[common])) if len(common) > 20 else np.nan

    # Apply 0.40%/yr fee adjustment backward from first_gld on spliced segment
    days_from_join = (spy_index - first_gld).days.to_numpy(float)
    fee_adj = np.where(days_from_join < 0, (1.0 - 0.004) ** (days_from_join / 365.25), 1.0)
    # Wait: going backward in time, if an ETF had 0.40% fee, its historical price was HIGHER before fee drag,
    # meaning forward return was lower by 0.40%/yr -> P_etf(t) = P_spot(t) * scale * (1 - 0.004)^((t - t0)/365.25)
    # Check: when t < t0, (t - t0) < 0 so (1-0.004)^(negative) > 1, hence going forward t -> t0 loses 0.40%/yr. Correct!
    join_proxy = float(proxy_aligned.loc[first_gld])
    join_gld = float(gld.iloc[0])
    spliced = proxy_aligned * (join_gld / join_proxy) * fee_adj
    spliced.loc[first_gld:] = gld_aligned.loc[first_gld:]
    diag = {
        "proxy": proxy_name,
        "gld_start": str(first_gld.date()),
        "spliced_first_valid": str(spliced.first_valid_index().date()),
        "overlap_daily_corr": corr,
        "pre_gld_fee_assumption": 0.004,
    }
    return gld_aligned.rename("gld"), spliced.rename("gold"), diag


def load_us_bundle() -> dict:
    """Load all frozen US daily series aligned to SPY trading dates (1998-12-01 to 2026-10-16)."""
    spy = load_yfinance_csv(US_SECTOR_CACHE / "yf_SPY.csv")["close"].rename("spy")
    irx = load_yfinance_csv(US_SECTOR_CACHE / "yf_IRX.csv")["close"].rename("irx") / 100.0
    keep = (spy.index >= pd.Timestamp("1998-12-01")) & (spy.index <= pd.Timestamp(US_END))
    spy = spy.loc[keep]
    dates = pd.DatetimeIndex(spy.index)
    irx = irx.reindex(dates.union(irx.index)).ffill().reindex(dates).bfill()
    cash_pos, cash_neg = ov.calendar_cash_factors(dates, irx.to_numpy(float), 0.015)

    ief = load_synthetic_ief(dates)
    gld_real, gold_spliced, gold_diag = load_gold_series(dates)

    extras = {}
    for key in ("yf_SPHQ", "yf_SPLV", "yf_RSP", "yf_SHY", "yf_HYG", "yf_VIX", "yf_VIX3M"):
        p = CACHE_DIR / f"{key}.csv"
        if p.exists():
            extras[key.replace("yf_", "").lower()] = load_close_csv(p).reindex(dates).ffill()

    baa_path = CACHE_DIR / "fred_BAA10Y.csv"
    baa10y = load_fred_csv(baa_path).reindex(dates).ffill() if baa_path.exists() else None
    hy_path = CACHE_DIR / "fred_BAMLH0A0HYM2.csv"
    hy_oas = load_fred_csv(hy_path).reindex(dates).ffill() if hy_path.exists() else None

    return {
        "dates": dates,
        "spy": spy,
        "irx": irx,
        "cash_pos": cash_pos,
        "cash_neg": cash_neg,
        "ief": ief,
        "gld_real": gld_real,
        "gold_spliced": gold_spliced,
        "gold_diag": gold_diag,
        "baa10y": baa10y,
        "hy_oas": hy_oas,
        **extras,
    }


def load_domestic_bundle() -> dict:
    """Load real RMB 513500 (split-adjusted unadjusted close), 518880 (total-return close), and 513500 premium."""
    import hashlib
    import json

    assert hashlib.sha256(DOMESTIC_RAW_FILE.read_bytes()).hexdigest() == DOMESTIC_RAW_SHA
    raw_doc = json.loads(DOMESTIC_RAW_FILE.read_text())["data"]["513500.SH"]
    raw_dates = (
        pd.to_datetime(raw_doc["timestamp"], unit="ms", utc=True)
        .tz_convert("Asia/Shanghai")
        .tz_localize(None)
        .normalize()
    )
    c513500 = pd.Series(np.asarray(raw_doc["close"], float), index=raw_dates).sort_index()
    c513500 = c513500[~c513500.index.duplicated()]
    c513500.loc[c513500.index < pd.Timestamp("2022-03-30")] /= 2.0
    c513500_full = c513500[c513500.index <= pd.Timestamp(DOMESTIC_END)]
    c513500_window = c513500_full[c513500_full.index >= pd.Timestamp(DOMESTIC_START)]

    p518 = pd.read_parquet(BTC_MARKET_DIR / "518880.SS.parquet")["Close"]
    p518.index = pd.DatetimeIndex(p518.index).normalize()
    c518880_full = p518.reindex(c513500_full.index).ffill()
    c518880 = c518880_full.reindex(c513500_window.index).ffill()

    prem_df = pd.read_csv(DOMESTIC_PREMIUM_FILE, parse_dates=["date"]).set_index("date").sort_index()
    prem_df.index = pd.DatetimeIndex(prem_df.index).normalize()
    prem_aligned = prem_df.reindex(c513500_window.index)

    dates = pd.DatetimeIndex(c513500_window.index)
    # 2% RMB cash proxy matching repo convention
    cash_pos, cash_neg = ov.calendar_cash_factors(dates, np.full(len(dates), 0.02), 0.0)
    return {
        "dates": dates,
        "c513500": c513500_window.rename("c513500"),
        "c513500_full": c513500_full.rename("c513500"),
        "c518880": c518880.rename("c518880"),
        "c518880_full": c518880_full.rename("c518880"),
        "premium_decision": prem_aligned["premium"],
        "premium_after": prem_aligned["premium_after_the_fact"],
        "estimated_nav": prem_aligned["estimated_nav"],
        "cash_pos": cash_pos,
        "cash_neg": cash_neg,
    }


def weekly_stage2_state(close: pd.Series, ma_weeks: int = 30, slope_weeks: int = 4) -> pd.Series:
    """Weekly close > rising ma_weeks SMA (exact S2 definition), forward-filled to daily index as strict bool."""
    states = pr.stage_states(close, ma_weeks=ma_weeks, slope_weeks=slope_weeks)
    aligned = states.reindex(close.index, method="ffill")
    return aligned.where(aligned.notna(), False).astype(bool)


def monthly_ma_state(close: pd.Series, ma_months: int = 10) -> pd.Series:
    """Month-end close > ma_months SMA of month-end closes, forward-filled to daily index as strict bool."""
    idx = np.flatnonzero(ov.month_end_mask(close.index))
    vals = close.iloc[idx]
    sma = vals.rolling(ma_months).mean()
    dec = (vals > sma).astype(bool)
    out = pd.Series(pd.NA, index=close.index, dtype="object")
    out.iloc[idx] = dec.to_numpy()
    out = out.ffill()
    return out.where(out.notna(), False).astype(bool)


def daily_buffered_stage_state(
    close: pd.Series,
    ma_days: int = 150,
    slope_days: int = 20,
    buffer: float = 0.03,
) -> pd.Series:
    """Daily rising-MA hysteresis state: OFF below MA*(1-buf), ON above MA*(1+buf) when MA is rising."""
    ma = close.rolling(ma_days).mean()
    rising = (ma > ma.shift(slope_days)).to_numpy(dtype=bool)
    vals = close.to_numpy(dtype=float)
    ma_v = ma.to_numpy(dtype=float)
    out = np.zeros(len(close), dtype=bool)
    on = False
    for i in range(len(close)):
        if np.isnan(ma_v[i]):
            continue
        if vals[i] < ma_v[i] * (1.0 - buffer):
            on = False
        elif vals[i] > ma_v[i] * (1.0 + buffer) and rising[i]:
            on = True
        out[i] = on
    return pd.Series(out, index=close.index, dtype=bool)


def daily_buffered_ma_state(
    close: pd.Series,
    ma_days: int = 210,
    buffer: float = 0.03,
) -> pd.Series:
    """Daily MA hysteresis state: OFF below MA*(1-buf), ON above MA*(1+buf), hold inside deadband."""
    ma = close.rolling(ma_days).mean().to_numpy(dtype=float)
    vals = close.to_numpy(dtype=float)
    out = np.zeros(len(close), dtype=bool)
    on = False
    for i in range(len(close)):
        if np.isnan(ma[i]):
            continue
        if vals[i] < ma[i] * (1.0 - buffer):
            on = False
        elif vals[i] > ma[i] * (1.0 + buffer):
            on = True
        out[i] = on
    return pd.Series(out, index=close.index, dtype=bool)


def daily_buffered_mtf3_equity_weight(
    close: pd.Series,
    ma_fast: int = 150,
    slope_days: int = 20,
    ma_slow: int = 210,
    buffer: float = 0.03,
) -> pd.Series:
    """Three-tier daily buffered MTF-3 target equity weight (1.0 / 0.5 / 0.0)."""
    fast_on = daily_buffered_stage_state(close, ma_days=ma_fast, slope_days=slope_days, buffer=buffer)
    slow_on = daily_buffered_ma_state(close, ma_days=ma_slow, buffer=buffer)
    score = fast_on.astype(int) + slow_on.astype(int)
    return pd.Series(
        np.where(score == 2, 1.0, np.where(score == 1, 0.5, 0.0)),
        index=close.index,
        dtype=float,
    )


def map_us_series_to_cn_strict(us_series: pd.Series, cn_dates: pd.DatetimeIndex) -> tuple[pd.Series, int]:
    """Map US close-dated series onto CN decision dates requiring strictly us_date < cn_date.

    Returns (mapped_series, min_calendar_lag_days).
    """
    us_dates = pd.DatetimeIndex(us_series.index)
    us_vals = us_series.to_numpy()
    pos = np.searchsorted(us_dates.to_numpy(), cn_dates.to_numpy(), side="left") - 1
    if (pos < 0).any():
        raise ValueError("US series does not start strictly before all CN dates")
    matched_dates = us_dates[pos]
    min_lag = int((cn_dates - matched_dates).days.min())
    if min_lag < 1:
        raise AssertionError(f"Cross-market lookahead detected: min_lag={min_lag}")
    return pd.Series(us_vals[pos], index=cn_dates, dtype=us_series.dtype), min_lag


def daily_buffered_st_ma_weight(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    atr_window: int = 10,
    multiplier: float = 3.0,
    ma_days: int = 150,
    buffer: float = 0.05,
) -> pd.Series:
    """Three-tier daily weight (1.0 / 0.5 / 0.0): Lamp 1 = SuperTrend, Lamp 2 = buffered long MA."""
    st_on = ind.supertrend_direction(high, low, close, atr_window=atr_window, multiplier=multiplier)
    ma_on = daily_buffered_ma_state(close, ma_days=ma_days, buffer=buffer)
    score = st_on.astype(int) + ma_on.astype(int)
    return pd.Series(
        np.where(score == 2, 1.0, np.where(score == 1, 0.5, 0.0)),
        index=close.index,
        dtype=float,
    )


def daily_buffered_vol_throttle(
    close: pd.Series,
    vol_window: int = 21,
    low_vol: float = 0.14,
    high_vol: float = 0.22,
    hysteresis: float = 0.02,
    mid_weight: float = 0.60,
    high_weight: float = 0.20,
    ann_days: int = 252,
) -> pd.Series:
    """Three-tier volatility throttle with symmetric hysteresis deadband (1.0 / mid_weight / high_weight)."""
    vol = np.log(close).diff().rolling(vol_window).std(ddof=1) * np.sqrt(float(ann_days))
    v_arr = vol.to_numpy(dtype=float)
    out = np.ones(len(close), dtype=float)
    tier = 0
    for i in range(len(close)):
        v = v_arr[i]
        if np.isnan(v):
            out[i] = 1.0
            continue
        if tier == 0:
            if v > high_vol + hysteresis:
                tier = 2
            elif v > low_vol + hysteresis:
                tier = 1
        elif tier == 1:
            if v > high_vol + hysteresis:
                tier = 2
            elif v < low_vol - hysteresis:
                tier = 0
        else:
            if v < low_vol - hysteresis:
                tier = 0
            elif v < high_vol - hysteresis:
                tier = 1
        out[i] = 1.0 if tier == 0 else (mid_weight if tier == 1 else high_weight)
    return pd.Series(out, index=close.index, dtype=float)
