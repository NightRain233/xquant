#!/usr/bin/env python3
"""Run a migrated trading research script from one stable entry point."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts" / "trading_research"


def available_scripts() -> list[str]:
    return sorted(
        path.stem for path in SCRIPT_DIR.glob("*.py") if path.name != "_compat.py"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script", nargs="?", choices=available_scripts())
    parser.add_argument("args", nargs=argparse.REMAINDER)
    parser.add_argument("--list", action="store_true", help="list available research scripts")
    options = parser.parse_args()
    if options.list:
        print("\n".join(available_scripts()))
        return 0
    if not options.script:
        parser.error("choose a script or use --list")

    command = [sys.executable, str(SCRIPT_DIR / f"{options.script}.py"), *options.args]
    env = os.environ.copy()
    env.setdefault("TRADING_ROOT", str(ROOT.parent / "trading"))
    return subprocess.call(command, cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
