import pandas as pd
import pytest

from xquant.defensive_overlay import (
    CorePortfolioConfig,
    align_nav_to_calendar,
    combine_core_satellite,
    filter_entries_by_market_ma,
    run_inverse_volatility_core,
)


def _price_frame(close_values, open_values=None):
    close = pd.Series(close_values, dtype=float)
    open_ = pd.Series(open_values if open_values is not None else close_values, dtype=float)
    index = pd.date_range("2025-01-01", periods=len(close), freq="B")
    return pd.DataFrame({
        "Open": open_.to_numpy(),
        "High": pd.concat([open_, close], axis=1).max(axis=1).to_numpy() + 1.0,
        "Low": pd.concat([open_, close], axis=1).min(axis=1).to_numpy() - 1.0,
        "Close": close.to_numpy(),
        "Volume": 1000.0,
    }, index=index)


def test_market_ma_gate_uses_latest_completed_reference_close_only():
    reference = _price_frame([10.0, 10.0, 12.0, 1.0])
    entries = pd.DataFrame([
        {"signalDate": reference.index[2], "symbol": "A", "market": "us"},
    ])
    selected, audit = filter_entries_by_market_ma(
        entries,
        {"SPY": reference},
        {"us": "SPY"},
        window=3,
    )
    assert selected["symbol"].tolist() == ["A"]
    assert audit.loc[0, "referenceDate"] == reference.index[2]
    assert audit.loc[0, "riskOn"]


def test_market_ma_gate_blocks_below_ma_and_missing_history():
    reference = _price_frame([10.0, 10.0, 8.0])
    entries = pd.DataFrame([
        {"signalDate": reference.index[1], "symbol": "EARLY", "market": "us"},
        {"signalDate": reference.index[2], "symbol": "BELOW", "market": "us"},
    ])
    selected, audit = filter_entries_by_market_ma(
        entries, {"SPY": reference}, {"us": "SPY"}, window=3
    )
    assert selected.empty
    assert audit["gateReason"].tolist() == [
        "insufficient_reference_history", "market_at_or_below_ma",
    ]


def test_inverse_volatility_core_waits_for_next_open_to_apply_target():
    prices = {
        "A": _price_frame([100 + i for i in range(8)]),
        "B": _price_frame([100 + 2 * i for i in range(8)]),
    }
    result = run_inverse_volatility_core(
        prices,
        ["A", "B"],
        start=pd.Timestamp("2025-01-01"),
        end=pd.Timestamp("2025-01-10"),
        config=CorePortfolioConfig(
            initial_capital=1_000.0,
            volatility_window=2,
            rebalance_sessions=1,
            one_way_cost_bps=0.0,
        ),
    )
    weights = result["weights"].set_index("date")
    assert weights.iloc[2][["A", "B"]].sum() == 0.0
    assert weights.iloc[3][["A", "B"]].sum() == 1.0


def test_inverse_volatility_core_drifts_weights_between_rebalances():
    dates = pd.date_range("2025-01-01", periods=5, freq="B")

    def frame(close):
        close = pd.Series(close, index=dates, dtype=float)
        open_ = close.shift(1).fillna(close.iloc[0])
        return pd.DataFrame({
            "Open": open_,
            "High": pd.concat([open_, close], axis=1).max(axis=1) + 1.0,
            "Low": pd.concat([open_, close], axis=1).min(axis=1) - 1.0,
            "Close": close,
            "Volume": 1_000.0,
        })

    result = run_inverse_volatility_core(
        {
            "A": frame([100.0, 101.0, 103.0, 104.0, 114.0]),
            "B": frame([100.0, 99.0, 97.0, 96.0, 96.0]),
        },
        ["A", "B"],
        start=dates[3],
        end=dates[4],
        config=CorePortfolioConfig(
            initial_capital=1_000.0,
            volatility_window=2,
            rebalance_sessions=10,
            one_way_cost_bps=0.0,
        ),
    )
    weights = result["weights"].set_index("date")
    first_close = weights.loc[dates[3], ["A", "B"]]
    portfolio_factor = first_close["A"] * (114.0 / 104.0) + first_close["B"]
    expected_a_weight = first_close["A"] * (114.0 / 104.0) / portfolio_factor

    assert weights.loc[dates[4], "A"] == pytest.approx(expected_a_weight)
    assert weights.loc[dates[4], "A"] > first_close["A"]
    assert result["nav"].set_index("date").loc[dates[4], "tradedNotional"] == 0.0


def test_inverse_volatility_core_charges_turnover_from_drifted_open_weights():
    dates = pd.date_range("2025-01-01", periods=5, freq="B")

    def frame(close, open_):
        close = pd.Series(close, index=dates, dtype=float)
        open_ = pd.Series(open_, index=dates, dtype=float)
        return pd.DataFrame({
            "Open": open_,
            "High": pd.concat([open_, close], axis=1).max(axis=1) + 1.0,
            "Low": pd.concat([open_, close], axis=1).min(axis=1) - 1.0,
            "Close": close,
            "Volume": 1_000.0,
        })

    result = run_inverse_volatility_core(
        {
            "A": frame(
                [100.0, 101.0, 103.0, 103.0, 113.0],
                [100.0, 100.0, 101.0, 103.0, 113.0],
            ),
            "B": frame(
                [100.0, 99.0, 97.0, 97.0, 97.0],
                [100.0, 100.0, 99.0, 97.0, 97.0],
            ),
        },
        ["A", "B"],
        start=dates[3],
        end=dates[4],
        config=CorePortfolioConfig(
            initial_capital=1_000.0,
            volatility_window=2,
            rebalance_sessions=1,
            one_way_cost_bps=0.0,
        ),
    )
    weights = result["weights"].set_index("date")
    nav = result["nav"].set_index("date")
    prior_close = weights.loc[dates[3]]
    gap_factors = pd.Series({"A": 113.0 / 103.0, "B": 1.0, "CASH": 1.0})
    open_contributions = prior_close * gap_factors
    open_weights = open_contributions / open_contributions.sum()
    target = weights.loc[dates[4]]
    expected_turnover = float((target - open_weights).abs().sum() / 2.0)
    value_after_gap = float(nav.loc[dates[3], "nav"] * open_contributions.sum())

    assert nav.loc[dates[4], "tradedNotional"] == pytest.approx(
        value_after_gap * expected_turnover
    )


def test_core_satellite_rebalances_to_frozen_budget():
    dates = pd.date_range("2025-01-01", periods=3, freq="B")

    def nav(returns):
        values = (1.0 + pd.Series(returns, index=dates)).cumprod() * 1_000.0
        return pd.DataFrame({
            "date": dates, "nav": values.to_numpy(), "return": returns,
            "cash": 0.0, "marketValue": values.to_numpy(), "grossExposure": 1.0,
            "positionCount": 1, "tradedNotional": 0.0,
        })

    result = combine_core_satellite(
        nav([0.0, 0.0, 0.0]),
        nav([0.0, 1.0, 0.0]),
        core_weight=0.8,
        rebalance_dates=pd.DatetimeIndex([dates[2]]),
        sleeve_rebalance_cost_bps=0.0,
    )
    weights = result["weights"].set_index("date")
    assert weights.loc[dates[1], "satelliteWeight"] > 0.2
    assert weights.loc[dates[2], "satelliteWeight"] == pytest.approx(0.2)


def test_align_nav_preserves_initial_capital_before_first_active_session():
    dates = pd.date_range("2025-01-01", periods=3, freq="B")
    source = pd.DataFrame([{
        "date": dates[1], "nav": 990.0, "return": -0.01, "cash": 0.0,
        "marketValue": 990.0, "grossExposure": 1.0, "positionCount": 2,
        "tradedNotional": 1_000.0,
    }])
    aligned = align_nav_to_calendar(source, dates).set_index("date")
    assert aligned.at[dates[0], "nav"] == pytest.approx(1_000.0)
    assert aligned.at[dates[0], "grossExposure"] == 0.0
    assert aligned.at[dates[1], "return"] == pytest.approx(-0.01)
