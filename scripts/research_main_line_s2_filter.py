"""Main-line overlay test (2026-11-10): does a 30-week trend filter (S2) on one sleeve improve the main line?

Run (from repo root):
  uv run python -I scripts/research_main_line_s2_filter.py

Asset pool, timing and weighting are separate hypotheses and are kept separate here:
  * pool      : fixed to the main line (510300 / 513100 / 518880 inverse-vol core + 7.5% BTC satellite).
  * timing    : S2 half-trend on one sleeve (the cut is a holding multiplier, not a new signal).
  * weighting : the cut goes to cash (primary) or is spread over the other sleeves (sensitivity only).

The base NAV is the frozen main-line file ``outputs/btc-satellite-corrected-prices-2026-10-18/nav_BTC_7.5.csv``.
Only the return effect of the filter and its switching cost is added. config.json is written before any result.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src")]
from xquant import main_line_overlay as mo  # noqa: E402

SLUG = "main-line-s2-filter-2026-11-10"
OUT = ROOT / "outputs" / SLUG
BASE_NAV = ROOT / "outputs" / "btc-satellite-corrected-prices-2026-10-18" / "nav_BTC_7.5.csv"
MARKET = ROOT / "outputs" / "btc-satellite-corrected-prices-2026-10-18" / "market_data"
QQQ_CACHE = ROOT / "outputs" / "tqqq-regime-switch-2026-11-10" / "cache" / "yf_QQQ.csv"

WINDOW = ("2016-06-07", "2026-09-30")
HALVES = {"2016-2021": ("2016-06-07", "2021-06-30"), "2021-2026": ("2021-07-01", "2026-09-30")}
COST, COST_STRESS = 0.003, 0.006  # 30 bp per side (main line), 60 bp stress

SLEEVES = {"510300.SS": "510300.SS", "513100.SS": "513100.SS", "518880.SS": "518880.SS"}
CASH = mo.CASH

VARIANTS = [
    # name, sleeve, signal source, off weight, ma weeks, reallocate, cost, role
    ("V0_base", None, None, None, None, False, COST, "frozen main line"),
    ("P_qqq_513100_off50", "513100.SS", "QQQ", 0.5, 30, False, COST, "primary"),
    ("W_realloc_513100_off50", "513100.SS", "QQQ", 0.5, 30, True, COST, "weighting sensitivity"),
    ("S_own_513100_off50", "513100.SS", "OWN", 0.5, 30, False, COST, "signal sensitivity (513100 own price)"),
    ("G_qqq_513100_off00", "513100.SS", "QQQ", 0.0, 30, False, COST, "grid: off 0%"),
    ("G_qqq_513100_off25", "513100.SS", "QQQ", 0.25, 30, False, COST, "grid: off 25%"),
    ("G_qqq_513100_off75", "513100.SS", "QQQ", 0.75, 30, False, COST, "grid: off 75%"),
    ("G_qqq_513100_ma20", "513100.SS", "QQQ", 0.5, 20, False, COST, "grid: 20-week MA"),
    ("G_qqq_513100_ma40", "513100.SS", "QQQ", 0.5, 40, False, COST, "grid: 40-week MA"),
    ("C_primary_cost60", "513100.SS", "QQQ", 0.5, 30, False, COST_STRESS, "cost stress 60 bp"),
    ("NEG_own_510300_off50", "510300.SS", "OWN", 0.5, 30, False, COST, "negative control: A-share sleeve (frozen: timing did not beat holding)"),
    ("EXP_own_518880_off50", "518880.SS", "OWN", 0.5, 30, False, COST, "exploratory: gold sleeve (trend rules not yet tested)"),
    ("X_all_sleeves_off50", "ALL", "MIXED", 0.5, 30, False, COST, "post-hoc extension: all three sleeves filtered (513100 by QQQ, others by own price); not in PASS"),
]
POST_HOC = {"X_all_sleeves_off50"}  # added after the primary result was seen; reported, never used for PASS

CRITERIA = {
    "C1": "full-window Sharpe >= base",
    "C2": "full-window Calmar >= base",
    "C3": "full-window CAGR >= base - 1.0 percentage point",
    "C4": "full-window max drawdown at least 2 points shallower than base",
    "C5": "Sharpe >= base in both halves (2016-2021, 2021-2026)",
    "PASS": "C1 and C2 and C3 and C4 and C5",
    "STRESS": "C1 and C2 still hold at 60 bp (primary variant only)",
}


def write_config() -> dict:
    cfg = {
        "slug": SLUG,
        "question": "Does a 30-week trend filter (S2) on one sleeve of the main line improve the frozen main line?",
        "pool": "510300 / 513100 / 518880 inverse-vol core (20d) + 7.5% BTC SuperTrend satellite, frozen",
        "base_nav": str(BASE_NAV.relative_to(ROOT)),
        "base_sha256": hashlib.sha256(BASE_NAV.read_bytes()).hexdigest(),
        "window": WINDOW,
        "halves": HALVES,
        "timing": "S2: weekly close above a rising 30-week mean -> multiplier 1; weekly close below -> off weight; executed next close",
        "signal_sources": {"QQQ": "QQQ close (yfinance cache), US Nasdaq-100 index behind 513100",
                           "OWN": "the sleeve's own close (corrected forward prices in market_data)"},
        "cost_per_side": {"main": COST, "stress": COST_STRESS},
        "cash_return": "0 (cash weight earns nothing in this overlay; the base NAV's own cash treatment is unchanged)",
        "execution_note": "overlay adds returns from weight changes plus switching cost on the trade day; base costs unchanged",
        "variants": [dict(zip(["name", "sleeve", "signal", "off", "ma_weeks", "reallocate", "cost", "role"], v))
                     for v in VARIANTS],
        "criteria": CRITERIA,
        "post_hoc_variants": sorted(POST_HOC),
        "post_hoc_note": "X_all_sleeves_off50 was added after the primary result. It is a diagnostic of the drawdown source, not a new candidate.",
        "selection": "none: the grid and the negative control are reported, the primary variant is fixed here",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    return cfg


def load_inputs():
    nav_file = pd.read_csv(BASE_NAV)
    dates = pd.to_datetime(nav_file["date"].astype(str).str[:10])
    weights = pd.DataFrame({
        "510300.SS": nav_file["weight_510300.SS"].to_numpy(float),
        "513100.SS": nav_file["weight_513100.SS"].to_numpy(float),
        "518880.SS": nav_file["weight_518880.SS"].to_numpy(float),
        "BTC-USD": nav_file["weight_BTC-USD"].to_numpy(float),
        CASH: nav_file["cash_weight"].to_numpy(float),
    }, index=dates)
    base_nav = pd.Series(nav_file["nav"].to_numpy(float), index=dates, name="base_nav")
    prices = {}
    for sym in ["510300.SS", "513100.SS", "518880.SS", "BTC-USD"]:
        p = pd.read_parquet(MARKET / f"{sym}.parquet")
        idx = pd.to_datetime(pd.Series(p.index).astype(str).str[:10]).to_numpy()
        prices[sym] = pd.Series(p["Close"].to_numpy(float), index=pd.DatetimeIndex(idx))
    price_df = pd.DataFrame({k: v.reindex(dates).to_numpy() for k, v in prices.items()}, index=dates)
    q = pd.read_csv(QQQ_CACHE)
    qidx = pd.to_datetime(q["Date"].astype(str).str[:10])
    qqq = pd.Series(q["Close"].to_numpy(float), index=qidx)
    qqq = qqq[~qqq.index.duplicated(keep="last")].reindex(dates, method="ffill")
    return weights, base_nav, price_df, qqq


def base_check(weights: pd.DataFrame, base_nav: pd.Series, price_df: pd.DataFrame) -> dict:
    """Replay the base NAV from its end-of-day weights and prices (no costs). The gap should be small."""
    r_asset = mo.asset_returns(price_df)
    replay = (weights.shift(1) * r_asset.reindex(columns=weights.columns).fillna(0.0)).sum(axis=1)
    file_ret = base_nav.pct_change()
    gap = (file_ret - replay).dropna()
    total = float(base_nav.iloc[-1] / base_nav.iloc[0] / (1.0 + replay.dropna()).prod())
    return {"mean_abs_daily_gap": float(gap.abs().mean()), "max_abs_daily_gap": float(gap.abs().max()),
            "cumulative_nav_ratio_file_over_replay_no_cost": total,
            "note": "gap = file return minus replay with end-of-day weights; differences are mostly the base costs"}


def build_variant(sleeve, signal, off, ma_weeks, realloc, cost, weights, price_df, qqq):
    """Return (overlay return, traded fraction, holding multiplier) for one variant; the base variant is all zeros/ones."""
    idx = weights.index
    if sleeve is None:
        return pd.Series(0.0, index=idx), pd.Series(0.0, index=idx), pd.Series(1.0, index=idx)
    if sleeve == "ALL":
        parts = [build_variant(sl, "QQQ" if sl == "513100.SS" else "OWN", off, ma_weeks, realloc, cost, weights, price_df, qqq)
                 for sl in ["510300.SS", "513100.SS", "518880.SS"]]
        effect = sum(p[0] for p in parts)
        traded = sum(p[1] for p in parts)
        mult = pd.concat([p[2] for p in parts], axis=1).mean(axis=1)
        return effect, traded, mult
    close = qqq if signal == "QQQ" else price_df[sleeve]
    mult = mo.trend_multiplier(close.dropna(), off=off, ma_weeks=ma_weeks).reindex(idx).ffill().fillna(1.0)
    r_asset = mo.asset_returns(price_df)
    returns = pd.concat([r_asset.reindex(columns=["510300.SS", "513100.SS", "518880.SS", "BTC-USD"]),
                         pd.DataFrame(0.0, index=idx, columns=[CASH])], axis=1)
    effect, traded = mo.overlay_return(weights, returns, mult, sleeve=sleeve, cost_per_side=cost, reallocate=realloc)
    return effect.fillna(0.0), traded.fillna(0.0), mult


def segment_perf(ret: pd.Series, start: str, end: str) -> dict:
    return mo.perf(mo.window(ret, start, end))


def main() -> None:
    cfg = write_config()
    weights, base_nav, price_df, qqq = load_inputs()
    base_ret = base_nav.pct_change()
    base_ret = base_ret[base_ret.index >= pd.Timestamp(WINDOW[0])]
    check = base_check(weights, base_nav, price_df)

    rows, mult_rows = [], []
    table_returns = {}
    for name, sleeve, signal, off, ma_weeks, realloc, cost, role in VARIANTS:
        effect, traded, mult = build_variant(sleeve, signal, off, ma_weeks, realloc, cost, weights, price_df, qqq)
        ret = (base_ret + effect.reindex(base_ret.index).fillna(0.0)).dropna()
        ret = ret[ret.index >= pd.Timestamp(WINDOW[0])]
        table_returns[name] = ret
        full = mo.perf(ret)
        years = (ret.index[-1] - ret.index[0]).days / 365.25
        switches = int((mult.diff().abs() > 1e-12).sum()) if sleeve != "ALL" else None
        row = {"variant": name, "role": role, "sleeve": sleeve or "", "signal": signal or "", "off_weight": off if off is not None else "",
               "ma_weeks": ma_weeks if signal else "", "reallocate": realloc, "cost_per_side": cost,
               **full, "switches_per_year": switches / years if switches is not None else float("nan"),
               "traded_fraction_per_year": float(traded.sum() / years) if sleeve else 0.0,
               "avg_multiplier": float(mult.loc[ret.index].mean()) if sleeve else 1.0}
        for label, (start, end) in HALVES.items():
            seg = segment_perf(ret, start, end)
            row[f"sharpe_{label}"] = seg["sharpe"]
            row[f"cagr_{label}"] = seg["cagr"]
            row[f"max_dd_{label}"] = seg["max_dd"]
        rows.append(row)
        mult_rows.append(pd.DataFrame({"date": ret.index, "variant": name, "multiplier": mult.loc[ret.index].to_numpy()}))

    table = pd.DataFrame(rows)
    base = table[table["variant"] == "V0_base"].iloc[0]
    verdict_rows = []
    for _, r in table.iterrows():
        if r["variant"] == "V0_base":
            continue
        c1 = r["sharpe"] >= base["sharpe"]
        c2 = r["calmar"] >= base["calmar"]
        c3 = r["cagr"] >= base["cagr"] - 0.01
        c4 = (r["max_dd"] - base["max_dd"]) >= 0.02
        c5 = all(r[f"sharpe_{h}"] >= base[f"sharpe_{h}"] for h in HALVES)
        verdict_rows.append({"variant": r["variant"], "role": r["role"], "C1_sharpe": c1, "C2_calmar": c2,
                             "C3_cagr": c3, "C4_shallower_2pt": c4, "C5_both_halves": c5,
                             "PASS": (c1 and c2 and c3 and c4 and c5) if r["variant"] not in POST_HOC else "n/a (post-hoc)",
                             "delta_sharpe": r["sharpe"] - base["sharpe"], "delta_calmar": r["calmar"] - base["calmar"],
                             "delta_cagr": r["cagr"] - base["cagr"], "delta_max_dd": r["max_dd"] - base["max_dd"]})
    verdicts = pd.DataFrame(verdict_rows)
    primary = table[table["variant"] == "P_qqq_513100_off50"].iloc[0]
    stress = table[table["variant"] == "C_primary_cost60"].iloc[0]
    stress_ok = bool(stress["sharpe"] >= base["sharpe"] and stress["calmar"] >= base["calmar"])

    OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT / "summary.csv", index=False)
    verdicts.to_csv(OUT / "verdicts.csv", index=False)
    pd.concat(mult_rows).to_csv(OUT / "multipliers_daily.csv", index=False)
    selfcheck = {"base_replay_check": check, "base_window": WINDOW,
                 "base_metrics_from_file": {k: float(base[k]) for k in ["cagr", "vol", "sharpe", "max_dd", "calmar"]},
                 "primary_stress_60bp_holds": stress_ok,
                 "primary_pass": bool(verdicts.loc[verdicts["variant"] == "P_qqq_513100_off50", "PASS"].iloc[0])}
    (OUT / "selfcheck.json").write_text(json.dumps(selfcheck, ensure_ascii=False, indent=2, default=float))

    # Diagnostics: where the base drawdown sits, when the primary filter first cut, and calendar-year returns.
    base_curve = (1.0 + base_ret).cumprod()
    dd_base = base_curve / base_curve.cummax() - 1.0
    trough = dd_base.idxmin()
    peak = base_curve.loc[:trough].idxmax()
    mult_p = pd.concat(mult_rows)
    mult_p = mult_p[mult_p["variant"] == "P_qqq_513100_off50"].set_index("date")["multiplier"]
    first_cut_after_peak = mult_p.loc[peak:][mult_p.loc[peak:] < 1.0]
    yearly = {}
    for name in ["V0_base", "P_qqq_513100_off50", "X_all_sleeves_off50"]:
        r_ = table_returns[name]
        yearly[name] = (1.0 + r_).groupby(r_.index.year).prod() - 1.0
    pd.DataFrame(yearly).to_csv(OUT / "yearly_returns.csv")
    diagnostic = {"base_max_drawdown": float(dd_base.min()), "peak": str(peak.date()), "trough": str(trough.date()),
                  "primary_first_cut_after_peak": str(first_cut_after_peak.index[0].date()) if len(first_cut_after_peak) else None,
                  "primary_multiplier_at_trough": float(mult_p.loc[trough])}
    (OUT / "drawdown_diagnostic.json").write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2))

    pd.set_option("display.width", 240)
    show = ["variant", "cagr", "vol", "sharpe", "max_dd", "calmar", "sharpe_2016-2021", "sharpe_2021-2026",
            "switches_per_year", "avg_multiplier"]
    print(table[show].round(3).to_string(index=False))
    print(verdicts.round(3).to_string(index=False))
    print(json.dumps(selfcheck, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
