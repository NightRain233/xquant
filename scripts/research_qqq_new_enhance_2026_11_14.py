"""New QQQ enhancement candidates: multi-timeframe risk control and relative rotation.

The earlier QQQ study only copied the S&P 500 half-trend and leveraged rules.  This
experiment keeps those as baselines and tests two different ideas:

* ``MTF-3``: the same multi-timeframe confirmation used in the new S&P study,
  applied to QQQ (100/50/0% according to weekly and monthly states).
* ``REL-12``: monthly 12-month relative momentum.  Hold QQQ when QQQ beats both
  SPY and cash and is above its 10-month mean; otherwise hold SPY when its own
  absolute trend is positive, and hold cash when neither equity passes.

``TVT-50`` is included as a transfer baseline: QQQ targets 15% volatility while
its weekly trend is on and is capped at 50% while off.  Signals are decided at
the close and filled at the next close.  Results are for research, not a trading
recommendation.
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
from xquant.weinstein_stage import load_yfinance_csv  # noqa: E402

SLUG = "qqq-new-enhance-2026-11-14"
OUT = ROOT / "outputs" / SLUG
QQQ_CACHE = ROOT / "outputs" / "weinstein-quick-checks-2026-10-18" / "cache" / "yf_QQQ.csv"
END = pd.Timestamp("2026-10-16")
START = pd.Timestamp("2000-01-03")
COST, COST30 = 0.001, 0.003
SEGMENTS = {"2000-2012": (START, pd.Timestamp("2012-12-31")),
            "2013-2026": (pd.Timestamp("2013-01-01"), END)}


def load_qqq() -> pd.Series:
    close = load_yfinance_csv(QQQ_CACHE)["close"]
    return close[(close.index >= pd.Timestamp("1998-12-01")) & (close.index <= END)]


def weekly_state(close: pd.Series, weeks: int = 30, slope_weeks: int = 4) -> np.ndarray:
    grouped = close.groupby(close.index.to_period("W-SUN"))
    weekly = pd.Series(grouped.last().to_numpy(), index=grouped.tail(1).index, dtype=float)
    mean = weekly.rolling(weeks).mean()
    rising = mean > mean.shift(slope_weeks)
    states, on = {}, False
    for date, value in weekly.items():
        if np.isnan(mean[date]):
            continue
        if value < mean[date]:
            on = False
        elif value > mean[date] and rising[date]:
            on = True
        states[date] = on
    return pd.Series(states, dtype=bool).reindex(close.index, method="ffill").fillna(False).to_numpy(float)


def monthly_state(close: pd.Series, months: int = 10) -> np.ndarray:
    idx = np.flatnonzero(ov.month_end_mask(close.index))
    vals = close.iloc[idx]
    mean = vals.rolling(months).mean()
    state = (vals > mean).astype(float).to_numpy()
    return pd.Series(state, index=close.index[idx]).reindex(close.index, method="ffill").fillna(0.0).to_numpy()


def state_signal(state: np.ndarray, start_i: int, vectors: dict[float, tuple[float, float]] | None = None):
    state = np.asarray(state, float)
    vectors = vectors or {0.0: (0.0, 0.0), 1.0: (1.0, 0.0)}

    def sig(i, _weights):
        if i == start_i or (i > start_i and state[i] != state[i - 1]):
            return np.asarray(vectors[float(state[i])], float)
        return None

    return sig


def mtf3_signal(close: pd.Series, start_i: int, week_ma: int = 30, month_ma: int = 10,
                slope_weeks: int = 4):
    week = weekly_state(close, week_ma, slope_weeks)
    month = monthly_state(close, month_ma)
    state = np.where((week + month) >= 2.0, 1.0, np.where((week + month) >= 1.0, 0.5, 0.0))
    return state_signal(state, start_i, vectors={0.0: (0.0, 0.0), 0.5: (0.5, 0.0), 1.0: (1.0, 0.0)})


def conditional_vt_signal(close: pd.Series, start_i: int, target: float = 0.15,
                          window: int = 21, off_cap: float = 0.50, band: float = 0.10):
    log_ret = np.log(close).diff()
    vol = log_ret.rolling(window).std(ddof=1).to_numpy(float) * np.sqrt(252.0)
    raw = np.divide(target, vol, out=np.full(len(close), np.nan), where=vol > 0)
    trend = weekly_state(close)
    wanted = np.minimum(np.where(trend > 0.5, 1.0, off_cap), raw)

    def sig(i, actual):
        if np.isnan(wanted[i]):
            return None
        if i == start_i or abs(wanted[i] - actual[0]) > band:
            return np.array([wanted[i], 0.0])
        return None

    return sig


def relative_rotation_signal(qqq: pd.Series, spy: pd.Series, cash_index: pd.Series,
                             start_i: int, lookback: int = 12, sma_months: int = 10):
    """Monthly QQQ/SPY relative momentum with absolute trend and cash filters."""
    idx = np.flatnonzero(ov.month_end_mask(qqq.index))
    q_m = qqq.iloc[idx]
    s_m = spy.iloc[idx]
    c_m = cash_index.iloc[idx]
    q_ret = q_m / q_m.shift(lookback) - 1.0
    s_ret = s_m / s_m.shift(lookback) - 1.0
    c_ret = c_m / c_m.shift(lookback) - 1.0
    q_sma = q_m.rolling(sma_months).mean()
    s_sma = s_m.rolling(sma_months).mean()
    state = np.zeros(len(idx), dtype=float)
    q_on = (q_ret > s_ret) & (q_ret > c_ret) & (q_m > q_sma)
    s_on = (s_ret >= q_ret) & (s_ret > c_ret) & (s_m > s_sma)
    state[q_on.to_numpy()] = 1.0
    state[(~q_on & s_on).to_numpy()] = 2.0
    full = pd.Series(state, index=qqq.index[idx]).reindex(qqq.index, method="ffill").fillna(0.0).to_numpy()
    return state_signal(full, start_i, vectors={0.0: (0.0, 0.0), 1.0: (1.0, 0.0), 2.0: (0.0, 1.0)})


def relative_qqq_only_signal(qqq: pd.Series, spy: pd.Series, cash_index: pd.Series,
                             start_i: int, lookback: int = 12, sma_months: int = 10):
    full = relative_rotation_state(qqq, spy, cash_index, lookback, sma_months)
    # Keep the QQQ leg only; this separates relative selection from asset rotation.
    return state_signal(np.where(full == 1.0, 1.0, 0.0), start_i)


def relative_rotation_state(qqq: pd.Series, spy: pd.Series, cash_index: pd.Series,
                            lookback: int = 12, sma_months: int = 10) -> np.ndarray:
    idx = np.flatnonzero(ov.month_end_mask(qqq.index))
    q_m, s_m, c_m = qqq.iloc[idx], spy.iloc[idx], cash_index.iloc[idx]
    q_ret, s_ret, c_ret = q_m / q_m.shift(lookback) - 1.0, s_m / s_m.shift(lookback) - 1.0, c_m / c_m.shift(lookback) - 1.0
    q_sma, s_sma = q_m.rolling(sma_months).mean(), s_m.rolling(sma_months).mean()
    q_on = (q_ret > s_ret) & (q_ret > c_ret) & (q_m > q_sma)
    s_on = (s_ret >= q_ret) & (s_ret > c_ret) & (s_m > s_sma)
    state = np.zeros(len(idx), dtype=float)
    state[q_on.to_numpy()] = 1.0
    state[(~q_on & s_on).to_numpy()] = 2.0
    return pd.Series(state, index=qqq.index[idx]).reindex(qqq.index, method="ffill").fillna(0.0).to_numpy()


def build_data():
    qqq = load_qqq()
    spy, bill = load_sp500()
    dates = qqq.index.intersection(spy.index)
    qqq, spy = qqq.reindex(dates), spy.reindex(dates)
    bill = bill.reindex(dates).ffill()
    pos, neg = ov.calendar_cash_factors(dates, bill.to_numpy(float), 0.015)
    return ov.MarketData(dates, qqq, spy, pos, neg), qqq, spy, bill


def run(data, qqq, spy, cash_index, name: str, start: pd.Timestamp, cost: float = COST, params: dict | None = None):
    params = params or {}
    start_i = int(data.dates.searchsorted(start))
    prices = pd.DataFrame({"a": qqq, "b": spy}, index=data.dates)
    if name == "B0":
        sig = state_signal(np.ones(len(data.dates)), start_i)
    elif name == "SPY":
        sig = state_signal(np.ones(len(data.dates), dtype=float), start_i,
                           vectors={1.0: (0.0, 1.0)})
    elif name == "S2":
        states = pr.stage_states(qqq)
        sig = pr.rule_stage_blend(states, data.dates, start_i, on=1.0, off=0.5)
        sig = ov._dict_adapter(sig)
    elif name == "VT":
        sig = ov.vol_target_band(qqq, start_i, target=0.15, cap=1.0, window=21, band=0.10)
    elif name == "MTF-3":
        sig = mtf3_signal(qqq, start_i, **params)
    elif name == "TVT-50":
        sig = conditional_vt_signal(qqq, start_i, **params)
    elif name == "REL-12":
        sig = relative_rotation_signal(qqq, spy, cash_index, start_i, **params)
    elif name == "REL-Q":
        sig = relative_qqq_only_signal(qqq, spy, cash_index, start_i, **params)
    else:
        raise ValueError(name)
    res = ov.run_overlay(prices, sig, start_i, cost, data.cash_pos, data.cash_neg)
    m = ov.perf_metrics(res.nav, res.tbill_daily, res.weights["a"], ov.count_trades(res))
    m["avg_spy_weight"] = float(res.weights["b"].iloc[1:].mean())
    m["avg_gross_weight"] = float(res.weights.iloc[1:].sum(axis=1).mean())
    return res, m


def monthly_q5(nav: pd.Series) -> dict:
    month = nav.resample("ME").last().pct_change().dropna()
    wins, losses = month[month > 0], month[month < 0]
    return {"monthly_win_rate": float((month > 0).mean()), "avg_win_month": float(wins.mean()),
            "avg_loss_month": float(losses.mean()), "payoff_ratio": float(wins.mean() / abs(losses.mean())),
            "profit_factor": float(wins.sum() / abs(losses.sum())), "best_month": float(month.max()),
            "worst_month": float(month.min())}


def segment_rows(results):
    rows = []
    for name, (res, _) in results.items():
        for seg, (s, e) in SEGMENTS.items():
            nav = ov.segment_slice(res.nav, s, e)
            rows.append({"strategy": name, "segment": seg,
                         **ov.perf_metrics(nav, res.tbill_daily, res.weights["a"].reindex(nav.index), 0)})
    return pd.DataFrame(rows)


def drawdown_events(nav: pd.Series, n: int = 8) -> pd.DataFrame:
    dd = nav / nav.cummax() - 1.0
    events, active = [], False
    start = trough = None
    for date, value in dd.items():
        if value < 0 and not active:
            active, start, trough = True, date, date
        if active and value < dd.loc[trough]:
            trough = date
        if active and value >= 0:
            events.append({"start": start, "trough": trough, "recovery": date,
                           "depth": float(dd.loc[trough]),
                           "days_to_recovery": int((date - trough).days)})
            active = False
    if active:
        events.append({"start": start, "trough": trough, "recovery": pd.NaT,
                       "depth": float(dd.loc[trough]), "days_to_recovery": np.nan})
    return pd.DataFrame(events).sort_values("depth").head(n)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data, qqq, spy, bill = build_data()
    cash_index = pd.Series(np.cumprod(data.cash_pos), index=data.dates)
    labels = ["B0", "SPY", "S2", "VT", "MTF-3", "TVT-50", "REL-12", "REL-Q"]
    params = {name: {} for name in labels}
    params["TVT-50"] = {"target": 0.15, "off_cap": 0.50}
    params["REL-12"] = {"lookback": 12, "sma_months": 10}
    params["REL-Q"] = {"lookback": 12, "sma_months": 10}
    results = {name: run(data, qqq, spy, cash_index, name, START, params=params[name]) for name in labels}
    summary = []
    for name, (res, m) in results.items():
        summary.append({"strategy": name, **m, **monthly_q5(res.nav)})
    pd.DataFrame(summary).to_csv(OUT / "summary_q3_q5.csv", index=False)
    pd.DataFrame({k: v[0].nav for k, v in results.items()}).to_csv(OUT / "nav_daily.csv", index_label="date")
    pd.DataFrame({k: v[0].weights["a"] for k, v in results.items()}).to_csv(OUT / "qqq_weights_daily.csv", index_label="date")
    pd.DataFrame({k: v[0].weights["b"] for k, v in results.items()}).to_csv(OUT / "spy_weights_daily.csv", index_label="date")
    pd.DataFrame({k: ov.yearly_returns(v[0].nav) for k, v in results.items()}).to_csv(OUT / "yearly_returns.csv", index_label="year")
    seg = segment_rows(results)
    seg.to_csv(OUT / "segments.csv", index=False)
    pd.concat([drawdown_events(res.nav).assign(strategy=name) for name, (res, _) in results.items()],
              ignore_index=True).to_csv(OUT / "drawdown_events.csv", index=False)

    contrib = ov.contribution_dates(data.dates, START, END)
    dca_rows, windows = [], []
    for name, (res, _) in results.items():
        dca_rows.append({"strategy": name, **ov.dca_account(res.nav, contrib, END)})
    pd.DataFrame(dca_rows).to_csv(OUT / "dca_full.csv", index=False)
    for day in contrib:
        w = ov.ten_year_window(data.dates, day)
        if w is None:
            continue
        c, e = w
        plain = ov.dca_account(results["B0"][0].nav, c, e)
        for name, (res, _) in results.items():
            account = plain if name == "B0" else ov.dca_account(res.nav, c, e)
            windows.append({"strategy": name, "start": str(day.date()), "end": str(e.date()), **account,
                            "ratio_gt_plain": bool(account["ratio"] > plain["ratio"]),
                            "xirr_gt_plain": bool(account["xirr"] > plain["xirr"])})
    wf = pd.DataFrame(windows)
    wf.to_csv(OUT / "dca_windows.csv", index=False)
    dca_summary = []
    for name in labels:
        sub = wf[wf.strategy == name]
        dca_summary.append({"strategy": name, "n_windows": len(sub), "median_xirr": sub.xirr.median(),
                            "worst_xirr": sub.xirr.min(), "median_max_float_loss": sub.max_float_loss.median(),
                            "median_ratio": sub.ratio.median(), "share_ratio_gt_plain": sub.ratio_gt_plain.mean(),
                            "share_xirr_gt_plain": sub.xirr_gt_plain.mean()})
    pd.DataFrame(dca_summary).to_csv(OUT / "dca_summary.csv", index=False)

    sens = []
    for wm in (20, 30, 40):
        for mm in (8, 10, 12):
            res, m = run(data, qqq, spy, cash_index, "MTF-3", START, params={"week_ma": wm, "month_ma": mm})
            sens.append({"family": "MTF-3", "variant": f"week{wm}_month{mm}", **m})
    for lookback in (6, 9, 12):
        for sma in (8, 10, 12):
            res, m = run(data, qqq, spy, cash_index, "REL-12", START,
                         params={"lookback": lookback, "sma_months": sma})
            sens.append({"family": "REL-12", "variant": f"lookback{lookback}_sma{sma}", **m})
    for target in (0.12, 0.15, 0.18):
        for cap in (0.25, 0.50, 0.75):
            res, m = run(data, qqq, spy, cash_index, "TVT-50", START,
                         params={"target": target, "off_cap": cap})
            sens.append({"family": "TVT-50", "variant": f"target{target}_offcap{cap}", **m})
    pd.DataFrame(sens).to_csv(OUT / "sensitivity.csv", index=False)

    cost_rows = []
    for name in labels:
        _, m = run(data, qqq, spy, cash_index, name, START, cost=COST30, params=params[name])
        cost_rows.append({"strategy": name, "cost_per_side": COST30, **m})
    pd.DataFrame(cost_rows).to_csv(OUT / "cost30.csv", index=False)

    rolling = []
    for year in range(2000, 2024):
        start = data.dates[data.dates.searchsorted(pd.Timestamp(f"{year}-01-01"))]
        base = run(data, qqq, spy, cash_index, "B0", start)[1]
        for name in labels[2:]:
            m = run(data, qqq, spy, cash_index, name, start, params=params[name])[1]
            rolling.append({"strategy": name, "start": str(start.date()), "sharpe": m["sharpe"],
                            "calmar": m["calmar"], "b0_sharpe": base["sharpe"], "b0_calmar": base["calmar"],
                            "sharpe_gt_b0": m["sharpe"] > base["sharpe"],
                            "calmar_gt_b0": m["calmar"] > base["calmar"]})
    pd.DataFrame(rolling).to_csv(OUT / "rolling_starts.csv", index=False)

    # Fixed QQQ exposure controls for the single-asset strategies.
    fixed = []
    for name in ("S2", "VT", "MTF-3", "TVT-50"):
        weight = results[name][1]["avg_weight"]
        fixed_res, fixed_m = run(data, qqq, spy, cash_index, "B0", START)
        # A separate fixed-weight signal keeps the average QQQ exposure but no timing.
        i = int(data.dates.searchsorted(START))
        prices = pd.DataFrame({"a": qqq, "b": spy}, index=data.dates)
        sig = ov.fixed_weight_signal(weight, data.dates, i)
        fixed_res = ov.run_overlay(prices, sig, i, COST, data.cash_pos, data.cash_neg)
        fm = ov.perf_metrics(fixed_res.nav, fixed_res.tbill_daily, fixed_res.weights["a"], ov.count_trades(fixed_res))
        fixed.append({"strategy": f"F_{name}", "matched_weight": weight, **fm})
    pd.DataFrame(fixed).to_csv(OUT / "fixed_weight.csv", index=False)

    b0 = next(row for row in summary if row["strategy"] == "B0")
    b0seg = seg[seg.strategy == "B0"].set_index("segment")
    dca_by = pd.DataFrame(dca_summary).set_index("strategy")
    c30 = pd.DataFrame(cost_rows).set_index("strategy")
    verdicts = []
    for name in labels[2:]:
        row = next(r for r in summary if r["strategy"] == name)
        candseg = seg[seg.strategy == name].set_index("segment")
        seg_ok = True
        details = []
        for segment in SEGMENTS:
            metric_ok = (candseg.loc[segment, "sharpe"] > b0seg.loc[segment, "sharpe"] or
                         candseg.loc[segment, "calmar"] > b0seg.loc[segment, "calmar"])
            cagr_ok = candseg.loc[segment, "cagr"] >= b0seg.loc[segment, "cagr"] - 0.03
            seg_ok &= metric_ok and cagr_ok
            details.append({"segment": segment, "risk_metric_beats": bool(metric_ok), "cagr_guard": bool(cagr_ok),
                            "cagr": float(candseg.loc[segment, "cagr"]), "b0_cagr": float(b0seg.loc[segment, "cagr"])})
        main_ok = row["sharpe"] > b0["sharpe"] or row["calmar"] > b0["calmar"]
        cost_ok = c30.loc[name, "sharpe"] > c30.loc["B0", "sharpe"] or c30.loc[name, "calmar"] > c30.loc["B0", "calmar"]
        dca_ok = dca_by.loc[name, "share_ratio_gt_plain"] >= 0.60
        verdicts.append({"strategy": name, "main_sharpe_or_calmar": bool(main_ok),
                         "segments_risk_metric_and_cagr": bool(seg_ok), "cost30_sharpe_or_calmar": bool(cost_ok),
                         "dca_ratio_share_ge_60pct": bool(dca_ok), "pass_all": bool(main_ok and seg_ok and cost_ok and dca_ok),
                         "dca_ratio_share": float(dca_by.loc[name, "share_ratio_gt_plain"]),
                         "segment_detail": json.dumps(details, ensure_ascii=False)})
    pd.DataFrame(verdicts).to_csv(OUT / "verdicts.csv", index=False)

    checks = {"weights_in_range": True, "default_reproducible": True, "no_lookahead": True}
    for name, (res, _) in results.items():
        checks["weights_in_range"] &= bool((res.weights >= -1e-12).all().all() and (res.weights.sum(axis=1) <= 1.0 + 1e-12).all())
        again = run(data, qqq, spy, cash_index, name, START, params=params[name])[0]
        checks["default_reproducible"] &= bool(np.allclose(res.nav.to_numpy(), again.nav.to_numpy()))
    for cutoff in pd.to_datetime(["2005-12-30", "2010-06-30", "2018-12-31", "2024-12-31"]):
        full_i = int(data.dates.searchsorted(cutoff, side="right") - 1)
        if full_i < 1:
            continue
        # Check state builders directly; truncated history must give the same decision at the cutoff.
        for builder in (mtf3_signal, conditional_vt_signal):
            full_sig = builder(qqq, 0)
            short_sig = builder(qqq.iloc[: full_i + 1], 0)
            a, b = full_sig(full_i, np.array([0.0, 0.0])), short_sig(full_i, np.array([0.0, 0.0]))
            if a is not None and b is not None:
                checks["no_lookahead"] &= bool(np.allclose(a, b, equal_nan=True))
        full_rel = relative_rotation_signal(qqq, spy, cash_index, 0)
        short_rel = relative_rotation_signal(qqq.iloc[: full_i + 1], spy.iloc[: full_i + 1],
                                             cash_index.iloc[: full_i + 1], 0)
        a, b = full_rel(full_i, np.array([0.0, 0.0])), short_rel(full_i, np.array([0.0, 0.0]))
        if a is not None and b is not None:
            checks["no_lookahead"] &= bool(np.allclose(a, b, equal_nan=True))
    (OUT / "selfcheck.json").write_text(json.dumps(checks, indent=2, ensure_ascii=False))
    cfg = {"slug": SLUG, "window": [str(START.date()), str(END.date())], "cost_per_side": COST,
           "baseline": "QQQ buy and hold; S2 and VT-1.0 are frozen transfer baselines",
           "new_rules": {"MTF-3": "QQQ 30-week rising trend + 10-month mean: 100/50/0%",
                         "REL-12": "monthly QQQ/SPY 12-month relative momentum plus absolute trend and cash filter",
                         "REL-Q": "same relative momentum filter, QQQ or cash only",
                         "TVT-50": "15% target volatility, 50% cap when weekly trend is off"},
           "execution": "close signal, next-close fill; 10bp and 30bp cost; ^IRX cash",
           "dca": "one unit monthly, complete 10-year windows, XIRR and unit drawdown",
           "verdict": "main risk metric, both segment risk metrics with CAGR guard, cost30, and DCA ratio share"}
    (OUT / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    (OUT / "README.md").write_text("""# QQQ 新量化增强候选（2026-11-14）

本实验把旧 QQQ 半仓趋势/杠杆结果作为基线，新增多周期确认和 QQQ/SPY 相对动量轮动。数据为 QQQ、SPY 分红复权价格与 ^IRX 现金利率，信号收盘判断、下一收盘成交；主成本每边 10bp，另做 30bp 压力测试。完整结果见 `summary_q3_q5.csv`、`segments.csv`、`sensitivity.csv`、`dca_summary.csv` 和 `verdicts.csv`。

候选规则：MTF-3（周线+月线确认）、REL-12（QQQ/SPY 12个月相对动量，并要求绝对趋势为正）、REL-Q（只在 QQQ 相对强时持有 QQQ，否则现金）、TVT-50（趋势条件波动率目标）。

复现：`uv run python -I scripts/research_qqq_new_enhance_2026_11_14.py`。
""", encoding="utf-8")


if __name__ == "__main__":
    main()
