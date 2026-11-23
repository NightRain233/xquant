import numpy as np
import pandas as pd

from xquant.indicators import (
    bollinger_zscore,
    dema,
    ema,
    hma,
    kama,
    kdj,
    rsi_wilder,
    select_low_vol_trend,
    supertrend_direction,
    tema,
    true_range,
    wma,
    zlema,
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


def test_zero_lag_ma_family_tracks_linear_trend_and_has_zero_lookahead():
    idx = pd.date_range("2024-01-01", periods=120, freq="D")
    # Pure linear ramp: Zero-Lag MAs (ZLEMA, DEMA, TEMA, HMA) should lag much less than plain SMA/EMA
    ramp = pd.Series(np.linspace(100.0, 220.0, len(idx)), index=idx)
    sma20 = ramp.rolling(20).mean()
    e20 = ema(ramp, 20)
    z20 = zlema(ramp, 20)
    d20 = dema(ramp, 20)
    t20 = tema(ramp, 20)
    h20 = hma(ramp, 20)
    k10 = kama(ramp, er_window=10)

    # On a steady linear trend, ZLEMA / DEMA / TEMA / HMA / KAMA are closer to current price than SMA/EMA
    last = ramp.iloc[-1]
    assert abs(last - z20.iloc[-1]) < abs(last - e20.iloc[-1])
    assert abs(last - d20.iloc[-1]) < abs(last - e20.iloc[-1])
    assert abs(last - t20.iloc[-1]) < abs(last - e20.iloc[-1])
    assert abs(last - h20.iloc[-1]) < abs(last - sma20.iloc[-1])
    assert abs(last - k10.iloc[-1]) < abs(last - sma20.iloc[-1])
    assert np.isclose(wma(pd.Series([1.0, 2.0, 3.0]), 3).iloc[-1], (1 * 1 + 2 * 2 + 3 * 3) / 6.0)

    # Strict anti-lookahead perturbation test: mutating prices after t=80 must never change <= 80
    pert = ramp.copy()
    pert.iloc[81:] = 10.0
    for fn in (
        lambda s: ema(s, 20),
        lambda s: dema(s, 20),
        lambda s: tema(s, 20),
        lambda s: zlema(s, 20),
        lambda s: hma(s, 20),
        lambda s: kama(s, 10),
        lambda s: rsi_wilder(s, 14),
        lambda s: bollinger_zscore(s, 20),
    ):
        a = fn(ramp).iloc[:81].to_numpy()
        b = fn(pert).iloc[:81].to_numpy()
        np.testing.assert_allclose(a, b, rtol=0, atol=1e-12, equal_nan=True)


def test_rsi_kdj_and_bollinger_zscore_behave_correctly_and_causally():
    idx = pd.date_range("2024-01-01", periods=80, freq="D")
    # Uptrend then sharp selloff
    vals = np.concatenate([np.linspace(100.0, 140.0, 50), np.linspace(140.0, 95.0, 30)])
    close = pd.Series(vals, index=idx)
    high = close * 1.01
    low = close * 0.99

    r = rsi_wilder(close, 14)
    assert r.iloc[45] > 80.0
    assert r.iloc[-1] < 20.0

    kdf = kdj(high, low, close, n=9, m1=3, m2=3)
    assert kdf["K"].iloc[45] > 80.0
    assert kdf["J"].iloc[-1] < 10.0

    z = bollinger_zscore(close, 20)
    assert z.iloc[45] > 1.0
    assert z.iloc[-1] < -1.0

    # Anti-lookahead on KDJ
    pert_c = close.copy()
    pert_c.iloc[51:] *= 0.5
    kdf_pert = kdj(pert_c * 1.01, pert_c * 0.99, pert_c, n=9, m1=3, m2=3)
    np.testing.assert_allclose(kdf.iloc[:51].to_numpy(), kdf_pert.iloc[:51].to_numpy(), rtol=0, atol=1e-12, equal_nan=True)
