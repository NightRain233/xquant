"""Fetch and freeze dedicated gold, precious-metal, macro, and domestic RMB market data
for the Gold Quantitative Enhancement Research Study (2026-11-23).

Writes immutable cached files into ``outputs/gold-enhance-2026-11-23/cache/``
and records SHA256 hashes + date spans in ``fetch_manifest.json``.
Never mutates any existing repository research cache.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import time

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SLUG = "gold-enhance-2026-11-23"
OUT = ROOT / "outputs" / SLUG
CACHE = OUT / "cache"
YF_START = "1970-01-01"
YF_END_EXCLUSIVE = "2026-11-21"  # captures through Friday 2026-11-20 close

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"
STOOQ_URL = "https://stooq.com/q/d/l/?s={}&i=d"


def download_url(url: str, dest: Path) -> None:
    for attempt in range(3):
        result = subprocess.run(
            ["curl", "--http1.1", "-fsSL", "--max-time", "90", "-A", "Mozilla/5.0", "-o", str(dest), url],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and dest.exists() and dest.stat().st_size > 120:
            head = dest.read_text(errors="ignore")[:200].lower()
            if "no data" not in head and "<html" not in head and "<!doctype" not in head:
                return
        print(f"curl attempt {attempt + 1} failed for {url}: {result.stderr.strip()[:160]}", flush=True)
        time.sleep(2)
    if dest.exists():
        dest.unlink(missing_ok=True)
    raise RuntimeError(f"could not download valid data from {url}")


def download_yahoo(ticker: str, dest: Path, auto_adjust: bool, start: str = YF_START) -> None:
    import yfinance as yf

    for attempt in range(3):
        try:
            frame = yf.Ticker(ticker).history(
                start=start,
                end=YF_END_EXCLUSIVE,
                auto_adjust=auto_adjust,
                actions=False,
            )
            if frame is None or frame.empty or len(frame) < 50:
                raise ValueError(f"empty or too-short history for {ticker}")
            frame.index.name = "Date"
            frame.to_csv(dest)
            return
        except Exception as exc:
            print(f"yahoo {ticker} attempt {attempt + 1} failed: {type(exc).__name__}: {str(exc)[:180]}", flush=True)
            time.sleep(2)
    raise RuntimeError(f"could not download {ticker}")


def summarize_csv(path: Path) -> dict:
    df = pd.read_csv(path)
    first_col = df.columns[0]
    return {
        "path": str(path.relative_to(ROOT)),
        "rows": int(len(df)),
        "first_date": str(df[first_col].iloc[0]) if len(df) else None,
        "last_date": str(df[first_col].iloc[-1]) if len(df) else None,
        "columns": list(df.columns),
        "bytes": int(path.stat().st_size),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)

    yahoo_specs = [
        # Core US Gold & Precious Metals
        ("yf_GLD", "GLD", True, "2004-01-01"),
        ("yf_IAU", "IAU", True, "2005-01-01"),
        ("yf_SLV", "SLV", True, "2006-01-01"),
        ("yf_GDX", "GDX", True, "2006-01-01"),
        ("yf_GDXJ", "GDXJ", True, "2009-01-01"),
        ("yf_UGL", "UGL", True, "2008-01-01"),
        ("yf_GCF", "GC=F", False, "1998-01-01"),
        ("yf_SIF", "SI=F", False, "1998-01-01"),
        ("yf_XAU_IDX", "^XAU", False, "1980-01-01"),
        # Defensive Shields & Macro Proxies
        ("yf_SPY", "SPY", True, "1993-01-01"),
        ("yf_IEF", "IEF", True, "2002-01-01"),
        ("yf_TLT", "TLT", True, "2002-01-01"),
        ("yf_SHY", "SHY", True, "2002-01-01"),
        ("yf_TIP", "TIP", True, "2003-01-01"),
        ("yf_DXY", "DX-Y.NYB", False, "1971-01-01"),
        ("yf_UUP", "UUP", True, "2007-01-01"),
        ("yf_IRX", "^IRX", False, "1970-01-01"),
        # Crypto Gold & Digital Gold
        ("yf_PAXG", "PAXG-USD", False, "2019-01-01"),
        ("yf_XAUT", "XAUT-USD", False, "2020-01-01"),
        ("yf_BTC", "BTC-USD", False, "2014-01-01"),
        # Domestic RMB Gold, Bonds & FX
        ("yf_518880", "518880.SS", True, "2013-01-01"),
        ("yf_511010", "511010.SS", True, "2013-01-01"),
        ("yf_511260", "511260.SS", True, "2017-01-01"),
        ("yf_CNY", "CNY=X", False, "2000-01-01"),
    ]

    files: dict[str, dict] = {}
    errors: dict[str, str] = {}

    for key, ticker, auto_adj, start in yahoo_specs:
        dest = CACHE / f"{key}.csv"
        if not dest.exists():
            try:
                download_yahoo(ticker, dest, auto_adjust=auto_adj, start=start)
            except Exception as exc:
                errors[key] = str(exc)
                continue
        files[key] = summarize_csv(dest)
        print(f"[YF] {key:12s}: {files[key]['rows']:6d} rows | {files[key]['first_date']} -> {files[key]['last_date']}", flush=True)

    # Public historical monthly gold dataset (1950+) for 50-year structural cycle context (1971-2000 pre-GC=F)
    extra_urls = [
        ("datasets_gold_monthly", "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"),
    ]
    for key, url in extra_urls:
        dest = CACHE / f"{key}.csv"
        if not dest.exists():
            try:
                download_url(url, dest)
            except Exception as exc:
                errors[key] = str(exc)
                continue
        files[key] = summarize_csv(dest)
        print(f"[EXTRA] {key:22s}: {files[key]['rows']:6d} rows | {files[key]['first_date']} -> {files[key]['last_date']}", flush=True)

    # FRED macro series (real yields, breakeven inflation, 10Y nominal, 3M T-bill, trade-weighted USD, CPI)
    for series in ("DFII10", "T10YIE", "DGS10", "TB3MS", "DTWEXBGS", "DTWEXM", "CPIAUCSL"):
        dest = CACHE / f"fred_{series}.csv"
        if not dest.exists():
            try:
                download_url(FRED_URL.format(series), dest)
            except Exception as exc:
                errors[f"fred_{series}"] = str(exc)
                continue
        files[f"fred_{series}"] = summarize_csv(dest)
        print(f"[FRED]  {series:12s}: {files[f'fred_{series}']['rows']:6d} rows | {files[f'fred_{series}']['first_date']} -> {files[f'fred_{series}']['last_date']}", flush=True)

    manifest = {
        "slug": SLUG,
        "fetched_at": datetime.now().astimezone().isoformat(),
        "end_inclusive": "2026-11-20",
        "files": files,
        "errors": errors,
    }
    (OUT / "fetch_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"\nSaved {len(files)} files, {len(errors)} errors.", flush=True)
    if errors:
        print("Non-fatal / failed downloads:", json.dumps(errors, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
