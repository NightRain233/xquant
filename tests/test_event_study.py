import pandas as pd

from xquant.event_study import EventStudyConfig, attach_forward_outcomes, summarize_events


def _prices() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [100, 102, 104, 103, 105, 106],
            "High": [101, 105, 106, 106, 108, 109],
            "Low": [99, 101, 102, 100, 104, 105],
            "Close": [100, 104, 105, 102, 107, 108],
        },
        index=pd.date_range("2026-01-01", periods=6, freq="B"),
    )


def _decision(**overrides) -> dict:
    row = {
        "symbol": "TEST",
        "decisionDate": "2026-01-01",
        "setup": "breakout",
        "permission": "buy",
        "stage": "breakout_confirmed",
        "dataStale": False,
        "dataGap": False,
        "maxAcceptablePrice": 103.0,
        "triggerPrice": None,
        "invalidationPrice": None,
        "stVal": 98.0,
    }
    row.update(overrides)
    return row


def test_buy_uses_next_open_and_respects_maximum_price():
    decisions = pd.DataFrame([
        _decision(),
        _decision(decisionDate="2026-01-02", maxAcceptablePrice=101.0),
    ])
    events = attach_forward_outcomes(
        decisions,
        lambda _: _prices(),
        config=EventStudyConfig(horizons=(2,), round_trip_cost_bps=20, independent_gap_sessions=1),
    )
    assert events.iloc[0]["executionOutcome"] == "executed"
    assert events.iloc[0]["entryPrice"] == 102.0
    assert round(events.iloc[0]["netReturn2Pct"], 6) == round((105 / 102 - 1) * 100 - 0.2, 6)
    assert events.iloc[1]["executionOutcome"] == "above_max"
    assert pd.isna(events.iloc[1]["entryPrice"])


def test_compression_daily_bar_marks_unknown_trigger_invalidation_order_ambiguous():
    decisions = pd.DataFrame([
        _decision(
            setup="compression_breakout",
            permission="conditional",
            stage="breakout_armed",
            triggerPrice=104.0,
            maxAcceptablePrice=106.0,
            invalidationPrice=101.5,
        )
    ])
    events = attach_forward_outcomes(decisions, lambda _: _prices())
    assert events.iloc[0]["executionOutcome"] == "ambiguous_intraday_order"
    assert pd.isna(events.iloc[0]["entryPrice"])


def test_summary_can_restrict_to_deoverlapped_events():
    decisions = pd.DataFrame([
        _decision(decisionDate="2026-01-01"),
        _decision(decisionDate="2026-01-02"),
    ])
    events = attach_forward_outcomes(
        decisions,
        lambda _: _prices(),
        config=EventStudyConfig(horizons=(2,), independent_gap_sessions=3),
    )
    summary = summarize_events(events, horizons=(2,))
    assert summary.iloc[0]["eventCount"] == 1
