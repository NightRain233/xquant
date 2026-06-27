"""Trend and volatility indicators shared by research experiments."""

from collections.abc import Sequence

import pandas as pd


def true_range(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
) -> pd.Series:
    """Return the largest intraday or overnight price range for each row."""
    previous_close = close.shift(1)
    ranges = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def supertrend_direction(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    atr_window: int = 10,
    multiplier: float = 3.0,
) -> pd.Series:
    """Return whether each close is above the active SuperTrend line."""
    atr = true_range(high, low, close).rolling(atr_window).mean()
    midpoint = (high + low) / 2.0
    basic_upper = midpoint + multiplier * atr
    basic_lower = midpoint - multiplier * atr
    final_upper = pd.Series(index=close.index, dtype=float)
    final_lower = pd.Series(index=close.index, dtype=float)
    supertrend = pd.Series(index=close.index, dtype=float)
    direction = pd.Series(False, index=close.index, dtype=bool)

    for position in range(len(close)):
        if pd.isna(atr.iloc[position]):
            continue
        if position == 0 or pd.isna(final_upper.iloc[position - 1]):
            final_upper.iloc[position] = basic_upper.iloc[position]
            final_lower.iloc[position] = basic_lower.iloc[position]
            supertrend.iloc[position] = final_upper.iloc[position]
            continue

        previous_close = close.iloc[position - 1]
        previous_upper = final_upper.iloc[position - 1]
        previous_lower = final_lower.iloc[position - 1]
        final_upper.iloc[position] = (
            basic_upper.iloc[position]
            if basic_upper.iloc[position] < previous_upper or previous_close > previous_upper
            else previous_upper
        )
        final_lower.iloc[position] = (
            basic_lower.iloc[position]
            if basic_lower.iloc[position] > previous_lower or previous_close < previous_lower
            else previous_lower
        )

        if supertrend.iloc[position - 1] == previous_upper:
            supertrend.iloc[position] = (
                final_lower.iloc[position]
                if close.iloc[position] > final_upper.iloc[position]
                else final_upper.iloc[position]
            )
        else:
            supertrend.iloc[position] = (
                final_upper.iloc[position]
                if close.iloc[position] < final_lower.iloc[position]
                else final_lower.iloc[position]
            )
        direction.iloc[position] = close.iloc[position] > supertrend.iloc[position]

    return direction.fillna(False)


def select_low_vol_trend(
    close: pd.DataFrame,
    returns: pd.DataFrame,
    date: pd.Timestamp,
    universe: Sequence[str],
    *,
    ma_window: int = 60,
    momentum_window: int = 63,
    volatility_window: int = 60,
    top_n: int = 3,
) -> list[str]:
    """Select upward-trending assets with the lowest recent volatility."""
    location = close.index.get_loc(date)
    warmup = max(ma_window, momentum_window, volatility_window)
    if not isinstance(location, int) or location < warmup:
        return []

    valid = []
    required_prices = max(ma_window, momentum_window + 1)
    for symbol in universe:
        if symbol not in close or symbol not in returns:
            continue
        price_history = close[symbol].iloc[location - required_prices + 1 : location + 1]
        return_history = returns[symbol].iloc[location - volatility_window + 1 : location + 1]
        if price_history.notna().all() and return_history.notna().all():
            valid.append(symbol)
    if not valid:
        return []

    price = close.iloc[location][valid]
    moving_average = close.iloc[location - ma_window + 1 : location + 1][valid].mean()
    momentum = price / close.iloc[location - momentum_window][valid] - 1.0
    volatility = returns.iloc[location - volatility_window + 1 : location + 1][valid].std(ddof=1)
    eligible = price.index[(price > moving_average) & (momentum > 0)]
    return volatility[eligible].sort_values().head(top_n).index.tolist()
