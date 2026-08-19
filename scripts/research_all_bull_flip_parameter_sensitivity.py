#!/usr/bin/env python3
"""Raw SuperTrend parameter diagnostic on the frozen rolling PIT universe.

This intentionally tests the timing layer only. The production
``setup=breakout`` classifier remains locked to SuperTrend 7/3 and is not
relabelled under alternative parameters.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import pandas_ta as ta


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from xquant.point_in_time_universe import filter_entries_by_membership  # noqa: E402
from xquant.signal_portfolio import (  # noqa: E402
    PortfolioConfig,
    performance_metrics,
    run_signal_portfolio,
    simple_supertrend_entries,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-catalog", type=Path, required=True)
    parser.add_argument("--price-data-dir", type=Path, required=True)
    parser.add_argument("--membership", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default="2026-07-10")
    args = parser.parse_args()

    start = pd.Timestamp(args.start).normalize()
    end = pd.Timestamp(args.end).normalize()
    symbols = json.loads(args.candidate_catalog.read_text())["symbols"]
    membership = pd.read_csv(args.membership, parse_dates=["snapshotDate", "effectiveDate"])
    membership = membership[membership["universe"].eq("rolling_monthly_pit")]
    market_by_symbol = membership.groupby("symbol")["market"].last().to_dict()
    base_prices = {
        symbol: pd.read_parquet(
            args.price_data_dir / f"{symbol}.parquet",
            columns=["Open", "High", "Low", "Close", "Volume"],
        )
        for symbol in symbols
    }
    config = PortfolioConfig(
        initial_capital=1_000_000.0,
        commission_bps=5.0,
        slippage_bps=5.0,
        max_position_weight=0.10,
        max_concurrent_positions=10,
        max_gross_exposure=1.0,
    )

    rows = []
    for length in (7, 10, 14):
        for multiplier in (2.0, 3.0, 4.0):
            prices = {}
            direction_column = f"SUPERTd_{length}_{multiplier}"
            for symbol, source in base_prices.items():
                frame = source.copy()
                indicator = ta.supertrend(
                    frame["High"], frame["Low"], frame["Close"],
                    length=length, multiplier=multiplier,
                )
                frame["ST_Dir"] = indicator[direction_column]
                prices[symbol] = frame
            raw_entries = simple_supertrend_entries(
                prices, market_by_symbol, start=start, end=end
            )
            entries = filter_entries_by_membership(raw_entries, membership)
            result = run_signal_portfolio(
                entries, prices, start=start, end=end, config=config
            )
            rows.append({
                "length": length,
                "multiplier": multiplier,
                "isProductionParameter": length == 7 and multiplier == 3.0,
                "candidateSignals": len(entries),
                **performance_metrics(result["nav"], result["trades"]),
            })

    output = pd.DataFrame(rows).sort_values(["length", "multiplier"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    print(output[[
        "length", "multiplier", "isProductionParameter", "cagr", "sharpe",
        "maxDrawdown", "calmar", "closedTrades",
    ]].to_string(index=False))


if __name__ == "__main__":
    main()
