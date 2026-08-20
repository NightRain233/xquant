import pandas as pd

from xquant.signal_portfolio import (
    PortfolioConfig,
    decision_entries,
    performance_metrics,
    run_signal_portfolio,
)


def _prices() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 105.0, 103.0, 99.0],
            "High": [101.0, 106.0, 106.0, 104.0, 100.0],
            "Low": [99.0, 100.0, 102.0, 98.0, 97.0],
            "Close": [100.0, 105.0, 103.0, 99.0, 98.0],
            "ST_Dir": [-1, 1, 1, -1, -1],
        },
        index=pd.date_range("2026-01-05", periods=5, freq="B"),
    )


def _entries() -> pd.DataFrame:
    return pd.DataFrame([{
        "signalDate": pd.Timestamp("2026-01-05"),
        "symbol": "TEST",
        "market": "us",
        "setup": "breakout",
        "score": 1,
        "maxAcceptablePrice": 102.0,
    }])


def test_portfolio_executes_on_next_session_and_exits_after_bearish_close():
    result = run_signal_portfolio(
        _entries(),
        {"TEST": _prices()},
        start=pd.Timestamp("2026-01-05"),
        end=pd.Timestamp("2026-01-09"),
        config=PortfolioConfig(
            initial_capital=1_000.0,
            commission_bps=0,
            slippage_bps=0,
            max_position_weight=1.0,
            max_concurrent_positions=1,
        ),
    )
    trade = result["trades"].iloc[0]
    assert trade["entryDate"] == pd.Timestamp("2026-01-06")
    assert trade["entryPrice"] == 101.0
    assert trade["exitDate"] == pd.Timestamp("2026-01-09")
    assert trade["exitPrice"] == 99.0


def test_bearish_exit_waits_for_next_session_with_valid_open():
    prices = _prices().reindex(pd.date_range("2026-01-05", periods=6, freq="B"))
    prices.loc[pd.Timestamp("2026-01-09"), "Open"] = float("nan")
    prices.loc[pd.Timestamp("2026-01-12"), ["Open", "High", "Low", "Close", "ST_Dir"]] = [
        97.0, 99.0, 96.0, 98.0, -1.0,
    ]
    result = run_signal_portfolio(
        _entries(),
        {"TEST": prices},
        start=pd.Timestamp("2026-01-05"),
        end=pd.Timestamp("2026-01-12"),
        config=PortfolioConfig(
            initial_capital=1_000.0,
            commission_bps=0,
            slippage_bps=0,
            max_position_weight=1.0,
            max_concurrent_positions=1,
        ),
    )
    trade = result["trades"].iloc[0]
    assert trade["exitDate"] == pd.Timestamp("2026-01-12")
    assert trade["exitPrice"] == 97.0
    sells = result["orders"].query("side == 'sell' and status == 'executed'")
    assert sells["date"].tolist() == [pd.Timestamp("2026-01-12")]


def test_maximum_price_and_concurrency_rejections_are_auditable():
    entries = pd.concat([
        _entries().assign(maxAcceptablePrice=100.0),
        _entries().assign(symbol="OTHER", maxAcceptablePrice=102.0),
    ], ignore_index=True)
    result = run_signal_portfolio(
        entries,
        {"TEST": _prices(), "OTHER": _prices()},
        start=pd.Timestamp("2026-01-05"),
        end=pd.Timestamp("2026-01-09"),
        config=PortfolioConfig(
            initial_capital=1_000.0,
            commission_bps=0,
            slippage_bps=0,
            max_position_weight=1.0,
            max_concurrent_positions=1,
        ),
    )
    assert set(result["rejections"]["reason"]) == {
        "above_max_acceptable_price",
    }
    assert result["orders"].query("side == 'buy' and status == 'executed'")["symbol"].tolist() == ["OTHER"]


def test_open_entry_sizing_does_not_use_existing_holdings_same_day_close():
    dates = pd.date_range("2026-01-05", periods=4, freq="B")
    entries = pd.DataFrame([
        {
            "signalDate": dates[0], "symbol": "A", "market": "us",
            "setup": "breakout", "score": 1, "maxAcceptablePrice": float("nan"),
        },
        {
            "signalDate": dates[1], "symbol": "B", "market": "us",
            "setup": "breakout", "score": 1, "maxAcceptablePrice": float("nan"),
        },
    ])

    def frame(closes):
        return pd.DataFrame({
            "Open": [100.0] * 4,
            "High": [201.0] * 4,
            "Low": [99.0] * 4,
            "Close": closes,
            "ST_Dir": [1.0] * 4,
        }, index=dates)

    config = PortfolioConfig(
        initial_capital=1_000.0,
        commission_bps=0,
        slippage_bps=0,
        max_position_weight=0.20,
        max_concurrent_positions=10,
    )
    notionals = []
    for current_close in (100.0, 200.0):
        result = run_signal_portfolio(
            entries,
            {
                "A": frame([100.0, 100.0, current_close, current_close]),
                "B": frame([100.0] * 4),
            },
            start=dates[0],
            end=dates[-1],
            config=config,
        )
        notionals.append(float(
            result["orders"].query("symbol == 'B' and status == 'executed'").iloc[0]["notional"]
        ))

    assert notionals == [200.0, 200.0]


def test_decision_variants_are_frozen_filters():
    decisions = pd.DataFrame([
        {
            "decisionDate": "2026-01-05", "symbol": "A", "market": "us",
            "setup": "breakout", "permission": "watch", "readinessScore": 1,
            "maxAcceptablePrice": 10.0, "dataStale": False, "dataGap": False,
        },
        {
            "decisionDate": "2026-01-05", "symbol": "B", "market": "us",
            "setup": "breakout", "permission": "buy", "readinessScore": 2,
            "maxAcceptablePrice": 10.0, "dataStale": False, "dataGap": False,
        },
        {
            "decisionDate": "2026-01-05", "symbol": "C", "market": "us",
            "setup": "pullback", "permission": "buy", "readinessScore": 3,
            "maxAcceptablePrice": 10.0, "dataStale": False, "dataGap": False,
        },
    ])
    assert len(decision_entries(decisions, "all_bull_flip")) == 2
    assert decision_entries(decisions, "all_bull_flip")["maxAcceptablePrice"].isna().all()
    assert decision_entries(decisions, "breakout_right_side_5")["symbol"].tolist() == ["B"]
    assert set(decision_entries(decisions, "breakout_plus_pullback")["symbol"]) == {"B", "C"}


def test_performance_metrics_include_costs_turnover_and_utilization():
    result = run_signal_portfolio(
        _entries(),
        {"TEST": _prices()},
        start=pd.Timestamp("2026-01-05"),
        end=pd.Timestamp("2026-01-09"),
        config=PortfolioConfig(
            initial_capital=1_000.0,
            commission_bps=5,
            slippage_bps=5,
            max_position_weight=1.0,
            max_concurrent_positions=1,
        ),
    )
    metrics = performance_metrics(result["nav"], result["trades"])
    assert metrics["closedTrades"] == 1
    assert metrics["totalTurnover"] > 1.9
    assert metrics["maxPositionCount"] == 1
    assert metrics["endNav"] < 1_000.0
