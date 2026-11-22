"""Pytest configuration for graceful handling of sibling ``trading`` repository tests.

Tests under ``tests/trading_research/`` and three cross-repo review tests import modules
from the sibling ``trading/backend`` repository. When ``trading/backend`` is accessible
(the normal dual-repo workspace), all tests run unchanged. In isolated single-repo
checkouts, CI, or sandboxes where ``trading/backend`` is unavailable, those tests are
cleanly ignored during collection with an explicit header notice instead of aborting
collection with ImportErrors.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRADING_ROOT = Path(os.environ.get("TRADING_ROOT", ROOT.parent / "trading")).expanduser().resolve()
TRADING_BACKEND = TRADING_ROOT / "backend"

CROSS_REPO_TEST_FILES = {
    "test_cross_market_execution_clock.py",
    "test_def200_cash_manual_review.py",
    "test_strategy_healthcheck_review.py",
}


def _trading_backend_accessible() -> bool:
    try:
        return (
            TRADING_BACKEND.is_dir()
            and os.access(TRADING_BACKEND, os.R_OK | os.X_OK)
            and (TRADING_BACKEND / "portfolio_strategies").is_dir()
        )
    except OSError:
        return False


TRADING_AVAILABLE = _trading_backend_accessible()


def pytest_report_header(config):  # noqa: ARG001
    if not TRADING_AVAILABLE:
        return (
            f"xquant test note: sibling trading repo not accessible at {TRADING_BACKEND}; "
            "skipping cross-repo trading tests (set TRADING_ROOT or run with ../trading present)."
        )
    return None


def pytest_ignore_collect(collection_path: Path, config):  # noqa: ARG001
    if TRADING_AVAILABLE:
        return False
    p = Path(collection_path)
    if p.name in CROSS_REPO_TEST_FILES:
        return True
    if "trading_research" in p.parts:
        return True
    return False
