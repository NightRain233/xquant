"""Protect review timing, conservation, and reporting boundaries."""
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("healthcheck", ROOT/"scripts/review_frozen_strategies.py")
review = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = review
spec.loader.exec_module(review)
from portfolio_strategies.market_data import PortfolioMarketData


def test_next_close_does_not_earn_signal_or_execution_day_jump_and_conserves_cash():
    config = review.get_strategy("btc_supertrend_satellite")
    dates = pd.bdate_range("2026-09-07", periods=5)
    close = pd.DataFrame(100., index=dates, columns=config.symbols)
    close["510300.SS"] = [100., 120., 150., 165., 165.]
    market = PortfolioMarketData(close.copy(), close.copy(), close.copy(), close, dates, dates[-1].date(), ())
    nav, events, audit = review.replay(config, market, {dates[1]: {"510300.SS": 1.}})
    assert nav.loc[dates[1], "nav"] == 100_000.
    assert nav.loc[dates[2], "nav"] == pytest.approx(100_000/1.003)
    assert nav.loc[dates[3], "nav"] == pytest.approx(100_000/1.003*1.1)
    assert events.execution_date.tolist() == [str(dates[2].date())]
    assert audit["max_cash_error"] < 1e-5
    stressed, _, _ = review.replay(config, market, {dates[1]: {"510300.SS": 1.}}, extra_cost_bps=20)
    assert stressed.nav.iloc[-1] < nav.nav.iloc[-1]


def test_window_retains_first_return_and_distinguishes_existing_drawdown():
    dates = pd.to_datetime(["2026-08-28", "2026-08-31", "2026-09-01", "2026-09-02"])
    nav = pd.DataFrame({"nav": [120., 100., 110., 105.], "cash_weight": 0., "weight_A": 1.}, index=dates)
    result = review.summarize(nav, "2026-08-31", "2026-09-02")
    assert result["return"] == pytest.approx(.05)
    assert result["max_drawdown"] == pytest.approx(105/110-1)
    assert result["current_drawdown_since_activation"] == pytest.approx(105/120-1)
    assert result["cagr"] is None
    assert result["sharpe_zero_rf"] is None


def test_theme_targets_do_not_change_when_future_prices_change():
    config = review.get_strategy("theme_alpha")
    dates = review.bimonthly_signal_dates
    from portfolio_strategies.schedules import xshg_sessions
    index = xshg_sessions("2025-01-02", "2026-09-30")
    steps = np.arange(len(index))
    close = pd.DataFrame({s: 100*np.exp(.001*steps+.02*np.sin(steps/(10+i))) for i,s in enumerate(config.symbols)}, index=index)
    day = pd.Timestamp("2026-08-25")
    market = PortfolioMarketData(close.copy(), close*1.01, close*.99, close, index, index[-1].date(), ())
    first = review.calculate_theme_alpha(config, market, day.date())
    shocked = close.copy()
    shocked.loc[shocked.index>day] *= .1
    changed = PortfolioMarketData(shocked.copy(), shocked*1.01, shocked*.99, shocked, index, index[-1].date(), ())
    second = review.calculate_theme_alpha(config, changed, day.date())
    assert {x.symbol: x.weight for x in first.target_weights} == {x.symbol: x.weight for x in second.target_weights}
    assert review.builtin(config)["params"]["defense_ma_window"] == 200
