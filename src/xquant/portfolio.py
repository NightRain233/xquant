"""Portfolio-weighting helpers shared by research experiments."""

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd


def normalize_weights(
    weights: Mapping[str, float],
    universe: Sequence[str],
) -> dict[str, float]:
    """Return non-negative asset weights plus an explicit cash balance."""
    clean = {symbol: float(max(0.0, weights.get(symbol, 0.0))) for symbol in universe}
    total = sum(clean.values())
    if total > 1.0 + 1e-12:
        clean = {symbol: value / total for symbol, value in clean.items()}
        total = 1.0
    clean["CASH"] = max(0.0, 1.0 - total)
    return clean


def apply_weight_cap(
    weights: Mapping[str, float],
    universe: Sequence[str],
    cap: float | None = None,
) -> dict[str, float]:
    """Apply a per-asset cap and redistribute feasible excess weight."""
    if cap is None:
        return normalize_weights(weights, universe)

    values = pd.Series(
        {symbol: max(0.0, weights.get(symbol, 0.0)) for symbol in universe},
        dtype=float,
    )
    total = values.sum()
    if total <= 0:
        return normalize_weights({}, universe)

    values /= total
    cap = float(cap)
    for _ in range(30):
        over = values > cap + 1e-12
        if not over.any():
            break
        excess = (values[over] - cap).sum()
        values[over] = cap
        under = values < cap - 1e-12
        capacity = (cap - values[under]).clip(lower=0.0)
        if excess <= 1e-12 or capacity.sum() <= 1e-12:
            break
        base = values[under].clip(lower=0.0)
        allocation = base / base.sum() if base.sum() > 1e-12 else capacity / capacity.sum()
        addition = np.minimum(excess * allocation, capacity)
        values.loc[addition.index] += addition

    return normalize_weights(values.to_dict(), universe)


def inverse_volatility_weights(
    returns: pd.DataFrame,
    universe: Sequence[str],
    cap: float | None = None,
) -> dict[str, float]:
    """Allocate assets inversely to sample volatility."""
    available = [symbol for symbol in universe if symbol in returns.columns]
    volatility = returns[available].std(ddof=1).replace(0, np.nan).dropna()
    volatility = volatility[volatility > 0]
    if volatility.empty:
        return normalize_weights({}, universe)

    inverse = 1.0 / volatility
    raw = (inverse / inverse.sum()).to_dict()
    return apply_weight_cap(raw, universe, cap)
