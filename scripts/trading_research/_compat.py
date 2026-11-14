"""Compatibility helpers for research scripts that reuse trading modules."""

from __future__ import annotations

import sys


def install_pandas_ta_compat() -> None:
    """Expose pandas-ta-classic under the backend's historical import name."""
    try:
        import pandas_ta  # type: ignore[import-not-found]  # noqa: F401
    except ModuleNotFoundError:
        import pandas_ta_classic as pandas_ta

        sys.modules["pandas_ta"] = pandas_ta
