#!/usr/bin/env python3
"""Audit long-sample exit timing and legacy-vs-corrected universe eligibility."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from xquant.point_in_time_universe import (  # noqa: E402
    UniverseConfig,
    filter_entries_by_membership,
)
from xquant.signal_portfolio import (  # noqa: E402
    PortfolioConfig,
    decision_entries,
    performance_metrics,
    run_signal_portfolio,
)


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.sort_index().copy()
    result.index = pd.DatetimeIndex(result.index).tz_localize(None).normalize()
    return result[~result.index.duplicated(keep="last")]


def _legacy_snapshot(
    prices: dict[str, pd.DataFrame],
    market_by_symbol: dict[str, str],
    calendars: dict[str, pd.DatetimeIndex],
    symbol_calendars: dict[str, pd.DatetimeIndex],
    snapshot_date: pd.Timestamp,
    effective_date: pd.Timestamp,
    config: UniverseConfig,
) -> pd.DataFrame:
    """Reproduce the pre-audit Close-only observed-session convention."""
    required = ["Open", "High", "Low", "Close", "Volume"]
    rows = []
    for symbol, raw in prices.items():
        market = market_by_symbol[symbol]
        history = _normalize(raw).loc[:snapshot_date]
        valid_ohlc = history.reindex(columns=required[:4]).notna().all(axis=1)
        history_sessions = int(valid_ohlc.sum())
        calendar = symbol_calendars.get(symbol, calendars.get(market, history.index))
        calendar = pd.DatetimeIndex(calendar)
        trailing_calendar = calendar[calendar <= snapshot_date][-config.liquidity_lookback_sessions:]
        trailing = history.reindex(trailing_calendar)
        expected = len(trailing_calendar)
        observed = int(trailing["Close"].notna().sum())
        suspension = 1.0 - observed / expected if expected else 1.0
        completeness = (
            float(trailing.reindex(columns=required).notna().mean().mean())
            if expected else 0.0
        )
        turnover = (
            pd.to_numeric(trailing.get("Close"), errors="coerce")
            * pd.to_numeric(trailing.get("Volume"), errors="coerce")
            * float(config.turnover_multipliers.get(symbol, 1.0))
        )
        median_turnover = float(turnover.median()) if turnover.notna().any() else np.nan
        floor = float(config.liquidity_floors.get(market, np.inf))
        reasons = []
        if symbol in config.excluded_symbols:
            reasons.append("excluded_non_tradable")
        if history_sessions < config.min_history_sessions:
            reasons.append("insufficient_history")
        if expected < config.liquidity_lookback_sessions:
            reasons.append("insufficient_calendar_history")
        if not np.isfinite(median_turnover) or median_turnover < floor:
            reasons.append("below_liquidity_floor")
        if suspension > config.max_suspension_rate:
            reasons.append("excess_suspension_rate")
        if completeness < config.min_data_completeness:
            reasons.append("incomplete_data")
        rows.append({
            "snapshotDate": snapshot_date, "effectiveDate": effective_date,
            "symbol": symbol, "market": market, "qualified": not reasons,
            "medianTradedValue": median_turnover, "selected": False,
        })
    result = pd.DataFrame(rows)
    for market, group in result[result["qualified"]].groupby("market"):
        ranked = group.sort_values(["medianTradedValue", "symbol"], ascending=[False, True])
        result.loc[ranked.index[:int(config.market_caps.get(market, 0))], "selected"] = True
    return result


def _valid_open(value: object) -> bool:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return bool(pd.notna(number) and np.isfinite(number) and number > 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--candidate-catalog", type=Path, required=True)
    parser.add_argument("--price-data-dir", type=Path, required=True)
    parser.add_argument("--membership", type=Path, required=True)
    parser.add_argument("--trades", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default="2026-07-10")
    args = parser.parse_args()

    start, end = pd.Timestamp(args.start), pd.Timestamp(args.end)
    symbols = json.loads(args.candidate_catalog.read_text())["symbols"]
    prices = {
        symbol: pd.read_parquet(args.price_data_dir / f"{symbol}.parquet")
        for symbol in symbols
    }
    corrected = pd.read_csv(args.membership, parse_dates=["snapshotDate", "effectiveDate"])
    corrected = corrected[corrected["universe"].eq("rolling_monthly_pit")].copy()
    market_by_symbol = corrected.groupby("symbol")["market"].last().to_dict()
    references = {
        "a_share": pd.DatetimeIndex(prices["510300.SS"].index).tz_localize(None).normalize(),
        "hong_kong": pd.DatetimeIndex(prices["2800.HK"].index).tz_localize(None).normalize(),
        "us": pd.DatetimeIndex(prices["SPY"].index).tz_localize(None).normalize(),
        "crypto": pd.DatetimeIndex(prices["BTC-USD"].index).tz_localize(None).normalize(),
        "gold": pd.DatetimeIndex(prices["GC=F"].index).tz_localize(None).normalize(),
    }
    symbol_calendars = {}
    for symbol in symbols:
        if symbol.endswith((".SS", ".SZ")):
            symbol_calendars[symbol] = references["a_share"]
        elif symbol.endswith(".HK"):
            symbol_calendars[symbol] = references["hong_kong"]
        elif market_by_symbol[symbol] == "crypto":
            symbol_calendars[symbol] = references["crypto"]
        elif symbol == "GC=F":
            symbol_calendars[symbol] = references["gold"]
        else:
            symbol_calendars[symbol] = references["us"]
    universe_config = UniverseConfig(
        turnover_multipliers={"GC=F": 100.0},
        excluded_symbols=frozenset({"000001.SS", "000300.SS"}),
    )
    legacy_frames = []
    schedule = corrected[["snapshotDate", "effectiveDate"]].drop_duplicates()
    for row in schedule.itertuples(index=False):
        legacy_frames.append(_legacy_snapshot(
            prices, market_by_symbol, references, symbol_calendars,
            row.snapshotDate, row.effectiveDate, universe_config,
        ))
    legacy = pd.concat(legacy_frames, ignore_index=True)

    selection = corrected[["effectiveDate", "symbol", "selected"]].merge(
        legacy[["effectiveDate", "symbol", "selected"]],
        on=["effectiveDate", "symbol"], suffixes=("Corrected", "Legacy"),
    )
    changes = selection[selection["selectedCorrected"] != selection["selectedLegacy"]]

    decisions = pd.read_parquet(args.decisions)
    decisions["market"] = decisions["symbol"].map(market_by_symbol)
    policy_entries = decision_entries(decisions, "all_bull_flip")
    config = PortfolioConfig(
        initial_capital=1_000_000.0, commission_bps=5.0, slippage_bps=5.0,
        max_position_weight=0.10, max_concurrent_positions=10,
        max_gross_exposure=1.0,
    )
    results = {}
    for convention, membership in (("legacy_close_only", legacy), ("corrected_tradable", corrected)):
        entries = filter_entries_by_membership(policy_entries, membership)
        result = run_signal_portfolio(entries, prices, start=start, end=end, config=config)
        results[convention] = {
            "candidateSignals": len(entries),
            **performance_metrics(result["nav"], result["trades"]),
        }

    trades = pd.read_csv(args.trades, parse_dates=["entryDate", "exitDate"])
    trades = trades[trades["strategy"].eq("policy_bull_flip_rolling_pit")]
    exit_checks = []
    for trade in trades.itertuples():
        frame = _normalize(prices[trade.symbol]).loc[trade.entryDate:trade.exitDate]
        bear_dates = frame.index[pd.to_numeric(frame["ST_Dir"], errors="coerce") < 0]
        bear_date = pd.Timestamp(bear_dates[0])
        later = _normalize(prices[trade.symbol]).loc[bear_date + pd.Timedelta(days=1):end]
        next_listed = pd.Timestamp(later.index[0]) if not later.empty else pd.NaT
        valid_dates = later.index[later["Open"].map(_valid_open)]
        expected_exit = pd.Timestamp(valid_dates[0]) if len(valid_dates) else pd.NaT
        exit_checks.append({
            "symbol": trade.symbol, "entryDate": trade.entryDate,
            "firstBearDate": bear_date, "nextListedDate": next_listed,
            "nextListedOpenValid": _valid_open(later.iloc[0]["Open"]) if not later.empty else False,
            "expectedExitDate": expected_exit, "actualExitDate": trade.exitDate,
            "matchesCorrectedRule": expected_exit == trade.exitDate,
        })
    exit_checks = pd.DataFrame(exit_checks)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics = pd.DataFrame([
        {"eligibilityConvention": name, **values} for name, values in results.items()
    ])
    metrics.to_csv(args.output_dir / "audit_fix_long_sample_metrics.csv", index=False)
    changes.to_csv(args.output_dir / "audit_fix_membership_changes.csv", index=False)
    exit_checks.to_csv(args.output_dir / "exit_timing_audit.csv", index=False)
    summary = {
        "selectionRowChanges": int(len(changes)),
        "effectiveDatesWithSelectionChanges": int(changes["effectiveDate"].nunique()),
        "auditedClosedTrades": int(len(exit_checks)),
        "exitRuleMismatches": int((~exit_checks["matchesCorrectedRule"]).sum()),
        "legacyLostExitOpportunities": int((~exit_checks["nextListedOpenValid"]).sum()),
    }
    (args.output_dir / "audit_fix_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(metrics[["eligibilityConvention", "candidateSignals", "cagr", "sharpe", "maxDrawdown"]].to_string(index=False))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
