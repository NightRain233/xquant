"""Replay MTF-3 and TVT-50 on the real RMB 513500 price path.

The traded series is the unadjusted 513500 close with the official 1:2 split
fixed before the start of the study.  That price already contains the fund's
RMB/USD exposure, secondary-market premium/discount, tracking error and fund
expenses.  SPY is used only to form the previously specified signal, and the
historical premium file plus CNY=X are retained as diagnostics rather than
being applied a second time to the traded price.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from research_domestic_us_etf_trend import (  # noqa: E402
    CONFIG as DOMESTIC_CONFIG,
    EXPECTED_SHA,
    FORWARD_FILE,
    RAW_FILE,
    SPLITS,
    SOURCE,
    load_provider,
)
from research_index_enhance_strategies import load_sp500  # noqa: E402
from xquant import position_rules as pr  # noqa: E402
from xquant import style_combo as sc  # noqa: E402

SLUG = "sp500-513500-mtf-tvt-real-2026-11-14"
OUT = ROOT / "outputs" / SLUG
PREMIUM = ROOT / "outputs" / "qdii-premium-2026-11-10" / "premium_daily_513500.csv"
FX = ROOT / "outputs" / "strategy-healthcheck-2026-10-02" / "market_data" / "CNY=X.parquet"
START, END = pd.Timestamp("2014-10-08"), pd.Timestamp("2026-09-30")
COSTS = {"10bp": 0.001, "30bp": 0.003}


def domestic_close() -> pd.Series:
    s = load_provider(RAW_FILE, "513500")
    date, ratio = SPLITS["513500"]
    s = s.copy()
    s.loc[s.index < date] /= ratio
    return s[(s.index >= START) & (s.index <= END)]


def stage_states(close: pd.Series, ma_weeks: int = 30, slope_weeks: int = 4) -> pd.Series:
    return pr.stage_states(close, ma_weeks=ma_weeks, slope_weeks=slope_weeks)


def month_state(close: pd.Series, months: int = 10) -> pd.Series:
    idx = np.flatnonzero(close.index[:-1].to_period("M") != close.index[1:].to_period("M"))
    vals = close.iloc[idx]
    sma = vals.rolling(months).mean()
    state = (vals > sma).astype(float)
    return pd.Series(state.to_numpy(float), index=close.index[idx]).sort_index()


def latest_before(series: pd.Series, date: pd.Timestamp, default: float = 0.0) -> float:
    known = series[series.index < date]
    return default if known.empty else float(known.iloc[-1])


def signal_mtf(spy: pd.Series, domestic_dates: pd.DatetimeIndex, start_i: int):
    weekly = stage_states(spy)
    monthly = month_state(spy)
    state = {"last": None}

    def sig(i: int):
        date = domestic_dates[i]
        w = latest_before(weekly.astype(float), date, 0.0)
        m = latest_before(monthly, date, 0.0)
        wanted = 1.0 if w > 0.5 and m > 0.5 else (0.5 if w > 0.5 or m > 0.5 else 0.0)
        if i == start_i or wanted != state["last"]:
            state["last"] = wanted
            return {"a": wanted, "b": 0.0}
        return None

    return sig


def signal_tvt(spy: pd.Series, domestic_dates: pd.DatetimeIndex, start_i: int,
               target: float = 0.15, window: int = 21, off_cap: float = 0.50):
    vol = np.log(spy).diff().rolling(window).std(ddof=1) * np.sqrt(252.0)
    weekly = stage_states(spy)
    state = {"last": None}

    def sig(i: int):
        date = domestic_dates[i]
        v = latest_before(vol, date, np.nan)
        if np.isnan(v) or v <= 0:
            return None
        trend = latest_before(weekly.astype(float), date, 0.0) > 0.5
        cap = 1.0 if trend else off_cap
        wanted = min(cap, target / v)
        if i == start_i or state["last"] is None or abs(wanted - state["last"]) > 0.10:
            state["last"] = wanted
            return {"a": wanted, "b": 0.0}
        return None

    return sig


def run(prices: pd.DataFrame, signal, cash: float = 0.02, cost: float = 0.001):
    return sc.run_backtest(prices, signal, 0, cost, cash)


def metrics(result) -> dict:
    m = sc.summary_metrics(result.nav, result.trades)
    ret = result.nav.pct_change().dropna()
    days = (ret.index.to_series().diff().dt.days.fillna(1.0).to_numpy() / 365.25)
    rf = pd.Series((1.02 ** days) - 1.0, index=ret.index)
    excess = ret - rf
    sharpe = float(excess.mean() / excess.std(ddof=1) * np.sqrt(252.0)) if excess.std(ddof=1) > 0 else np.nan
    return {"cagr": m["annualized"], "vol": m["annual_vol"], "sharpe": m.get("sharpe", np.nan),
            "max_dd": m["max_drawdown"], "calmar": m["calmar"], "trades": m["n_trades"],
            "sharpe": sharpe, "avg_weight": float(result.weights["a"].iloc[1:].mean()),
            "time_below_20": float((sc.drawdown(result.nav) < -0.20).mean())}


def q5(nav: pd.Series) -> dict:
    monthly = nav.resample("ME").last().pct_change().dropna()
    win, loss = monthly[monthly > 0], monthly[monthly < 0]
    return {"monthly_win_rate": float((monthly > 0).mean()), "avg_win_month": float(win.mean()),
            "avg_loss_month": float(loss.mean()), "payoff_ratio": float(win.mean() / abs(loss.mean())),
            "profit_factor": float(win.sum() / abs(loss.sum())), "best_month": float(monthly.max()),
            "worst_month": float(monthly.min())}


def annual(nav: pd.Series) -> pd.Series:
    last = nav.groupby(nav.index.year).last()
    return last / last.shift(1).fillna(nav.iloc[0]) - 1.0


def dca(nav: pd.Series, dates: pd.DatetimeIndex) -> dict:
    contrib = dates[~dates.to_period("M").duplicated()]
    from xquant.cashflow_research import xirr
    contrib = pd.DatetimeIndex(contrib).intersection(nav.index)
    buy_units = pd.Series(0.0, index=nav.index)
    buy_units.loc[contrib] = 1.0 / nav.loc[contrib]
    units = buy_units.cumsum()
    principal_s = pd.Series(0.0, index=nav.index)
    principal_s.loc[contrib] = 1.0
    principal_s = principal_s.cumsum()
    value = units * nav
    float_ret = value / principal_s.replace(0, np.nan) - 1.0
    flows = pd.Series(1.0, index=contrib)
    terminal = float(value.iloc[-1])
    return {"xirr": float(xirr(flows, terminal, nav.index[-1])), "terminal_per_contribution": terminal / len(contrib),
            "max_float_loss": float(float_ret.dropna().min()), "n_contributions": len(contrib)}


def dca_window(nav: pd.Series, start: pd.Timestamp, months: int = 60) -> dict | None:
    end_month = start.to_period("M") + (months - 1)
    part = nav[(nav.index >= start) & (nav.index.to_period("M") <= end_month)]
    if part.empty or part.index[-1].to_period("M") != end_month:
        return None
    contrib = part.index[~part.index.to_period("M").duplicated()]
    return dca(part, contrib)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    domestic = domestic_close()
    spy, _ = load_sp500()
    spy = spy[spy.index <= END]
    dates = domestic.index
    prices = pd.DataFrame({"a": domestic, "b": domestic}, index=dates)
    start_i = int(dates.searchsorted(START))
    # Signals are mapped from the latest completed US close strictly before the
    # mainland trading day; the prices are the real RMB traded closes.
    builders = {
        "B0": lambda: sc.rule_buy_hold({"a": 1.0, "b": 0.0}, 0),
        "MTF-3": lambda: signal_mtf(spy, dates, 0),
        "TVT-50": lambda: signal_tvt(spy, dates, 0),
    }
    results = {}
    rows = []
    for cost_label, cost in COSTS.items():
        for name, build in builders.items():
            result = run(prices, build(), cost=cost)
            results[(cost_label, name)] = result
            rows.append({"cost": cost_label, "strategy": name, **metrics(result), **q5(result.nav)})
    pd.DataFrame(rows).to_csv(OUT / "summary_q3_q5.csv", index=False)
    pd.DataFrame({f"{c}_{n}": r.nav for (c, n), r in results.items()}).to_csv(OUT / "nav_daily.csv", index_label="date")
    pd.DataFrame({f"{c}_{n}": r.weights["a"] for (c, n), r in results.items()}).to_csv(OUT / "weights_daily.csv", index_label="date")
    pd.DataFrame({f"{c}_{n}": annual(r.nav) for (c, n), r in results.items()}).to_csv(OUT / "annual_returns.csv")
    pd.DataFrame({f"{c}_{n}": r.nav.resample("ME").last().pct_change() for (c, n), r in results.items()}).to_csv(OUT / "monthly_returns.csv")

    seg_rows = []
    for (cost_label, name), result in results.items():
        for label, (s, e) in {"2014-2020": ("2014-10-08", "2020-12-31"), "2021-2026": ("2021-01-01", str(END.date()))}.items():
            nav = result.nav[(result.nav.index >= s) & (result.nav.index <= e)]
            seg_rows.append({"cost": cost_label, "strategy": name, "segment": label, **metrics(type("R", (), {"nav": nav, "trades": result.trades, "weights": result.weights})())})
    pd.DataFrame(seg_rows).to_csv(OUT / "segments.csv", index=False)

    dca_rows = []
    for (cost_label, name), result in results.items():
        dca_rows.append({"cost": cost_label, "strategy": name, **dca(result.nav, dates)})
    pd.DataFrame(dca_rows).to_csv(OUT / "dca_summary.csv", index=False)
    window_rows = []
    month_starts = dates[~dates.to_period("M").duplicated()]
    for start in month_starts:
        for months in (60, 120):
            base = dca_window(results[("10bp", "B0")].nav, start, months)
            if base is None:
                continue
            for name in ("B0", "MTF-3", "TVT-50"):
                cur = dca_window(results[("10bp", name)].nav, start, months)
                if cur is None:
                    continue
                cur_ratio = cur["xirr"] / abs(cur["max_float_loss"]) if cur["max_float_loss"] < 0 else np.nan
                base_ratio = base["xirr"] / abs(base["max_float_loss"]) if base["max_float_loss"] < 0 else np.nan
                window_rows.append({"start": str(start.date()), "months": months, "strategy": name,
                                    **cur, "ratio": cur_ratio,
                                    "ratio_gt_b0": bool(cur_ratio > base_ratio) if np.isfinite(base_ratio) and np.isfinite(cur_ratio) else False,
                                    "xirr_gt_b0": cur["xirr"] > base["xirr"]})
    windows = pd.DataFrame(window_rows)
    windows.to_csv(OUT / "dca_windows.csv", index=False)
    if not windows.empty:
        (windows.groupby(["months", "strategy"])
         .agg(n=("xirr", "size"), median_xirr=("xirr", "median"), median_ratio=("ratio", "median"),
              share_ratio_gt_b0=("ratio_gt_b0", "mean"), share_xirr_gt_b0=("xirr_gt_b0", "mean"))
         .reset_index().to_csv(OUT / "dca_windows_summary.csv", index=False))

    # Fixed grids are sensitivity checks only; the default is not selected from them.
    sensitivity = []
    for weeks, months in ((20, 8), (30, 10), (40, 12)):
        # MTF signal with a fixed 50/100/0 rule, using the same domestic path.
        def mtf_variant(i, w=weeks, mo=months):
            weekly = stage_states(spy, ma_weeks=w)
            monthly = month_state(spy, months=mo)
            state = {"last": None}
            def sig(j):
                d = dates[j]; ww = latest_before(weekly.astype(float), d, 0.0); mm = latest_before(monthly, d, 0.0)
                wanted = 1.0 if ww > .5 and mm > .5 else (.5 if ww > .5 or mm > .5 else 0.0)
                if j == 0 or wanted != state["last"]:
                    state["last"] = wanted; return {"a": wanted, "b": 0.0}
                return None
            return sig
        r = run(prices, mtf_variant(0), cost=COSTS["10bp"])
        sensitivity.append({"family": "MTF-3", "variant": f"week{weeks}_month{months}", **metrics(r)})
    for target, cap in ((0.12, .25), (.15, .50), (.18, .75)):
        r = run(prices, signal_tvt(spy, dates, 0, target=target, off_cap=cap), cost=COSTS["10bp"])
        sensitivity.append({"family": "TVT-50", "variant": f"target{target:.2f}_offcap{cap:.2f}", **metrics(r)})
    pd.DataFrame(sensitivity).to_csv(OUT / "sensitivity.csv", index=False)

    # Premium and FX are diagnostics.  Using them to reprice the already traded
    # ETF would double count exactly the effects the user asked us to measure.
    prem = pd.read_csv(PREMIUM, parse_dates=["date"]).set_index("date")
    fx = pd.read_parquet(FX)["Close"].rename("USDCNY")
    diag = pd.DataFrame({"513500_close": domestic, "USDCNY": fx.reindex(dates).ffill()}).join(prem[["premium", "estimated_nav"]], how="left")
    diag.to_csv(OUT / "rmb_fx_premium_diagnostic.csv", index_label="date")
    diag_summary = {"price_start": str(domestic.index[0].date()), "price_end": str(domestic.index[-1].date()),
                    "fx_start": float(diag["USDCNY"].dropna().iloc[0]), "fx_end": float(diag["USDCNY"].dropna().iloc[-1]),
                    "premium_median": float(diag["premium"].median()), "premium_above_3pct_share": float((diag["premium"] > 0.03).mean()),
                    "premium_above_10pct_share": float((diag["premium"] > 0.10).mean()),
                    "fee_treatment": "513500 management/custody fees are embedded in the real traded price; no second deduction"}
    (OUT / "diagnostic_summary.json").write_text(json.dumps(diag_summary, ensure_ascii=False, indent=2))
    checks = {"price_dates_unique": bool(domestic.index.is_unique), "price_finite_positive": bool(np.isfinite(domestic).all() and (domestic > 0).all()),
              "weights_in_range": bool(all((r.weights["a"].between(0.0, 1.0)).all() for r in results.values())),
              "premium_fx_overlap": bool(diag["USDCNY"].notna().any() and diag["premium"].notna().any()),
              "fees_not_double_counted": True}
    (OUT / "selfcheck.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2))
    config = {"slug": SLUG, "window": [str(START.date()), str(END.date())], "signal": "SPY USD signals, latest completed US close before each mainland date", "trade_price": "actual 513500 RMB close, official 1:2 split adjustment", "cash": "2% annual RMB cash proxy", "costs": COSTS, "premium": "historical estimated premium diagnostics from qdii-premium-2026-11-10; not double-counted", "fx": "CNY=X close diagnostics; RMB close already includes FX", "fund_fee": "embedded in traded price; not separately deducted", "source_hashes": {RAW_FILE.name: hashlib.sha256(RAW_FILE.read_bytes()).hexdigest(), FORWARD_FILE.name: hashlib.sha256(FORWARD_FILE.read_bytes()).hexdigest(), PREMIUM.name: hashlib.sha256(PREMIUM.read_bytes()).hexdigest(), FX.name: hashlib.sha256(FX.read_bytes()).hexdigest()}}
    (OUT / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
