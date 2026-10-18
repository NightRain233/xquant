import numpy as np
import pandas as pd

from xquant.three_asset_research import drawdown_events, entry_recovery, replay, rolling_windows


def test_overnight_gap_belongs_to_old_holdings_and_attribution_conserves():
    dates = pd.date_range("2020-01-01", periods=3)
    close = pd.DataFrame([[10., 10.], [10., 10.], [30., 10.]], index=dates)
    opening = pd.DataFrame([[10., 10.], [10., 10.], [20., 10.]], index=dates)
    target = pd.DataFrame([[1., 0.], [0., 1.]], index=dates[1:])
    daily, _, _ = replay(opening, close, target, cost_bps=0)
    # Selling at 20 captures the old holding's overnight doubling, no intraday rally.
    assert daily.nav.iloc[-1] == 200000
    assert daily[0].iloc[-1] == 100000
    assert daily.pnl_residual.abs().max() < 1e-8


def test_actual_gross_fees_and_native_half_turnover_are_distinct():
    dates = pd.date_range("2020-01-01", periods=3)
    price = pd.DataFrame(10., index=dates, columns=["a", "b"])
    target = pd.DataFrame([[1., 0.], [0., 1.]], index=dates[1:], columns=price.columns)
    native, _, _ = replay(price, price, target)
    gross, _, trades = replay(price, price, target, cost_mode="gross")
    assert np.isclose(native.cost.iloc[-1], 99.9)
    assert gross.cost.iloc[-1] > 199
    for day, group in trades.groupby("date"):
        assert np.isclose((group.quantity_delta.abs()*group.open).sum()*.001, gross.loc[day, "cost"])
    assert gross.pnl_residual.abs().max() < 1e-8


def test_unrecovered_drawdown_is_censored_not_zero_duration():
    nav = pd.Series([100., 80., 100., 90., 85.], index=pd.date_range("2020-01-01", periods=5))
    events = drawdown_events(nav)
    assert events.censored.tolist() == [False, True]
    assert events.underwater_calendar_days.tolist() == [2, 2]
    assert pd.isna(events.recovery.iloc[-1])
    entries = entry_recovery(nav)
    assert entries.censored.tolist() == [False, False, True, True]


def test_rolling_uses_actual_calendar_year_and_prior_available_close():
    dates = pd.to_datetime(["2015-01-01", "2015-01-05", "2018-01-04", "2018-01-05"])
    nav = pd.Series([100., 110., 90., 121.], index=dates)
    result = rolling_windows(nav, 3)
    assert result.start.tolist() == [dates[0], dates[1]]
    np.testing.assert_allclose(result.total_return, [-.1, .1])
