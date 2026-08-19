#!/usr/bin/env python3
"""Run event research on a point-in-time trading unified-policy decision stream."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from xquant.event_study import EventStudyConfig, attach_forward_outcomes, summarize_events  # noqa: E402


def _price_loader(data_dir: Path):
    cache: dict[str, pd.DataFrame] = {}

    def load(symbol: str) -> pd.DataFrame:
        if symbol not in cache:
            cache[symbol] = pd.read_parquet(
                data_dir / f"{symbol}.parquet",
                columns=["Open", "High", "Low", "Close"],
            )
        return cache[symbol]

    return load


def _execution_summary(events: pd.DataFrame) -> pd.DataFrame:
    formal = events[events["formalSignal"] & events["independentEvent"]]
    if formal.empty:
        return pd.DataFrame()
    return (
        formal.groupby(["setup", "permission", "executionOutcome"], dropna=False)
        .size()
        .rename("eventCount")
        .reset_index()
    )


def _gate_summary(events: pd.DataFrame) -> pd.DataFrame:
    controls = events[events["independentEvent"]].copy()
    if controls.empty:
        return pd.DataFrame()
    controls["gate"] = controls["nextGate"].fillna("PASSED_ALL")
    return summarize_events(
        controls,
        group_columns=("setup", "permission", "gate"),
        independent_only=False,
    )


def _cluster_bootstrap_summary(events: pd.DataFrame, *, samples: int = 2000) -> pd.DataFrame:
    independent = events[events["independentEvent"]].copy()
    groups = {
        "pullback_buy_executed": independent.query(
            "setup == 'pullback' and permission == 'buy' and entryPrice == entryPrice"
        ),
        "pullback_wait_restrength": independent.query(
            "setup == 'pullback' and stage == 'pullback_wait_restrength'"
        ),
        "pullback_approaching": independent.query(
            "setup == 'pullback' and stage == 'pullback_approaching'"
        ),
        "compression_triggered": independent.query(
            "setup == 'compression_breakout' and permission == 'conditional' and entryPrice == entryPrice"
        ),
    }
    rng = np.random.default_rng(20260811)
    rows = []
    for label, group in groups.items():
        for horizon in (5, 10, 20):
            column = f"netReturn{horizon}Pct"
            valid = group.dropna(subset=[column])
            symbol_values = {
                symbol: values[column].to_numpy()
                for symbol, values in valid.groupby("symbol")
            }
            symbols = np.array(list(symbol_values))
            bootstrap = []
            if len(symbols):
                for _ in range(samples):
                    sampled = rng.choice(symbols, len(symbols), replace=True)
                    bootstrap.append(
                        np.concatenate([symbol_values[symbol] for symbol in sampled]).mean()
                    )
            rows.append({
                "cohort": label,
                "horizonSessions": horizon,
                "eventCount": int(len(valid)),
                "symbolCount": int(len(symbols)),
                "meanNetReturnPct": valid[column].mean(),
                "clusterCiLowPct": np.quantile(bootstrap, 0.025) if bootstrap else None,
                "clusterCiHighPct": np.quantile(bootstrap, 0.975) if bootstrap else None,
            })
    return pd.DataFrame(rows)


def _paired_pullback_comparison(events: pd.DataFrame, *, samples: int = 5000) -> pd.DataFrame:
    independent = events[events["independentEvent"]].copy()
    buy = independent.query(
        "setup == 'pullback' and permission == 'buy' and entryPrice == entryPrice"
    )
    rng = np.random.default_rng(20260811)
    rows = []
    for control_stage in ("pullback_wait_restrength", "pullback_approaching"):
        control = independent[independent["stage"] == control_stage]
        for horizon in (5, 10, 20):
            column = f"netReturn{horizon}Pct"
            paired = pd.concat(
                [
                    buy.groupby("symbol")[column].mean().rename("formal"),
                    control.groupby("symbol")[column].mean().rename("control"),
                ],
                axis=1,
            ).dropna()
            differences = (paired["formal"] - paired["control"]).to_numpy()
            bootstrap = [
                rng.choice(differences, len(differences), replace=True).mean()
                for _ in range(samples)
            ] if len(differences) else []
            rows.append({
                "controlStage": control_stage,
                "horizonSessions": horizon,
                "pairedSymbolCount": int(len(differences)),
                "formalMinusControlPct": differences.mean() if len(differences) else None,
                "pairedMedianDifferencePct": np.median(differences) if len(differences) else None,
                "ciLowPct": np.quantile(bootstrap, 0.025) if bootstrap else None,
                "ciHighPct": np.quantile(bootstrap, 0.975) if bootstrap else None,
            })
    return pd.DataFrame(rows)


def _pullback_max_price_counterfactual(
    events: pd.DataFrame,
    price_loader,
    *,
    round_trip_cost_bps: float,
) -> pd.DataFrame:
    formal = events[
        events["independentEvent"]
        & (events["setup"] == "pullback")
        & (events["permission"] == "buy")
    ]
    rows = []
    cost_pct = round_trip_cost_bps / 100.0
    for _, event in formal.iterrows():
        prices = price_loader(str(event["symbol"])).sort_index().copy()
        prices.index = pd.DatetimeIndex(prices.index).tz_localize(None).normalize()
        future = prices.loc[prices.index > pd.Timestamp(event["decisionDate"])].iloc[:20]
        if len(future) < 20:
            continue
        entry = float(future.iloc[0]["Open"])
        rows.append({
            "executionOutcome": event["executionOutcome"],
            "return5Pct": (float(future.iloc[4]["Close"]) / entry - 1.0) * 100.0 - cost_pct,
            "return10Pct": (float(future.iloc[9]["Close"]) / entry - 1.0) * 100.0 - cost_pct,
            "return20Pct": (float(future.iloc[19]["Close"]) / entry - 1.0) * 100.0 - cost_pct,
            "mfe20Pct": (float(future["High"].max()) / entry - 1.0) * 100.0,
            "mae20Pct": (float(future["Low"].min()) / entry - 1.0) * 100.0,
        })
    details = pd.DataFrame(rows)
    if details.empty:
        return details
    return details.groupby("executionOutcome").agg(
        eventCount=("return20Pct", "size"),
        avgReturn5Pct=("return5Pct", "mean"),
        medianReturn5Pct=("return5Pct", "median"),
        avgReturn10Pct=("return10Pct", "mean"),
        medianReturn10Pct=("return10Pct", "median"),
        avgReturn20Pct=("return20Pct", "mean"),
        medianReturn20Pct=("return20Pct", "median"),
        avgMfe20Pct=("mfe20Pct", "mean"),
        avgMae20Pct=("mae20Pct", "mean"),
    ).reset_index()


def _research_summary(decisions: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    independent = events[events["independentEvent"]]
    breakout = decisions[decisions["setup"] == "breakout"]
    pullback = independent[
        (independent["setup"] == "pullback")
        & (independent["permission"] == "buy")
    ]
    pullback_executed = pullback[pullback["entryPrice"].notna()]
    compression = independent[
        (independent["setup"] == "compression_breakout")
        & (independent["permission"] == "conditional")
    ]
    compression_triggered = compression[compression["entryPrice"].notna()]
    rows = [
        ("decision_rows", len(decisions)),
        ("symbols", decisions["symbol"].nunique()),
        ("independent_events", len(independent)),
        ("breakout_candidates", len(breakout)),
        ("breakout_formal_buy", int((breakout["permission"] == "buy").sum())),
        ("breakout_distance_atr_median", breakout["distanceToSupertrendAtr"].median()),
        ("breakout_distance_atr_le_2", int((breakout["distanceToSupertrendAtr"] <= 2).sum())),
        ("pullback_formal_independent", len(pullback)),
        ("pullback_executed_independent", len(pullback_executed)),
        ("pullback_execution_rate", pullback["entryPrice"].notna().mean()),
        ("pullback_avg_net_return_5_pct", pullback_executed["netReturn5Pct"].mean()),
        ("pullback_avg_net_return_10_pct", pullback_executed["netReturn10Pct"].mean()),
        ("pullback_avg_net_return_20_pct", pullback_executed["netReturn20Pct"].mean()),
        ("compression_conditional_independent", len(compression)),
        ("compression_triggered_independent", len(compression_triggered)),
        ("compression_trigger_rate", compression["entryPrice"].notna().mean()),
        ("compression_avg_net_return_20_pct", compression_triggered["netReturn20Pct"].mean()),
    ]
    return pd.DataFrame(rows, columns=["metric", "value"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--decision-metadata", type=Path)
    parser.add_argument("--price-data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--round-trip-cost-bps", type=float, default=20.0)
    parser.add_argument("--independent-gap-sessions", type=int, default=20)
    args = parser.parse_args()

    decisions = pd.read_parquet(args.decisions)
    config = EventStudyConfig(
        round_trip_cost_bps=args.round_trip_cost_bps,
        independent_gap_sessions=args.independent_gap_sessions,
    )
    price_loader = _price_loader(args.price_data_dir)
    events = attach_forward_outcomes(
        decisions,
        price_loader,
        config=config,
    )
    summary = summarize_events(events)
    raw_summary = summarize_events(events, independent_only=False)
    gate_summary = _gate_summary(events)
    execution_summary = _execution_summary(events)
    market_summary = summarize_events(
        events,
        group_columns=("market", "setup", "permission"),
    )
    yearly_summary = summarize_events(
        events.assign(year=pd.to_datetime(events["decisionDate"]).dt.year),
        group_columns=("year", "setup", "permission"),
    )
    bootstrap_summary = _cluster_bootstrap_summary(events)
    paired_comparison = _paired_pullback_comparison(events)
    max_price_counterfactual = _pullback_max_price_counterfactual(
        events,
        price_loader,
        round_trip_cost_bps=args.round_trip_cost_bps,
    )
    research_summary = _research_summary(decisions, events)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    events.to_csv(args.output_dir / "event_details.csv", index=False)
    summary.to_csv(args.output_dir / "event_summary_independent.csv", index=False)
    raw_summary.to_csv(args.output_dir / "event_summary_all.csv", index=False)
    gate_summary.to_csv(args.output_dir / "gate_summary.csv", index=False)
    execution_summary.to_csv(args.output_dir / "execution_summary.csv", index=False)
    market_summary.to_csv(args.output_dir / "market_summary.csv", index=False)
    yearly_summary.to_csv(args.output_dir / "yearly_summary.csv", index=False)
    bootstrap_summary.to_csv(args.output_dir / "cluster_bootstrap_summary.csv", index=False)
    paired_comparison.to_csv(args.output_dir / "paired_pullback_comparison.csv", index=False)
    max_price_counterfactual.to_csv(args.output_dir / "pullback_max_price_counterfactual.csv", index=False)
    research_summary.to_csv(args.output_dir / "research_summary.csv", index=False)

    decision_metadata = {}
    metadata_path = args.decision_metadata or args.decisions.with_suffix(".metadata.json")
    if metadata_path.exists():
        decision_metadata = json.loads(metadata_path.read_text())
    metadata = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "decisionSource": str(args.decisions.resolve()),
        "decisionMetadata": decision_metadata,
        "priceDataDir": str(args.price_data_dir.resolve()),
        "roundTripCostBps": args.round_trip_cost_bps,
        "independentGapSessions": args.independent_gap_sessions,
        "eventCount": int(len(events)),
        "independentEventCount": int(events["independentEvent"].sum()) if not events.empty else 0,
        "formalSignalCount": int(events["formalSignal"].sum()) if not events.empty else 0,
        "method": "next-session execution; 5/10/20-session event returns; no portfolio overlap assumptions",
        "compressionAmbiguity": "daily bars with both trigger and invalidation touched are excluded from execution outcomes",
    }
    (args.output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
