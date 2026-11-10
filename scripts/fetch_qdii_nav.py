"""Fetch unit NAV history and recent unadjusted daily prices of the mainland QDII ETFs 513500 and 513100
(Eastmoney via akshare). Recent prices only extend the frozen TickFlow series to the latest premium reading.

Raw tables go to ``outputs/<slug>/cache`` (git-ignored); the manifest with source, range and SHA256
is written next to the outputs. Nothing is interpolated: a failed fetch exits 1.

Run (from repo root): .venv/bin/python scripts/fetch_qdii_nav.py
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SLUG = "qdii-premium-2026-11-10"
OUT = ROOT / "outputs" / SLUG
CACHE = OUT / "cache"
FUNDS = ["513500", "513100"]


def main() -> int:
    import akshare as ak

    CACHE.mkdir(parents=True, exist_ok=True)
    manifest = {"fetched_at": datetime.now().astimezone().isoformat(), "akshare_version": ak.__version__,
                "source": "Eastmoney via akshare.fund_open_fund_info_em(indicator='单位净值走势')", "files": {}}
    for fund in FUNDS:
        try:
            table = ak.fund_open_fund_info_em(symbol=fund, indicator="单位净值走势")
        except Exception as error:  # noqa: BLE001 - record and stop, never invent data
            print(f"fetch failed for {fund}: {error!r}")
            return 1
        if table.empty:
            print(f"empty NAV table for {fund}")
            return 1
        path = CACHE / f"nav_{fund}.csv"
        table.to_csv(path, index=False)
        manifest["files"][path.name] = {"fund": fund, "rows": len(table), "first": str(table["净值日期"].iloc[0]),
                                        "last": str(table["净值日期"].iloc[-1]),
                                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        try:
            prices = ak.fund_etf_hist_em(symbol=fund, period="daily", start_date="20260801", end_date="20261231", adjust="")
        except Exception as error:  # noqa: BLE001
            print(f"price fetch failed for {fund}: {error!r}")
            return 1
        price_path = CACHE / f"price_recent_{fund}.csv"
        prices.to_csv(price_path, index=False)
        manifest["files"][price_path.name] = {"fund": fund, "rows": len(prices), "first": str(prices["日期"].iloc[0]),
                                              "last": str(prices["日期"].iloc[-1]), "adjust": "none",
                                              "source": "akshare.fund_etf_hist_em",
                                              "sha256": hashlib.sha256(price_path.read_bytes()).hexdigest()}
    (OUT / "data_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
