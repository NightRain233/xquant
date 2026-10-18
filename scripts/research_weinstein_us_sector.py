"""Weinstein stage-2 review on the 11 SPDR US sector ETFs (frozen rules, 2026-10-18).

Same rules and engine as the A-share review (``research_weinstein_etf_stage.py``,
``xquant.weinstein_stage``); only data (yfinance, auto_adjust=True) and the
benchmark (SPY) change. Reads the snapshot written by
``scripts/fetch_weinstein_us_sector_data.py`` (SHA256-verified, no network) and
writes all tables to ``outputs/weinstein-us-sector-2026-10-18/``.

Run:
  PYTHONPATH=src uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 \
      python scripts/research_weinstein_us_sector.py
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
    CostModel, StageParams, annual_returns, cash_growth_from_yield, execution_dates, load_yfinance_csv,
    nav_metrics, panel, run_stage_strategy, run_target_weights, stage_signals, trade_metrics, weekly_closes,
    window_return,
)

SLUG = "weinstein-us-sector-2026-10-18"
OUT = ROOT / "outputs" / SLUG
A_SHARE_OUT = ROOT / "outputs" / "weinstein-etf-stage-2026-10-18"
BENCH = "SPY"
SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "XLRE", "XLC"]
ORIGINAL_NINE = SECTORS[:9]
NAMES = {"SPY": "标普500", "XLB": "原材料", "XLE": "能源", "XLF": "金融", "XLI": "工业", "XLK": "科技",
         "XLP": "必需消费", "XLU": "公用事业", "XLV": "医疗", "XLY": "可选消费", "XLRE": "房地产", "XLC": "通信服务"}
WINDOWS = [
    ("2000-2002科网熊市", "2000-01-01", "2002-12-31"),
    ("2007-10至2009-03金融危机", "2007-10-09", "2009-03-09"),
    ("2008全年", "2008-01-01", "2008-12-31"),
    ("2010-2021牛市", "2010-01-01", "2021-12-31"),
    ("2020疫情急跌(02-19至03-23)", "2020-02-19", "2020-03-23"),
    ("2020全年", "2020-01-01", "2020-12-31"),
    ("2022全年", "2022-01-01", "2022-12-31"),
]
MAIN = StageParams()
COSTS = CostModel()
S30 = "温斯坦阶段2策略(30周,主结果)"
S20 = "温斯坦(20周,敏感性)"
B_SPY = "买入持有SPY"
B_EW = "11行业ETF等权买入持有(年度再平衡)"
B_FILTER = "大盘过滤(SPY站上30周线持有,否则现金)"


def load_data():
    manifest = json.loads((OUT / "fetch_manifest.json").read_text())
    frames, raws = {}, {}
    for name, meta in manifest["files"].items():
        path = OUT / "cache" / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == meta["sha256"], f"snapshot changed: {path}"
        frames[meta["ticker"]] = load_yfinance_csv(path)
        raws[meta["ticker"]] = pd.read_csv(path)
    irx_raw = raws.pop("^IRX")
    irx = pd.Series(irx_raw["Close"].to_numpy(float), index=pd.DatetimeIndex([pd.Timestamp(d[:10]) for d in irx_raw["Date"]]))
    frames.pop("^IRX")
    return manifest, frames, raws, irx.sort_index()


def build(frames, params):
    calendar = frames[BENCH].index
    symbols = [BENCH, *SECTORS]
    for s in SECTORS:
        extra = frames[s].index.difference(calendar)
        assert extra.empty, f"{s} has dates outside the SPY calendar: {extra[:3]}"
    opens = panel({s: frames[s] for s in symbols}, "open", calendar)
    closes = panel({s: frames[s] for s in symbols}, "close", calendar)
    weekly = weekly_closes(closes)
    return opens, closes, weekly, signals_for(weekly, params)


def signals_for(weekly, params):
    sig = stage_signals(weekly, BENCH, params)
    # SPY is only the relative-strength yardstick, never a candidate (its RS is 0, so buy is already False).
    assert not sig.buy[BENCH].any()
    sig.buy[BENCH] = False
    return sig


def first_exec_day(weekly, sig, calendar):
    """First trading day after the first week where all nine 1998 sector ETFs have full signal history."""
    ready = sig.eligible[ORIGINAL_NINE].all(axis=1)
    week = ready[ready].index[0]
    return execution_dates(pd.DatetimeIndex([week]), calendar).iloc[0], week


def benchmarks(opens, closes, weekly, sig30, start, cash_growth=None):
    calendar = closes.index
    out = {}
    out[B_SPY] = run_target_weights(opens, closes, {start: {BENCH: 1.0}}, start, COSTS, cash_growth)
    # equal-weight sector pool, rebalanced on the first trading day of each year; a fund joins once it has
    # the same 30-week signal history the strategy needs (identical to the A-share review)
    sched = {start: None}
    exec_map = execution_dates(weekly.index, calendar)
    days = [start] + [calendar[calendar >= pd.Timestamp(f"{y}-01-01")][0] for y in range(start.year + 1, calendar[-1].year + 1)]
    for day in days:
        week = exec_map[exec_map == day].index
        week = week[0] if len(week) else weekly.index[weekly.index < day][-1]
        members = sig30.eligible.loc[week, SECTORS]
        members = list(members[members].index)
        sched[day] = {s: 1.0 / len(members) for s in members}
    out[B_EW] = run_target_weights(opens, closes, sched, start, COSTS, cash_growth)
    above = (weekly[BENCH] > sig30.ma[BENCH]) & sig30.ma[BENCH].notna()
    sched, state = {}, None
    for week, flag in above.items():
        day = exec_map[week]
        if pd.isna(day) or day < start:
            state = bool(flag)
            continue
        if day == start or bool(flag) != state:
            sched[day] = {BENCH: 1.0} if flag else {}
        state = bool(flag)
    if start not in sched:  # state entering the backtest
        sched[start] = {BENCH: 1.0} if state else {}
    out[B_FILTER] = run_target_weights(opens, closes, sched, start, COSTS, cash_growth)
    return out


def window_cagr(nav, start, end):
    w = window_return(nav, start, end)
    seg = nav[(nav.index >= pd.Timestamp(start)) & (nav.index <= pd.Timestamp(end))]
    years = ((seg.index[-1] - pd.Timestamp(start)).days + 1) / 365.25
    return (1 + w["return"]) ** (1 / years) - 1


def summarize(name, nav_frame, trades, is_strategy):
    m = nav_metrics(nav_frame["nav"])
    row = {"strategy": name, **m, "avg_exposure": nav_frame["exposure"].mean()}
    if is_strategy:
        row.update(trade_metrics(trades, m["years"]))
    for label, a, b in WINDOWS:
        w = window_return(nav_frame["nav"], a, b)
        row[f"{label}_收益"], row[f"{label}_区间内最大回撤"] = w["return"], w["max_drawdown"]
    row["2010-2021牛市_年化"] = window_cagr(nav_frame["nav"], "2010-01-01", "2021-12-31")
    return row


def self_checks(opens, closes, weekly, sig, nav, trades, fills, params, start, nav_cash):
    checks = {}
    checks["cash_plus_holdings_equals_nav_max_abs_err"] = float((nav["cash"] + nav["holdings"] - nav["nav"]).abs().max())
    checks["min_cash"] = float(nav["cash"].min())
    checks["max_positions_observed"] = int(nav["positions"].max())
    checks["spy_never_traded"] = bool((fills["symbol"] != BENCH).all())
    f = fills.dropna(subset=["signal_week"])
    checks["fills_after_signal_week"] = bool((pd.to_datetime(f["date"]) > pd.to_datetime(f["signal_week"])).all())
    checks["fill_price_equals_open_x_slippage"] = bool(np.allclose(
        f["fill_price"], np.where(f["side"] == "buy", f["open"] * (1 + COSTS.slippage), f["open"] * (1 - COSTS.slippage))))
    checks["fill_open_matches_data"] = bool(all(abs(opens.at[pd.Timestamp(r.date), r.symbol] - r.open) < 1e-12
                                                for r in f.itertuples()))
    checks["fills_are_next_trading_day"] = bool(all(
        closes.index[closes.index.searchsorted(pd.Timestamp(r.signal_week), side="right")] == pd.Timestamp(r.date)
        for r in f.itertuples()))
    checks["no_fill_before_start"] = bool((pd.to_datetime(fills["date"]) >= start).all())
    sample = weekly.index[::37]
    mismatches = 0
    for w in sample:
        trunc = signals_for(weekly.loc[:w], params)
        for attr in ("buy", "sell"):
            mismatches += int((getattr(trunc, attr).loc[w] != getattr(sig, attr).loc[w]).sum())
    checks["lookahead_truncation_weeks_tested"] = int(len(sample))
    checks["lookahead_truncation_mismatches"] = mismatches
    closed = trades[trades["status"] == "closed"]
    checks["closed_trades"] = int(len(closed))
    checks["sell_fills"] = int((fills["side"] == "sell").sum())
    checks["tbill_run_cash_plus_holdings_equals_nav_max_abs_err"] = float(
        (nav_cash["cash"] + nav_cash["holdings"] - nav_cash["nav"]).abs().max())
    checks["passed"] = (checks["cash_plus_holdings_equals_nav_max_abs_err"] < 1e-9 and checks["min_cash"] > -1e-9
                        and checks["max_positions_observed"] <= params.max_positions and checks["spy_never_traded"]
                        and checks["fills_after_signal_week"] and checks["fill_price_equals_open_x_slippage"]
                        and checks["fill_open_matches_data"] and checks["fills_are_next_trading_day"]
                        and checks["no_fill_before_start"] and mismatches == 0
                        and checks["closed_trades"] == checks["sell_fills"]
                        and checks["tbill_run_cash_plus_holdings_equals_nav_max_abs_err"] < 1e-9)
    return checks


def a_share_comparison(us_summary):
    """US vs A-share: gap of each strategy vs its own buy-and-hold benchmark, plus trade statistics."""
    a = pd.read_csv(A_SHARE_OUT / "research_summary.csv").set_index("strategy")
    a_sens = pd.read_csv(A_SHARE_OUT / "sensitivity.csv").set_index("strategy")
    us = us_summary.set_index("strategy")
    rows = []

    def row(market, label, strat, bh, ew, bh_name):
        rows.append({"市场": market, "版本": label, "区间": f"{strat['start']}~{strat['end']}", "策略年化": strat["cagr"],
                     "买入持有基准": bh_name, "基准年化": bh["cagr"], "相对买入持有差距(年化,百分点)": strat["cagr"] - bh["cagr"],
                     "相对池子等权差距(年化,百分点)": strat["cagr"] - ew["cagr"],
                     "策略最大回撤": strat["max_drawdown"], "基准最大回撤": bh["max_drawdown"],
                     "胜率": strat["win_rate"], "盈亏比(平均盈利/平均亏损)": strat["payoff_ratio"],
                     "年均交易次数(平仓笔数)": strat["round_trips_per_year"], "平均敞口": strat["avg_exposure"]})

    a_bh, a_ew = a.loc["买入持有沪深300(510300)"], a.loc["ETF池等权买入持有(年度再平衡)"]
    row("A股", "30周(主结果)", a.loc["温斯坦阶段2策略(30周,主结果)"], a_bh, a_ew, "沪深300ETF")
    row("A股", "20周(敏感性)", a_sens.loc["MA20/最多5只"], a_bh, a_ew, "沪深300ETF")
    row("美股", "30周(主结果)", us.loc[S30], us.loc[B_SPY], us.loc[B_EW], "SPY")
    row("美股", "20周(敏感性)", us.loc[S20], us.loc[B_SPY], us.loc[B_EW], "SPY")
    return pd.DataFrame(rows)


def main():
    manifest, frames, raws, irx = load_data()
    opens, closes, weekly, sig = build(frames, MAIN)
    calendar = closes.index
    start, ready_week = first_exec_day(weekly, sig, calendar)
    growth = cash_growth_from_yield(irx, calendar)

    # ---- data manifest
    rows = []
    file_of = {m["ticker"]: n for n, m in manifest["files"].items()}
    for s in [BENCH, *SECTORS, "^IRX"]:
        name = file_of[s]
        raw = raws.get(s)
        f = frames.get(s)
        elig = sig.eligible[s][sig.eligible[s]].index if s in sig.eligible else []
        rows.append({"symbol": s, "name": NAMES.get(s, "13周美国国债收益率(%),仅现金敏感性"),
                     "role": "benchmark" if s == BENCH else ("cash_yield" if s == "^IRX" else "pool"),
                     "first_date": manifest["files"][name]["first"], "last_date": manifest["files"][name]["last"],
                     "rows": manifest["files"][name]["rows"],
                     "first_signal_week": elig[0].date() if len(elig) else None,
                     "dividend_events": int((raw["Dividends"] > 0).sum()) if raw is not None else None,
                     "split_or_spinoff_events": int((raw["Stock Splits"] > 0).sum()) if raw is not None else None,
                     "source_file": name, "source_sha256": manifest["files"][name]["sha256"]})
        if f is not None:
            assert (f[["open", "close"]] > 0).all().all(), s
    pd.DataFrame(rows).to_csv(OUT / "data_manifest.csv", index=False)

    # ---- main strategy, 20-week sensitivity, benchmarks
    nav, trades, fills = run_stage_strategy(opens, closes, sig, start, MAIN, COSTS)
    p20 = StageParams(ma_weeks=20)
    sig20 = signals_for(weekly, p20)
    nav20, trades20, _ = run_stage_strategy(opens, closes, sig20, start, p20, COSTS)
    results = {S30: (nav, trades), S20: (nav20, trades20)}
    for name, (bnav, btr, _) in benchmarks(opens, closes, weekly, sig, start).items():
        results[name] = (bnav, btr)
    strat_like = {S30, S20, B_FILTER}
    summary = pd.DataFrame([summarize(n, r[0], r[1], n in strat_like) for n, r in results.items()])
    summary.to_csv(OUT / "research_summary.csv", index=False)
    annual = pd.DataFrame({n: annual_returns(r[0]["nav"]) for n, r in results.items()})
    annual.index.name = "year"
    annual.to_csv(OUT / "annual_returns.csv")
    pd.DataFrame({n: r[0]["nav"] for n, r in results.items()}).assign(
        策略敞口=nav["exposure"], 策略持仓数=nav["positions"]).to_csv(OUT / "nav_daily.csv")
    trades.assign(name=trades["symbol"].map(NAMES)).to_csv(OUT / "trades.csv", index=False)
    trades20.assign(name=trades20["symbol"].map(NAMES)).to_csv(OUT / "trades_ma20.csv", index=False)
    fills.to_csv(OUT / "fills.csv", index=False)
    windows = summary.set_index("strategy")[[c for c in summary.columns if c.endswith("_收益") or "区间内最大回撤" in c
                                             or c.endswith("_年化")]].T
    windows.to_csv(OUT / "period_windows.csv")

    t = trades.copy()
    t["entry_year"] = pd.to_datetime(t["entry_date"]).dt.year
    activity = t.groupby("entry_year").agg(new_trades=("symbol", "size"), win_rate=("return", lambda r: (r > 0).mean()),
                                           avg_return=("return", "mean"))
    activity["avg_exposure"] = nav["exposure"].groupby(nav.index.year).mean()
    activity.to_csv(OUT / "strategy_yearly_activity.csv")
    by_symbol = trades.groupby("symbol").agg(trades=("return", "size"), win_rate=("return", lambda r: (r > 0).mean()),
                                             avg_return=("return", "mean"), avg_holding_weeks=("holding_weeks", "mean"),
                                             pnl=("received", "sum"))
    by_symbol["pnl"] = by_symbol["pnl"] - trades.groupby("symbol")["spent"].sum()
    by_symbol.assign(name=by_symbol.index.map(NAMES)).sort_values("pnl", ascending=False).to_csv(OUT / "trades_by_symbol.csv")

    # ---- parameter sensitivity (diagnostic only; never used to pick parameters)
    sens = []
    grid = [(ma, 5) for ma in (20, 26, 30, 40)] + [(30, 3), (30, 8)]
    for ma, n in grid:
        p = StageParams(ma_weeks=ma, max_positions=n, slot_weight=1.0 / n)
        snav, stra, _ = run_stage_strategy(opens, closes, signals_for(weekly, p), start, p, COSTS)
        sens.append({"ma_weeks": ma, "max_positions": n, "slot_weight": 1.0 / n, **summarize(f"MA{ma}/最多{n}只", snav, stra, True)})
    dnav, dtra, _ = run_stage_strategy(opens, closes, sig, start, MAIN, CostModel(fee_rate=0.001, slippage=0.001))
    sens.append({"ma_weeks": 30, "max_positions": 5, "slot_weight": 0.2,
                 **summarize("MA30/最多5只/成本翻倍(单边20bp)", dnav, dtra, True)})
    pd.DataFrame(sens).to_csv(OUT / "sensitivity.csv", index=False)

    # ---- cash-yield sensitivity: idle cash earns the 13-week T-bill yield (^IRX)
    cash_rows, cash_annual = [], {}
    nav_c, tr_c, _ = run_stage_strategy(opens, closes, sig, start, MAIN, COSTS, cash_growth=growth)
    nav20_c, tr20_c, _ = run_stage_strategy(opens, closes, sig20, start, p20, COSTS, cash_growth=growth)
    bench_c = benchmarks(opens, closes, weekly, sig, start, cash_growth=growth)
    for name, (n_, t_) in {S30: (nav_c, tr_c), S20: (nav20_c, tr20_c), B_FILTER: bench_c[B_FILTER][:2],
                           B_SPY: bench_c[B_SPY][:2], B_EW: bench_c[B_EW][:2]}.items():
        r = summarize(name + "+现金按国债", n_, t_, name in strat_like)
        r["cagr_cash_0"] = summary.set_index("strategy").loc[name, "cagr"]
        r["cagr_uplift"] = r["cagr"] - r["cagr_cash_0"]
        cash_rows.append(r)
        cash_annual[name + "+现金按国债"] = annual_returns(n_["nav"])
    cash_annual["13周国债年均收益率(%)"] = irx.groupby(irx.index.year).mean() / 100
    pd.DataFrame(cash_rows).to_csv(OUT / "cash_tbill_sensitivity.csv", index=False)
    ca = pd.DataFrame(cash_annual)
    ca.index.name = "year"
    ca.loc[ca.index >= start.year].to_csv(OUT / "cash_tbill_annual_returns.csv")

    # ---- US vs A-share
    comp = a_share_comparison(summary)
    comp.to_csv(OUT / "us_vs_a_share.csv", index=False)

    # ---- latest signal (as of the last completed week)
    last = weekly.index[-1]
    latest = pd.DataFrame({"name": pd.Series(NAMES), "weekly_close": sig.close.loc[last], "ma30": sig.ma.loc[last],
                           "ma30_rising": sig.rising.loc[last], "rs26_vs_spy": sig.rs.loc[last],
                           "buy_condition": sig.buy.loc[last], "sell_condition": sig.sell.loc[last]}).loc[SECTORS]
    latest["held_in_backtest"] = latest.index.isin(trades.loc[trades["status"] == "open", "symbol"])
    latest.insert(0, "signal_week", last.date())
    latest.sort_values("rs26_vs_spy", ascending=False).to_csv(OUT / "latest_signal.csv")

    checks = self_checks(opens, closes, weekly, sig, nav, trades, fills, MAIN, start, nav_c)
    (OUT / "self_checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n")
    config = {"slug": SLUG, "benchmark": BENCH, "pool": SECTORS, "names": NAMES,
              "first_signal_week_all_nine_ready": ready_week.date().isoformat(),
              "first_execution_day": start.date().isoformat(), "last_data_day": calendar[-1].date().isoformat(),
              "last_signal_week": last.date().isoformat(), "params": MAIN.__dict__, "costs": COSTS.__dict__,
              "price_adjustment": "yfinance Ticker.history(auto_adjust=True): Open/Close adjusted for splits and "
                                  "dividends (dividends reinvested); exchange-local dates",
              "yfinance_version": manifest["yfinance_version"], "cash_return_main": 0.0,
              "cash_return_sensitivity": "^IRX close of the previous trading day, (1+y)^(calendar days/365), floored at 0",
              "windows": WINDOWS, "sensitivity_grid": grid,
              "equal_weight_membership": "fund joins at the first annual rebalance after it has 34 weeks of history "
                                         "(same eligibility as strategy signals; identical to the A-share review)",
              "a_share_reference": "outputs/weinstein-etf-stage-2026-10-18 (read only)"}
    (OUT / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2, default=str) + "\n")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    print("start", start.date(), "ready week", ready_week.date(), "last week", last.date())
    print(summary.set_index("strategy")[["cagr", "max_drawdown", "longest_recovery_days", "annual_volatility", "win_rate",
                                          "payoff_ratio", "round_trips_per_year", "avg_holding_weeks", "avg_exposure"]].round(4))
    print(windows.round(4))
    print(pd.DataFrame(sens).set_index("strategy")[["cagr", "max_drawdown", "win_rate", "payoff_ratio",
                                                     "round_trips_per_year", "avg_holding_weeks", "avg_exposure"]].round(4))
    print(pd.DataFrame(cash_rows).set_index("strategy")[["cagr", "cagr_cash_0", "cagr_uplift", "max_drawdown"]].round(4))
    print(comp.round(4).to_string())
    print(json.dumps(checks, indent=1))


if __name__ == "__main__":
    main()
