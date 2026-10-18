import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "research_weinstein_quick_checks.py"
SPEC = importlib.util.spec_from_file_location("weinstein_quick_checks", SCRIPT)
quick = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(quick)


def _daily(closes, opens=None):
    index = pd.bdate_range("2024-01-01", periods=len(closes))
    closes = np.asarray(closes, dtype=float)
    opens = closes if opens is None else np.asarray(opens, dtype=float)
    return pd.DataFrame({"Open": opens, "High": np.maximum(opens, closes), "Low": np.minimum(opens, closes),
                         "Close": closes}, index=index)


def test_signal_trades_at_next_open_and_misses_signal_day_move():
    daily = _daily([100, 110, 121], opens=[100, 105, 121])
    hold = pd.Series([0.0, 1.0, 1.0], index=daily.index)

    nav, trades = quick.simulate(daily, hold, cost=0.0)

    # signal on day 2 close; bought at day 3 open (121) which equals day 3 close
    assert trades == 1
    assert nav.iloc[1] == 1.0
    assert nav.iloc[2] == 1.0


def test_cost_is_charged_once_per_switch():
    daily = _daily([100, 100, 100, 100])
    hold = pd.Series([1.0, 1.0, 0.0, 0.0], index=daily.index)

    nav, trades = quick.simulate(daily, hold, cost=0.01)

    assert trades == 2
    assert np.isclose(nav.iloc[-1], 0.99 * 0.99)


def test_weinstein_rule_requires_a_rising_average():
    # a long decline keeps the 30-week average falling; the last week pops above it
    falling_then_pop = pd.Series(list(np.linspace(140, 100, 40)) + [130.0],
                                 index=pd.date_range("2020-01-03", periods=41, freq="W-FRI"))

    weinstein = quick.ma_rule(falling_then_pop, "weinstein")
    plain = quick.ma_rule(falling_then_pop, "filter")

    assert plain.iloc[-1] == 1.0
    assert weinstein.iloc[-1] == 0.0


def test_weekly_bars_skip_holiday_weeks_and_stamp_last_trading_day():
    index = pd.DatetimeIndex(["2024-01-02", "2024-01-05", "2024-01-15", "2024-01-17"])
    daily = pd.DataFrame({"Open": [1.0, 2, 3, 4], "High": [1.0, 2, 3, 4], "Low": [1.0, 2, 3, 4],
                          "Close": [1.0, 2, 3, 4]}, index=index)

    weekly = quick.weekly_bars(daily, "W-FRI")

    assert list(weekly.index) == [pd.Timestamp("2024-01-05"), pd.Timestamp("2024-01-17")]
    assert list(weekly["Close"]) == [2.0, 4.0]
