#!/usr/bin/env python3
"""Compare the former library-default RMA SuperTrend with the frozen SMA contract."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

import pandas as pd
import pandas_ta_classic as ta

ROOT = Path(__file__).resolve().parents[2]
TRADING_ROOT = Path(os.environ.get("TRADING_ROOT", ROOT.parent / "trading")).expanduser().resolve()
BACKEND_DIR = TRADING_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from supertrend_contract import CONTRACT_VERSION, calculate_supertrend  # noqa: E402


DEFAULT_SYMBOLS = ("510300.SS", "513100.SS", "518880.SS", "BTC-USD")


def _direction_column(frame: pd.DataFrame) -> str | None:
    return next((column for column in frame.columns if column.startswith("SUPERTd_")), None)


def compare_symbol(symbol: str, *, length: int, multiplier: float) -> dict[str, Any]:
    frame = pd.read_parquet(BACKEND_DIR / "data" / f"{symbol}.parquet").sort_index()
    frame = frame.dropna(subset=["High", "Low", "Close"])
    old = ta.supertrend(
        frame["High"], frame["Low"], frame["Close"], length=length, multiplier=multiplier
    )
    old_column = _direction_column(old)
    new = calculate_supertrend(
        frame["High"], frame["Low"], frame["Close"], length=length, multiplier=multiplier
    )
    new_column = _direction_column(new)
    if old_column is None or new_column is None:
        raise ValueError(f"SuperTrend direction output is missing for {symbol}")

    aligned = pd.concat(
        [old[old_column].rename("old"), new[new_column].rename("new")], axis=1
    ).dropna()
    differences = aligned[aligned["old"] != aligned["new"]]
    old_flips = aligned["old"].diff().fillna(0).ne(0)
    new_flips = aligned["new"].diff().fillna(0).ne(0)
    return {
        "symbol": symbol,
        "rowsCompared": len(aligned),
        "directionDifferences": len(differences),
        "differenceRatio": len(differences) / len(aligned) if len(aligned) else 0.0,
        "oldFlipCount": int(old_flips.sum()),
        "newFlipCount": int(new_flips.sum()),
        "firstDifferences": [index.isoformat() for index in differences.index[:10]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="*", default=list(DEFAULT_SYMBOLS))
    parser.add_argument("--length", type=int, default=10)
    parser.add_argument("--multiplier", type=float, default=3.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs" / "trading-research" / "supertrend-contract-diff-2026-11-14.json",
    )
    args = parser.parse_args()
    rows = [compare_symbol(symbol, length=args.length, multiplier=args.multiplier) for symbol in args.symbols]
    payload = {
        "contractVersion": CONTRACT_VERSION,
        "comparison": "pandas-ta default RMA versus project SMA ATR",
        "length": args.length,
        "multiplier": args.multiplier,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
