"""Fetch and freeze extra US market inputs for the 4-direction S&P 500 study (2026-11-22).

Writes immutable cached files into ``outputs/sp500-four-directions-2026-11-22/cache/``
and records SHA256 hashes + date spans in ``fetch_manifest.json``.

Inputs downloaded:
* Yahoo Finance (auto_adjust=True): GLD, SPHQ, SPLV, RSP, SHY
* Yahoo Finance (auto_adjust=False): ^VIX, ^VIX3M, GC=F
* FRED: BAMLH0A0HYM2 (ICE BofA US High Yield Index Option-Adjusted Spread, daily)
* Stooq: xauusd (spot gold USD/oz daily, used only to splice pre-GLD 1998-2004 gold returns)

Existing frozen repo datasets are NOT re-downloaded:
* SPY, ^IRX: outputs/weinstein-us-sector-2026-10-18/cache/
* IEF, fred_DGS10: outputs/sp500-enhance-vs-dca-2026-11-10/cache/
* 513500 raw/premium: outputs/qdii-premium-2026-11-10/ & domestic-etf-small-account-2026-10-04
* 518880 (proportional forward-adjusted RMB gold ETF): outputs/btc-satellite-corrected-prices-2026-10-18/market_data/
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
SLUG = "sp500-four-directions-2026-11-22"
OUT = ROOT / "outputs" / SLUG
CACHE = OUT / "cache"
YF_START = "1998-01-01"
YF_END_EXCLUSIVE = "2026-10-17"  # aligns inclusive end 2026-10-16 with frozen SPY cache
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"
STOOQ_URL = "https://stooq.com/q/d/l/?s={}&i=d"


def download_url(url: str, dest: Path) -> None:
    for attempt in range(3):
        result = subprocess.run(
            ["curl", "-fsSL", "--max-time", "120", "-o", str(dest), url],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and dest.exists() and dest.stat().st_size > 100:
            return
        print(f"curl attempt {attempt + 1} failed for {url}: {result.stderr.strip()[:200]}", flush=True)
        time.sleep(2)
    raise RuntimeError(f"could not download {url}")


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
            if frame.empty:
                raise ValueError(f"empty history for {ticker}")
            frame.index.name = "Date"
            frame.to_csv(dest)
            return
        except Exception as exc:
            print(f"yahoo {ticker} attempt {attempt + 1} failed: {type(exc).__name__}: {str(exc)[:200]}", flush=True)
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
        ("yf_GLD", "GLD", True),
        ("yf_SPHQ", "SPHQ", True),
        ("yf_SPLV", "SPLV", True),
        ("yf_RSP", "RSP", True),
        ("yf_SHY", "SHY", True),
        ("yf_HYG", "HYG", True),
        ("yf_VIX", "^VIX", False),
        ("yf_VIX3M", "^VIX3M", False),
        ("yf_GCF", "GC=F", False),
    ]
    files: dict[str, dict] = {}
    errors: dict[str, str] = {}

    for key, ticker, auto_adj in yahoo_specs:
        dest = CACHE / f"{key}.csv"
        if not dest.exists():
            try:
                download_yahoo(ticker, dest, auto_adjust=auto_adj)
            except Exception as exc:
                errors[key] = str(exc)
                continue
        files[key] = summarize_csv(dest)
        print(key, files[key]["rows"], files[key]["first_date"], "->", files[key]["last_date"], flush=True)

    # FRED daily credit spread (Moody's Baa minus 10Y Treasury, full daily history since 1986)
    for series in ("BAA10Y", "BAMLH0A0HYM2"):
        fred_dest = CACHE / f"fred_{series}.csv"
        if not fred_dest.exists():
            try:
                download_url(FRED_URL.format(series), fred_dest)
            except Exception as exc:
                errors[f"fred_{series}"] = str(exc)
        if fred_dest.exists():
            files[f"fred_{series}"] = summarize_csv(fred_dest)
            print(
                f"fred_{series}",
                files[f"fred_{series}"]["rows"],
                files[f"fred_{series}"]["first_date"],
                "->",
                files[f"fred_{series}"]["last_date"],
                flush=True,
            )

    manifest = {
        "slug": SLUG,
        "fetched_at": datetime.now().astimezone().isoformat(),
        "end_inclusive": "2026-10-16",
        "files": files,
        "errors": errors,
    }
    (OUT / "fetch_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    if errors:
        print("ERRORS:", errors, flush=True)
        raise SystemExit(f"Data fetch failed: {errors}")


if __name__ == "__main__":
    main()
