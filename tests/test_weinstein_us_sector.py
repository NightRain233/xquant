"""Tests for the parts added for the US sector-ETF Weinstein review (engine itself: test_weinstein_stage.py)."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from xquant.weinstein_stage import (
    CostModel, StageParams, cash_growth_from_yield, load_yfinance_csv, run_stage_strategy, run_target_weights,
    weekly_closes,
)

ROOT = Path(__file__).resolve().parents[1]


def _load_script():
    spec = importlib.util.spec_from_file_location("research_weinstein_us_sector",
                                                  ROOT / "scripts" / "research_weinstein_us_sector.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_yfinance_csv_keeps_exchange_date_and_adjusted_columns(tmp_path):
    path = tmp_path / "x.csv"
    path.write_text("Date,Open,High,Low,Close,Volume,Dividends,Stock Splits,Capital Gains\n"
                    "2024-03-08 00:00:00-05:00,10.0,11,9,10.5,100,0.0,0.0,0.0\n"
                    "2024-03-11 00:00:00-04:00,10.6,11,9,10.8,100,0.1,0.0,0.0\n")
    frame = load_yfinance_csv(path)
    assert list(frame.index) == [pd.Timestamp("2024-03-08"), pd.Timestamp("2024-03-11")]  # DST change ignored
    assert list(frame.columns) == ["open", "close"]
    assert frame.loc["2024-03-11", "open"] == 10.6


def test_cash_growth_uses_previous_day_yield_and_calendar_gap():
    calendar = pd.DatetimeIndex(["2024-01-05", "2024-01-08", "2024-01-09"])  # Fri, Mon, Tue
    yields = pd.Series([5.0, 99.0, 4.0], index=calendar)  # Monday's spike must not affect Monday
    g = cash_growth_from_yield(yields, calendar)
    assert g.iloc[0] == 1.0
    assert g.iloc[1] == pytest.approx(1.05 ** (3 / 365))
    assert g.iloc[2] == pytest.approx(1.99 ** (1 / 365))


def test_cash_growth_floors_negative_yield_and_ffills_gaps():
    calendar = pd.DatetimeIndex(["2024-01-02", "2024-01-03", "2024-01-04"])
    yields = pd.Series([-0.1, 3.0], index=pd.DatetimeIndex(["2023-12-29", "2024-01-03"]))
    g = cash_growth_from_yield(yields, calendar)
    assert g.iloc[1] == 1.0  # 2024-01-02 yield is the ffilled -0.1 -> floored at 0
    assert g.iloc[2] == pytest.approx(1.03 ** (1 / 365))


def test_cash_growth_accrues_on_idle_cash_only():
    days = pd.bdate_range("2024-01-01", periods=10)
    closes = pd.DataFrame({"B": np.linspace(10, 11, 10)}, index=days)
    opens = closes.copy()
    growth = pd.Series(1.001, index=days)
    # all cash: grows by 1.001 per day after the first
    nav_cash, _, _ = run_target_weights(opens, closes, {}, days[0], CostModel(), cash_growth=growth)
    assert nav_cash["nav"].iloc[-1] == pytest.approx(1.001 ** 9)
    assert (nav_cash["cash"] + nav_cash["holdings"] - nav_cash["nav"]).abs().max() < 1e-12
    # fully invested from day one: the yield has no effect
    full = {days[0]: {"B": 1.0}}
    a, _, _ = run_target_weights(opens, closes, full, days[0], CostModel(), cash_growth=growth)
    b, _, _ = run_target_weights(opens, closes, full, days[0], CostModel())
    assert a["nav"].iloc[-1] == pytest.approx(b["nav"].iloc[-1])


def test_stage_strategy_default_cash_is_zero_and_yield_only_adds():
    days = pd.bdate_range("2024-01-01", periods=60)
    rng = np.random.default_rng(1)
    closes = pd.DataFrame(np.exp(np.cumsum(rng.normal(0, 0.02, (60, 3)), axis=0)) * 10, index=days, columns=["B", "U", "V"])
    opens = closes.shift(1).fillna(closes)
    p = StageParams(ma_weeks=3, slope_lag_weeks=1, rs_weeks=2, max_positions=2, slot_weight=0.5)
    script = _load_script()
    sig = script.stage_signals(weekly_closes(closes), "B", p)
    base, _, fills = run_stage_strategy(opens, closes, sig, days[0], p, CostModel())
    same, _, _ = run_stage_strategy(opens, closes, sig, days[0], p, CostModel(), cash_growth=pd.Series(1.0, index=days))
    pd.testing.assert_frame_equal(base, same)
    more, _, fills2 = run_stage_strategy(opens, closes, sig, days[0], p, CostModel(), cash_growth=pd.Series(1.0002, index=days))
    assert list(fills["symbol"]) == list(fills2["symbol"])  # same decisions
    assert (more["nav"] >= base["nav"] - 1e-12).all()


def test_script_never_buys_the_benchmark_and_starts_when_nine_are_ready():
    script = _load_script()
    weeks = pd.date_range("2000-01-07", periods=60, freq="W-FRI")
    rng = np.random.default_rng(2)
    cols = ["SPY", *script.SECTORS]
    weekly = pd.DataFrame(np.exp(np.cumsum(rng.normal(0.003, 0.03, (60, len(cols))), axis=0)), index=weeks, columns=cols)
    weekly.loc[:weeks[45], ["XLRE", "XLC"]] = np.nan  # late listings
    sig = script.signals_for(weekly, StageParams())
    assert not sig.buy["SPY"].any()
    assert not sig.eligible.loc[:weeks[45], ["XLRE", "XLC"]].any().any()
    calendar = pd.bdate_range(weeks[0] - pd.Timedelta(days=4), weeks[-1] + pd.Timedelta(days=3))
    start, ready = script.first_exec_day(weekly, sig, calendar)
    assert ready == weeks[33]  # 30-week MA + 4-week slope lag
    assert start == ready + pd.Timedelta(days=3)  # next Monday
