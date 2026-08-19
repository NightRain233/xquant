#!/usr/bin/env python3
"""Compare executable breakout anchors against the legacy post-flip ST distance gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _eligible_legacy_breakouts(decisions: pd.DataFrame) -> pd.DataFrame:
    rows = decisions[decisions["setup"].eq("breakout")].copy()
    rows["parsedFailedGates"] = rows["failedGates"].map(json.loads)
    return rows[
        rows["parsedFailedGates"].map(
            lambda gates: all(gate == "DISTANCE_ABOVE_2_ATR" for gate in gates)
        )
    ].copy()


def _attach_outcomes(
    candidates: pd.DataFrame,
    price_data_dir: Path,
    *,
    independent_gap_sessions: int,
    round_trip_cost_bps: float,
) -> pd.DataFrame:
    output: list[dict[str, object]] = []
    cost_pct = round_trip_cost_bps / 100.0
    for symbol, events in candidates.groupby("symbol", sort=False):
        prices = pd.read_parquet(price_data_dir / f"{symbol}.parquet")
        prices.index = pd.DatetimeIndex(prices.index).tz_localize(None).normalize()
        prices = prices.sort_index()
        prices = prices[~prices.index.duplicated(keep="last")]
        previous_position = -10_000
        for _, event in events.sort_values("decisionDate").iterrows():
            decision_date = pd.Timestamp(event["decisionDate"]).normalize()
            position = int(prices.index.searchsorted(decision_date, side="right") - 1)
            if position - previous_position < independent_gap_sessions:
                continue
            previous_position = position
            future = prices.iloc[position + 1 : position + 61]
            if len(future) < 20:
                continue
            entry = float(future.iloc[0]["Open"])
            atr = float(event["atr"])
            signal_close = float(event["close"])
            st_value = float(event["stVal"])
            exits = future[future["ST_Dir"] < 0]
            policy_exit = exits.iloc[0] if not exits.empty else future.iloc[-1]
            row = event.to_dict()
            row.update(
                {
                    "nextOpen": entry,
                    "nextGapAtr": (entry - signal_close) / atr,
                    "nextOpenAboveSignalSt": entry >= st_value,
                    "netReturn5Pct": (float(future.iloc[4]["Close"]) / entry - 1) * 100 - cost_pct,
                    "netReturn10Pct": (float(future.iloc[9]["Close"]) / entry - 1) * 100 - cost_pct,
                    "netReturn20Pct": (float(future.iloc[19]["Close"]) / entry - 1) * 100 - cost_pct,
                    "policyExitReturnPct": (float(policy_exit["Close"]) / entry - 1) * 100 - cost_pct,
                }
            )
            output.append(row)
    return pd.DataFrame(output)


def _summarize(events: pd.DataFrame) -> pd.DataFrame:
    filters = {
        "base": pd.Series(True, index=events.index),
        "macd_hist_positive": events["macdHist"] > 0,
    }
    rows: list[dict[str, object]] = []
    for filter_name, filter_mask in filters.items():
        for cap_atr in (0.0, 0.25, 0.5, 1.0):
            sample = events[
                filter_mask
                & events["nextOpenAboveSignalSt"]
                & (events["nextGapAtr"] <= cap_atr)
            ]
            rows.append(
                {
                    "filter": filter_name,
                    "maxNextSessionGapAtr": cap_atr,
                    "eventCount": len(sample),
                    "symbolCount": sample["symbol"].nunique(),
                    "avgNetReturn5Pct": sample["netReturn5Pct"].mean(),
                    "avgNetReturn10Pct": sample["netReturn10Pct"].mean(),
                    "avgNetReturn20Pct": sample["netReturn20Pct"].mean(),
                    "medianNetReturn20Pct": sample["netReturn20Pct"].median(),
                    "hitRate20": (sample["netReturn20Pct"] > 0).mean(),
                    "avgPolicyExitReturnPct": sample["policyExitReturnPct"].mean(),
                    "medianPolicyExitReturnPct": sample["policyExitReturnPct"].median(),
                    "policyExitHitRate": (sample["policyExitReturnPct"] > 0).mean(),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--price-data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--round-trip-cost-bps", type=float, default=20.0)
    parser.add_argument("--independent-gap-sessions", type=int, default=20)
    args = parser.parse_args()

    decisions = pd.read_parquet(args.decisions)
    candidates = _eligible_legacy_breakouts(decisions)
    events = _attach_outcomes(
        candidates,
        args.price_data_dir,
        independent_gap_sessions=args.independent_gap_sessions,
        round_trip_cost_bps=args.round_trip_cost_bps,
    )
    summary = _summarize(events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.output, index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
