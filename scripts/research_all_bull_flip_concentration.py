#!/usr/bin/env python3
"""Audit symbol profit concentration and pre-defined asset-class exclusions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from xquant.point_in_time_universe import filter_entries_by_membership  # noqa: E402
from xquant.signal_portfolio import (  # noqa: E402
    PortfolioConfig,
    decision_entries,
    performance_metrics,
    run_signal_portfolio,
)


INDIVIDUAL_STOCKS = frozenset({
    "000890.SZ", "002015.SZ", "002119.SZ", "002309.SZ", "002796.SZ",
    "600345.SS", "600487.SS", "601288.SS", "601991.SS", "605289.SS",
    "AAPL", "GOOGL", "MU", "NVDA", "TSLA",
})
CRYPTO = frozenset({"BTC-USD", "ETH-USD"})


def _asset_class(symbol: str) -> str:
    if symbol in INDIVIDUAL_STOCKS:
        return "individual_stock"
    if symbol in CRYPTO:
        return "crypto"
    if symbol == "GC=F":
        return "future"
    if symbol in {"000001.SS", "000300.SS"}:
        return "non_tradable_index"
    return "etf"


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
        symbol: pd.read_parquet(
            args.price_data_dir / f"{symbol}.parquet",
            columns=["Open", "High", "Low", "Close", "Volume", "ST_Dir"],
        )
        for symbol in symbols
    }
    membership = pd.read_csv(args.membership)
    membership = membership[membership["universe"].eq("rolling_monthly_pit")]
    market_by_symbol = membership.groupby("symbol")["market"].last().to_dict()
    decisions = pd.read_parquet(args.decisions)
    decisions["market"] = decisions["symbol"].map(market_by_symbol)
    entries = filter_entries_by_membership(
        decision_entries(decisions, "all_bull_flip"), membership
    )

    trades = pd.read_csv(args.trades)
    trades = trades[trades["strategy"].eq("policy_bull_flip_rolling_pit")]
    attribution = trades.groupby("symbol", as_index=False).agg(
        closedTrades=("netPnl", "size"),
        realizedNetPnl=("netPnl", "sum"),
        averageNetReturn=("netReturn", "mean"),
        medianNetReturn=("netReturn", "median"),
        winRate=("netPnl", lambda values: float((values > 0).mean())),
    ).sort_values(["realizedNetPnl", "symbol"], ascending=[False, True])
    attribution["assetClass"] = attribution["symbol"].map(_asset_class)
    total_realized = float(attribution["realizedNetPnl"].sum())
    attribution["shareOfNetRealizedPnl"] = (
        attribution["realizedNetPnl"] / total_realized
    )
    attribution["cumulativeShareOfNetRealizedPnl"] = (
        attribution["realizedNetPnl"].cumsum() / total_realized
    )

    config = PortfolioConfig(
        initial_capital=1_000_000.0,
        commission_bps=5.0,
        slippage_bps=5.0,
        max_position_weight=0.10,
        max_concurrent_positions=10,
        max_gross_exposure=1.0,
    )
    scenarios = {
        "baseline": frozenset(),
        "exclude_600487": frozenset({"600487.SS"}),
        "exclude_individual_stocks": INDIVIDUAL_STOCKS,
        "exclude_crypto": CRYPTO,
        "etf_and_futures_only": INDIVIDUAL_STOCKS | CRYPTO,
    }
    rows = []
    for scenario, excluded in scenarios.items():
        scenario_entries = entries[~entries["symbol"].isin(excluded)]
        result = run_signal_portfolio(
            scenario_entries,
            prices,
            start=start,
            end=end,
            config=config,
        )
        rows.append({
            "scenario": scenario,
            "excludedSymbols": "|".join(sorted(excluded)),
            "candidateSignals": len(scenario_entries),
            **performance_metrics(result["nav"], result["trades"]),
        })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    attribution.to_csv(args.output_dir / "symbol_pnl_attribution.csv", index=False)
    sensitivity = pd.DataFrame(rows)
    sensitivity.to_csv(args.output_dir / "exclusion_sensitivity.csv", index=False)
    metadata = {
        "individualStocks": sorted(INDIVIDUAL_STOCKS),
        "crypto": sorted(CRYPTO),
        "attributionBasis": "closed-trade realized net PnL after modeled costs",
        "exclusionBasis": "full portfolio rerun; freed cash and position slots may be reused",
        "warning": "exclusions are ex-post stress diagnostics, not candidate strategies",
    }
    (args.output_dir / "concentration_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )
    print(attribution.head(10).to_string(index=False))
    print(sensitivity[[
        "scenario", "candidateSignals", "cagr", "sharpe", "maxDrawdown",
        "closedTrades",
    ]].to_string(index=False))


if __name__ == "__main__":
    main()
