"""Single-asset position rules: weekly Bollinger bands and trailing dividend yield.

Pure helpers for the dividend-low-vol timing research. Rules plug into
``style_combo.run_backtest``: the asset is column ``a``, the remainder sits in
cash, and every signal uses closes up to and including its own day only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from xquant.style_combo import Signal, is_period_end, is_week_end


def weekly_band_levels(close: pd.Series, window: int = 20, k: float = 2.0) -> pd.DataFrame:
    """Bollinger bands on weekly closes (population std), indexed by each week's last trading day."""
    grouped = close.groupby(close.index.to_period("W-SUN"))
    weekly = pd.Series(grouped.last().to_numpy(), index=grouped.tail(1).index, dtype=float)
    mid = weekly.rolling(window).mean()
    std = weekly.rolling(window).std(ddof=0)
    return pd.DataFrame({"close": weekly, "mid": mid, "upper": mid + k * std, "lower": mid - k * std}).dropna()


def daily_band_levels(close: pd.Series, window: int = 20, k: float = 2.0) -> pd.DataFrame:
    """Bands as seen each day: the last ``window - 1`` finished weeks plus today's close as the forming week."""
    weeks = close.index.to_period("W-SUN")
    rows = {}
    finished: list[float] = []
    for j, (date, value) in enumerate(close.items()):
        if len(finished) >= window - 1:
            sample = np.array(finished[-(window - 1):] + [float(value)]) if window > 1 else np.array([float(value)])
            m, s = sample.mean(), sample.std(ddof=0)
            rows[date] = {"close": float(value), "mid": m, "upper": m + k * s, "lower": m - k * s}
        if j + 1 < len(close) and weeks[j] != weeks[j + 1]:
            finished.append(float(value))
    return pd.DataFrame.from_dict(rows, orient="index")


def band_zone(close: float, upper: float, lower: float, near: float = 0.02) -> str | None:
    """"lower"/"upper" when within ``near`` of a band, "both" when the bands are too tight to tell apart."""
    at_lower = close <= lower * (1 + near)
    at_upper = close >= upper * (1 - near)
    if at_lower and at_upper:
        return "both"
    if at_lower:
        return "lower"
    return "upper" if at_upper else None


def trailing_dividend_yield(total_return: pd.Series, price: pd.Series, window: int = 252) -> pd.Series:
    """Dividends actually paid over the last ``window`` trading days, as total-return growth over price growth."""
    return (total_return / total_return.shift(window)) / (price / price.shift(window)) - 1.0


def expanding_percentile(series: pd.Series, min_periods: int = 756) -> pd.Series:
    """Rank of each value within its own history so far (0-1], NaN until ``min_periods`` observations."""
    return series.dropna().expanding(min_periods).rank(pct=True).reindex(series.index)


def rolling_percentile(series: pd.Series, window: int = 1260) -> pd.Series:
    """Rank of each value within the last ``window`` observations, NaN until the window is full."""
    return series.dropna().rolling(window).rank(pct=True).reindex(series.index)


def _weight_signal(weight: float) -> dict[str, float]:
    return {"a": float(weight), "b": 0.0}


def rule_all_in_out(levels: pd.DataFrame, dates: pd.DatetimeIndex, start_i: int, near: float = 0.02,
                    start_held: bool = False) -> Signal:
    """100% when near the lower band, 0% when near the upper band, otherwise keep the current position."""
    rows = levels.to_dict("index")
    state = {"weight": 1.0 if start_held else 0.0}

    def sig(i):
        previous = state["weight"]
        row = rows.get(dates[i])
        if row is not None:
            zone = band_zone(row["close"], row["upper"], row["lower"], near)
            if zone == "lower":
                state["weight"] = 1.0
            elif zone == "upper":
                state["weight"] = 0.0
        if i == start_i or state["weight"] != previous:
            return _weight_signal(state["weight"])
        return None
    return sig


def rule_core_tilt(levels: pd.DataFrame, dates: pd.DatetimeIndex, start_i: int, near: float = 0.02,
                   base: float = 0.7, high: float = 1.0, low: float = 0.5) -> Signal:
    """``high`` near the lower band and ``low`` near the upper band; back to ``base`` on crossing the middle band."""
    rows = levels.to_dict("index")
    state = {"weight": base}

    def sig(i):
        previous = state["weight"]
        row = rows.get(dates[i])
        if row is not None:
            zone = band_zone(row["close"], row["upper"], row["lower"], near)
            if zone == "lower":
                state["weight"] = high
            elif zone == "upper":
                state["weight"] = low
            elif zone is None:
                if previous == high and row["close"] >= row["mid"]:
                    state["weight"] = base
                elif previous == low and row["close"] <= row["mid"]:
                    state["weight"] = base
        if i == start_i or state["weight"] != previous:
            return _weight_signal(state["weight"])
        return None
    return sig


def rule_yield_tilt(percentile: pd.Series, dates: pd.DatetimeIndex, start_i: int, high_pct: float = 0.7,
                    low_pct: float = 0.3, base: float = 0.7, high: float = 1.0, low: float = 0.5) -> Signal:
    """Weekly: ``high`` when the yield percentile is high, ``low`` when low, else (or without history) ``base``."""
    values = percentile.reindex(dates).to_numpy(float)
    state = {"weight": base}

    def sig(i):
        previous = state["weight"]
        if i == start_i or is_week_end(dates, i):
            p = values[i]
            if np.isnan(p):
                state["weight"] = base
            elif p >= high_pct:
                state["weight"] = high
            elif p <= low_pct:
                state["weight"] = low
            else:
                state["weight"] = base
        if i == start_i or state["weight"] != previous:
            return _weight_signal(state["weight"])
        return None
    return sig


def rule_fixed_weight(weight: float, dates: pd.DatetimeIndex, start_i: int, freq: str = "Q") -> Signal:
    """Constant exposure rebalanced at each period end; the comparator for a rule's average position."""
    def sig(i):
        if i == start_i or is_period_end(dates, i, freq):
            return _weight_signal(weight)
        return None
    return sig


def timing_placebo(positions: pd.Series, asset_returns: pd.Series, cash_annual: float = 0.02,
                   min_shift: int = 60) -> dict:
    """Compare a position path with every circular time shift of itself (no costs, same time in the market).

    ``positions`` are end-of-day weights, so each day's return uses the previous day's weight.
    """
    days = positions.index.to_series().diff().dt.days.fillna(0).to_numpy()
    cash = (1.0 + cash_annual) ** (days / 365.0) - 1.0
    asset = asset_returns.reindex(positions.index).fillna(0.0).to_numpy(float)
    weights = positions.to_numpy(float)
    years = (positions.index[-1] - positions.index[0]).days / 365.25

    def score(path: np.ndarray) -> tuple[float, float]:
        held = np.concatenate([[path[0]], path[:-1]])
        nav = np.cumprod(1.0 + held * asset + (1.0 - held) * cash)
        return float(nav[-1] ** (1.0 / years) - 1.0), float((nav / np.maximum.accumulate(nav) - 1.0).min())

    actual_ann, actual_dd = score(weights)
    n = len(weights)
    shifted = [score(np.roll(weights, s)) for s in range(min_shift, n - min_shift + 1)]
    ann = np.array([s[0] for s in shifted])
    dd = np.array([s[1] for s in shifted])
    return {"actual_annualized": actual_ann, "placebo_median_annualized": float(np.median(ann)),
            "placebo_p95_annualized": float(np.quantile(ann, 0.95)), "share_placebo_ge_actual": float((ann >= actual_ann).mean()),
            "actual_max_drawdown": actual_dd, "placebo_median_max_drawdown": float(np.median(dd)),
            "share_placebo_dd_ge_actual": float((dd >= actual_dd).mean()), "n_shifts": len(shifted)}
