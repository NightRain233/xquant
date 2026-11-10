"""Fetch and cache the extra inputs for the S&P 500 enhancement vs DCA study (2026-11-10).

Writes into ``outputs/sp500-enhance-vs-dca-2026-11-10/cache``; every downloaded file sits in its own
directory (untrusted data, never executed). Files:

* ``yf_IEF``: iShares 7-10yr Treasury ETF, ``Ticker.history(auto_adjust=True)`` from 2002-07.
* ``yf_GSPC``: ``^GSPC`` price only (``auto_adjust=False``, no actions), from 1927-12.
* ``fred_UNRATE``, ``fred_TB3MS``, ``fred_DGS10``: FRED ``fredgraph.csv`` downloads.
* ``shiller_ie_data``: Robert Shiller monthly data (``ie_data.xls``).

SPY and ^IRX are not copied: they are read from the existing ``weinstein-us-sector-2026-10-18`` cache,
whose hashes are verified by the research script.

Run (yfinance needs network):
  uv run python -I scripts/fetch_sp500_enhance_data.py
Then the manifest is written to ``outputs/<slug>/fetch_manifest.json`` with SHA256 and row counts.
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
SLUG = "sp500-enhance-vs-dca-2026-11-10"
OUT = ROOT / "outputs" / SLUG
CACHE = OUT / "cache"
YF_START, YF_END_EXCLUSIVE = "1927-01-01", "2026-10-17"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"
SHILLER_URL = "https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/downloads/ie_data.xls"


def download(url: str, dest: Path) -> None:
    """Plain curl (urllib timed out against FRED in this environment); fails loudly on HTTP errors."""
    for attempt in range(3):
        result = subprocess.run(["curl", "-fsSL", "--max-time", "120", "-o", str(dest), url],
                                capture_output=True, text=True)
        if result.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
            return
        print(f"curl attempt {attempt + 1} failed for {url}: {result.stderr.strip()[:200]}", flush=True)
        time.sleep(3)
    raise RuntimeError(f"could not download {url}")


def yahoo(ticker: str, dest_dir: Path, auto_adjust: bool, start: str) -> Path:
    import yfinance as yf  # imported here so the other downloads do not need yfinance

    path = dest_dir / f"yf_{ticker.replace('^', '')}.csv"
    for attempt in range(3):
        try:
            frame = yf.Ticker(ticker).history(start=start, end=YF_END_EXCLUSIVE, auto_adjust=auto_adjust,
                                              actions=False)
            if frame.empty:
                raise ValueError("empty history")
            frame.index.name = "Date"
            frame.to_csv(path)
            return path
        except Exception as exc:  # keep the error visible; never invent data
            print(f"{ticker} attempt {attempt + 1} failed: {type(exc).__name__}: {str(exc)[:200]}", flush=True)
            time.sleep(3)
    raise RuntimeError(f"could not download {ticker}")


def row_count(path: Path) -> int:
    if path.suffix == ".xls":
        raw = pd.read_excel(path, sheet_name="Data", header=None, engine="xlrd")
        header = raw.index[raw.iloc[:, 0].astype(str).str.strip() == "Date"][0]
        return int(raw.iloc[header + 1:].dropna(how="all").shape[0])
    return int(len(pd.read_csv(path)))


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    files = {}
    targets = {}
    targets["yf_IEF"] = ("yf_IEF", lambda d: yahoo("IEF", d, True, "2002-07-01"))
    targets["yf_GSPC"] = ("yf_GSPC", lambda d: yahoo("^GSPC", d, False, YF_START))
    for series in ("UNRATE", "TB3MS", "DGS10"):
        targets[f"fred_{series}"] = (f"fred_{series}",
                                     lambda d, s=series: _fred(s, d))
    targets["shiller_ie_data"] = ("shiller_ie_data", lambda d: _shiller(d))
    for key, (name, action) in targets.items():
        directory = CACHE / name
        existing = list(directory.glob("*")) if directory.exists() else []
        if existing:
            path = existing[0]
        else:
            directory.mkdir(parents=True, exist_ok=True)
            path = action(directory)
        files[key] = {"path": str(path.relative_to(ROOT)), "rows": row_count(path),
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
        print(key, files[key], flush=True)
    manifest = {"fetched_at": datetime.now().astimezone().isoformat(), "end_inclusive": "2026-10-16",
                "sources": {"yf_IEF": "yfinance Ticker.history(auto_adjust=True, actions=False)",
                            "yf_GSPC": "yfinance Ticker.history(auto_adjust=False, actions=False), price only",
                            "fred": FRED_URL.format("<series>"), "shiller": SHILLER_URL},
                "files": files}
    (OUT / "fetch_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


def _fred(series: str, directory: Path) -> Path:
    path = directory / f"fred_{series}.csv"
    download(FRED_URL.format(series), path)
    return path


def _shiller(directory: Path) -> Path:
    path = directory / "ie_data.xls"
    download(SHILLER_URL, path)
    return path


if __name__ == "__main__":
    main()
