"""New S&P 500 enhancement rules, compared with the frozen baselines.

The 2026-11-10 study already tested S2, VT-1.0, F10, absolute momentum,
GTT, calendar rules and RSI(2).  This pass deliberately tests new rule
families only:

* MTF-3: a 30-week rising-trend state and a 10-month trend state are
  combined into three positions (100/50/0%).
* DD-RB: a drawdown risk budget reduces exposure to 75/50/25% after the
  running high has fallen 10/20/30%.
* TVT-50: volatility targeting at 15% while the weekly trend is on, capped
  at 50% while it is off.  This is a conditional volatility rule, rather
  than the previously tested F10xVT (which exits to zero on a monthly rule).

Signals are decided at a close and filled at the next close.  All prices and
cash rates come from the cached SPY/^IRX data used by the prior study.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from research_index_enhance_strategies import load_sp500  # noqa: E402
from xquant import overlay_rules as ov  # noqa: E402
from xquant import position_rules as pr  # noqa: E402

SLUG = "sp500-new-enhance-2026-11-14"
OUT = ROOT / "outputs" / SLUG
START, END = "2000-01-03", "2026-10-16"
SEGMENTS = {"2000-2012": ("2000-01-03", "2012-12-31"), "2013-2026": ("2013-01-01", END)}
COST, COST30 = 0.001, 0.003


def monthly_state(close: pd.Series, months: int = 10) -> np.ndarray:
    idx = np.flatnonzero(ov.month_end_mask(close.index))
    vals = close.iloc[idx]
    sma = vals.rolling(months).mean()
    decisions = (vals > sma).astype(float).to_numpy()
    out = pd.Series(np.nan, index=close.index)
    out.iloc[idx] = decisions
    return out.ffill().fillna(0.0).to_numpy(float)


def weekly_state(close: pd.Series, weeks: int = 30, slope_weeks: int = 4) -> np.ndarray:
    states = pr.stage_states(close, ma_weeks=weeks, slope_weeks=slope_weeks)
    return states.reindex(close.index, method="ffill").fillna(False).to_numpy(float)


def state_signal(state: np.ndarray, start_i: int):
    state = np.asarray(state, float)

    def sig(i, _weights):
        if i == start_i or (i > start_i and np.any(state[i] != state[i - 1])):
            return np.array([state[i], 0.0])
        return None

    return sig


def mtf3_signal(close: pd.Series, start_i: int, week_ma: int = 30, month_ma: int = 10,
                slope_weeks: int = 4):
    w = weekly_state(close, week_ma, slope_weeks)
    m = monthly_state(close, month_ma)
    # Both trends on -> 100%; one on -> 50%; both off -> cash.
    state = np.where((w + m) >= 2.0, 1.0, np.where((w + m) >= 1.0, 0.5, 0.0))
    return state_signal(state, start_i)


def drawdown_budget_signal(close: pd.Series, start_i: int,
                           thresholds: tuple[float, float, float] = (-0.10, -0.20, -0.30),
                           weights: tuple[float, float, float, float] = (1.0, 0.75, 0.50, 0.25)):
    dd = close / close.cummax() - 1.0
    t1, t2, t3 = thresholds
    state = np.select([dd > t1, dd > t2, dd > t3], weights[:3], default=weights[3])
    return state_signal(state, start_i)


def conditional_vt_signal(close: pd.Series, start_i: int, target: float = 0.15,
                          window: int = 21, off_cap: float = 0.50, band: float = 0.10):
    log_ret = np.log(close).diff()
    vol = log_ret.rolling(window).std(ddof=1).to_numpy(float) * np.sqrt(252.0)
    raw = np.divide(target, vol, out=np.full(len(close), np.nan), where=vol > 0)
    trend = weekly_state(close, weeks=30, slope_weeks=4)
    wanted = np.minimum(np.where(trend > 0.5, 1.0, off_cap), raw)

    def sig(i, actual):
        if np.isnan(wanted[i]):
            return None
        if i == start_i or abs(wanted[i] - actual[0]) > band:
            return np.array([wanted[i], 0.0])
        return None

    return sig


def build_data():
    spy, bill = load_sp500()
    keep = (spy.index >= pd.Timestamp("1998-12-01")) & (spy.index <= pd.Timestamp(END))
    spy, bill = spy[keep], bill.reindex(spy.index).ffill()
    pos, neg = ov.calendar_cash_factors(spy.index, bill.to_numpy(float), 0.015)
    return ov.MarketData(spy.index, spy, spy.copy(), pos, neg), spy


def run(data, name: str, start: str, cost: float = COST, params: dict | None = None):
    params = params or {}
    start_i = int(data.dates.searchsorted(pd.Timestamp(start)))
    if name in {"B0", "S2", "VT"}:
        res = ov.simulate(data, {"B0": "B0", "S2": "S2", "VT": "VT"}[name],
                          start, cost=cost)
    elif name == "MTF-3":
        sig = mtf3_signal(data.spy, start_i, **params)
        prices = pd.DataFrame({"a": data.spy, "b": data.spy}, index=data.dates)
        res = ov.run_overlay(prices, sig, start_i, cost, data.cash_pos, data.cash_neg)
    elif name == "DD-RB":
        sig = drawdown_budget_signal(data.spy, start_i, **params)
        prices = pd.DataFrame({"a": data.spy, "b": data.spy}, index=data.dates)
        res = ov.run_overlay(prices, sig, start_i, cost, data.cash_pos, data.cash_neg)
    elif name == "TVT-50":
        sig = conditional_vt_signal(data.spy, start_i, **params)
        prices = pd.DataFrame({"a": data.spy, "b": data.spy}, index=data.dates)
        res = ov.run_overlay(prices, sig, start_i, cost, data.cash_pos, data.cash_neg)
    elif name == "FIXED":
        sig = ov.fixed_weight_signal(float(params["weight"]), data.dates, start_i)
        prices = pd.DataFrame({"a": data.spy, "b": data.spy}, index=data.dates)
        res = ov.run_overlay(prices, sig, start_i, cost, data.cash_pos, data.cash_neg)
    else:
        raise ValueError(name)
    m = ov.perf_metrics(res.nav, res.tbill_daily, res.weights["a"], ov.count_trades(res))
    return res, m


def monthly_q5(nav: pd.Series) -> dict:
    month = nav.resample("ME").last().pct_change().dropna()
    wins, losses = month[month > 0], month[month < 0]
    payoff = wins.mean() / abs(losses.mean()) if len(losses) else np.nan
    pf = wins.sum() / abs(losses.sum()) if len(losses) else np.nan
    return {"monthly_n": len(month), "monthly_win_rate": float((month > 0).mean()),
            "avg_win_month": float(wins.mean()), "avg_loss_month": float(losses.mean()),
            "payoff_ratio": float(payoff), "profit_factor": float(pf),
            "best_month": float(month.max()), "worst_month": float(month.min())}


def drawdown_events(nav: pd.Series, n: int = 8) -> pd.DataFrame:
    dd = nav / nav.cummax() - 1.0
    events = []
    in_event = False
    start = trough = None
    for date, value in dd.items():
        if value < 0 and not in_event:
            in_event, start, trough = True, date, date
        if in_event and value < dd.loc[trough]:
            trough = date
        if in_event and value >= 0:
            events.append({"start": start, "trough": trough, "recovery": date,
                           "depth": float(dd.loc[trough]),
                           "days_to_recovery": int((date - trough).days)})
            in_event = False
    if in_event:
        events.append({"start": start, "trough": trough, "recovery": pd.NaT,
                       "depth": float(dd.loc[trough]), "days_to_recovery": np.nan})
    return pd.DataFrame(events).sort_values("depth").head(n)


def segment_metrics(results: dict, data):
    rows = []
    for label, (res, _) in results.items():
        for seg, (s, e) in SEGMENTS.items():
            nav = ov.segment_slice(res.nav, s, e)
            m = ov.perf_metrics(nav, res.tbill_daily, res.weights["a"].reindex(nav.index), 0)
            rows.append({"strategy": label, "segment": seg, **m})
    return pd.DataFrame(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data, spy = build_data()
    labels = ["B0", "S2", "VT", "MTF-3", "DD-RB", "TVT-50"]
    params = {"MTF-3": {}, "DD-RB": {}, "TVT-50": {}}
    results = {label: run(data, label, START, params=params.get(label))[0:2] for label in labels}
    summary = []
    for label, (res, m) in results.items():
        summary.append({"strategy": label, **m, **monthly_q5(res.nav)})
    fixed_results = {}
    for label in ("MTF-3", "TVT-50"):
        weight = results[label][1]["avg_weight"]
        fixed_results[label] = run(data, "FIXED", START, params={"weight": weight})
        res, m = fixed_results[label]
        summary.append({"strategy": f"F_{label}", "matched_weight": weight, **m, **monthly_q5(res.nav)})
    pd.DataFrame([{"strategy": f"F_{label}", "matched_weight": results[label][1]["avg_weight"], **m}
                  for label, (res, m) in fixed_results.items()]).to_csv(OUT / "fixed_weight.csv", index=False)
    pd.DataFrame(summary).to_csv(OUT / "summary_q3_q5.csv", index=False)
    pd.DataFrame({k: v[0].nav for k, v in results.items()}).to_csv(OUT / "nav_daily.csv", index_label="date")
    pd.DataFrame({k: v[0].weights["a"] for k, v in results.items()}).to_csv(OUT / "weights_daily.csv", index_label="date")
    pd.DataFrame({k: ov.yearly_returns(v[0].nav) for k, v in results.items()}).rename_axis("year").to_csv(OUT / "yearly_returns.csv")
    segment_metrics(results, data).to_csv(OUT / "segments.csv", index=False)
    dd = pd.concat([drawdown_events(v[0].nav).assign(strategy=k) for k, v in results.items()], ignore_index=True)
    dd.to_csv(OUT / "drawdown_events.csv", index=False)

    # DCA lens: full path and all complete 10-year windows.
    contrib = ov.contribution_dates(data.dates, START, END)
    dca_rows = []
    for label, (res, _) in results.items():
        dca_rows.append({"strategy": label, **ov.dca_account(res.nav, contrib, END)})
    pd.DataFrame(dca_rows).to_csv(OUT / "dca_full.csv", index=False)
    windows = []
    for day in contrib:
        w = ov.ten_year_window(data.dates, day)
        if w is None:
            continue
        c, e = w
        plain = ov.dca_account(results["B0"][0].nav, c, e)
        for label, (res, _) in results.items():
            a = plain if label == "B0" else ov.dca_account(res.nav, c, e)
            windows.append({"strategy": label, "start": str(day.date()), "end": str(e.date()), **a,
                            "ratio_gt_plain": bool(a["ratio"] > plain["ratio"]),
                            "xirr_gt_plain": bool(a["xirr"] > plain["xirr"])})
    wf = pd.DataFrame(windows)
    wf.to_csv(OUT / "dca_windows.csv", index=False)
    dca_summary = []
    for label in labels:
        sub = wf[wf.strategy == label]
        dca_summary.append({"strategy": label, "n_windows": len(sub), "median_xirr": sub.xirr.median(),
                            "worst_xirr": sub.xirr.min(), "median_max_float_loss": sub.max_float_loss.median(),
                            "median_ratio": sub.ratio.median(), "share_ratio_gt_plain": sub.ratio_gt_plain.mean(),
                            "share_xirr_gt_plain": sub.xirr_gt_plain.mean()})
    pd.DataFrame(dca_summary).to_csv(OUT / "dca_summary.csv", index=False)

    # Pre-specified small grids; no parameter is selected from these results.
    sens = []
    for wm in (20, 30, 40):
        for mm in (8, 10, 12):
            res, m = run(data, "MTF-3", START, params={"week_ma": wm, "month_ma": mm})
            sens.append({"family": "MTF-3", "variant": f"week{wm}_month{mm}", **m, **monthly_q5(res.nav)})
    for ts in ((-0.05, -0.15, -0.25), (-0.10, -0.20, -0.30), (-0.15, -0.25, -0.35)):
        for ws in ((1.0, 0.75, 0.50, 0.25), (1.0, 0.80, 0.60, 0.40)):
            res, m = run(data, "DD-RB", START, params={"thresholds": ts, "weights": ws})
            sens.append({"family": "DD-RB", "variant": f"t{ts}_w{ws}", **m, **monthly_q5(res.nav)})
    for target in (0.12, 0.15, 0.18):
        for cap in (0.25, 0.50, 0.75):
            res, m = run(data, "TVT-50", START, params={"target": target, "off_cap": cap})
            sens.append({"family": "TVT-50", "variant": f"target{target}_offcap{cap}", **m, **monthly_q5(res.nav)})
    pd.DataFrame(sens).to_csv(OUT / "sensitivity.csv", index=False)

    # Cost stress and rolling starts provide a simple robustness check.
    cost_rows = []
    for label in labels:
        _, m = run(data, label, START, cost=COST30, params=params.get(label))
        cost_rows.append({"strategy": label, "cost_per_side": COST30, **m})
    pd.DataFrame(cost_rows).to_csv(OUT / "cost30.csv", index=False)
    rolling = []
    for year in range(2000, 2024):
        st = data.dates[data.dates.searchsorted(pd.Timestamp(f"{year}-01-01"))]
        base = run(data, "B0", str(st.date()))[1]
        for label in labels[1:]:
            m = run(data, label, str(st.date()), params=params.get(label))[1]
            rolling.append({"strategy": label, "start": str(st.date()), "sharpe": m["sharpe"],
                            "calmar": m["calmar"], "b0_sharpe": base["sharpe"], "b0_calmar": base["calmar"],
                            "sharpe_gt_b0": m["sharpe"] > base["sharpe"], "calmar_gt_b0": m["calmar"] > base["calmar"]})
    pd.DataFrame(rolling).to_csv(OUT / "rolling_starts.csv", index=False)

    # Pre-registered decision table.  A candidate must improve at least one
    # risk-adjusted metric in the full sample and in each segment, retain an
    # improvement at 30bp, and beat plain DCA's ratio in at least 60% of the
    # complete 10-year windows.  The segment CAGR guard prevents a tiny risk
    # metric edge from hiding a materially weaker return stream.
    b0_main = next(row for row in summary if row["strategy"] == "B0")
    b0_seg = segment_metrics(results, data)
    dca_by = {r["strategy"]: r for r in dca_summary}
    c30 = {r["strategy"]: r for r in cost_rows}
    verdicts = []
    for label in labels[1:]:
        row = next(r for r in summary if r["strategy"] == label)
        seg_ok = True
        seg_detail = []
        for seg in SEGMENTS:
            cand = next(r for r in segment_metrics(results, data).to_dict("records")
                        if r["strategy"] == label and r["segment"] == seg)
            base = next(r for r in b0_seg.to_dict("records")
                        if r["strategy"] == "B0" and r["segment"] == seg)
            metric_ok = (cand["sharpe"] > base["sharpe"] or cand["calmar"] > base["calmar"])
            cagr_guard = cand["cagr"] >= base["cagr"] - 0.03
            seg_ok = seg_ok and metric_ok and cagr_guard
            seg_detail.append({"segment": seg, "risk_metric_beats": metric_ok, "cagr_guard": cagr_guard,
                               "sharpe": cand["sharpe"], "b0_sharpe": base["sharpe"],
                               "calmar": cand["calmar"], "b0_calmar": base["calmar"],
                               "cagr": cand["cagr"], "b0_cagr": base["cagr"]})
        main_ok = row["sharpe"] > b0_main["sharpe"] or row["calmar"] > b0_main["calmar"]
        cost_row = c30[label]
        b0_cost = c30["B0"]
        cost_ok = cost_row["sharpe"] > b0_cost["sharpe"] or cost_row["calmar"] > b0_cost["calmar"]
        dca_ratio = float(dca_by[label]["share_ratio_gt_plain"])
        dca_ok = dca_ratio >= 0.60
        verdicts.append({"strategy": label, "main_sharpe_or_calmar": main_ok,
                         "segments_risk_metric_and_cagr": seg_ok, "cost30_sharpe_or_calmar": cost_ok,
                         "dca_ratio_share_ge_60pct": dca_ok,
                         "pass_all": main_ok and seg_ok and cost_ok and dca_ok,
                         "dca_ratio_share": dca_ratio,
                         "segment_detail": json.dumps(seg_detail, ensure_ascii=False)})
    pd.DataFrame(verdicts).to_csv(OUT / "verdicts.csv", index=False)

    # Internal consistency checks catch accidental weight overflow, repeated
    # runs that disagree, and a state that changes when future rows are removed.
    checks = {"weights_in_range": True, "default_reproducible": True, "no_lookahead": True}
    for label, (res, _) in results.items():
        checks["weights_in_range"] &= bool((res.weights["a"].between(0.0, 1.0)).all())
        if label in {"MTF-3", "DD-RB", "TVT-50"}:
            again = run(data, label, START, params=params.get(label))[0]
            checks["default_reproducible"] &= bool(np.allclose(res.nav.to_numpy(), again.nav.to_numpy()))
    # At month/quarter cutoffs, recomputed signals from truncated history must
    # agree with the full-history signal at that date.
    for cutoff in pd.to_datetime(["2005-12-30", "2010-06-30", "2018-12-31", "2024-12-31"]):
        full_i = int(data.dates.searchsorted(cutoff, side="right") - 1)
        if full_i < 1:
            continue
        short = data.spy.iloc[: full_i + 1]
        for builder, kwargs in ((mtf3_signal, {}), (drawdown_budget_signal, {}), (conditional_vt_signal, {})):
            full_sig = builder(data.spy, 0, **kwargs)
            short_sig = builder(short, 0, **kwargs)
            # Signals at the cutoff are represented by the target requested at
            # that close; actual weights are irrelevant to this check.
            a = full_sig(full_i, np.array([0.0, 0.0]))
            b = short_sig(len(short) - 1, np.array([0.0, 0.0]))
            if a is not None and b is not None:
                checks["no_lookahead"] &= bool(np.allclose(a, b, equal_nan=True))
    (OUT / "selfcheck.json").write_text(json.dumps(checks, indent=2, ensure_ascii=False))
    cfg = {"slug": SLUG, "window": [START, END], "cost_per_side": COST,
           "baselines": {"B0": "buy and hold", "S2": "frozen weekly half-trend", "VT": "frozen 15%/21-day VT-1.0"},
           "new_rules": {"MTF-3": "weekly 30-week rising state + monthly 10-month state: 100/50/0%",
                         "DD-RB": "running drawdown tiers >-10/-20/-30%: 100/75/50/25%",
                         "TVT-50": "15% volatility target when weekly trend on, cap 50% when off"},
           "execution": "close signal, next-close fill; SPY total return and ^IRX cash; 10bp and 30bp stress",
           "dca": "1 unit monthly, complete 10-year windows, XIRR and unit drawdown",
           "verdict_criteria": {"main": "Sharpe or Calmar > B0", "segments": "each segment has Sharpe or Calmar > B0 and CAGR no more than 3pp below B0", "cost30": "Sharpe or Calmar > B0 at 30bp per side", "dca": "ratio_gt_plain share >= 60%"}}
    (OUT / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
