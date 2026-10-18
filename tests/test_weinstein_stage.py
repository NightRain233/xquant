import numpy as np
import pandas as pd
import pytest

from xquant.weinstein_stage import (
    CostModel, StageParams, execution_dates, longest_underwater, run_stage_strategy, run_target_weights,
    stage_signals, weekly_closes,
)

SMALL = StageParams(ma_weeks=3, slope_lag_weeks=1, rs_weeks=2, max_positions=2, slot_weight=0.5)


def make_daily(weekly_paths: dict, start="2024-01-01"):
    """Daily bars (Mon–Fri) where each week's closes all equal the weekly path value; open = close."""
    weeks = len(next(iter(weekly_paths.values())))
    days = pd.bdate_range(start, periods=weeks * 5)
    close = pd.DataFrame({s: np.repeat(v, 5) for s, v in weekly_paths.items()}, index=days, dtype=float)
    return close.copy(), close


def test_weekly_close_uses_last_trading_day_of_week():
    days = pd.DatetimeIndex(["2024-04-01", "2024-04-02", "2024-04-03", "2024-04-08", "2024-04-12"])
    close = pd.DataFrame({"A": [1.0, 2.0, 3.0, 4.0, 5.0]}, index=days)
    weekly = weekly_closes(close)
    assert list(weekly.index) == [pd.Timestamp("2024-04-03"), pd.Timestamp("2024-04-12")]
    assert list(weekly["A"]) == [3.0, 5.0]
    exec_day = execution_dates(weekly.index, days)
    assert exec_day.iloc[0] == pd.Timestamp("2024-04-08") and pd.isna(exec_day.iloc[1])


def test_signals_do_not_change_when_future_prices_change():
    rng = np.random.default_rng(0)
    weekly = pd.DataFrame(np.exp(np.cumsum(rng.normal(0, 0.04, (80, 3)), axis=0)), columns=["B", "X", "Y"],
                          index=pd.date_range("2020-01-03", periods=80, freq="W-FRI"))
    base = stage_signals(weekly, "B", StageParams())
    shocked = weekly.copy()
    shocked.iloc[50:] *= 3.0
    alt = stage_signals(shocked, "B", StageParams())
    for attr in ("buy", "sell", "rs", "ma"):
        pd.testing.assert_frame_equal(getattr(base, attr).iloc[:50], getattr(alt, attr).iloc[:50])


def test_buy_fills_next_open_with_costs_and_ledger_reconciles():
    flat = [10.0] * 12
    up = [10.0] * 4 + [11, 12, 13, 14, 15, 16, 17, 18]
    opens, closes = make_daily({"B": flat, "U": up})
    opens["U"] = closes["U"] + 0.5  # distinguishable open price
    sig = stage_signals(weekly_closes(closes), "B", SMALL)
    first_buy_week = sig.buy["U"].idxmax()
    assert sig.buy["U"].any()
    nav, trades, fills = run_stage_strategy(opens, closes, sig, closes.index[0], SMALL, CostModel())
    fill = fills.iloc[0]
    expected_day = closes.index[closes.index.searchsorted(first_buy_week, side="right")]
    assert fill["date"] == expected_day and fill["side"] == "buy"
    assert fill["fill_price"] == pytest.approx(opens.at[expected_day, "U"] * 1.0005)
    assert fill["quantity"] * fill["fill_price"] * 1.0005 == pytest.approx(0.5)  # 50% slot of 1.0 NAV incl. fee
    assert (nav["cash"] + nav["holdings"] - nav["nav"]).abs().max() < 1e-12
    assert nav["cash"].min() >= 0


def test_candidates_ranked_by_relative_strength_and_capped():
    flat = [10.0] * 10
    paths = {"B": flat,
             "S1": [10.0] * 4 + [11, 12, 13, 14, 15, 16],
             "S2": [10.0] * 4 + [12, 14, 16, 18, 20, 22],
             "S3": [10.0] * 4 + [13, 16, 19, 22, 25, 28]}
    opens, closes = make_daily(paths)
    sig = stage_signals(weekly_closes(closes), "B", SMALL)
    nav, trades, fills = run_stage_strategy(opens, closes, sig, closes.index[0], SMALL, CostModel())
    first_day = fills["date"].min()
    bought = set(fills.loc[fills["date"] == first_day, "symbol"])
    assert bought == {"S3", "S2"}
    assert nav["positions"].max() <= 2


def test_sell_when_close_below_ma_and_round_trip_recorded():
    path = [10.0] * 4 + [12, 14, 16, 18, 9, 9, 9, 9]
    opens, closes = make_daily({"B": [10.0] * 12, "U": path})
    sig = stage_signals(weekly_closes(closes), "B", SMALL)
    nav, trades, fills = run_stage_strategy(opens, closes, sig, closes.index[0], SMALL, CostModel())
    closed = trades[trades["status"] == "closed"]
    assert len(closed) == 1
    assert closed.iloc[0]["exit_date"] > pd.Timestamp(closed.iloc[0]["exit_signal_week"])
    assert nav["positions"].iloc[-1] == 0


def test_target_weights_buy_and_hold_matches_price_path_after_costs():
    opens, closes = make_daily({"B": [10.0, 11, 12, 13]})
    nav, _, _ = run_target_weights(opens, closes, {closes.index[0]: {"B": 1.0}}, closes.index[0], CostModel())
    assert nav["nav"].iloc[-1] == pytest.approx(1.3 / (1.0005 * 1.0005))


def test_longest_underwater_reports_open_and_closed_spells():
    idx = pd.date_range("2024-01-01", periods=6, freq="D")
    recovered = longest_underwater(pd.Series([1.1, 1.0, 0.9, 1.2, 1.3, 1.25], index=idx))
    assert recovered["longest_recovery_days"] == 3 and recovered["longest_recovery_completed"]
    open_spell = longest_underwater(pd.Series([1.1, 1.0, 0.9, 0.95, 1.0, 1.05], index=idx))
    assert open_spell["longest_recovery_days"] == 5 and not open_spell["longest_recovery_completed"]
