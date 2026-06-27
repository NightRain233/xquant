import numpy as np
import pandas as pd

from xquant.indicators import (
    select_low_vol_trend,
    supertrend_direction,
    true_range,
)


def test_true_range_includes_overnight_gaps():
    high = pd.Series([10.0, 12.0, 11.0])
    low = pd.Series([8.0, 9.0, 7.0])
    close = pd.Series([9.0, 10.0, 8.0])

    result = true_range(high, low, close)

    assert result.tolist() == [2.0, 3.0, 4.0]


def test_supertrend_stays_off_during_warmup_then_detects_uptrend():
    index = pd.date_range("2026-01-01", periods=6)
    high = pd.Series([10, 11, 12, 13, 14, 15], index=index, dtype=float)
    low = pd.Series([9, 10, 11, 12, 13, 14], index=index, dtype=float)
    close = pd.Series([9.5, 10.5, 11.5, 12.5, 13.5, 14.5], index=index)

    direction = supertrend_direction(high, low, close, atr_window=2, multiplier=1.0)

    assert direction.tolist() == [False, False, False, True, True, True]


def test_low_vol_trend_requires_trend_and_momentum_then_selects_lowest_volatility():
    index = pd.date_range("2026-01-01", periods=70)
    step = np.arange(70)
    close = pd.DataFrame(
        {
            "SMOOTH": np.linspace(100, 112, 70),
            "CHOPPY": np.linspace(100, 120, 70) + np.sin(step) * 4,
            "STEADY": np.linspace(100, 116, 70) + np.sin(step) * 0.4,
            "FALLING": np.linspace(120, 90, 70),
        },
        index=index,
    )
    returns = close.pct_change()

    selected = select_low_vol_trend(close, returns, index[-1], close.columns, top_n=2)

    assert selected == ["SMOOTH", "STEADY"]
