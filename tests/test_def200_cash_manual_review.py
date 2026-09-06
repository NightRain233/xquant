import os
import sys
from pathlib import Path

import pandas as pd
import pytest


XQUANT_ROOT = Path(__file__).resolve().parents[1]
TRADING_BACKEND = Path(os.environ.get("TRADING_ROOT", XQUANT_ROOT.parent / "trading")).expanduser().resolve() / "backend"
for path in (TRADING_BACKEND, XQUANT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.replay_theme_alpha_next_close_v2 import (  # noqa: E402
    _kernel_flow_audit,
    _lot_trade_plan,
    _q8_apply_cap,
)
from scripts.scan_theme_alpha_minimum_capital import (  # noqa: E402
    _evaluate_initial_capital,
    _lot_trade_plan_side_prices,
)


def test_q8_cap_reference_exposes_full_universe_fill():
    result = _q8_apply_cap({"A": 1.0}, ["A", "B", "C"], 0.5)

    assert result == pytest.approx({"A": 0.5, "B": 0.25, "C": 0.25, "CASH": 0.0})


def test_integer_lot_plan_preserves_cash_and_uses_existing_quantities():
    state = {"cash": 3_000.0, "quantities": {"A": 0.0, "B": 0.0}}
    prices = {"A": 4.2, "B": 9.0}
    plan = _lot_trade_plan(
        state,
        prices,
        ("A", "B"),
        {"A": 0.55, "B": 0.30, "CASH": 0.15},
        0.0005,
        0.15,
    )

    assert all(quantity % 100 == 0 for quantity in plan["target_quantities"].values())
    assert plan["cash_after"] >= 0.0
    assert plan["commission"] == pytest.approx(plan["gross_traded"] * 0.0005)


def test_integer_lot_plan_can_sell_existing_lots_without_new_funding():
    state = {"cash": 100.0, "quantities": {"A": 500.0, "B": 0.0}}
    prices = {"A": 4.2, "B": 9.0}
    plan = _lot_trade_plan(
        state,
        prices,
        ("A", "B"),
        {"A": 0.0, "B": 0.0, "CASH": 1.0},
        0.001,
        1.0,
    )

    assert plan["target_quantities"]["A"] == 0.0
    assert plan["target_quantities"]["B"] == 0.0
    assert plan["cash_after"] == pytest.approx(100.0 + 500.0 * 4.2 - plan["commission"])


def test_integer_lot_sell_is_clamped_after_rounding_to_final_trade_limit():
    state = {"cash": 1_400.0, "quantities": {"A": 400.0, "B": 0.0}}
    prices = {"A": 4.225, "B": 9.0}
    plan = _lot_trade_plan(
        state,
        prices,
        ("A", "B"),
        {"A": 0.0, "B": 0.0, "CASH": 1.0},
        0.0005,
        0.15,
    )

    # A naive floor would sell all 400 shares.  The final integer order is
    # clamped to one 100-share lot: 422.50 / 3,090.00 < 15%.
    assert plan["target_quantities"]["A"] == 300.0
    assert plan["actual_trade_ratios"]["A"] == pytest.approx(
        100.0 * 4.225 / 3_090.0
    )
    assert plan["actual_trade_limit_violation_count"] == 0


def test_flow_audit_reconstructs_quantity_and_cash_from_fills():
    kernel = {
        "nav": pd.DataFrame(
            [
                {"valuation_date": "2026-01-01", "cash": 1_000.0},
                {"valuation_date": "2026-01-02", "cash": 579.58},
            ]
        ),
        "positions": pd.DataFrame(
            [
                {"valuation_date": "2026-01-01", "symbol": "A", "quantity": 0.0},
                {"valuation_date": "2026-01-01", "symbol": "CASH", "quantity": 1_000.0},
                {"valuation_date": "2026-01-02", "symbol": "A", "quantity": 100.0},
                {"valuation_date": "2026-01-02", "symbol": "CASH", "quantity": 579.58},
            ]
        ),
        "trades": pd.DataFrame(
            [
                {
                    "execution_date": "2026-01-02",
                    "symbol": "A",
                    "quantity_delta": 100.0,
                    "price": 4.2,
                    "fees": 0.42,
                    "slippage": 0.0,
                }
            ]
        ),
    }

    audit = _kernel_flow_audit(kernel)

    assert audit["kernelQuantityFromTradesMaxAbsError"] == pytest.approx(0.0)
    assert audit["kernelCashFromTradesMaxAbsError"] == pytest.approx(0.0)
    assert audit["kernelQuantityFromTradesViolationCount"] == 0
    assert audit["kernelCashFromTradesViolationCount"] == 0


def test_minimum_capital_snapshot_requires_one_lot_under_final_trade_cap():
    symbols = ("A",)
    prices = {"A": 9.164}
    desired = {"A": 0.50, "CASH": 0.50}
    executable = {"A": 0.15, "CASH": 0.85}

    below_floor = _evaluate_initial_capital(
        6_109,
        prices,
        desired,
        executable,
        symbols,
        0.0005,
        0.0,
        0.0,
    )
    at_floor = _evaluate_initial_capital(
        6_110,
        prices,
        desired,
        executable,
        symbols,
        0.0005,
        0.0,
        0.0,
    )

    assert below_floor["positive_executable_zero_lot_symbols"] == ["A"]
    assert at_floor["positive_executable_zero_lot_symbols"] == []
    assert at_floor["target_quantities"]["A"] == 100.0
    assert at_floor["max_actual_trade_ratio"] <= 0.15


def test_minimum_capital_snapshot_keeps_buy_stress_and_cash_reserve_explicit():
    metrics = _evaluate_initial_capital(
        7_000,
        {"A": 9.164},
        {"A": 0.50, "CASH": 0.50},
        {"A": 0.15, "CASH": 0.85},
        ("A",),
        0.0005,
        0.05,
        0.02,
    )

    assert metrics["execution_prices"]["A"] == pytest.approx(9.6222)
    assert metrics["commission_rate_one_way"] == pytest.approx(0.0005)
    assert metrics["buy_price_up"] == pytest.approx(0.05)
    assert metrics["sell_price_down"] == pytest.approx(0.0)
    assert metrics["cash_reserve"] == pytest.approx(0.02)
    assert metrics["cash_reserve_satisfied"] is True
    assert metrics["cash_after"] >= 140.0


def test_side_specific_price_stress_does_not_raise_sell_proceeds():
    state = {"cash": 100.0, "quantities": {"A": 200.0}}
    plan = _lot_trade_plan_side_prices(
        state,
        {"A": 4.2},
        {"A": 4.2 * 1.05},
        {"A": 4.2 * 0.95},
        ("A",),
        {"A": 0.0, "CASH": 1.0},
        0.0005,
        1.0,
    )

    assert plan["target_quantities"]["A"] == 0.0
    assert plan["cash_after"] == pytest.approx(
        100.0 + 200.0 * 4.2 * 0.95 - plan["commission"]
    )
