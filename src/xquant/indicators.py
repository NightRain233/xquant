"""Trend and volatility indicators shared by research experiments."""

from collections.abc import Sequence

import numpy as np
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


def ema(close: pd.Series, span: int) -> pd.Series:
    """Strictly causal exponential moving average."""
    return close.astype(float).ewm(span=int(span), adjust=False, min_periods=int(span)).mean()


def dema(close: pd.Series, span: int) -> pd.Series:
    """Double Exponential Moving Average: 2*EMA(N) - EMA(EMA(N), N)."""
    e1 = ema(close, span)
    e2 = e1.ewm(span=int(span), adjust=False, min_periods=int(span)).mean()
    return 2.0 * e1 - e2


def tema(close: pd.Series, span: int) -> pd.Series:
    """Triple Exponential Moving Average: 3*E1 - 3*E2 + E3."""
    e1 = ema(close, span)
    e2 = e1.ewm(span=int(span), adjust=False, min_periods=int(span)).mean()
    e3 = e2.ewm(span=int(span), adjust=False, min_periods=int(span)).mean()
    return 3.0 * e1 - 3.0 * e2 + e3


def zlema(close: pd.Series, span: int) -> pd.Series:
    """Zero-Lag EMA (Ehlers): EMA of de-lagged price 2*P_t - P_{t-lag}, lag=(N-1)//2."""
    n = int(span)
    lag = max(1, (n - 1) // 2)
    adj = 2.0 * close.astype(float) - close.astype(float).shift(lag)
    return adj.ewm(span=n, adjust=False, min_periods=n).mean()


def wma(series: pd.Series, window: int) -> pd.Series:
    """Linearly weighted moving average (weights 1..window)."""
    w = int(window)
    if w <= 1:
        return series.astype(float).copy()
    weights = np.arange(1.0, w + 1.0, dtype=float)
    denom = float(weights.sum())
    arr = series.to_numpy(dtype=float)
    out = np.full(len(arr), np.nan, dtype=float)
    if len(arr) >= w:
        windows = np.lib.stride_tricks.sliding_window_view(arr, w)
        out[w - 1 :] = (windows * weights).sum(axis=1) / denom
    return pd.Series(out, index=series.index, dtype=float)


def hma(close: pd.Series, window: int) -> pd.Series:
    """Hull Moving Average: WMA(2*WMA(N/2) - WMA(N), round(sqrt(N)))."""
    n = max(2, int(window))
    half = max(1, n // 2)
    sqrt_n = max(1, int(round(np.sqrt(n))))
    raw = 2.0 * wma(close, half) - wma(close, n)
    return wma(raw, sqrt_n)


def kama(close: pd.Series, er_window: int = 10, fast: int = 2, slow: int = 30) -> pd.Series:
    """Kaufman Adaptive Moving Average (strictly causal)."""
    arr = close.to_numpy(dtype=float)
    n = len(arr)
    w = int(er_window)
    out = np.full(n, np.nan, dtype=float)
    if n <= w:
        return pd.Series(out, index=close.index, dtype=float)
    fast_sc = 2.0 / (float(fast) + 1.0)
    slow_sc = 2.0 / (float(slow) + 1.0)
    diffs = np.abs(np.diff(arr, prepend=arr[0]))
    out[w] = arr[w]
    for i in range(w + 1, n):
        change = abs(arr[i] - arr[i - w])
        vol = float(diffs[i - w + 1 : i + 1].sum())
        er = change / vol if vol > 1e-12 else 0.0
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
        out[i] = out[i - 1] + sc * (arr[i] - out[i - 1])
    return pd.Series(out, index=close.index, dtype=float)


def rsi_wilder(close: pd.Series, window: int = 14) -> pd.Series:
    """Standard Wilder RSI (0..100, strictly causal)."""
    w = int(window)
    delta = close.astype(float).diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / w, adjust=False, min_periods=w).mean()
    avg_loss = loss.ewm(alpha=1.0 / w, adjust=False, min_periods=w).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    zero_loss = avg_loss == 0.0
    both_zero = zero_loss & (avg_gain == 0.0)
    rsi = rsi.where(~zero_loss, 100.0)
    rsi = rsi.where(~both_zero, 50.0)
    return rsi.where(avg_gain.notna(), np.nan)


def kdj(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    n: int = 9,
    m1: int = 3,
    m2: int = 3,
) -> pd.DataFrame:
    """Standard KDJ stochastic oscillator (returns DataFrame with columns K, D, J)."""
    ll = low.astype(float).rolling(int(n), min_periods=int(n)).min().to_numpy(float)
    hh = high.astype(float).rolling(int(n), min_periods=int(n)).max().to_numpy(float)
    c = close.astype(float).to_numpy(float)
    size = len(c)
    k_arr = np.full(size, np.nan, dtype=float)
    d_arr = np.full(size, np.nan, dtype=float)
    j_arr = np.full(size, np.nan, dtype=float)
    k_prev = 50.0
    d_prev = 50.0
    a1 = 1.0 / float(m1)
    a2 = 1.0 / float(m2)
    for i in range(size):
        if np.isnan(ll[i]) or np.isnan(hh[i]) or np.isnan(c[i]):
            continue
        span = hh[i] - ll[i]
        rsv = (c[i] - ll[i]) / span * 100.0 if span > 1e-12 else 50.0
        k_val = (1.0 - a1) * k_prev + a1 * rsv
        d_val = (1.0 - a2) * d_prev + a2 * k_val
        k_arr[i] = k_val
        d_arr[i] = d_val
        j_arr[i] = 3.0 * k_val - 2.0 * d_val
        k_prev = k_val
        d_prev = d_val
    return pd.DataFrame({"K": k_arr, "D": d_arr, "J": j_arr}, index=close.index)


def bollinger_zscore(close: pd.Series, window: int = 20) -> pd.Series:
    """Rolling population z-score (Close - SMA) / std(ddof=0)."""
    s = close.astype(float)
    ma = s.rolling(int(window), min_periods=int(window)).mean()
    sd = s.rolling(int(window), min_periods=int(window)).std(ddof=0)
    return (s - ma) / sd.replace(0.0, np.nan)
