#!/usr/bin/env python3
"""Replay production scan_v2 policy only on point-in-time bull-flip sessions."""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


CANDIDATE_EXCLUSIONS = {
    "CNY=X",
    "^HSI",
    "000688.SS",
    "000852.SS",
    "000905.SS",
}


def _load_replay_module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("trading_replay_unified_decisions", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load replay module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replay_events(
    *,
    replay_script: Path,
    data_dir: Path,
    symbols: list[str],
    start: str,
    end: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    production = _load_replay_module(replay_script)
    representatives = list(dict.fromkeys(
        symbol
        for values in production.SYSTEM_MARKET_REPRESENTATIVES.values()
        for symbol in values
    ))
    required = list(dict.fromkeys([*symbols, *representatives]))
    frames: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
    missing: list[str] = []
    for symbol in required:
        path = data_dir / f"{symbol}.parquet"
        if not path.exists():
            missing.append(symbol)
            continue
        frames[symbol] = production._prepare_frames(path)

    available = [symbol for symbol in symbols if symbol in frames]
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    representative_cache: dict[tuple[str, str, str], dict[str, Any] | None] = {}
    rows: list[dict[str, Any]] = []
    flip_counts: dict[str, int] = {}
    for symbol in available:
        daily, _ = frames[symbol]
        direction = pd.to_numeric(daily["_st_dir"], errors="coerce")
        bull_flip = direction.gt(0) & direction.shift(1).le(0)
        dates = daily.index[
            bull_flip & (daily.index >= start_ts) & (daily.index <= end_ts)
        ]
        flip_counts[symbol] = int(len(dates))
        for session_date in dates:
            evaluation_clock = production._evaluation_clock(symbol, session_date)
            item = production._item_as_of(symbol, frames, session_date, evaluation_clock)
            if item is None:
                continue
            target_market = production.classify_symbol_market(symbol)
            market_representatives = production.SYSTEM_MARKET_REPRESENTATIVES.get(
                target_market, ()
            )
            representative_items = []
            for representative in market_representatives:
                if representative not in frames or representative == symbol:
                    continue
                cache_key = (
                    representative,
                    pd.Timestamp(session_date).date().isoformat(),
                    production.classify_trading_venue(symbol),
                )
                if cache_key not in representative_cache:
                    representative_cache[cache_key] = production._item_as_of(
                        representative, frames, session_date, evaluation_clock
                    )
                representative_item = representative_cache[cache_key]
                if representative_item is not None:
                    representative_items.append(representative_item)
            response = production.build_scan_response(
                [item],
                requested_symbols=[symbol],
                representative_items=representative_items,
            )
            row = production._flatten(response["items"][0])
            row["evaluationClock"] = evaluation_clock.isoformat()
            rows.append(row)

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(["decisionDate", "symbol"]).reset_index(drop=True)
    metadata = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceRepository": "trading",
        **production._git_state(),
        "schemaVersion": production.SCHEMA_VERSION,
        "policyVersion": production.POLICY_VERSION,
        "start": start,
        "end": end,
        "requestedSymbols": symbols,
        "availableSymbols": available,
        "missingSymbols": [symbol for symbol in symbols if symbol in missing],
        "rowCount": int(len(result)),
        "rawBullFlipCount": int(sum(flip_counts.values())),
        "rawBullFlipCountBySymbol": flip_counts,
        "pointInTimeRule": "production daily/weekly item builders truncated at each raw bull-flip session",
        "eventOnlyRule": "non-bull-flip sessions omitted because both studied entry variants require setup=breakout",
        "executionRule": "decision stream only; no future prices used",
        "replayScript": str(replay_script.resolve()),
    }
    return result, metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-script", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--symbols", nargs="*")
    parser.add_argument("--start", default="2023-03-01")
    parser.add_argument("--end", default="2026-07-10")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    symbols = (
        [symbol.upper() for symbol in args.symbols]
        if args.symbols
        else sorted(
            path.stem
            for path in args.data_dir.glob("*.parquet")
            if not path.stem.endswith("_weekly")
            and path.stem not in CANDIDATE_EXCLUSIONS
        )
    )
    decisions, metadata = replay_events(
        replay_script=args.replay_script,
        data_dir=args.data_dir,
        symbols=symbols,
        start=args.start,
        end=args.end,
    )
    metadata["candidateCatalogRule"] = (
        "explicit --symbols" if args.symbols
        else "all local non-weekly parquet instruments minus fixed support-index/currency exclusions"
    )
    metadata["candidateExclusions"] = sorted(CANDIDATE_EXCLUSIONS)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    decisions.to_parquet(args.output, index=False)
    args.output.with_suffix(".metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({
        "rowCount": metadata["rowCount"],
        "rawBullFlipCount": metadata["rawBullFlipCount"],
        "availableSymbols": len(metadata["availableSymbols"]),
        "missingSymbols": metadata["missingSymbols"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
