"""Pre-registered test (2026-11-10): S&P 500 "enhancement" rules vs buy-and-hold and monthly DCA.

Run (from repo root, after ``scripts/fetch_sp500_enhance_data.py``):
  uv run python -I scripts/research_sp500_enhance_vs_dca.py

Inputs: ``outputs/sp500-enhance-vs-dca-2026-11-10/cache`` (hashes checked against ``fetch_manifest.json``) and the
SPY / ^IRX cache of ``weinstein-us-sector-2026-10-18`` (checked by ``load_sp500``). Rules, windows, costs and verdict
criteria are fixed in CONFIG and written to config.json before any result is computed. Sensitivity runs are reported
only and never used to choose a rule. Cached downloads are parsed with pandas only and never executed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from research_index_enhance_strategies import load_sp500  # noqa: E402
from xquant import band_timing as bt  # noqa: E402
from xquant import overlay_rules as ov  # noqa: E402
from xquant import position_rules as pr  # noqa: E402
from xquant import style_combo as sc  # noqa: E402
from xquant.weinstein_stage import load_yfinance_csv  # noqa: E402

SLUG = "sp500-enhance-vs-dca-2026-11-10"
OUT = ROOT / "outputs" / SLUG
CACHE = OUT / "cache"
US_DIR = ROOT / "outputs" / "weinstein-us-sector-2026-10-18"
OLD_VERDICTS = ROOT / "outputs" / "index-enhance-strategies-2026-11-05" / "verdicts.csv"

END = "2026-10-16"
MAIN_START, START_2003 = "2000-01-03", "2003-01-02"
COST, COST30, BORROW = 0.001, 0.003, 0.015
SEG1, SEG2 = ("2000-01-03", "2012-12-31"), ("2013-01-01", END)
SEGMENTS = {"2000-01-03~2012-12-31": SEG1, "2013-01-01~2026-10-16": SEG2}
LONG_UNIVERSE_START = "1934-01-02"  # warm-up; TB3MS and the Shiller dividends cover it
LONG_RUN_START, LONG_GTT_START, LONG_END = "1935-01-01", "1949-01-01", "1999-12-31"
LONG_HALVES = {"1935-1966": ("1935-01-01", "1966-12-31"), "1967-1999": ("1967-01-01", "1999-12-31")}
LONG_GTT_HALVES = {"1949-1966": ("1949-01-01", "1966-12-31"), "1967-1999": ("1967-01-01", "1999-12-31")}
ROLLING_YEARS = range(2000, 2024)
KEY_PERIODS = {"2000-03-24~2002-10-09": ("2000-03-24", "2002-10-09"),
               "2007-10-09~2009-03-09": ("2007-10-09", "2009-03-09"),
               "2020-02-19~2020-03-23": ("2020-02-19", "2020-03-23"),
               "2022 full year": ("2022-01-01", "2022-12-31"),
               "2023-01-01~2026-10-16": ("2023-01-01", END)}
POST_PUBLICATION = {"F10": 2007, "DM-cash": 2014, "DM-IEF": 2014, "GTT": 2016, "VT-1.0": 2017, "VT-1.5": 2017,
                    "F10xVT": 2017, "TOM": 1988, "HAL": 2002, "RSI2": 2008}

# (label, rule key understood by overlay_rules.build_signal, frozen parameters)
STRATEGIES = [
    ("S2", "S2", {}),
    ("S1", "S1", {}),
    ("F10", "F10", {"months": 10}),
    ("DM-cash", "DM", {"months": 12}),
    ("DM-IEF", "DM_IEF", {"months": 12}),
    ("GTT", "GTT", {"months": 10}),
    ("VT-1.0", "VT", {"target": 0.15, "window": 21}),
    ("VT-1.5", "VT15", {"target": 0.15, "window": 21}),
    ("F10xVT", "F10xVT", {"months": 10, "target": 0.15, "window": 21}),
    ("TOM", "TOM", {"last_n": 1, "first_n": 3}),
    ("HAL", "HAL", {}),
    ("RSI2", "RSI2", {"entry_below": 10.0}),
]
LABELS = [label for label, _, _ in STRATEGIES]
CAPS = {"S1": 1.5, "VT-1.5": 1.5}
B0 = "B0"
# (variant, family, rule key, parameters); reported only
SENSITIVITY = [
    ("F10 SMA 8 months", "F10", "F10", {"months": 8}),
    ("F10 SMA 12 months", "F10", "F10", {"months": 12}),
    ("DM-cash lookback 6 months", "DM-cash", "DM", {"months": 6}),
    ("DM-cash lookback 9 months", "DM-cash", "DM", {"months": 9}),
    ("DM-IEF lookback 6 months", "DM-IEF", "DM_IEF", {"months": 6}),
    ("DM-IEF lookback 9 months", "DM-IEF", "DM_IEF", {"months": 9}),
    ("VT-1.0 target 0.12", "VT-1.0", "VT", {"target": 0.12, "window": 21}),
    ("VT-1.0 target 0.18", "VT-1.0", "VT", {"target": 0.18, "window": 21}),
    ("VT-1.0 vol window 10 days", "VT-1.0", "VT", {"target": 0.15, "window": 10}),
    ("VT-1.0 vol window 63 days", "VT-1.0", "VT", {"target": 0.15, "window": 63}),
    ("VT-1.5 target 0.12", "VT-1.5", "VT15", {"target": 0.12, "window": 21}),
    ("VT-1.5 target 0.18", "VT-1.5", "VT15", {"target": 0.18, "window": 21}),
    ("VT-1.5 vol window 10 days", "VT-1.5", "VT15", {"target": 0.15, "window": 10}),
    ("VT-1.5 vol window 63 days", "VT-1.5", "VT15", {"target": 0.15, "window": 63}),
    ("TOM last 1 + first 2 days", "TOM", "TOM", {"last_n": 1, "first_n": 2}),
    ("TOM last 2 + first 4 days", "TOM", "TOM", {"last_n": 2, "first_n": 4}),
    ("RSI2 entry below 5", "RSI2", "RSI2", {"entry_below": 5.0}),
    ("RSI2 entry below 20", "RSI2", "RSI2", {"entry_below": 20.0}),
    ("GTT SMA 12 months", "GTT", "GTT", {"months": 12}),
]
SD1_VARIANTS = {"SD1 base (-10% / -20%)": (-0.10, -0.20),
                "SD1 thresholds (-5% / -15%)": (-0.05, -0.15),
                "SD1 thresholds (-15% / -30%)": (-0.15, -0.30)}

RULE_TEXT = {
    "B0": "SPY buy-and-hold (dividend-adjusted); fully invested from the fill after the window-start close",
    "S2": "half-trend: 100% SPY while weekly close > rising 30-week mean, 50% after a weekly close below it (position_rules.rule_stage_blend)",
    "S1": "trend leverage: 1.5x SPY while weekly close > 200-day mean, re-levered at month ends, else cash (position_rules.rule_trend_leverage)",
    "F10": "Faber: month-end close > mean of the last 10 month-end closes -> 100% SPY, else cash; fill next close",
    "DM-cash": "Antonacci absolute momentum: month-end SPY trailing 12-month total return > trailing 12-month compounded T-bill -> 100% SPY, else cash",
    "DM-IEF": "as DM-cash, but the off state holds the bond (IEF from 2002-07-30; before that a synthetic bond from DGS10)",
    "GTT": "growth-trend timing (monthly): out only if the month-end close < 10-month SMA AND the latest published UNRATE (month m-1 at month-end m) > its 12-month mean of available values; else 100% SPY",
    "VT-1.0": "volatility target: weight = min(1.0, 0.15 / realized vol), realized vol = std of the last 21 daily log returns x sqrt(252); fill next close only if |target - actual weight| > 0.10",
    "VT-1.5": "as VT-1.0 with cap 1.5 (borrowing at T-bill + 1.5%)",
    "F10xVT": "VT-1.0 target when F10 is on, else 0; same 0.10 no-trade band",
    "TOM": "turn of month: invested from the close of the 2nd-to-last trading day of a month to the close of the 3rd trading day of the next month (last day's and first 3 days' returns)",
    "HAL": "Halloween: 100% SPY from the close of the last trading day of October to the close of the last trading day of April; else cash",
    "RSI2": "Connors RSI(2): enter when close > 200-day SMA and Wilder RSI(2) < 10; exit when close > 5-day SMA; fill next close; cash otherwise",
    "F_w": "fixed SPY weight equal to the strategy's average weight, rebalanced at month ends, rest in T-bills",
    "SD1": "smart DCA (DCA lens only): contributions 1 unit each month; DD = SPY drawdown from running max at the previous close; DD > -10%: invest 0.8 and reserve 0.2; -20% < DD <= -10%: invest 1 + 50% of reserve; DD <= -20%: invest 1 + 100% of reserve; invested money in SPY, reserve in T-bills",
}
CONFIG_BASE = {
    "slug": SLUG,
    "end_date": END,
    "execution": "signal at the close of day t, order fills at the close of day t+1 (cost 10bp per side on traded notional); monthly rules decide at the last trading day's close and fill at the next close; TOM/HAL use trade closes fixed by the calendar",
    "cost": {"main_per_side": COST, "stress_per_side": COST30},
    "cash": "13-week T-bill (^IRX, previous close) accrued per 365 calendar days as in style_combo.run_backtest; long sample: TB3MS of the previous month / 252 per trading day",
    "borrow_spread": BORROW,
    "windows": {"main": [MAIN_START, END], "start_2003": START_2003, "segments": SEGMENTS,
                "long_sample": [LONG_RUN_START, LONG_END], "long_gtt": [LONG_GTT_START, LONG_END],
                "long_halves": LONG_HALVES, "long_gtt_halves": LONG_GTT_HALVES,
                "long_universe_warmup_start": LONG_UNIVERSE_START,
                "rolling_starts": "first trading day of each January 2000..2023 to END",
                "dca_windows": "120 monthly contributions from the first trading day of the month; terminal = last trading day of the 120th month; complete months only",
                "key_periods": KEY_PERIODS, "post_publication": POST_PUBLICATION},
    "rules": RULE_TEXT,
    "strategies": [{"label": l, "rule": r, "params": p, "cap": CAPS.get(l, 1.0)} for l, r, p in STRATEGIES],
    "sensitivity": [{"variant": v, "family": f, "rule": r, "params": p} for v, f, r, p in SENSITIVITY],
    "sd1_variants": {k: list(v) for k, v in SD1_VARIANTS.items()},
    "dca_lens": {"contribution": "1 unit on the first trading day of every month, 2000-01 to 2026-10",
                 "account": "V_t = sum(units bought up to t) x NAV_t; units bought = (1 - 10bp) / NAV at the contribution close",
                 "xirr": "cashflow_research.xirr", "unit_drawdown": "TWR (NAV) drawdown inside the window",
                 "ratio": "XIRR / |unit MaxDD|", "plain_dca": "B0 under this lens"},
    "metrics": {"cagr": "style_combo.annualized (calendar years / 365.25)", "vol": "std of daily returns x sqrt(252)",
                "sharpe": "mean(daily return - daily T-bill) / std(daily return - daily T-bill) x sqrt(252)",
                "max_dd": "min over time of NAV / running max - 1", "calmar": "CAGR / |MaxDD|",
                "avg_weight": "mean end-of-day SPY weight over the window",
                "trades_per_year": "executions that change the position, excluding the first purchase",
                "share_days_dd_below_20": "share of days with NAV drawdown < -20%", "worst_year": "minimum calendar-year return"},
    "verdict": {"sharpe_beats_hold": "Sharpe > B0 in the main window AND in both segments AND in the long sample (1935-1999; GTT 1949-1999)",
                "calmar_beats_hold": "same four conditions using Calmar",
                "cost_flag": "still true at 30bp per side in the main window (Sharpe and Calmar)",
                "dca_flag": "share of 10-year DCA windows with ratio > plain DCA ratio >= 60%",
                "dm_ief_long": "DM-IEF is not run on the long sample by spec; its long-sample condition is reported as n/a"},
    "interpretations": [
        "TOM/HAL: holding periods are the calendar windows as stated (trade closes fixed by the calendar); the rule decides one close earlier so the engine's next-close fill lands on the stated close. The calendar is passed explicitly and known in advance.",
        "GTT holds 100% SPY before its first month-end decision (out requires both conditions to be known).",
        "Sharpe denominator is the std of daily excess returns; CAGR uses calendar years (style_combo convention).",
        "DCA cost of 10bp is applied to the whole contribution (the strategy NAV already contains its internal cash).",
        "SD1 running max starts at the SPY cache start (1998-12-01).",
        "VT: the 10bp band uses the actual SPY weight; the F10xVT exit can leave a residual <= 0.10 exposure when the band blocks it (rule kept literal).",
        "RSI(2) uses Wilder smoothing via ewm(alpha=1/2), seeded at the first daily change.",
        "Long sample: Jan 1934 uses its own TB3MS value (first observation); the Shiller dividend ends 2024-06, so the validation window ends there.",
        "Post-publication: F10xVT uses 2017 (the later of its two components); TOM 1988 uses the composite series (constructed total return to 1999-12-31, SPY afterwards).",
        "Long sample: the Shiller monthly dividend yield is applied per trading day (spec); UNRATE is the revised FRED series (limitation).",
        "Timing placebo: the actual Sharpe in placebo.csv is computed in the same constant-cash framework as the shifted paths; CAGR and MaxDD are checked against band_timing.timing_placebo.",
    ],
}


# --------------------------------------------------------------------------- hashes and config

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_config() -> dict:
    manifest = json.loads((OUT / "fetch_manifest.json").read_text())
    us_manifest = json.loads((US_DIR / "fetch_manifest.json").read_text())["files"]
    files = {}
    for key, info in manifest["files"].items():
        path = ROOT / info["path"]
        assert sha256(path) == info["sha256"], f"cache changed since fetch: {path}"
        files[key] = {"path": info["path"], "rows": info["rows"], "sha256": info["sha256"]}
    for name in ("yf_SPY.csv", "yf_IRX.csv"):
        path = US_DIR / "cache" / name
        assert sha256(path) == us_manifest[name]["sha256"], path
        files[name] = {"path": str(path.relative_to(ROOT)), "rows": us_manifest[name]["rows"],
                       "sha256": us_manifest[name]["sha256"]}
    config = {**CONFIG_BASE, "data_files": files}
    (OUT / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False, default=json_default))
    return files


# --------------------------------------------------------------------------- inputs

def read_fred(series: str) -> pd.Series:
    raw = pd.read_csv(CACHE / f"fred_{series}" / f"fred_{series}.csv")
    values = pd.to_numeric(raw[series], errors="coerce")
    return pd.Series(values.to_numpy(float), index=pd.to_datetime(raw["observation_date"])).dropna()


def read_fred_monthly(series: str, allow_gaps: bool = False) -> pd.Series:
    """Monthly FRED series by PeriodIndex. UNRATE has unpublished months (Oct 2025), kept as gaps."""
    s = read_fred(series)
    s.index = s.index.to_period("M")
    assert s.index.is_unique and s.index.is_monotonic_increasing
    if not allow_gaps:
        assert len(pd.period_range(s.index[0], s.index[-1], freq="M")) == len(s), f"{series} has monthly gaps"
    return s


def read_gspc() -> pd.Series:
    raw = pd.read_csv(CACHE / "yf_GSPC" / "yf_GSPC.csv")
    s = pd.Series(raw["Close"].astype(float).to_numpy(), index=pd.to_datetime(raw["Date"].str[:10]))
    return s[~s.index.duplicated()].sort_index().dropna()


def read_shiller() -> pd.DataFrame:
    raw = pd.read_excel(CACHE / "shiller_ie_data" / "ie_data.xls", sheet_name="Data", header=None, engine="xlrd")
    header = int(raw.index[raw.iloc[:, 0].astype(str).str.strip().eq("Date")][0])
    body = raw.iloc[header + 1:, :3].copy()
    body.columns = ["date", "P", "D"]
    body = body[pd.to_numeric(body["date"], errors="coerce").notna()]
    x = body["date"].astype(float).to_numpy()
    year = np.floor(x + 1e-9)
    month = np.round((x - year) * 100).astype(int)  # "1871.1" in the sheet is October (YYYY.MM)
    assert ((month >= 1) & (month <= 12)).all()
    periods = pd.PeriodIndex.from_fields(year=year.astype(int), month=month, freq="M")
    out = pd.DataFrame({"P": pd.to_numeric(body["P"]).to_numpy(float),
                        "D": pd.to_numeric(body["D"]).to_numpy(float)}, index=periods)
    assert out.index.is_unique and out.index.is_monotonic_increasing
    return out


def main_universe():
    spy, bill = load_sp500()
    keep = spy.index <= pd.Timestamp(END)
    spy, bill = spy[keep], bill[keep]
    dates = spy.index
    ief_raw = load_yfinance_csv(CACHE / "yf_IEF" / "yf_IEF.csv")["close"]
    ief = ief_raw.reindex(dates.union(ief_raw.index)).ffill().reindex(dates)
    dgs = read_fred("DGS10")
    dgs = dgs.reindex(dates.union(dgs.index)).ffill().reindex(dates)
    synthetic_ret = ov.synthetic_bond_returns(dgs)
    synthetic_px = 100.0 * (1.0 + synthetic_ret).cumprod()
    ief0 = ief.first_valid_index()
    bond_values = np.where(dates >= ief0, ief.to_numpy(float) / ief[ief0] * synthetic_px[ief0],
                           synthetic_px.to_numpy(float))
    bond = pd.Series(bond_values, index=dates, name="bond")
    pos, neg = ov.calendar_cash_factors(dates, bill.to_numpy(float), BORROW)
    data = ov.MarketData(dates=dates, spy=spy, bond=bond, cash_pos=pos, cash_neg=neg,
                         unrate=read_fred_monthly("UNRATE", allow_gaps=True))
    overlap = dates > ief0
    ief_ret = ief.pct_change()
    syn_year = (1.0 + synthetic_ret[overlap]).groupby(dates[overlap].year).prod() - 1.0
    ief_year = (1.0 + ief_ret[overlap]).groupby(dates[overlap].year).prod() - 1.0
    diff = syn_year - ief_year
    validation = {
        "ief_first_date": str(ief0.date()), "overlap_days": int(overlap.sum()),
        "overlap_daily_corr": float(synthetic_ret[overlap].corr(ief_ret[overlap])),
        "overlap_cagr_synthetic": float(sc.annualized(pd.Series((1.0 + synthetic_ret[overlap]).cumprod().to_numpy(),
                                                                index=dates[overlap]))),
        "overlap_cagr_ief": float(sc.annualized(ief[overlap].dropna())),
        "annual_return_diff_mean_abs": float(diff.abs().mean()),
        "annual_return_diff_max_abs": float(diff.abs().max()),
        "annual_return_diff_by_year": {int(k): round(float(v), 6) for k, v in diff.items()},
    }
    return data, bill, validation


def long_universe():
    """Constructed total return 1934-2024-06 (daily ^GSPC price return + Shiller D/P/252) and the long run data."""
    gspc = read_gspc()
    shiller = read_shiller()
    tb = read_fred_monthly("TB3MS")
    tb_prev = tb.shift(1).fillna(tb.iloc[0])
    closes = gspc[(gspc.index >= pd.Timestamp(LONG_UNIVERSE_START)) & (gspc.index <= pd.Timestamp("2024-06-30"))]
    per = closes.index.to_period("M")
    dy = (shiller["D"] / shiller["P"]).reindex(per)
    assert dy.notna().all(), "Shiller dividend missing inside the long-sample span"
    tr = ov.long_total_return(closes, pd.Series(dy.to_numpy(float), index=closes.index))
    rate = pd.Series(tb_prev.reindex(per).to_numpy(float) / 100.0, index=closes.index)
    assert rate.notna().all()
    tr_long = tr[tr.index <= pd.Timestamp(LONG_END)]
    pos, neg = ov.daily_cash_factors(rate[tr_long.index].to_numpy(float), BORROW)
    data = ov.MarketData(dates=tr_long.index, spy=tr_long, bond=tr_long, cash_pos=pos, cash_neg=neg,
                         unrate=read_fred_monthly("UNRATE", allow_gaps=True))
    return data, tr, shiller, tb_prev


def composite_universe(main: ov.MarketData, long_tr: pd.Series, tb_prev: pd.Series) -> ov.MarketData:
    """Constructed total return to 1999-12-31, then SPY (dividend-adjusted) rebased to it (for TOM from 1988)."""
    le = pd.Timestamp(LONG_END)
    left = long_tr[long_tr.index <= le]
    spy_before = main.spy[main.spy.index <= le]
    spy_after = main.spy[main.spy.index > le]
    right = left.iloc[-1] * spy_after / spy_before.iloc[-1]
    close = pd.concat([left, right]).sort_index()
    rate = pd.Series(tb_prev.reindex(close.index.to_period("M")).to_numpy(float) / 100.0, index=close.index)
    assert rate.notna().all()
    pos, neg = ov.daily_cash_factors(rate.to_numpy(float), BORROW)
    return ov.MarketData(dates=close.index, spy=close, bond=close, cash_pos=pos, cash_neg=neg)


# --------------------------------------------------------------------------- runs

def run(data: ov.MarketData, rule: str, params: dict, start, cost: float = COST):
    res = ov.simulate(data, rule, start, cost=cost, **params)
    return res, ov.perf_metrics(res.nav, res.tbill_daily, res.weights["a"], ov.count_trades(res))


def window_metrics(res, start, end) -> dict:
    nav = ov.segment_slice(res.nav, start, end)
    return ov.perf_metrics(nav, res.tbill_daily, res.weights["a"].reindex(nav.index), 0)


def first_trading_day(dates: pd.DatetimeIndex, day) -> pd.Timestamp:
    return pd.Timestamp(dates[dates.searchsorted(pd.Timestamp(day))])


def stats(m: dict) -> dict:
    return {"cagr": m["cagr"], "vol": m["vol"], "sharpe": m["sharpe"], "calmar": m["calmar"], "max_dd": m["max_dd"]}


def cash_rate_mean(data: ov.MarketData, start: pd.Timestamp, end: pd.Timestamp) -> float:
    """Annualized T-bill rate over the window (the constant rate handed to timing_placebo)."""
    idx = data.dates
    s, e = idx.searchsorted(start), idx.searchsorted(end, side="right") - 1
    growth = float(np.prod(data.cash_pos[s + 1:e + 1]))
    days = (idx[e] - idx[s]).days
    return growth ** (365.0 / days) - 1.0


def json_default(value):
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, pd.Timestamp):
        return str(value.date())
    return str(value)


# --------------------------------------------------------------------------- main

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    write_config()
    selfcheck: dict = {}

    data, bill, ief_validation = main_universe()
    dates = data.dates
    selfcheck["data_window"] = {"main_first_date": str(dates[0].date()), "end": str(dates[-1].date())}
    selfcheck["synthetic_bond_validation"] = ief_validation

    long_data, long_tr, shiller, tb_prev = long_universe()
    composite = composite_universe(data, long_tr, tb_prev)

    # ---- main window (B0 + 12 rules)
    main_runs = {B0: run(data, "B0", {}, MAIN_START)}
    for label, rule, params in STRATEGIES:
        main_runs[label] = run(data, rule, params, MAIN_START)
    b0m = main_runs[B0][1]
    navs = pd.DataFrame({k: v[0].nav for k, v in main_runs.items()})
    navs.index.name = "date"
    navs.to_csv(OUT / "nav_daily.csv", float_format="%.10g")
    weight_cols = {}
    for label, (res, _) in main_runs.items():
        if label == B0:
            continue
        weight_cols[f"{label}_spy_weight"] = res.weights["a"]
        if label == "DM-IEF":
            weight_cols["DM-IEF_bond_weight"] = res.weights["b"]
    pd.DataFrame(weight_cols).to_csv(OUT / "weights_daily.csv", index_label="date", float_format="%.6f")

    summary_rows = []
    for label, (_, m) in main_runs.items():
        summary_rows.append({"strategy": label, **m, "sharpe_gt_b0": m["sharpe"] > b0m["sharpe"],
                             "calmar_gt_b0": m["calmar"] > b0m["calmar"]})
    for label, _, _ in STRATEGIES:
        avg = main_runs[label][1]["avg_weight"]
        _, m_fixed = run(data, "FIXED", {"weight": avg}, MAIN_START)
        summary_rows.append({"strategy": f"F_w (SPY {avg:.3f}, matched to {label})", **m_fixed,
                             "sharpe_gt_b0": m_fixed["sharpe"] > b0m["sharpe"],
                             "calmar_gt_b0": m_fixed["calmar"] > b0m["calmar"]})
    pd.DataFrame(summary_rows).to_csv(OUT / "summary.csv", index=False)

    pd.DataFrame({k: ov.yearly_returns(v[0].nav) for k, v in main_runs.items()}).rename_axis("year").to_csv(
        OUT / "yearly_returns.csv", float_format="%.6f")

    key_rows = []
    for period, (s, e) in KEY_PERIODS.items():
        for label, (res, _) in main_runs.items():
            key_rows.append({"period": period, "strategy": label, **ov.key_period_stats(res.nav, s, e)})
    pd.DataFrame(key_rows).to_csv(OUT / "key_periods.csv", index=False)

    seg_metric = {}
    seg_rows = []
    for label, (res, _) in main_runs.items():
        for name, (s, e) in SEGMENTS.items():
            ms = window_metrics(res, s, e)
            bs = window_metrics(main_runs[B0][0], s, e)
            seg_metric[(label, name)] = (ms, bs)
            seg_rows.append({"strategy": label, "segment": name, **stats(ms), "b0_cagr": bs["cagr"],
                             "b0_sharpe": bs["sharpe"], "b0_calmar": bs["calmar"], "b0_max_dd": bs["max_dd"],
                             "sharpe_gt_b0": ms["sharpe"] > bs["sharpe"], "calmar_gt_b0": ms["calmar"] > bs["calmar"]})
    pd.DataFrame(seg_rows).to_csv(OUT / "segments.csv", index=False)

    # ---- 2003 start
    rows = []
    _, b0_03 = run(data, "B0", {}, START_2003)
    rows.append({"strategy": B0, **b0_03, "sharpe_gt_b0": False, "calmar_gt_b0": False})
    for label, rule, params in STRATEGIES:
        _, m = run(data, rule, params, START_2003)
        rows.append({"strategy": label, **m, "sharpe_gt_b0": m["sharpe"] > b0_03["sharpe"],
                     "calmar_gt_b0": m["calmar"] > b0_03["calmar"]})
    pd.DataFrame(rows).to_csv(OUT / "start2003.csv", index=False)

    # ---- cost 30bp per side
    rows = []
    _, b0_c30 = run(data, "B0", {}, MAIN_START, COST30)
    rows.append({"strategy": B0, **b0_c30, "sharpe_gt_b0": False, "calmar_gt_b0": False})
    cost30 = {}
    for label, rule, params in STRATEGIES:
        _, m = run(data, rule, params, MAIN_START, COST30)
        cost30[label] = m
        rows.append({"strategy": label, **m, "sharpe_gt_b0": m["sharpe"] > b0_c30["sharpe"],
                     "calmar_gt_b0": m["calmar"] > b0_c30["calmar"]})
    pd.DataFrame(rows).to_csv(OUT / "cost30.csv", index=False)

    # ---- rolling starts (each January 2000..2023 to END)
    rows = []
    for year in ROLLING_YEARS:
        start = first_trading_day(dates, f"{year}-01-01")
        _, b0r = run(data, "B0", {}, start)
        for label, rule, params in [(B0, "B0", {})] + STRATEGIES:
            m = b0r if label == B0 else run(data, rule, params, start)[1]
            rows.append({"row_type": "start", "strategy": label, "start": str(start.date()), "years": m["years"],
                         **stats(m), "b0_cagr": b0r["cagr"], "b0_sharpe": b0r["sharpe"], "b0_calmar": b0r["calmar"],
                         "sharpe_gt_b0": m["sharpe"] > b0r["sharpe"], "calmar_gt_b0": m["calmar"] > b0r["calmar"],
                         "sharpe_diff": m["sharpe"] - b0r["sharpe"], "calmar_diff": m["calmar"] - b0r["calmar"]})
    rolling = pd.DataFrame(rows)
    summary_lines = []
    for label in LABELS:
        sub = rolling[(rolling.strategy == label) & (rolling.row_type == "start")]
        summary_lines.append({"row_type": "summary", "strategy": label, "start": f"n={len(sub)}",
                              "sharpe_gt_b0": int(sub.sharpe_gt_b0.sum()), "calmar_gt_b0": int(sub.calmar_gt_b0.sum()),
                              "sharpe_diff": float(sub.sharpe_diff.median()), "calmar_diff": float(sub.calmar_diff.median()),
                              "cagr_diff": float((sub.cagr - sub.b0_cagr).median())})
    pd.concat([rolling, pd.DataFrame(summary_lines)], ignore_index=True).to_csv(OUT / "rolling_starts.csv", index=False)

    # ---- post-publication
    rows = []
    for label, rule, params in STRATEGIES:
        if label not in POST_PUBLICATION:
            continue
        year = POST_PUBLICATION[label]
        universe, name = (composite, "composite (constructed to 1999-12-31, then SPY)") if label == "TOM" else (data, "main")
        start = first_trading_day(universe.dates, f"{year}-01-01")
        _, m = run(universe, rule, params, start)
        _, b = run(universe, "B0", {}, start)
        rows.append({"strategy": label, "publication_year": year, "universe": name, "start": str(start.date()),
                     "end": END, **stats(m), "b0_cagr": b["cagr"], "b0_sharpe": b["sharpe"], "b0_calmar": b["calmar"],
                     "b0_max_dd": b["max_dd"], "sharpe_gt_b0": m["sharpe"] > b["sharpe"],
                     "calmar_gt_b0": m["calmar"] > b["calmar"]})
    for label in ("S2", "S1"):
        rows.append({"strategy": label, "publication_year": "n/a (reference rule)", "universe": "main"})
    pd.DataFrame(rows).to_csv(OUT / "post_publication.csv", index=False)

    # ---- long sample and the validation of its total-return construction
    long_runs = {B0: run(long_data, "B0", {}, LONG_RUN_START), "B0_1949": run(long_data, "B0", {}, LONG_GTT_START)}
    for label, rule, params in STRATEGIES:
        if label == "DM-IEF":
            continue
        long_runs[label] = run(long_data, rule, params, LONG_GTT_START if label == "GTT" else LONG_RUN_START)
    rows, long_full = [], {}
    for label, (res, _) in long_runs.items():
        gtt_like = label in ("GTT", "B0_1949")
        base_key = "B0_1949" if gtt_like else B0
        first, halves = (LONG_GTT_START, LONG_GTT_HALVES) if gtt_like else (LONG_RUN_START, LONG_HALVES)
        windows = [(f"{first[:4]}-1999", first, LONG_END)] + [(k, s, e) for k, (s, e) in halves.items()]
        for window, s, e in windows:
            mm = window_metrics(res, s, e)
            bb = window_metrics(long_runs[base_key][0], s, e)
            name = "B0 (1949 window)" if label == "B0_1949" else label
            rows.append({"strategy": name, "window": window, **stats(mm), "b0_cagr": bb["cagr"], "b0_sharpe": bb["sharpe"],
                         "b0_calmar": bb["calmar"], "b0_max_dd": bb["max_dd"],
                         "sharpe_gt_b0": mm["sharpe"] > bb["sharpe"], "calmar_gt_b0": mm["calmar"] > bb["calmar"]})
            if window == f"{first[:4]}-1999":
                long_full[label] = {"sharpe": mm["sharpe"], "calmar": mm["calmar"],
                                    "b0_sharpe": bb["sharpe"], "b0_calmar": bb["calmar"]}
    pd.DataFrame(rows).to_csv(OUT / "long_sample.csv", index=False)

    tr_span = long_tr[(long_tr.index >= pd.Timestamp("2000-01-03")) & (long_tr.index <= pd.Timestamp("2024-06-28"))]
    common = tr_span.index.intersection(data.spy.index)
    r_tr = tr_span.pct_change()[common]
    r_spy = data.spy.pct_change()[common]
    yr_tr = (1.0 + r_tr).groupby(common.year).prod() - 1.0
    yr_spy = (1.0 + r_spy).groupby(common.year).prod() - 1.0
    diff = yr_tr - yr_spy
    rows = [{"row_type": "year", "item": int(y), "tr_constructed": float(yr_tr[y]), "spy_adjusted": float(yr_spy[y]),
             "diff": float(diff[y])} for y in yr_tr.index]
    validation = {"span": f"{common[0].date()}..{common[-1].date()}",
                  "daily_corr": float(r_tr.corr(r_spy)), "daily_mean_abs_diff": float((r_tr - r_spy).abs().mean()),
                  "annual_diff_mean_abs": float(diff.abs().mean()), "annual_diff_max_abs": float(diff.abs().max()),
                  "cagr_tr_constructed": float(sc.annualized(tr_span.loc[common[0]:common[-1]])),
                  "cagr_spy_adjusted": float(sc.annualized(data.spy.loc[common[0]:common[-1]])),
                  "span_years": float((common[-1] - common[0]).days / 365.25)}
    rows.append({"row_type": "summary", "item": validation["span"], **{k: v for k, v in validation.items() if k != "span"}})
    pd.DataFrame(rows).to_csv(OUT / "long_sample_validation.csv", index=False)
    selfcheck["long_sample_validation"] = validation
    selfcheck["shiller"] = {"first_period": str(shiller.index[0]), "last_period": str(shiller.index[-1]),
                            "last_dividend_period": str(shiller["D"].dropna().index[-1]),
                            "dividend_missing_1934_2024_06": bool(shiller.loc["1934-01":"2024-06", "D"].isna().any())}

    # ---- sensitivity (main window, reported only)
    rows = [{"family": label, "variant": "base", **m, "sharpe_gt_b0": m["sharpe"] > b0m["sharpe"],
             "calmar_gt_b0": m["calmar"] > b0m["calmar"]} for label, (_, m) in main_runs.items() if label != B0]
    for variant, family, rule, params in SENSITIVITY:
        _, m = run(data, rule, params, MAIN_START)
        rows.append({"family": family, "variant": variant, **m, "sharpe_gt_b0": m["sharpe"] > b0m["sharpe"],
                     "calmar_gt_b0": m["calmar"] > b0m["calmar"]})
    pd.DataFrame(rows).to_csv(OUT / "sensitivity.csv", index=False)

    # ---- timing placebo (shift the weight path against the market; same weights)
    annual_cash = cash_rate_mean(data, pd.Timestamp(MAIN_START), dates[-1])
    rows = []
    for label, rule, params in STRATEGIES:
        res = main_runs[label][0]
        idx = res.nav.index
        returns = np.column_stack([data.spy.pct_change().reindex(idx).fillna(0.0).to_numpy(float),
                                   data.bond.pct_change().reindex(idx).fillna(0.0).to_numpy(float)])
        scores = ov.placebo_scores(res.weights[["a", "b"]].to_numpy(float), returns, idx, annual_cash,
                                   range(60, len(idx) - 60 + 1))
        act_cagr, act_sharpe, act_dd = scores["actual"]
        row = {"strategy": label, "n_shifts": len(scores["sharpe"]), "constant_cash_annual": annual_cash,
               "actual_cagr_same_framework": act_cagr, "actual_sharpe": act_sharpe, "actual_max_dd": act_dd,
               "placebo_median_sharpe": float(np.median(scores["sharpe"])),
               "placebo_p95_sharpe": float(np.quantile(scores["sharpe"], 0.95)),
               "placebo_median_max_dd": float(np.median(scores["dd"])),
               "share_sharpe_ge_actual": float((scores["sharpe"] >= act_sharpe).mean()),
               "share_dd_no_worse": float((scores["dd"] >= act_dd).mean()),
               "share_sharpe_ge_and_dd_no_worse": float(((scores["sharpe"] >= act_sharpe) & (scores["dd"] >= act_dd)).mean())}
        if label != "DM-IEF":
            tp = bt.timing_placebo(res.weights["a"], data.spy.pct_change(), annual_cash)
            row.update({f"tp_{k}": v for k, v in tp.items()})
            selfcheck.setdefault("placebo_framework_vs_band_timing", {})[label] = {
                "cagr_abs_diff": abs(tp["actual_annualized"] - act_cagr), "maxdd_abs_diff": abs(tp["actual_max_drawdown"] - act_dd)}
        rows.append(row)
    pd.DataFrame(rows).to_csv(OUT / "placebo.csv", index=False)

    # ---- DCA lens
    contrib_all = ov.contribution_dates(dates, MAIN_START, END)
    spy_series = data.spy
    cash_series = pd.Series(data.cash_pos, index=dates)
    navs_main = {k: v[0].nav for k, v in main_runs.items()}
    full_rows = [{"strategy": B0, **ov.dca_account(navs_main[B0], contrib_all, END)}]
    full_rows += [{"strategy": label, **ov.dca_account(navs_main[label], contrib_all, END)} for label in LABELS]
    sd1_full = ov.sd1_account(spy_series, cash_series, contrib_all, END)
    full_rows.append({"strategy": "SD1", **sd1_full, "unit_max_dd": np.nan, "ratio": np.nan})
    full = pd.DataFrame(full_rows)
    full.to_csv(OUT / "dca_full_path.csv", index=False)
    plain_full = full[full.strategy == B0].iloc[0]
    selfcheck["dca_full_path"] = {r.strategy: {"xirr": float(r.xirr), "max_float_loss": float(r.max_float_loss),
                                               "terminal_per_contributed": float(r.terminal_per_contributed)}
                                  for r in full.itertuples()}

    windows = []
    for start_day in contrib_all:
        win = ov.ten_year_window(dates, start_day)
        if win is not None:
            windows.append((start_day, *win))
    selfcheck["dca_windows"] = {"count": len(windows), "first": str(windows[0][0].date()),
                                "last": str(windows[-1][0].date()), "contributions_each": sorted({len(w[1]) for w in windows})}
    rows, plain_by_start = [], {}
    for start_day, contrib_w, end_w in windows:
        plain = ov.dca_account(navs_main[B0], contrib_w, end_w)
        plain_by_start[start_day] = plain
        for label in [B0] + LABELS:
            acct = plain if label == B0 else ov.dca_account(navs_main[label], contrib_w, end_w)
            rows.append({"strategy": label, "start": str(start_day.date()), "end": str(end_w.date()), **acct,
                         "ratio_gt_plain": acct["ratio"] > plain["ratio"], "xirr_gt_plain": acct["xirr"] > plain["xirr"]})
        sd1 = ov.sd1_account(spy_series, cash_series, contrib_w, end_w)
        rows.append({"strategy": "SD1", "start": str(start_day.date()), "end": str(end_w.date()), **sd1,
                     "unit_max_dd": np.nan, "ratio": np.nan, "ratio_gt_plain": False,
                     "xirr_gt_plain": sd1["xirr"] > plain["xirr"]})
    windows_frame = pd.DataFrame(rows)
    windows_frame.to_csv(OUT / "dca_windows.csv", index=False)

    dca_rows = []
    for label in [B0] + LABELS + ["SD1"]:
        sub = windows_frame[windows_frame.strategy == label]
        has_ratio = sub["ratio"].notna().all()
        share_ratio = float(sub.ratio_gt_plain.mean()) if has_ratio and label != B0 else np.nan
        dca_rows.append({"strategy": label, "n_windows": len(sub),
                         "median_xirr": float(sub.xirr.median()), "p10_xirr": float(sub.xirr.quantile(0.10)),
                         "worst_xirr": float(sub.xirr.min()),
                         "median_max_float_loss": float(sub.max_float_loss.median()),
                         "worst_max_float_loss": float(sub.max_float_loss.min()),
                         "median_ratio": float(sub.ratio.median()) if has_ratio else np.nan,
                         "share_ratio_gt_plain": share_ratio,
                         "share_xirr_gt_plain": float(sub.xirr_gt_plain.mean()) if label != B0 else np.nan,
                         "ratio_share_ge_60pct": bool(share_ratio >= 0.6) if has_ratio and label != B0 else None})
    pd.DataFrame(dca_rows).to_csv(OUT / "dca_summary.csv", index=False)
    dca_by = {r["strategy"]: r for r in dca_rows}

    sd1_rows = []
    for variant, thresholds in SD1_VARIANTS.items():
        full_v = ov.sd1_account(spy_series, cash_series, contrib_all, END, thresholds=thresholds)
        wins = []
        for start_day, contrib_w, end_w in windows:
            v = ov.sd1_account(spy_series, cash_series, contrib_w, end_w, thresholds=thresholds)
            p = plain_by_start[start_day]
            wins.append({"xirr": v["xirr"], "float": v["max_float_loss"], "plain_xirr": p["xirr"],
                         "plain_float": p["max_float_loss"]})
        wins = pd.DataFrame(wins)
        sd1_rows.append({"variant": variant, "t1": thresholds[0], "t2": thresholds[1],
                         "full_xirr": full_v["xirr"], "full_max_float_loss": full_v["max_float_loss"],
                         "full_terminal_per_contributed": full_v["terminal_per_contributed"],
                         "plain_full_xirr": plain_full["xirr"], "plain_full_max_float_loss": plain_full["max_float_loss"],
                         "plain_full_terminal_per_contributed": plain_full["terminal_per_contributed"],
                         "n_windows": len(wins), "median_xirr_sd1": float(wins.xirr.median()),
                         "median_xirr_plain": float(wins.plain_xirr.median()),
                         "share_windows_xirr_gt_plain": float((wins.xirr > wins.plain_xirr).mean()),
                         "median_float_loss_sd1": float(wins["float"].median()),
                         "median_float_loss_plain": float(wins.plain_float.median()),
                         "share_windows_float_loss_better": float((wins["float"] > wins.plain_float).mean())})
    pd.DataFrame(sd1_rows).to_csv(OUT / "sd1.csv", index=False)

    # ---- verdicts (pre-registered; computed after every run above)
    summary_main = {label: main_runs[label][1] for label in main_runs}
    verdicts = []
    for label in LABELS:
        m = summary_main[label]
        seg = {name: (seg_metric[(label, name)][0], seg_metric[(label, name)][1]) for name in SEGMENTS}
        base_ok_sharpe = m["sharpe"] > b0m["sharpe"] and all(a["sharpe"] > b["sharpe"] for a, b in seg.values())
        base_ok_calmar = m["calmar"] > b0m["calmar"] and all(a["calmar"] > b["calmar"] for a, b in seg.values())
        long_key = "GTT" if label == "GTT" else label
        if label in long_full:
            lf = long_full[label]
            long_sharpe_ok = bool(lf["sharpe"] > lf["b0_sharpe"])
            long_calmar_ok = bool(lf["calmar"] > lf["b0_calmar"])
            sharpe_label = bool(base_ok_sharpe and long_sharpe_ok)
            calmar_label = bool(base_ok_calmar and long_calmar_ok)
            long_sharpe_text, long_calmar_text = lf["sharpe"], lf["calmar"]
            b0_long_sharpe, b0_long_calmar = lf["b0_sharpe"], lf["b0_calmar"]
        else:
            long_sharpe_ok = long_calmar_ok = None
            sharpe_label = calmar_label = "n/a (no long sample)"
            long_sharpe_text = long_calmar_text = b0_long_sharpe = b0_long_calmar = np.nan
        verdicts.append({
            "strategy": label,
            "sharpe_beats_hold": sharpe_label, "calmar_beats_hold": calmar_label,
            "sharpe_main": m["sharpe"], "b0_sharpe_main": b0m["sharpe"],
            "sharpe_seg_2000_2012": seg["2000-01-03~2012-12-31"][0]["sharpe"], "b0_sharpe_seg_2000_2012": seg["2000-01-03~2012-12-31"][1]["sharpe"],
            "sharpe_seg_2013_2026": seg["2013-01-01~2026-10-16"][0]["sharpe"], "b0_sharpe_seg_2013_2026": seg["2013-01-01~2026-10-16"][1]["sharpe"],
            "sharpe_long": long_sharpe_text, "b0_sharpe_long": b0_long_sharpe,
            "calmar_main": m["calmar"], "b0_calmar_main": b0m["calmar"],
            "calmar_seg_2000_2012": seg["2000-01-03~2012-12-31"][0]["calmar"], "b0_calmar_seg_2000_2012": seg["2000-01-03~2012-12-31"][1]["calmar"],
            "calmar_seg_2013_2026": seg["2013-01-01~2026-10-16"][0]["calmar"], "b0_calmar_seg_2013_2026": seg["2013-01-01~2026-10-16"][1]["calmar"],
            "calmar_long": long_calmar_text, "b0_calmar_long": b0_long_calmar,
            "sharpe_beats_hold_excluding_long": bool(base_ok_sharpe), "calmar_beats_hold_excluding_long": bool(base_ok_calmar),
            "still_true_cost30_sharpe": bool(cost30[label]["sharpe"] > b0_c30["sharpe"]),
            "still_true_cost30_calmar": bool(cost30[label]["calmar"] > b0_c30["calmar"]),
            "dca_share_ratio_gt_plain": dca_by[label]["share_ratio_gt_plain"],
            "dca_ratio_share_ge_60pct": dca_by[label]["ratio_share_ge_60pct"],
        })
    pd.DataFrame(verdicts).to_csv(OUT / "verdicts.csv", index=False)

    # ---- self checks
    exec_day = main_runs[B0][0].nav.index[1]
    nocost = run(data, "B0", {}, MAIN_START, cost=0.0)[0]
    exact_error = abs(nocost.nav.iloc[-1] / nocost.nav.iloc[1] - data.spy.iloc[-1] / data.spy.loc[exec_day])
    window_start = first_trading_day(dates, MAIN_START)
    raw_years = (dates[-1] - window_start).days / 365.25
    raw_cagr = (data.spy.iloc[-1] / data.spy.loc[window_start]) ** (1.0 / raw_years) - 1.0
    selfcheck["b0_cagr"] = {
        "executed_span_abs_error": float(exact_error),
        "raw_spy_cagr_window": float(raw_cagr),
        "b0_cagr_cost0_window": float(sc.annualized(nocost.nav)),
        "b0_cagr_net_10bp_window": float(b0m["cagr"]),
        "note": "B0 holds cash on the window-start close and buys at the next close; the cost-free NAV ratio over the executed span equals SPY's raw ratio (abs error above)",
    }
    old = pd.read_csv(OLD_VERDICTS).set_index("rule")
    reproduce = {}
    for key, name in [("S2", "S2 标普 半仓持有+半仓趋势"), ("S1", "S1 标普 1.5倍趋势杠杆")]:
        _, m_old = run(data, key, {}, "1999-10-01")
        prior = old.loc[name]
        reproduce[key] = {"cagr_new": m_old["cagr"], "cagr_prior": float(prior["annualized"]),
                          "maxdd_new": m_old["max_dd"], "maxdd_prior": float(prior["max_drawdown"]),
                          "cagr_abs_diff": abs(m_old["cagr"] - float(prior["annualized"])),
                          "maxdd_abs_diff": abs(m_old["max_dd"] - float(prior["max_drawdown"]))}
    selfcheck["old_window_reproduction_1999_10_01"] = reproduce
    engine_diff = {}
    i_main = int(dates.searchsorted(pd.Timestamp(MAIN_START)))
    prices = pd.DataFrame({"a": data.spy, "b": data.spy})
    for key, sig_fn in [("S2", lambda: pr.rule_stage_blend(pr.stage_states(data.spy), dates, i_main)),
                        ("S1", lambda: pr.rule_trend_leverage(data.spy, i_main)),
                        ("B0", lambda: sc.rule_buy_hold({"a": 1.0, "b": 0.0}, i_main))]:
        ref = sc.run_backtest(prices, sig_fn(), i_main, COST, bill, BORROW)
        engine_diff[key] = float(np.max(np.abs(ref.nav.to_numpy() - main_runs[key][0].nav.to_numpy())))
    selfcheck["engine_vs_style_combo_run_backtest_max_nav_diff"] = engine_diff
    selfcheck["weights"] = {}
    for label in LABELS:
        checks = main_runs[label][0].checks
        cap = CAPS.get(label, 1.0)
        selfcheck["weights"][label] = {"cap": cap, "min_target": checks["min_target_weight"],
                                       "max_target_gross": checks["max_target_gross"],
                                       "targets_within_cap": bool(checks["min_target_weight"] >= -1e-12
                                                                  and checks["max_target_gross"] <= cap + 1e-12),
                                       "end_of_day_max_gross_drift": checks["max_gross_weight"],
                                       "end_of_day_min_weight": checks["min_weight"]}
    selfcheck["nav_finite_positive"] = bool(np.isfinite(navs.to_numpy(float)).all() and (navs > 0).all().all())
    selfcheck["max_cash_plus_holdings_residual"] = max(float(main_runs[k][0].checks["max_cash_plus_holdings_residual"])
                                                       for k in main_runs)
    selfcheck["pytest_overlay_rules"] = run_pytest()
    (OUT / "selfcheck.json").write_text(json.dumps(selfcheck, indent=2, ensure_ascii=False, default=json_default))

    write_readme()
    pd.set_option("display.width", 220, "display.max_columns", 40)
    print(pd.DataFrame(verdicts).round(4).to_string())


def run_pytest() -> dict:
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_overlay_rules.py"], cwd=str(ROOT),
                            capture_output=True, text=True)
    lines = (result.stdout or result.stderr).strip().splitlines()
    return {"returncode": result.returncode, "summary": lines[-1] if lines else ""}


def write_readme() -> None:
    text = """# S&P 500 enhancement vs DCA (2026-11-10)

Generated by `scripts/research_sp500_enhance_vs_dca.py` from `cache/` (fetched by `scripts/fetch_sp500_enhance_data.py`).

- `config.json`: rules, windows, criteria, costs and SHA256/row counts of every cached input (written before results).
- `summary.csv`: main window 2000-01-03 to 2026-10-16 for B0, S2, S1, rules 1-10 and matched fixed-weight F_w rows.
- `segments.csv`, `start2003.csv`, `cost30.csv`, `sensitivity.csv`, `key_periods.csv`, `yearly_returns.csv`.
- `rolling_starts.csv`: one row per January start 2000-2023 plus summary rows (`row_type = summary`).
- `post_publication.csv`: each rule from its publication year to the end, against B0 over the same window.
- `long_sample.csv` and `long_sample_validation.csv`: 1935-1999 (GTT 1949-1999) run on the constructed total return.
- `placebo.csv`: circular timing placebo with Sharpe and drawdown shares.
- `dca_full_path.csv`, `dca_windows.csv`, `dca_summary.csv`, `sd1.csv`: DCA lens (120-month windows) and SD1.
- `verdicts.csv`: pre-registered labels; `selfcheck.json`: reproduction and integrity checks.
- `nav_daily.csv`, `weights_daily.csv`: daily NAVs and end-of-day weights of the main window.
"""
    (OUT / "README.md").write_text(text)


if __name__ == "__main__":
    main()
