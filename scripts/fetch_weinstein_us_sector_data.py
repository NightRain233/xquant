"""Fetch a dated US sector-ETF daily snapshot (yfinance) for the Weinstein US review.

Writes raw ``Ticker.history(auto_adjust=True)`` CSVs (Open/Close adjusted for
splits and dividends = dividends reinvested) to ``outputs/<slug>/cache`` (git-
ignored) and a manifest with the SHA256 of every file. ``^IRX`` (13-week T-bill
yield, percent) is fetched for the cash-yield sensitivity only.

Run (needs network; the system proxy in ``https_proxy`` is used by yfinance):
  uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with yfinance \
      python scripts/fetch_weinstein_us_sector_data.py
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import time

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
SLUG = "weinstein-us-sector-2026-10-18"
SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "XLRE", "XLC"]
TICKERS = ["SPY", *SECTORS, "^IRX"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default="2026-10-16", help="last trading day to include (Friday of last full week)")
    parser.add_argument("--start", default="1998-12-01")
    args = parser.parse_args()
    out = ROOT / "outputs" / SLUG
    cache = out / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    end = (pd.Timestamp(args.as_of) + pd.Timedelta(days=1)).date().isoformat()
    manifest = {"provider": "Yahoo Finance via yfinance Ticker.history(auto_adjust=True, actions=True)",
                "yfinance_version": yf.__version__, "fetched_at": datetime.now().astimezone().isoformat(),
                "proxy": os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY"),
                "start": args.start, "end_exclusive": end, "files": {}, "errors": []}
    for t in TICKERS:
        name = f"yf_{t.replace('^', '')}.csv"
        path = cache / name
        if not path.exists():
            for attempt in range(3):
                try:
                    h = yf.Ticker(t).history(start=args.start, end=end, auto_adjust=True, actions=True)
                    if h.empty:
                        raise ValueError("empty history")
                    h.index.name = "Date"
                    h.to_csv(path)
                    break
                except Exception as exc:  # keep the error, never invent data
                    manifest["errors"].append({"ticker": t, "attempt": attempt + 1, "error": type(exc).__name__,
                                               "message": str(exc)[:200]})
                    time.sleep(3)
            time.sleep(1.0)
        if path.exists():
            frame = pd.read_csv(path)
            manifest["files"][name] = {"ticker": t, "rows": int(len(frame)), "first": str(frame["Date"].iloc[0])[:10],
                                       "last": str(frame["Date"].iloc[-1])[:10],
                                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        print(t, manifest["files"].get(name, "FAILED"), flush=True)
    (out / "fetch_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
