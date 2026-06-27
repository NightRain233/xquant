"""Performance-series helpers shared by research experiments."""

import pandas as pd


def nav_from_returns(
    returns: pd.Series,
    *,
    initial_capital: float = 100.0,
) -> pd.Series:
    """Compound periodic returns into a net asset value series."""
    return (1.0 + returns.fillna(0.0)).cumprod() * initial_capital


def drawdown_series(
    nav: pd.Series,
    *,
    initial_capital: float = 100.0,
) -> pd.Series:
    """Calculate drawdown while treating initial capital as the first peak."""
    nav = nav.dropna()
    if nav.empty:
        return nav
    peak = nav.cummax().clip(lower=initial_capital)
    return nav / peak - 1.0
