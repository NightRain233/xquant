"""Weinstein stage-2 ETF review (frozen rules, 2026-10-18).

Reads the TickFlow ``forward`` (proportional forward-adjusted) snapshot fetched by
``scripts/fetch_weinstein_etf_data.py`` and writes all result tables to
``outputs/weinstein-etf-stage-2026-10-18/``. No network access.

Run:  uv run --frozen python scripts/research_weinstein_etf_stage.py
(or, when the project venv cannot sync, ``uv run --no-project --with pandas==3.0.3
--with numpy==2.4.6`` with ``PYTHONPATH=src``).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xquant.weinstein_stage import (  # noqa: E402
    CostModel, StageParams, annual_returns, execution_dates, load_tickflow_batches, nav_metrics,
    panel, run_stage_strategy, run_target_weights, stage_signals, trade_metrics, weekly_closes,
    window_return,
)

SLUG = "weinstein-etf-stage-2026-10-18"
OUT = ROOT / "outputs" / SLUG
UNIVERSE = ROOT.parent / "trading/backend/universes/a_share_etf_core.json"
BENCH = "510300.SS"
START = "2015-01-01"  # first execution day = first trading day on/after this date
# Pool members tracking Hong Kong indices are not A-share ETFs; excluded by the frozen rule.
EXCLUDED_NON_A_SHARE = {"513010.SS": "恒生科技（港股）", "513120.SS": "港股创新药", "513910.SS": "港股通央企红利"}
BEAR_WINDOWS = [
    ("2015股灾（2015-06-08至2016-01-28）", "2015-06-08", "2016-01-28"),
    ("2018全年", "2018-01-01", "2018-12-31"),
    ("2022全年", "2022-01-01", "2022-12-31"),
    ("2021-02至2024-02长熊", "2021-02-10", "2024-02-05"),
]
MAIN = StageParams()
COSTS = CostModel()


def load_data():
    manifest = json.loads((OUT / "fetch_manifest.json").read_text())
    files = [OUT / "cache" / n for n, m in manifest["files"].items() if m["adjust"] == "forward"]
    for path in files:  # verify the raw snapshot has not changed since the fetch
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest["files"][path.name]["sha256"], path
    universe = json.loads(UNIVERSE.read_text())["symbols"]
    names = {u["symbol"]: u["name"] for u in universe}
    provider = {s.replace(".SS", ".SH"): s for s in names}
    frames = load_tickflow_batches(files, provider_to_symbol=provider)
    raw = load_tickflow_batches([OUT / "cache" / n for n, m in manifest["files"].items() if m["adjust"] == "none"],
                                provider_to_symbol=provider)
    return manifest, universe, names, frames, raw


def build(frames, symbols, params):
    calendar = frames[BENCH].index
    for s in symbols:
        extra = frames[s].index.difference(calendar)
        assert extra.empty, f"{s} has dates outside the 510300 calendar: {extra[:3]}"
    opens, closes = panel({s: frames[s] for s in symbols}, "open", calendar), panel({s: frames[s] for s in symbols}, "close", calendar)
    weekly = weekly_closes(closes)
    return opens, closes, weekly, stage_signals(weekly, BENCH, params)


def first_exec_day(calendar):
    return calendar[calendar >= pd.Timestamp(START)][0]


def benchmarks(opens, closes, weekly, sig30, start):
    calendar = closes.index
    out = {}
    out["买入持有沪深300(510300)"] = run_target_weights(opens, closes, {start: {BENCH: 1.0}}, start, COSTS)
    # equal-weight pool, rebalanced at the first trading day of each year, same eligibility as the strategy
    sched = {}
    exec_map = execution_dates(weekly.index, calendar)
    for year in range(start.year, calendar[-1].year + 1):
        day = calendar[calendar >= pd.Timestamp(f"{year}-01-01")][0]
        week = exec_map[exec_map == day].index
        week = week[0] if len(week) else weekly.index[weekly.index < day][-1]
        members = sig30.eligible.loc[week]
        members = list(members[members].index)
        sched[day] = {s: 1.0 / len(members) for s in members}
    out["ETF池等权买入持有(年度再平衡)"] = run_target_weights(opens, closes, sched, start, COSTS)
    # market filter: hold 510300 while its weekly close > 30-week SMA, otherwise cash
    above = (weekly[BENCH] > sig30.ma[BENCH]) & sig30.ma[BENCH].notna()
    sched, state = {}, None
    for week, flag in above.items():
        day = exec_map[week]
        if pd.isna(day) or day < start:
            state = bool(flag)  # state entering the backtest
            continue
        if day == start or bool(flag) != state:
            sched[day] = {BENCH: 1.0} if flag else {}
        state = bool(flag)
    out["大盘过滤(510300站上30周线持有,否则现金)"] = run_target_weights(opens, closes, sched, start, COSTS)
    return out


def summarize(name, nav_frame, trades, is_strategy):
    m = nav_metrics(nav_frame["nav"])
    row = {"strategy": name, **m, "avg_exposure": nav_frame["exposure"].mean()}
    if is_strategy:
        row.update(trade_metrics(trades, m["years"]))
    for label, a, b in BEAR_WINDOWS:
        w = window_return(nav_frame["nav"], a, b)
        row[f"{label}_收益"], row[f"{label}_区间内最大回撤"] = w["return"], w["max_drawdown"]
    return row


def self_checks(opens, closes, weekly, sig, nav, trades, fills, params):
    checks = {}
    # 1. cash + holdings == nav every day; cash never negative
    checks["cash_plus_holdings_equals_nav_max_abs_err"] = float((nav["cash"] + nav["holdings"] - nav["nav"]).abs().max())
    checks["min_cash"] = float(nav["cash"].min())
    checks["max_positions_observed"] = int(nav["positions"].max())
    # 2. every fill happens strictly after its signal week and at that day's open price
    f = fills.dropna(subset=["signal_week"])
    checks["fills_after_signal_week"] = bool((pd.to_datetime(f["date"]) > pd.to_datetime(f["signal_week"])).all())
    checks["fill_price_equals_open_x_slippage"] = bool(np.allclose(
        f["fill_price"], np.where(f["side"] == "buy", f["open"] * 1.0005, f["open"] * 0.9995)))
    checks["fill_open_matches_data"] = bool(all(abs(opens.at[pd.Timestamp(r.date), r.symbol] - r.open) < 1e-12 for r in f.itertuples()))
    checks["fills_are_next_trading_day"] = bool(all(
        closes.index[closes.index.searchsorted(pd.Timestamp(r.signal_week), side="right")] == pd.Timestamp(r.date)
        for r in f.itertuples()))
    # 3. no look-ahead: recompute signals with data truncated at a sample of weeks
    sample = weekly.index[::37]
    mismatches = 0
    for w in sample:
        trunc = stage_signals(weekly.loc[:w], BENCH, params)
        for attr in ("buy", "sell"):
            a = getattr(trunc, attr).loc[w]
            b = getattr(sig, attr).loc[w]
            mismatches += int((a != b).sum())
    checks["lookahead_truncation_weeks_tested"] = int(len(sample))
    checks["lookahead_truncation_mismatches"] = mismatches
    # 4. trades ledger reconciles with fills
    closed = trades[trades["status"] == "closed"]
    checks["closed_trades"] = int(len(closed))
    checks["sell_fills"] = int((fills["side"] == "sell").sum())
    checks["passed"] = (checks["cash_plus_holdings_equals_nav_max_abs_err"] < 1e-9 and checks["min_cash"] > -1e-9
                        and checks["max_positions_observed"] <= params.max_positions and checks["fills_after_signal_week"]
                        and checks["fill_price_equals_open_x_slippage"] and checks["fill_open_matches_data"]
                        and checks["fills_are_next_trading_day"] and mismatches == 0
                        and checks["closed_trades"] == checks["sell_fills"])
    return checks


def main():
    manifest, universe, names, frames, raw = load_data()
    symbols = [u["symbol"] for u in universe if u["symbol"] not in EXCLUDED_NON_A_SHARE]
    opens, closes, weekly, sig = build(frames, symbols, MAIN)
    start = first_exec_day(closes.index)

    # ---- data manifest
    rows = []
    file_of = {s: n for n, m in manifest["files"].items() if m["adjust"] == "forward" for s in m["symbols"]}
    for u in universe:
        s = u["symbol"]
        f = frames[s]
        elig = sig.eligible[s][sig.eligible[s]].index if s in sig.eligible else []
        div_days = int(((f["close"].pct_change() - raw[s]["close"].reindex(f.index).pct_change()).abs() > 1e-4).sum())
        rows.append({"symbol": s, "name": u["name"], "bucket": u["bucket"],
                     "included": s not in EXCLUDED_NON_A_SHARE, "exclusion_reason": EXCLUDED_NON_A_SHARE.get(s, ""),
                     "first_date": f.index[0].date(), "last_date": f.index[-1].date(), "rows": len(f),
                     "first_signal_week": elig[0].date() if len(elig) else None,
                     "adjustment_event_days": div_days, "source_file": file_of[s],
                     "source_sha256": manifest["files"][file_of[s]]["sha256"]})
    pd.DataFrame(rows).to_csv(OUT / "data_manifest.csv", index=False)

    # ---- main strategy + benchmarks
    nav, trades, fills = run_stage_strategy(opens, closes, sig, start, MAIN, COSTS)
    results = {"温斯坦阶段2策略(30周,主结果)": (nav, trades)}
    for name, (bnav, btr, _) in benchmarks(opens, closes, weekly, sig, start).items():
        results[name] = (bnav, btr)
    summary = pd.DataFrame([summarize(n, r[0], r[1], i == 0 or n.startswith("大盘过滤"))
                            for i, (n, r) in enumerate(results.items())])
    summary.to_csv(OUT / "research_summary.csv", index=False)
    annual = pd.DataFrame({n: annual_returns(r[0]["nav"]) for n, r in results.items()})
    annual.index.name = "year"
    annual.to_csv(OUT / "annual_returns.csv")
    pd.DataFrame({n: r[0]["nav"] for n, r in results.items()}).assign(
        策略敞口=nav["exposure"], 策略持仓数=nav["positions"]).to_csv(OUT / "nav_daily.csv")
    trades.assign(name=trades["symbol"].map(names)).to_csv(OUT / "trades.csv", index=False)
    fills.to_csv(OUT / "fills.csv", index=False)
    bear = summary.set_index("strategy")[[c for c in summary.columns if "_收益" in c or "区间内最大回撤" in c]].T
    bear.to_csv(OUT / "bear_windows.csv")

    # per-year strategy activity
    t = trades.copy()
    t["entry_year"] = pd.to_datetime(t["entry_date"]).dt.year
    activity = t.groupby("entry_year").agg(new_trades=("symbol", "size"), win_rate=("return", lambda r: (r > 0).mean()),
                                           avg_return=("return", "mean"))
    activity["avg_exposure"] = nav["exposure"].groupby(nav.index.year).mean()
    activity.to_csv(OUT / "strategy_yearly_activity.csv")

    # ---- sensitivity (diagnostic only; never used to pick parameters)
    sens = []
    grid = [(ma, 5) for ma in (20, 26, 30, 40)] + [(30, 3), (30, 8)]
    for ma, n in grid:
        p = StageParams(ma_weeks=ma, max_positions=n, slot_weight=1.0 / n)
        s_sig = stage_signals(weekly, BENCH, p)
        snav, stra, _ = run_stage_strategy(opens, closes, s_sig, start, p, COSTS)
        sens.append({"ma_weeks": ma, "max_positions": n, "slot_weight": 1.0 / n,
                     **summarize(f"MA{ma}/最多{n}只", snav, stra, True)})
        if (ma, n) == (20, 5):
            stra.assign(name=stra["symbol"].map(names)).to_csv(OUT / "trades_ma20.csv", index=False)
            annual["温斯坦(20周,敏感性)"] = annual_returns(snav["nav"])
    double = CostModel(fee_rate=0.001, slippage=0.001)
    dnav, dtra, _ = run_stage_strategy(opens, closes, sig, start, MAIN, double)
    sens.append({"ma_weeks": 30, "max_positions": 5, "slot_weight": 0.2,
                 **summarize("MA30/最多5只/成本翻倍(单边20bp)", dnav, dtra, True)})
    pd.DataFrame(sens).to_csv(OUT / "sensitivity.csv", index=False)
    annual.to_csv(OUT / "annual_returns.csv")

    # ---- latest signal (as of the last completed week)
    last = weekly.index[-1]
    latest = pd.DataFrame({"name": pd.Series(names), "weekly_close": sig.close.loc[last], "ma30": sig.ma.loc[last],
                           "ma30_rising": sig.rising.loc[last], "rs26_vs_510300": sig.rs.loc[last],
                           "buy_condition": sig.buy.loc[last], "sell_condition": sig.sell.loc[last]}).loc[symbols]
    latest["held_in_backtest"] = latest.index.isin(trades.loc[trades["status"] == "open", "symbol"])
    latest.insert(0, "signal_week", last.date())
    latest.sort_values("rs26_vs_510300", ascending=False).to_csv(OUT / "latest_signal.csv")

    checks = self_checks(opens, closes, weekly, sig, nav, trades, fills, MAIN)
    (OUT / "self_checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n")
    config = {"slug": SLUG, "benchmark": BENCH, "first_execution_day": start.date().isoformat(),
              "last_data_day": closes.index[-1].date().isoformat(), "params": MAIN.__dict__, "costs": COSTS.__dict__,
              "universe_file": "trading/backend/universes/a_share_etf_core.json",
              "universe_sha256": manifest["universe_sha256"], "excluded_non_a_share": EXCLUDED_NON_A_SHARE,
              "price_adjustment": "TickFlow adjust=forward (proportional forward adjustment, dividends reinvested)",
              "cash_return": 0.0, "bear_windows": BEAR_WINDOWS, "sensitivity_grid": grid}
    (OUT / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2, default=str) + "\n")
    pd.set_option("display.width", 250)
    print(summary.set_index("strategy")[["cagr", "max_drawdown", "longest_recovery_days", "annual_volatility",
                                          "win_rate", "round_trips_per_year", "avg_exposure"]].round(4))
    print(pd.DataFrame(sens).set_index("strategy")[["cagr", "max_drawdown", "win_rate", "payoff_ratio",
                                                     "round_trips_per_year", "avg_holding_weeks", "avg_exposure"]].round(4))
    print(json.dumps(checks, indent=1))


if __name__ == "__main__":
    main()
