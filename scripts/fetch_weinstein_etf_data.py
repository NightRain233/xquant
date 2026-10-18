"""Fetch a dated A-share ETF daily snapshot for the Weinstein stage review.

Writes only to ``outputs/<slug>/cache`` (git-ignored raw responses) and a
manifest with SHA256 per raw file. Two adjustments are requested per symbol:

* ``forward``  proportional forward adjustment: the return series used for the
  backtest (cash dividends treated as reinvested, splits neutralised);
* ``none``     raw prices, kept only to audit dividend / split events.

The free TickFlow endpoint is used, the same provider as the existing frozen
``strategy-healthcheck-2026-10-02`` snapshot (which is ``forward_additive``
and therefore not used for return calculation here).
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
import requests

ROOT = Path(__file__).resolve().parents[1]
SLUG = "weinstein-etf-stage-2026-10-18"
UNIVERSE = ROOT.parent / "trading/backend/universes/a_share_etf_core.json"


def fetch(symbols, adjust, start, end_exclusive, base):
    params = {
        "symbols": ",".join(s.replace(".SS", ".SH") for s in symbols),
        "period": "1d",
        "adjust": adjust,
        "count": 10000,
        "start_time": int(pd.Timestamp(start, tz="Asia/Shanghai").timestamp() * 1000),
        "end_time": int(pd.Timestamp(end_exclusive, tz="Asia/Shanghai").timestamp() * 1000),
    }
    headers = {"x-api-key": os.environ["TICKFLOW_API_KEY"]} if os.environ.get("TICKFLOW_API_KEY") else {}
    response = requests.get(base + "/v1/klines/batch", params=params, headers=headers, timeout=60)
    response.raise_for_status()
    return response.content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default="2026-10-16")
    parser.add_argument("--start", default="2013-01-01")
    parser.add_argument("--batch-size", type=int, default=3)
    args = parser.parse_args()
    out = ROOT / "outputs" / SLUG
    cache = out / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    symbols = [s["symbol"] for s in json.loads(UNIVERSE.read_text())["symbols"]]
    end = (pd.Timestamp(args.as_of) + pd.Timedelta(days=1)).date().isoformat()
    base = os.environ.get("TICKFLOW_BASE_URL", "https://free-api.tickflow.org").rstrip("/")
    manifest = {"provider": "TickFlow free API /v1/klines/batch", "fetched_at": datetime.now().astimezone().isoformat(),
                "start": args.start, "end_exclusive": end, "universe_file": str(UNIVERSE.relative_to(ROOT.parent)),
                "universe_sha256": hashlib.sha256(UNIVERSE.read_bytes()).hexdigest(), "files": {}, "errors": []}
    for adjust in ("forward", "none"):
        for pos in range(0, len(symbols), args.batch_size):
            batch = symbols[pos:pos + args.batch_size]
            name = f"tickflow_{adjust}_{'_'.join(s.split('.')[0] for s in batch)}.json"
            path = cache / name
            if not path.exists():
                for attempt in range(3):
                    try:
                        path.write_bytes(fetch(batch, adjust, args.start, end, base))
                        break
                    except Exception as exc:  # keep the error, never invent data
                        manifest["errors"].append({"file": name, "attempt": attempt + 1,
                                                   "error": type(exc).__name__, "message": str(exc)[:200]})
                        time.sleep(3)
                time.sleep(0.6)
            if path.exists():
                manifest["files"][name] = {"adjust": adjust, "symbols": batch,
                                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            print(adjust, batch, "ok" if path.exists() else "FAILED", flush=True)
    (out / "fetch_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
