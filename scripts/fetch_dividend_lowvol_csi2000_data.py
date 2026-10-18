"""Fetch index total-return history (CSIndex via akshare) and two ETFs (TickFlow).

Raw files go to ``outputs/<slug>/cache`` (git-ignored); the manifest with
source, range and SHA256 is written next to the outputs. Nothing is
interpolated or invented: a failed fetch is recorded and the script exits 1.

Run: uv run --no-project --with pandas==3.0.3 --with numpy --with akshare \
         python scripts/fetch_dividend_lowvol_csi2000_data.py
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SLUG = "dividend-lowvol-csi2000-2026-10-18"
INDEXES = {
    "H20269": "dividend_lowvol_tr",   # 红利低波全收益
    "H30269": "dividend_lowvol_px",   # 红利低波价格指数（仅用于对照分红影响）
    "932000": "csi2000_px",           # 中证2000价格指数（未取到全收益版本）
    "H00300": "csi300_tr",            # 沪深300全收益
    "000300": "csi300_px",            # 沪深300价格指数（用于估计分红缺口）
}
ETFS = {"512890.SH": "etf_dividend_lowvol", "563300.SH": "etf_csi2000"}
END = "2026-10-16"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    import akshare as ak
    import requests

    out = ROOT / "outputs" / SLUG
    cache = out / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    manifest = {"fetched_at": datetime.now().astimezone().isoformat(), "files": {}, "errors": []}
    for code, name in INDEXES.items():
        path = cache / f"csindex_{code}.csv"
        try:
            if not path.exists():
                df = ak.stock_zh_index_hist_csindex(symbol=code, start_date="20130101", end_date="20261018")
                df.to_csv(path, index=False)
            df = pd.read_csv(path)
            manifest["files"][path.name] = {"source": "CSIndex official site via akshare.stock_zh_index_hist_csindex",
                "code": code, "role": name, "name": str(df["指数中文简称"].iloc[0]), "rows": len(df),
                "first": str(df["日期"].iloc[0]), "last": str(df["日期"].iloc[-1]), "sha256": sha(path)}
        except Exception as exc:
            manifest["errors"].append({"code": code, "error": repr(exc)[:200]})
    base = os.environ.get("TICKFLOW_BASE_URL", "https://free-api.tickflow.org").rstrip("/")
    for sym, name in ETFS.items():
        path = cache / f"tickflow_forward_{sym.split('.')[0]}.json"
        try:
            if not path.exists():
                params = {"symbols": sym, "period": "1d", "adjust": "forward", "count": 10000,
                          "start_time": int(pd.Timestamp("2013-01-01", tz="Asia/Shanghai").timestamp() * 1000),
                          "end_time": int(pd.Timestamp("2026-10-17", tz="Asia/Shanghai").timestamp() * 1000)}
                r = requests.get(base + "/v1/klines/batch", params=params, timeout=60)
                r.raise_for_status()
                path.write_bytes(r.content)
            d = json.loads(path.read_text())["data"][sym]
            ts = pd.to_datetime(d["timestamp"], unit="ms", utc=True).tz_convert("Asia/Shanghai")
            manifest["files"][path.name] = {"source": "TickFlow free API /v1/klines/batch, adjust=forward",
                "code": sym, "role": name, "rows": len(ts), "first": str(ts[0].date()),
                "last": str(ts[-1].date()), "sha256": sha(path)}
        except Exception as exc:
            manifest["errors"].append({"code": sym, "error": repr(exc)[:200]})
    (out / "data_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=1))
    return 1 if manifest["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
