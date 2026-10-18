"""Verify hashes, then extract the study to a fresh directory and reproduce it."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/three-asset-core-2026-10-03"


def main():
    manifest = json.loads((OUT/"manifest.json").read_text())
    checked = 0
    for group in ["source", "outputs"]:
        for name, expected in manifest[group].items():
            path = ROOT/name if group == "source" or "/" in name else OUT/name
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
            checked += 1
    with tempfile.TemporaryDirectory(prefix="three-core-reproduction-") as temporary:
        work = Path(temporary)
        with zipfile.ZipFile(OUT/"reproduction_bundle.zip") as bundle:
            for name, expected in manifest["bundle_members"].items():
                assert hashlib.sha256(bundle.read(name)).hexdigest() == expected, name
            bundle.extractall(work)
        env = {**os.environ, "PYTHONPATH": str(work/"src")}
        commands = [
            [sys.executable, "-m", "pytest", "tests/test_three_asset_research.py", "-q"],
            [sys.executable, "scripts/review_three_asset_core.py", "--snapshot", "inputs/market_data", "--reference", "inputs/reference"],
            [sys.executable, "scripts/render_three_asset_review.py"],
        ]
        logs = []
        for command in commands:
            result = subprocess.run(command, cwd=work, env=env, text=True, capture_output=True)
            logs.append({"command": command, "returncode": result.returncode,
                         "stdout": result.stdout, "stderr": result.stderr})
            if result.returncode:
                print(json.dumps(logs, indent=2))
                raise RuntimeError("Extracted reproduction failed")
        reproduced = work/"outputs/three-asset-core-2026-10-03"
        count = 0
        for original in OUT.glob("*.csv"):
            fresh = reproduced/original.name
            pd.testing.assert_frame_equal(pd.read_csv(original), pd.read_csv(fresh), rtol=1e-12, atol=1e-10)
            count += 1
        result = {"hashes_checked": checked, "bundle_members_checked": len(manifest["bundle_members"]),
                  "csvs_reproduced": count, "commands": logs, "status": "passed"}
        (OUT/"standalone_verification.json").write_text(json.dumps(result, indent=2))
        print(json.dumps({k: v for k, v in result.items() if k != "commands"}, indent=2))
    # Include verification evidence without recursively hashing the manifest.
    manifest["outputs"]["standalone_verification.json"] = hashlib.sha256((OUT/"standalone_verification.json").read_bytes()).hexdigest()
    (OUT/"manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
