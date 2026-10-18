"""Fetch an isolated, dated OHLCV snapshot for the frozen strategy review.

Run with the sibling trading/backend environment. Never writes production data.
Provider errors and per-symbol coverage are retained alongside the snapshot.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import time
import zipfile

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "research/trading-ledger-2026-09-05/core90_recovery_2026_09_05/original_xquant.zip"
FIELDS = ("Open", "High", "Low", "Close", "Volume")


def normalize(frame):
    frame = frame.copy()
    index = pd.DatetimeIndex(frame.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    frame.index = index.normalize()
    return frame.loc[~frame.index.duplicated()].sort_index().dropna(subset=list(FIELDS[:4]))


def fetch_tickflow(symbols, start, end, output):
    import os
    provider = {s.replace(".SS", ".SH"): s for s in symbols}
    params = {
        "symbols": ",".join(provider), "period": "1d", "adjust": "forward_additive",
        "count": 10000,
        "start_time": int(pd.Timestamp(start, tz="Asia/Shanghai").timestamp() * 1000),
        "end_time": int(pd.Timestamp(end, tz="Asia/Shanghai").timestamp() * 1000),
    }
    headers = {"x-api-key": os.environ["TICKFLOW_API_KEY"]} if os.environ.get("TICKFLOW_API_KEY") else {}
    base = os.environ.get("TICKFLOW_BASE_URL", "https://free-api.tickflow.org").rstrip("/")
    response = requests.get(base + "/v1/klines/batch", params=params, headers=headers, timeout=45)
    response.raise_for_status()
    payload = response.json()
    key = hashlib.sha256(",".join(symbols).encode()).hexdigest()[:12]
    (output / "cache" / f"tickflow_raw_{key}.json").write_text(json.dumps(payload))
    frames = {}
    for key, data in (payload.get("data") or {}).items():
        if key not in provider or not data.get("timestamp"):
            continue
        index = pd.to_datetime(data["timestamp"], unit="ms", utc=True).tz_convert("Asia/Shanghai").tz_localize(None).normalize()
        frame = pd.DataFrame({f: data[f.lower()] for f in FIELDS}, index=index)
        frame["Volume"] = frame["Volume"] * 100
        frames[provider[key]] = normalize(frame)
    if not frames:
        raise ValueError("TickFlow returned no OHLCV rows; response keys=" + str(list(payload)))
    return frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", choices=("tickflow", "yahoo"), required=True)
    parser.add_argument("--symbols", nargs="*")
    parser.add_argument("--start", default="2013-01-01")
    parser.add_argument("--batch-size", type=int, default=3)
    args = parser.parse_args()
    out = args.output.resolve()
    for folder in (out, out / "market_data", out / "cache"):
        folder.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE) as archive:
        symbols = sorted({Path(n).stem for n in archive.namelist() if "market_data/" in n and n.endswith(".parquet") and "_weekly" not in n})
    symbols = args.symbols or sorted(set(symbols + ["CNY=X", "HKDCNY=X"]))
    if args.source == "tickflow":
        symbols = [s for s in symbols if s.endswith((".SS", ".SZ"))]
    else:
        symbols = [s for s in symbols if not s.endswith((".SS", ".SZ"))]
    symbols = [s for s in symbols if not (out / "market_data" / f"{s}.parquet").exists()]
    # Use only fully elapsed dates; latest data is audited against market calendars later.
    end = (pd.Timestamp(args.as_of) + pd.Timedelta(days=1)).date().isoformat()
    manifest = {"requested_as_of": args.as_of, "fetched_at": datetime.now().astimezone().isoformat(),
                "source": args.source, "start": args.start, "end_exclusive": end,
                "adjustment": "forward_additive" if args.source == "tickflow" else "yfinance_auto_adjust",
                "symbols": {}, "errors": []}
    try:
        if args.source == "tickflow":
            frames = {}
            for position in range(0, len(symbols), args.batch_size):
                batch = symbols[position:position+args.batch_size]
                try:
                    frames.update(fetch_tickflow(batch, args.start, end, out))
                    print(f"Fetched TickFlow batch {batch}", flush=True)
                except Exception as exc:
                    manifest["errors"].append({"symbols": batch, "error": type(exc).__name__, "message": str(exc)[:200]})
                    print(f"Failed TickFlow batch {batch}: {type(exc).__name__}", flush=True)
                time.sleep(.5)
        else:
            import yfinance as yf
            yf.set_tz_cache_location(str(out / "cache" / "yfinance"))
            frames = {}
            failures = 0
            for symbol in symbols:
                try:
                    frame = yf.Ticker(symbol).history(start=args.start, end=end, auto_adjust=True, actions=False, raise_errors=True, timeout=45)
                    if frame.empty:
                        raise ValueError("No rows")
                    frames[symbol] = normalize(frame[list(FIELDS)])
                    failures = 0
                    print(f"Fetched {symbol}: {len(frame)} rows", flush=True)
                except Exception as exc:
                    failures += 1
                    manifest["errors"].append({"symbol": symbol, "error": type(exc).__name__, "message": str(exc)[:200]})
                    print(f"Failed {symbol}: {type(exc).__name__}", flush=True)
                    if failures >= 3:
                        manifest["errors"].append({"error": "CONSECUTIVE_FAILURE_CIRCUIT_BREAK", "remaining_symbols_not_attempted": True})
                        break
                time.sleep(0.4)
        for symbol in symbols:
            frame = frames.get(symbol)
            if frame is None or frame.empty:
                manifest["symbols"][symbol] = {"status": "MISSING"}
                continue
            path = out / "market_data" / f"{symbol}.parquet"
            if path.exists():
                raise FileExistsError(f"Refusing to overwrite {path}")
            frame.to_parquet(path)
            manifest["symbols"][symbol] = {
                "status": "FETCHED", "rows": len(frame), "first": str(frame.index.min().date()),
                "last": str(frame.index.max().date()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
    except Exception as exc:
        manifest["errors"].append({"error": type(exc).__name__, "message": str(exc)[:300]})
    suffix = datetime.now().strftime("%Y%m%dT%H%M%S")
    (out / f"fetch_{args.source}_{suffix}.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
    return 1 if not any(s.get("status") == "FETCHED" for s in manifest["symbols"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
