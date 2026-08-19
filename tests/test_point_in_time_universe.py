import pandas as pd
import pytest

from xquant.point_in_time_universe import (
    UniverseConfig,
    add_membership_transitions,
    evaluate_snapshot,
    filter_entries_by_membership,
)


def _prices(turnover_scale: float = 1.0) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=8, freq="B")
    return pd.DataFrame({
        "Open": 10.0,
        "High": 11.0,
        "Low": 9.0,
        "Close": 10.0,
        "Volume": 100.0 * turnover_scale,
    }, index=dates)


def _config() -> UniverseConfig:
    return UniverseConfig(
        min_history_sessions=3,
        liquidity_lookback_sessions=3,
        max_suspension_rate=0.0,
        min_data_completeness=1.0,
        liquidity_floors={"us": 1.0},
        market_caps={"us": 1},
    )


def test_snapshot_uses_only_as_of_data_and_ranks_by_liquidity():
    future_winner = _prices(0.5)
    future_winner.loc[future_winner.index[5]:, "Volume"] = 10_000.0
    prices = {"A": _prices(1.0), "B": future_winner}
    calendar = prices["A"].index
    result = evaluate_snapshot(
        prices,
        {"A": "us", "B": "us"},
        {"us": calendar},
        snapshot_date=calendar[4],
        effective_date=calendar[5],
        config=_config(),
    )
    assert result.set_index("symbol").at["A", "selected"]
    assert not result.set_index("symbol").at["B", "selected"]
    assert result["historySessions"].max() == 5


def test_zero_volume_session_counts_as_suspended_not_complete_trading():
    prices = _prices()
    snapshot_date = prices.index[4]
    prices.loc[prices.index[3], "Volume"] = 0.0
    result = evaluate_snapshot(
        {"A": prices},
        {"A": "us"},
        {"us": prices.index},
        snapshot_date=snapshot_date,
        effective_date=prices.index[5],
        config=_config(),
    ).set_index("symbol").loc["A"]
    assert result["historySessions"] == 4
    assert result["completeLookbackSessions"] == 3
    assert result["observedLookbackSessions"] == 2
    assert result["dataCompleteness"] == 1.0
    assert result["suspensionRate"] == pytest.approx(1 / 3)
    assert not result["qualified"]
    assert "excess_suspension_rate" in result["failureReasons"]


def test_official_non_trading_status_overrides_positive_volume():
    prices = _prices()
    prices["isTrading"] = True
    prices.loc[prices.index[3], "isTrading"] = False
    result = evaluate_snapshot(
        {"A": prices},
        {"A": "us"},
        {"us": prices.index},
        snapshot_date=prices.index[4],
        effective_date=prices.index[5],
        config=_config(),
    ).set_index("symbol").loc["A"]
    assert result["observedLookbackSessions"] == 2
    assert result["suspensionRate"] == pytest.approx(1 / 3)
    assert not result["qualified"]


def test_membership_filter_respects_effective_date_and_keeps_old_exit_history():
    membership = pd.DataFrame([
        {"effectiveDate": "2025-01-03", "symbol": "A", "selected": True},
        {"effectiveDate": "2025-02-03", "symbol": "A", "selected": False},
        {"effectiveDate": "2025-02-03", "symbol": "B", "selected": True},
    ])
    entries = pd.DataFrame([
        {"signalDate": "2025-01-02", "symbol": "A"},
        {"signalDate": "2025-01-06", "symbol": "A"},
        {"signalDate": "2025-02-04", "symbol": "A"},
        {"signalDate": "2025-02-04", "symbol": "B"},
    ])
    selected = filter_entries_by_membership(entries, membership)
    assert list(zip(selected["signalDate"], selected["symbol"])) == [
        (pd.Timestamp("2025-01-06"), "A"),
        (pd.Timestamp("2025-02-04"), "B"),
    ]


def test_transition_ledger_records_removal_reason_without_deleting_rows():
    membership = pd.DataFrame([
        {"effectiveDate": "2025-01-03", "symbol": "A", "selected": True, "qualified": True},
        {"effectiveDate": "2025-01-03", "symbol": "B", "selected": False, "qualified": True},
        {"effectiveDate": "2025-02-03", "symbol": "A", "selected": False, "qualified": False},
        {"effectiveDate": "2025-02-03", "symbol": "B", "selected": True, "qualified": True},
    ])
    result = add_membership_transitions(membership)
    events = result.set_index(["effectiveDate", "symbol"])["membershipEvent"]
    assert events.loc[("2025-01-03", "A")] == "entered"
    assert events.loc[("2025-02-03", "A")] == "exited_ineligible"
    assert events.loc[("2025-02-03", "B")] == "entered"
