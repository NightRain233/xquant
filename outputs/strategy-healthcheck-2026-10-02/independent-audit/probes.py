"""Offline counterexamples; writes no accounts or original review artifacts.

Run from xquant with ../trading/backend/.venv/bin/python <this file>.
"""
import importlib.util
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import review_frozen_strategies as review
from portfolio_strategies.market_data import PortfolioMarketData


def btc_execution_probe():
    config = review.get_strategy("btc_supertrend_satellite")
    dates = pd.bdate_range("2026-09-07", periods=6)
    targets = {
        dates[1]: {"510300.SS": 0.925, "BTC-USD": 0.075},
        dates[3]: {"510300.SS": 0.8, "BTC-USD": 0.075, "CASH": 0.125},
    }
    rows = []
    for btc_close in (100.0, 200.0):
        close = pd.DataFrame(100.0, index=dates, columns=config.symbols)
        close.loc[dates[4]:, "BTC-USD"] = btc_close
        market = PortfolioMarketData(
            close, close, close, close, dates, dates[-1].date(), ()
        )
        nav, events, _ = review.replay(config, market, targets)
        row = nav.loc[dates[4]]
        rows.append({
            "btc_utc_close_later_than_etf_close": btc_close,
            "etf_quantity_at_same_label_close": row.nav * row["weight_510300.SS"] / 100,
            "gross_nav": float(events.iloc[1].gross_nav),
        })
    assert rows[0]["etf_quantity_at_same_label_close"] != rows[1]["etf_quantity_at_same_label_close"]
    return rows


def multi_asset_open_probe():
    path = ROOT.parent / "trading/scripts/research_multi_asset_balanced_portfolio.py"
    spec = importlib.util.spec_from_file_location("multi_asset_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    date = pd.Timestamp("2026-09-01")
    rows = []
    for us_open in (100.0, 200.0):
        frames = {
            symbol: pd.DataFrame({"Open": [price], "Close": [price]}, index=[date])
            for symbol, price in (("510300.SS", 100.0), ("SPY", us_open))
        }
        state = {"cash": 0.0, "shares": {"510300.SS": 1.0, "SPY": 1.0},
                 "lastPrices": {}, "costPaid": 0.0}
        result = module.rebalance_at_open(
            state, {"510300.SS": 0.5, "SPY": 0.5}, frames, date, 0.0, 0.0
        )
        rows.append({"later_us_open": us_open,
                     "earlier_a_share_open_quantity": result["shares"]["510300.SS"]})
    assert rows[0]["earlier_a_share_open_quantity"] != rows[1]["earlier_a_share_open_quantity"]
    return rows


if __name__ == "__main__":
    print(json.dumps({
        "scope": "Fixed synthetic targets, not strategy tuning or corrected performance estimates",
        "btc_execution": btc_execution_probe(),
        "multi_asset_execution": multi_asset_open_probe(),
    }, indent=2))
