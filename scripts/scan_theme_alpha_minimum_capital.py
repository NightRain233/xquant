"""Measure fixed-budget feasibility for the current Theme Alpha contract.

This is an isolated, read-only feasibility snapshot for the existing
``Core80 + LVT20 + Def200 Cash`` strategy.  It fetches a dated TickFlow
snapshot without writing ``trading/backend/data`` and reuses the current
``PortfolioPaperEngine`` weight-limit decisions plus the v2 integer-lot plan.

The output includes a 6,000/8,000/10,000 CNY comparison plus a diagnostic
frontier.  It does not turn a selected budget into a recommendation or require
historical rebalance errors to stay within an arbitrary tolerance.  No strategy
parameters or research artifacts are changed.
"""
from __future__ import annotations

import os

import argparse
from datetime import date, datetime, time, timedelta
import json
import math
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TRADING_ROOT = Path(os.environ.get("TRADING_ROOT", ROOT.parent / "trading")).expanduser().resolve()
TRADING_BACKEND = TRADING_ROOT / "backend"
if str(TRADING_BACKEND) not in sys.path:
    sys.path.insert(0, str(TRADING_BACKEND))

from portfolio_strategies.market_data import build_portfolio_market_data  # noqa: E402
from portfolio_strategies.paper_engine import PortfolioPaperEngine  # noqa: E402
from portfolio_strategies.registry import get_strategy  # noqa: E402

from scripts.replay_theme_alpha_next_close_v2 import (  # noqa: E402
    COMMISSION_RATES,
    LOT_SIZE,
    _date,
    _json,
    _lot_trade_plan,
    _valid_calculations,
    _weights_from_calculation,
    _weights_from_state,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")
SNAPSHOT_START = date(2021, 7, 1)
DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "def200-cash-minimum-capital-2026-09-06-v2"
MAX_ASSET_TRADE = 0.15
DEFENDED_CORE_SYMBOLS = ("510300.SS", "513100.SS")
FIXED_BUDGETS = (6_000, 8_000, 10_000)
BASE_COMMISSION_RATE = 0.0005
FIXED_BUDGET_CASH_RESERVE = 0.02
WEIGHT_TOLERANCES = (0.05, 0.03, 0.02, 0.01)
# A price stress is side-specific.  The old script raised both buy and sell
# prices through one ``price_buffer`` field, which was not a conservative
# execution model.  The frontier keeps buy-side stress scenarios and leaves
# sell prices at the market close; the fixed-budget report also runs an
# explicitly asymmetric buy-up/sell-down sensitivity.
BUY_PRICE_UPS = (0.0, 0.05, 0.10)
CASH_RESERVES = (0.0, 0.02, 0.05)
CAPITAL_SCAN_MAX = 100_000
PATH_FRONTIER_SCENARIOS = (
    # commission, buy price up, sell price down, first-build reserve
    (BASE_COMMISSION_RATE, 0.0, 0.0, 0.0),
    (BASE_COMMISSION_RATE, 0.05, 0.05, 0.02),
)
PATH_COARSE_STEP = 100
FIXED_BUDGET_PRICE_SCENARIOS = (
    ("close_base", 0.0, 0.0),
    ("asymmetric_5pct", 0.05, 0.05),
)


def _engine_adapter() -> PortfolioPaperEngine:
    """Build an adapter for the stateless decision methods on the paper engine."""
    return PortfolioPaperEngine.__new__(PortfolioPaperEngine)


def _fetch_fresh_snapshot(config, as_of_date: date):
    """Fetch a complete, isolated market snapshot through the existing adapter."""
    # Keep data-provider dependencies lazy so pure frontier helpers remain
    # testable in the lighter xquant environment.
    from analysis_data import _fetch_tickflow_daily_batch

    start = datetime.combine(SNAPSHOT_START, time(0), tzinfo=SHANGHAI)
    end = datetime.combine(
        as_of_date + timedelta(days=1), time(0), tzinfo=SHANGHAI
    )
    frames = _fetch_tickflow_daily_batch(
        list(config.symbols),
        start,
        end,
        request_key=(
            f"minimum-capital-snapshot-{as_of_date.isoformat()}-"
            f"{datetime.now(SHANGHAI).strftime('%Y%m%dT%H%M%S')}"
        ),
    )
    missing = [symbol for symbol in config.symbols if symbol not in frames]
    if missing:
        raise RuntimeError(f"Fresh TickFlow snapshot is missing symbols: {missing}")

    common_end = min(
        pd.DatetimeIndex(frames[symbol].index).tz_localize(None).normalize().max()
        for symbol in config.symbols
    ).date()
    market_data = build_portfolio_market_data(
        config,
        frames,
        datetime.combine(as_of_date, time(16, 0), tzinfo=SHANGHAI),
    )
    if market_data.blocked:
        diagnostics = [diagnostic.__dict__ for diagnostic in market_data.diagnostics]
        raise RuntimeError("Fresh snapshot was blocked: " + _json(diagnostics))
    return frames, market_data, common_end


def _load_isolated_snapshot(config, input_root: Path):
    """Load a previously saved isolated snapshot without a new API request."""
    snapshot_root = input_root / "market_snapshot"
    frames = {
        symbol: pd.read_parquet(snapshot_root / f"{symbol}.parquet")
        for symbol in config.symbols
    }
    common_end = min(
        pd.DatetimeIndex(frames[symbol].index).tz_localize(None).normalize().max()
        for symbol in config.symbols
    ).date()
    market_data = build_portfolio_market_data(
        config,
        frames,
        datetime.combine(common_end, time(16, 0), tzinfo=SHANGHAI),
    )
    if market_data.blocked:
        diagnostics = [diagnostic.__dict__ for diagnostic in market_data.diagnostics]
        raise RuntimeError("Saved snapshot was blocked: " + _json(diagnostics))
    return frames, market_data, common_end


def _initial_state(capital: float, symbols) -> dict:
    return {
        "cash": float(capital),
        "quantities": {symbol: 0.0 for symbol in symbols},
    }


def _side_execution_prices(
    mark_prices: dict[str, float],
    buy_price_up: float,
    sell_price_down: float,
) -> tuple[dict[str, float], dict[str, float]]:
    """Return buy and sell prices without changing the strategy's mark price.

    ``buy_price_up`` and ``sell_price_down`` are independent, one-sided
    execution stresses.  A zero value means execution at the dated Close.
    The strategy target and NAV remain marked at ``mark_prices``.
    """
    buy_prices = {
        symbol: float(price) * (1.0 + float(buy_price_up))
        for symbol, price in mark_prices.items()
    }
    sell_prices = {
        symbol: float(price) * (1.0 - float(sell_price_down))
        for symbol, price in mark_prices.items()
    }
    return buy_prices, sell_prices


def _lot_trade_plan_side_prices(
    state,
    mark_prices: dict[str, float],
    buy_prices: dict[str, float],
    sell_prices: dict[str, float],
    symbols,
    executable: dict[str, float],
    commission_rate: float,
    max_asset_trade: float,
):
    """Plan integer lots with distinct buy/sell execution prices.

    Target weights are converted to lots using the dated Close (the strategy
    mark), while cash flow and the 15% final-order cap use the corresponding
    side's execution price.  This keeps price stress separate from the
    strategy's signal and valuation contract.
    """
    current_quantities = dict(state["quantities"])
    gross_nav = float(
        state["cash"]
        + sum(
            float(current_quantities.get(symbol, 0.0)) * float(mark_prices[symbol])
            for symbol in symbols
        )
    )
    if gross_nav <= 0.0:
        raise ValueError("Integer-lot plan has non-positive marked NAV")
    max_trade_notional = float(max_asset_trade) * gross_nav
    max_buy_delta_lots = {
        symbol: math.floor(
            max_trade_notional / float(buy_prices[symbol]) / LOT_SIZE + 1e-12
        )
        for symbol in symbols
    }
    max_sell_delta_lots = {
        symbol: math.floor(
            max_trade_notional / float(sell_prices[symbol]) / LOT_SIZE + 1e-12
        )
        for symbol in symbols
    }

    target_quantities = dict(current_quantities)
    estimated_fee = 0.0
    for _ in range(20):
        target_quantities = {}
        for symbol in symbols:
            current_quantity = float(current_quantities.get(symbol, 0.0))
            floored_target = math.floor(
                max(0.0, float(executable.get(symbol, 0.0)))
                * max(0.0, gross_nav - estimated_fee)
                / float(mark_prices[symbol])
                / LOT_SIZE
            ) * LOT_SIZE
            lower_bound = current_quantity - max_sell_delta_lots[symbol] * LOT_SIZE
            upper_bound = current_quantity + max_buy_delta_lots[symbol] * LOT_SIZE
            target_quantities[symbol] = min(
                max(floored_target, lower_bound),
                upper_bound,
            )

        gross_traded = 0.0
        for symbol in symbols:
            delta = target_quantities[symbol] - current_quantities.get(symbol, 0.0)
            if delta >= 0.0:
                gross_traded += delta * float(buy_prices[symbol])
            else:
                gross_traded += -delta * float(sell_prices[symbol])
        updated_fee = gross_traded * float(commission_rate)
        if abs(updated_fee - estimated_fee) < 1e-8:
            estimated_fee = updated_fee
            break
        estimated_fee = updated_fee

    def cash_after(plan):
        buys = 0.0
        sells = 0.0
        for symbol in symbols:
            delta = plan[symbol] - current_quantities.get(symbol, 0.0)
            if delta >= 0.0:
                buys += delta * float(buy_prices[symbol])
            else:
                sells += -delta * float(sell_prices[symbol])
        traded = buys + sells
        fee = traded * float(commission_rate)
        return float(state["cash"]) + sells - buys - fee, traded, fee

    funding_adjustment_lots = 0
    while True:
        cash_after_value, gross_traded, fee = cash_after(target_quantities)
        if cash_after_value >= -1e-8:
            break
        candidates = [
            symbol
            for symbol in symbols
            if target_quantities[symbol] - current_quantities.get(symbol, 0.0)
            >= LOT_SIZE
        ]
        if not candidates:
            raise ValueError("Integer-lot plan cannot fund its commission without capital")
        symbol = max(
            candidates,
            key=lambda item: (
                target_quantities[item] - current_quantities.get(item, 0.0),
                item,
            ),
        )
        target_quantities[symbol] -= LOT_SIZE
        funding_adjustment_lots += 1

    cash_after_value, gross_traded, fee = cash_after(target_quantities)
    actual_trade_ratios = {}
    for symbol in symbols:
        delta = abs(target_quantities[symbol] - current_quantities.get(symbol, 0.0))
        execution_price = (
            float(buy_prices[symbol])
            if target_quantities[symbol] >= current_quantities.get(symbol, 0.0)
            else float(sell_prices[symbol])
        )
        actual_trade_ratios[symbol] = delta * execution_price / gross_nav
    return {
        "target_quantities": target_quantities,
        "gross_traded": gross_traded,
        "commission": fee,
        "cash_after": cash_after_value,
        "funding_adjustment_lots": funding_adjustment_lots,
        "max_asset_trade_notional": max_trade_notional,
        "actual_trade_ratios": actual_trade_ratios,
        "max_actual_trade_ratio": max(actual_trade_ratios.values(), default=0.0),
        "actual_trade_limit_violation_count": sum(
            ratio > float(max_asset_trade) + 1e-10
            for ratio in actual_trade_ratios.values()
        ),
    }


def _evaluate_initial_capital(
    capital: int,
    prices: dict[str, float],
    desired: dict[str, float],
    executable: dict[str, float],
    symbols,
    commission_rate: float,
    buy_price_up: float,
    cash_reserve: float,
    max_asset_trade: float = MAX_ASSET_TRADE,
    *,
    sell_price_down: float = 0.0,
) -> dict:
    """Evaluate an all-cash first build using the real integer-lot planner."""
    mark_prices = {symbol: float(price) for symbol, price in prices.items()}
    buy_prices, sell_prices = _side_execution_prices(
        mark_prices, buy_price_up, sell_price_down
    )
    state = _initial_state(capital, symbols)
    plan = _lot_trade_plan_side_prices(
        state,
        mark_prices,
        buy_prices,
        sell_prices,
        symbols,
        executable,
        commission_rate,
        max_asset_trade,
    )
    after_state = {
        "cash": plan["cash_after"],
        "quantities": plan["target_quantities"],
    }
    actual_weights, post_nav, values = _weights_from_state(
        after_state, mark_prices, symbols
    )
    positive_target_zero = [
        symbol
        for symbol in symbols
        if float(desired.get(symbol, 0.0)) > 1e-12
        and after_state["quantities"].get(symbol, 0.0) < LOT_SIZE - 1e-12
    ]
    positive_executable_zero = [
        symbol
        for symbol in symbols
        if float(executable.get(symbol, 0.0)) > 1e-12
        and after_state["quantities"].get(symbol, 0.0) < LOT_SIZE - 1e-12
    ]
    all_symbols = (*symbols, "CASH")
    max_error_vs_executable = max(
        abs(
            float(actual_weights.get(symbol, 0.0))
            - float(executable.get(symbol, 0.0))
        )
        for symbol in all_symbols
    )
    max_error_vs_desired = max(
        abs(float(actual_weights.get(symbol, 0.0)) - float(desired.get(symbol, 0.0)))
        for symbol in all_symbols
    )
    reserve_amount = float(capital) * float(cash_reserve)
    return {
        "capital": int(capital),
        "commission_rate_one_way": float(commission_rate),
        "buy_price_up": float(buy_price_up),
        "sell_price_down": float(sell_price_down),
        "mark_prices": mark_prices,
        "buy_execution_prices": buy_prices,
        "sell_execution_prices": sell_prices,
        # Kept as a compatibility alias for older local consumers.  New
        # reports use the explicit side-specific fields above.
        "execution_prices": buy_prices,
        "cash_reserve": float(cash_reserve),
        "target_quantities": plan["target_quantities"],
        "actual_weights": actual_weights,
        "values": values,
        "post_nav": float(post_nav),
        "cash_after": float(plan["cash_after"]),
        "cash_after_ratio_of_initial": float(plan["cash_after"] / capital),
        "reserve_amount": reserve_amount,
        "cash_reserve_satisfied": bool(plan["cash_after"] + 1e-8 >= reserve_amount),
        "gross_traded": float(plan["gross_traded"]),
        "commission": float(plan["commission"]),
        "funding_adjustment_lots": int(plan["funding_adjustment_lots"]),
        "max_actual_trade_ratio": float(plan["max_actual_trade_ratio"]),
        "actual_trade_limit_violation_count": int(
            plan["actual_trade_limit_violation_count"]
        ),
        "positive_target_zero_lot_symbols": positive_target_zero,
        "positive_executable_zero_lot_symbols": positive_executable_zero,
        "positive_target_zero_lot_count": len(positive_target_zero),
        "positive_executable_zero_lot_count": len(positive_executable_zero),
        "max_abs_weight_error_vs_executable": float(max_error_vs_executable),
        "max_abs_weight_error_vs_desired": float(max_error_vs_desired),
        "evidence_class": "VERIFIED_LATEST_MARKET_SNAPSHOT",
    }


def _scenario_id(
    commission_rate: float,
    buy_price_up: float,
    cash_reserve: float,
    sell_price_down: float = 0.0,
) -> str:
    return (
        f"fee_{commission_rate:.4f}_buyup_{buy_price_up:.2f}"
        f"_selldown_{sell_price_down:.2f}"
        f"_reserve_{cash_reserve:.2f}"
    )


def _latest_frontier(
    config,
    latest_prices: dict[str, float],
    desired: dict[str, float],
    executable: dict[str, float],
    *,
    scan_max: int = CAPITAL_SCAN_MAX,
):
    """Find exact integer-CNY first-build frontiers for each explicit scenario."""
    positive_symbols = [
        symbol
        for symbol in config.symbols
        if float(desired.get(symbol, 0.0)) > 1e-12
    ]
    rows = []
    allocation_rows = []
    scenario_metrics = {}
    for commission_rate in COMMISSION_RATES:
        for buy_price_up in BUY_PRICE_UPS:
            for cash_reserve in CASH_RESERVES:
                scenario = _scenario_id(commission_rate, buy_price_up, cash_reserve)
                stressed_lot_floor = max(
                    latest_prices[symbol] * (1.0 + buy_price_up) * LOT_SIZE
                    / MAX_ASSET_TRADE
                    for symbol in positive_symbols
                )
                hard_floor = max(1, math.ceil(stressed_lot_floor - 1e-9))
                found: dict[float, tuple[int, dict]] = {}
                for capital in range(hard_floor, scan_max + 1):
                    metrics = _evaluate_initial_capital(
                        capital,
                        latest_prices,
                        desired,
                        executable,
                        config.symbols,
                        commission_rate,
                        buy_price_up,
                        cash_reserve,
                    )
                    if (
                        metrics["positive_target_zero_lot_count"] == 0
                        and metrics["positive_executable_zero_lot_count"] == 0
                        and metrics["actual_trade_limit_violation_count"] == 0
                        and metrics["cash_reserve_satisfied"]
                    ):
                        for tolerance in WEIGHT_TOLERANCES:
                            if (
                                tolerance not in found
                                and metrics["max_abs_weight_error_vs_executable"]
                                <= tolerance + 1e-12
                            ):
                                found[tolerance] = (capital, metrics)
                    if len(found) == len(WEIGHT_TOLERANCES):
                        break

                for tolerance in WEIGHT_TOLERANCES:
                    capital_metrics = found.get(tolerance)
                    capital = capital_metrics[0] if capital_metrics else None
                    metrics = capital_metrics[1] if capital_metrics else None
                    row = {
                        "scenario_id": scenario,
                        "basis": "latest_complete_snapshot_first_build",
                        "commission_rate_one_way": float(commission_rate),
                        "buy_price_up": float(buy_price_up),
                        "sell_price_down": 0.0,
                        "cash_reserve": float(cash_reserve),
                        "weight_error_tolerance": float(tolerance),
                        "hard_one_lot_15pct_floor": hard_floor,
                        "minimum_capital_cny": capital,
                        "frontier_found": capital is not None,
                        "evidence_class": "VERIFIED_LATEST_MARKET_SNAPSHOT",
                    }
                    if metrics is not None:
                        row.update(
                            {
                                "post_nav": metrics["post_nav"],
                                "cash_after": metrics["cash_after"],
                                "cash_after_ratio_of_initial": metrics[
                                    "cash_after_ratio_of_initial"
                                ],
                                "gross_traded": metrics["gross_traded"],
                                "commission": metrics["commission"],
                                "positive_target_zero_lot_count": metrics[
                                    "positive_target_zero_lot_count"
                                ],
                                "positive_executable_zero_lot_count": metrics[
                                    "positive_executable_zero_lot_count"
                                ],
                                "max_actual_trade_ratio": metrics[
                                    "max_actual_trade_ratio"
                                ],
                                "max_abs_weight_error_vs_executable": metrics[
                                    "max_abs_weight_error_vs_executable"
                                ],
                                "max_abs_weight_error_vs_desired": metrics[
                                    "max_abs_weight_error_vs_desired"
                                ],
                                "funding_adjustment_lots": metrics[
                                    "funding_adjustment_lots"
                                ],
                            }
                        )
                        for symbol in (*config.symbols, "CASH"):
                            actual_weight = metrics["actual_weights"].get(symbol, 0.0)
                            target_weight = desired.get(symbol, 0.0)
                            executable_weight = executable.get(symbol, 0.0)
                            allocation_rows.append(
                                {
                                    "scenario_id": scenario,
                                    "weight_error_tolerance": float(tolerance),
                                    "minimum_capital_cny": capital,
                                    "symbol": symbol,
                                    "target_weight": float(target_weight),
                                    "executable_weight": float(executable_weight),
                                    "actual_weight": float(actual_weight),
                                    "actual_minus_executable": float(
                                        actual_weight - executable_weight
                                    ),
                                    "actual_minus_target": float(
                                        actual_weight - target_weight
                                    ),
                                    "quantity": (
                                        None
                                        if symbol == "CASH"
                                        else float(metrics["target_quantities"].get(symbol, 0.0))
                                    ),
                                        "execution_price": (
                                            None
                                            if symbol == "CASH"
                                            else float(metrics["buy_execution_prices"][symbol])
                                        ),
                                    "cash_after": float(metrics["cash_after"]),
                                    "evidence_class": metrics["evidence_class"],
                                }
                            )
                    rows.append(row)
                scenario_metrics[scenario] = {
                    "hardFloor": hard_floor,
                    "frontiers": {
                        str(tolerance): (
                            found[tolerance][0] if tolerance in found else None
                        )
                        for tolerance in WEIGHT_TOLERANCES
                    },
                }
    return pd.DataFrame(rows), pd.DataFrame(allocation_rows), scenario_metrics


def _issue_duration_rows(event_rows):
    """Group an issue across consecutive rebalance events."""
    issues = sorted(
        {
            issue
            for row in event_rows
            for issue in row.get("issues", [])
        }
    )
    compact = []
    for issue in issues:
        issue_rows = [row for row in event_rows if issue in row.get("issues", [])]
        group = []
        groups = []
        previous_index = None
        for row in issue_rows:
            if previous_index is None or row["event_index"] == previous_index + 1:
                group.append(row)
            else:
                groups.append(group)
                group = [row]
            previous_index = row["event_index"]
        if group:
            groups.append(group)
        for group in groups:
            compact.append(
                {
                    "issue": issue,
                    "event_count": len(group),
                    "first_signal_date": group[0]["signal_date"],
                    "last_execution_date": group[-1]["execution_date"],
                    "calendar_days_inclusive": (
                        pd.Timestamp(group[-1]["execution_date"])
                        - pd.Timestamp(group[0]["signal_date"])
                    ).days
                    + 1,
                }
            )
    return compact


def _historical_path_check(
    config,
    market_data,
    calculations,
    capital: int,
    commission_rate: float,
    buy_price_up: float,
    cash_reserve: float,
    *,
    sell_price_down: float = 0.0,
):
    """Check a candidate amount against the fresh-data historical event path."""
    adapter = _engine_adapter()
    state = _initial_state(capital, config.symbols)
    execution_by_signal = {}
    for calculation in calculations:
        signal_timestamp = pd.Timestamp(calculation.signal_date)
        location = int(market_data.sessions.get_loc(signal_timestamp))
        if location + 1 < len(market_data.sessions):
            execution_by_signal[calculation.signal_date] = market_data.sessions[
                location + 1
            ].date()

    counts = {
        "signal_count": len(calculations),
        "execution_event_count": 0,
        "executed_event_count": 0,
        "skipped_event_count": 0,
        "positive_executable_zero_lot_event_count": 0,
        "positive_target_zero_lot_event_count": 0,
        "actual_trade_limit_violation_count": 0,
        "one_lot_sell_capital_blocked_event_count": 0,
        "one_lot_sell_capital_blocked_symbol_count": 0,
        "defense_sell_event_count": 0,
        "defense_sell_symbol_count": 0,
        "defense_one_lot_sell_capital_blocked_event_count": 0,
        "defense_one_lot_sell_capital_blocked_symbol_count": 0,
        "cash_shortfall_adjustment_event_count": 0,
        "funding_adjustment_lots": 0,
        "lot_rounding_event_count": 0,
        "strategy_stepwise_cap_asset_count": 0,
    }
    zero_lot_rows = []
    event_rows = []
    max_weight_error = 0.0
    max_weight_error_vs_desired = 0.0
    max_trade_ratio = 0.0
    max_one_lot_sell_ratio = 0.0
    max_defense_one_lot_sell_ratio = 0.0
    minimum_cash = float(capital)
    minimum_cash_ratio = 1.0
    first_build_cash = None
    total_commission = 0.0
    total_traded = 0.0

    for event_index, calculation in enumerate(calculations):
        execution_date = execution_by_signal.get(calculation.signal_date)
        if execution_date is None:
            continue
        timestamp = pd.Timestamp(execution_date)
        base_prices = {
            symbol: float(market_data.close.at[timestamp, symbol])
            for symbol in config.symbols
        }
        current_weights, gross_nav, _ = _weights_from_state(
            state, base_prices, config.symbols
        )
        desired = _weights_from_calculation(calculation)
        should_execute, turnover = adapter._should_execute(
            config, current_weights, desired
        )
        counts["execution_event_count"] += 1
        issues = []
        event_row = {
            "event_index": event_index,
            "signal_date": calculation.signal_date.isoformat(),
            "execution_date": execution_date.isoformat(),
            "turnover_from_current": float(turnover),
            "issues": issues,
            "evidence_class": "VERIFIED_LATEST_MARKET_SNAPSHOT_PATH",
        }
        if not should_execute:
            counts["skipped_event_count"] += 1
            issues.append("strategy_threshold_skip")
            event_row["after_cash"] = float(state["cash"])
            event_row["after_quantities"] = _json(state["quantities"])
            event_rows.append(event_row)
            continue

        executable = adapter._executable_weights(config, current_weights, desired)
        buy_prices, sell_prices = _side_execution_prices(
            base_prices, buy_price_up, sell_price_down
        )
        blocked_sell_symbols = []
        defense_sell_symbols = []
        defense_blocked_symbols = []
        for symbol in config.symbols:
            current_quantity = float(state["quantities"].get(symbol, 0.0))
            current_value = current_quantity * base_prices[symbol]
            executable_value = float(executable.get(symbol, 0.0)) * gross_nav
            if (
                current_quantity < LOT_SIZE - 1e-12
                or executable_value >= current_value - 1e-8
            ):
                continue
            one_lot_sell_ratio = LOT_SIZE * sell_prices[symbol] / gross_nav
            max_one_lot_sell_ratio = max(max_one_lot_sell_ratio, one_lot_sell_ratio)
            is_defense_sell = (
                symbol in DEFENDED_CORE_SYMBOLS
                and float(desired.get(symbol, 0.0))
                < float(current_weights.get(symbol, 0.0)) - 1e-10
            )
            if is_defense_sell:
                defense_sell_symbols.append(symbol)
                max_defense_one_lot_sell_ratio = max(
                    max_defense_one_lot_sell_ratio, one_lot_sell_ratio
                )
            if one_lot_sell_ratio > MAX_ASSET_TRADE + 1e-10:
                blocked_sell_symbols.append(symbol)
                if is_defense_sell:
                    defense_blocked_symbols.append(symbol)
        if defense_sell_symbols:
            counts["defense_sell_event_count"] += 1
            counts["defense_sell_symbol_count"] += len(defense_sell_symbols)
        counts["one_lot_sell_capital_blocked_event_count"] += len(
            blocked_sell_symbols
        )
        counts["one_lot_sell_capital_blocked_symbol_count"] += len(
            blocked_sell_symbols
        )
        counts["defense_one_lot_sell_capital_blocked_event_count"] += len(
            defense_blocked_symbols
        )
        counts["defense_one_lot_sell_capital_blocked_symbol_count"] += len(
            defense_blocked_symbols
        )
        if blocked_sell_symbols:
            issues.append("one_lot_sell_blocked_by_15pct")
        if defense_blocked_symbols:
            issues.append("defense_one_lot_sell_blocked_by_15pct")

        stepwise_cap_symbols = [
            symbol
            for symbol in config.symbols
            if float(desired.get(symbol, 0.0))
            > float(executable.get(symbol, 0.0)) + 1e-10
        ]
        counts["strategy_stepwise_cap_asset_count"] += len(stepwise_cap_symbols)
        if stepwise_cap_symbols:
            issues.append("strategy_stepwise_15pct_cap")

        before_quantities = dict(state["quantities"])
        plan = _lot_trade_plan_side_prices(
            state,
            base_prices,
            buy_prices,
            sell_prices,
            config.symbols,
            executable,
            commission_rate,
            MAX_ASSET_TRADE,
        )
        state["quantities"] = plan["target_quantities"]
        state["cash"] = plan["cash_after"]
        counts["executed_event_count"] += 1
        if first_build_cash is None:
            first_build_cash = float(state["cash"])
        counts["actual_trade_limit_violation_count"] += int(
            plan["actual_trade_limit_violation_count"]
        )
        counts["funding_adjustment_lots"] += int(plan["funding_adjustment_lots"])
        if plan["funding_adjustment_lots"]:
            counts["cash_shortfall_adjustment_event_count"] += 1
            issues.append("cash_shortfall_lot_adjustment")
        total_commission += float(plan["commission"])
        total_traded += float(plan["gross_traded"])
        actual_weights, post_nav, _ = _weights_from_state(
            state, base_prices, config.symbols
        )
        event_max_error = max(
            abs(
                float(actual_weights.get(symbol, 0.0))
                - float(executable.get(symbol, 0.0))
            )
            for symbol in (*config.symbols, "CASH")
        )
        event_max_error_desired = max(
            abs(
                float(actual_weights.get(symbol, 0.0))
                - float(desired.get(symbol, 0.0))
            )
            for symbol in (*config.symbols, "CASH")
        )
        max_weight_error = max(max_weight_error, event_max_error)
        max_weight_error_vs_desired = max(
            max_weight_error_vs_desired, event_max_error_desired
        )
        max_trade_ratio = max(max_trade_ratio, float(plan["max_actual_trade_ratio"]))
        minimum_cash = min(minimum_cash, float(state["cash"]))
        minimum_cash_ratio = min(
            minimum_cash_ratio,
            float(state["cash"]) / float(post_nav) if post_nav else 0.0,
        )
        positive_zero = [
            symbol
            for symbol in config.symbols
            if float(executable.get(symbol, 0.0)) > 1e-12
            and state["quantities"].get(symbol, 0.0) < LOT_SIZE - 1e-12
        ]
        target_zero = [
            symbol
            for symbol in config.symbols
            if float(desired.get(symbol, 0.0)) > 1e-12
            and state["quantities"].get(symbol, 0.0) < LOT_SIZE - 1e-12
        ]
        counts["positive_executable_zero_lot_event_count"] += len(positive_zero)
        counts["positive_target_zero_lot_event_count"] += len(target_zero)
        if positive_zero:
            issues.append("positive_executable_zero_lot")
        if target_zero:
            issues.append("positive_target_zero_lot")
        if event_max_error > 1e-10:
            counts["lot_rounding_event_count"] += 1
            issues.append("lot_rounding_weight_error")
        if positive_zero or target_zero or blocked_sell_symbols:
            zero_lot_rows.append(
                {
                    "event_index": event_index,
                    "signal_date": calculation.signal_date.isoformat(),
                    "execution_date": execution_date.isoformat(),
                    "one_lot_sell_capital_blocked_symbols": _json(
                        blocked_sell_symbols
                    ),
                    "positive_executable_zero_lot_symbols": _json(positive_zero),
                    "positive_target_zero_lot_symbols": _json(target_zero),
                    "before_quantities": _json(before_quantities),
                    "after_quantities": _json(state["quantities"]),
                    "evidence_class": "VERIFIED_LATEST_MARKET_SNAPSHOT_PATH",
                }
            )
        event_row.update(
            {
                "after_cash": float(state["cash"]),
                "after_quantities": _json(state["quantities"]),
                "max_abs_weight_error_vs_executable": float(event_max_error),
                "max_abs_weight_error_vs_desired": float(event_max_error_desired),
                "funding_adjustment_lots": int(plan["funding_adjustment_lots"]),
                "defense_sell_symbols": _json(defense_sell_symbols),
                "blocked_sell_symbols": _json(blocked_sell_symbols),
                "positive_executable_zero_lot_symbols": _json(positive_zero),
                "positive_target_zero_lot_symbols": _json(target_zero),
            }
        )
        event_rows.append(event_row)

    # The reserve is a first-build budget margin.  It is not a rule that
    # forces the strategy to retain a fixed cash percentage after later
    # signals legitimately deploy or release cash.
    reserve_ok = (
        first_build_cash is not None
        and first_build_cash >= float(capital) * float(cash_reserve) - 1e-8
    )
    return {
        **counts,
        "capital": int(capital),
        "commission_rate_one_way": float(commission_rate),
        "buy_price_up": float(buy_price_up),
        "sell_price_down": float(sell_price_down),
        "cash_reserve": float(cash_reserve),
        "minimum_cash": float(minimum_cash),
        "first_build_cash": (
            None if first_build_cash is None else float(first_build_cash)
        ),
        "minimum_cash_ratio_of_post_trade_nav": float(minimum_cash_ratio),
        "cash_reserve_satisfied": bool(reserve_ok),
        "total_commission": float(total_commission),
        "total_gross_traded": float(total_traded),
        "max_actual_trade_ratio": float(max_trade_ratio),
        "max_one_lot_sell_ratio": float(max_one_lot_sell_ratio),
        "max_defense_one_lot_sell_ratio": float(max_defense_one_lot_sell_ratio),
        "max_abs_weight_error_vs_executable": float(max_weight_error),
        "max_abs_weight_error_vs_desired": float(max_weight_error_vs_desired),
        "zero_lot_rows": zero_lot_rows,
        "event_rows": event_rows,
        "issue_duration_rows": _issue_duration_rows(event_rows),
        "evidence_class": "VERIFIED_LATEST_MARKET_SNAPSHOT_PATH",
    }


def _historical_path_frontier(
    config,
    market_data,
    calculations,
    latest_prices,
    desired,
    executable,
    *,
    scan_max: int = CAPITAL_SCAN_MAX,
    coarse_step: int = PATH_COARSE_STEP,
):
    """Find path-feasible candidates for two explicitly labelled scenarios.

    The historical path check is much more expensive than the latest
    first-build scan.  It therefore uses a global integer-CNY coarse scan and
    an exact one-yuan refinement around the first passing interval.  The
    output records that search method instead of presenting it as an
    unqualified mathematical minimum.
    """
    positive_symbols = [
        symbol
        for symbol in config.symbols
        if float(desired.get(symbol, 0.0)) > 1e-12
    ]
    rows = []
    allocations = []
    for (
        commission_rate,
        buy_price_up,
        sell_price_down,
        cash_reserve,
    ) in PATH_FRONTIER_SCENARIOS:
        hard_floor = max(
            1,
            math.ceil(
                max(
                    latest_prices[symbol]
                    * (1.0 + buy_price_up)
                    * LOT_SIZE
                    / MAX_ASSET_TRADE
                    for symbol in positive_symbols
                )
                - 1e-9
            ),
        )
        found_coarse = {}
        previous_coarse = hard_floor - 1
        for capital in range(hard_floor, scan_max + 1, coarse_step):
            metrics = _historical_path_check(
                config,
                market_data,
                calculations,
                capital,
                commission_rate,
                buy_price_up,
                cash_reserve,
                sell_price_down=sell_price_down,
            )
            latest_metrics = _evaluate_initial_capital(
                capital,
                latest_prices,
                desired,
                executable,
                config.symbols,
                commission_rate,
                buy_price_up,
                cash_reserve,
                sell_price_down=sell_price_down,
            )
            for tolerance in WEIGHT_TOLERANCES:
                if tolerance in found_coarse:
                    continue
                path_feasible = (
                    metrics["positive_executable_zero_lot_event_count"] == 0
                    and metrics["positive_target_zero_lot_event_count"] == 0
                    and metrics["actual_trade_limit_violation_count"] == 0
                    and metrics["one_lot_sell_capital_blocked_event_count"] == 0
                    and metrics["cash_reserve_satisfied"]
                    and metrics["max_abs_weight_error_vs_executable"]
                    <= tolerance + 1e-12
                )
                latest_feasible = (
                    latest_metrics["positive_target_zero_lot_count"] == 0
                    and latest_metrics["positive_executable_zero_lot_count"] == 0
                    and latest_metrics["actual_trade_limit_violation_count"] == 0
                    and latest_metrics["cash_reserve_satisfied"]
                    and latest_metrics["max_abs_weight_error_vs_executable"]
                    <= tolerance + 1e-12
                )
                if path_feasible and latest_feasible:
                    found_coarse[tolerance] = (
                        capital,
                        previous_coarse,
                        metrics,
                        latest_metrics,
                    )
            if len(found_coarse) == len(WEIGHT_TOLERANCES):
                break
            previous_coarse = capital

        for tolerance in WEIGHT_TOLERANCES:
            coarse = found_coarse.get(tolerance)
            exact_capital = None
            exact_metrics = None
            exact_latest_metrics = None
            if coarse is not None:
                coarse_capital, previous_capital, _coarse_metrics, _coarse_latest = coarse
                exact_start = max(hard_floor, previous_capital + 1)
                for candidate in range(exact_start, coarse_capital + 1):
                    metrics = _historical_path_check(
                        config,
                        market_data,
                        calculations,
                        candidate,
                        commission_rate,
                        buy_price_up,
                        cash_reserve,
                        sell_price_down=sell_price_down,
                    )
                    latest_metrics = _evaluate_initial_capital(
                        candidate,
                        latest_prices,
                        desired,
                        executable,
                        config.symbols,
                        commission_rate,
                        buy_price_up,
                        cash_reserve,
                        sell_price_down=sell_price_down,
                    )
                    path_feasible = (
                        metrics["positive_executable_zero_lot_event_count"] == 0
                        and metrics["positive_target_zero_lot_event_count"] == 0
                        and metrics["actual_trade_limit_violation_count"] == 0
                        and metrics["one_lot_sell_capital_blocked_event_count"] == 0
                        and metrics["cash_reserve_satisfied"]
                        and metrics["max_abs_weight_error_vs_executable"]
                        <= tolerance + 1e-12
                    )
                    latest_feasible = (
                        latest_metrics["positive_target_zero_lot_count"] == 0
                        and latest_metrics["positive_executable_zero_lot_count"] == 0
                        and latest_metrics["actual_trade_limit_violation_count"] == 0
                        and latest_metrics["cash_reserve_satisfied"]
                        and latest_metrics["max_abs_weight_error_vs_executable"]
                        <= tolerance + 1e-12
                    )
                    if path_feasible and latest_feasible:
                        exact_capital = candidate
                        exact_metrics = metrics
                        exact_latest_metrics = latest_metrics
                        break
            scenario = _scenario_id(
                commission_rate,
                buy_price_up,
                cash_reserve,
                sell_price_down,
            )
            row = {
                "scenario_id": scenario,
                "basis": "fresh_market_snapshot_real_holding_event_path",
                "commission_rate_one_way": float(commission_rate),
                "buy_price_up": float(buy_price_up),
                "sell_price_down": float(sell_price_down),
                "cash_reserve": float(cash_reserve),
                "weight_error_tolerance": float(tolerance),
                "hard_one_lot_15pct_floor": hard_floor,
                "minimum_capital_cny": exact_capital,
                "frontier_found": exact_capital is not None,
                "search_method": f"global_coarse_{coarse_step}_CNY_then_exact_local_refinement",
                "evidence_class": "VERIFIED_LATEST_MARKET_SNAPSHOT_PATH",
            }
            if exact_metrics is not None:
                row.update(
                    {
                        "positive_executable_zero_lot_event_count": exact_metrics[
                            "positive_executable_zero_lot_event_count"
                        ],
                        "positive_target_zero_lot_event_count": exact_metrics[
                            "positive_target_zero_lot_event_count"
                        ],
                        "actual_trade_limit_violation_count": exact_metrics[
                            "actual_trade_limit_violation_count"
                        ],
                        "one_lot_sell_capital_blocked_event_count": exact_metrics[
                            "one_lot_sell_capital_blocked_event_count"
                        ],
                        "defense_one_lot_sell_capital_blocked_event_count": exact_metrics[
                            "defense_one_lot_sell_capital_blocked_event_count"
                        ],
                        "first_build_cash": exact_metrics["first_build_cash"],
                        "minimum_cash": exact_metrics["minimum_cash"],
                        "cash_reserve_satisfied": exact_metrics[
                            "cash_reserve_satisfied"
                        ],
                        "total_commission": exact_metrics["total_commission"],
                        "max_actual_trade_ratio": exact_metrics[
                            "max_actual_trade_ratio"
                        ],
                        "max_one_lot_sell_ratio": exact_metrics[
                            "max_one_lot_sell_ratio"
                        ],
                        "max_defense_one_lot_sell_ratio": exact_metrics[
                            "max_defense_one_lot_sell_ratio"
                        ],
                        "max_abs_weight_error_vs_executable": exact_metrics[
                            "max_abs_weight_error_vs_executable"
                        ],
                        "max_abs_weight_error_vs_desired": exact_metrics[
                            "max_abs_weight_error_vs_desired"
                        ],
                        "latest_first_build_cash": exact_latest_metrics["cash_after"],
                        "latest_first_build_max_actual_trade_ratio": exact_latest_metrics[
                            "max_actual_trade_ratio"
                        ],
                        "latest_first_build_max_abs_weight_error_vs_executable": exact_latest_metrics[
                            "max_abs_weight_error_vs_executable"
                        ],
                        "latest_first_build_max_abs_weight_error_vs_desired": exact_latest_metrics[
                            "max_abs_weight_error_vs_desired"
                        ],
                        "signal_count": exact_metrics["signal_count"],
                        "executed_event_count": exact_metrics["executed_event_count"],
                        "skipped_event_count": exact_metrics["skipped_event_count"],
                    }
                )
                first_build = _evaluate_initial_capital(
                    exact_capital,
                    latest_prices,
                    desired,
                    executable,
                    config.symbols,
                    commission_rate,
                    buy_price_up,
                    cash_reserve,
                    sell_price_down=sell_price_down,
                )
                for symbol in (*config.symbols, "CASH"):
                    target_weight = float(desired.get(symbol, 0.0))
                    executable_weight = float(executable.get(symbol, 0.0))
                    actual_weight = float(first_build["actual_weights"].get(symbol, 0.0))
                    allocations.append(
                        {
                            "scenario_id": scenario,
                            "weight_error_tolerance": float(tolerance),
                            "minimum_capital_cny": exact_capital,
                            "symbol": symbol,
                            "target_weight": target_weight,
                            "executable_weight": executable_weight,
                            "actual_weight_at_latest_snapshot_first_build": actual_weight,
                            "actual_minus_executable": actual_weight - executable_weight,
                            "actual_minus_target": actual_weight - target_weight,
                            "quantity": (
                                None
                                if symbol == "CASH"
                                else float(first_build["target_quantities"].get(symbol, 0.0))
                            ),
                            "execution_price": (
                                None
                                if symbol == "CASH"
                                else float(first_build["buy_execution_prices"][symbol])
                            ),
                            "cash_after_latest_snapshot_first_build": float(
                                first_build["cash_after"]
                            ),
                            "evidence_class": "VERIFIED_LATEST_MARKET_SNAPSHOT_PATH",
                        }
                    )
            rows.append(row)
    return pd.DataFrame(rows), pd.DataFrame(allocations)


def _fixed_budget_outputs(
    config,
    market_data,
    calculations,
    latest_prices,
    desired,
    executable,
):
    """Build the requested fixed-budget comparison and event evidence."""
    initial_summary = []
    initial_allocations = []
    path_summary = []
    path_events = []
    path_durations = []
    positive_symbols = [
        symbol
        for symbol in config.symbols
        if float(desired.get(symbol, 0.0)) > 1e-12
    ]
    stepwise_cap_symbols = [
        symbol
        for symbol in config.symbols
        if float(desired.get(symbol, 0.0))
        > float(executable.get(symbol, 0.0)) + 1e-10
    ]

    for scenario_id, buy_price_up, sell_price_down in FIXED_BUDGET_PRICE_SCENARIOS:
        for capital in FIXED_BUDGETS:
            first_build = _evaluate_initial_capital(
                capital,
                latest_prices,
                desired,
                executable,
                config.symbols,
                BASE_COMMISSION_RATE,
                buy_price_up,
                FIXED_BUDGET_CASH_RESERVE,
                sell_price_down=sell_price_down,
            )
            path = _historical_path_check(
                config,
                market_data,
                calculations,
                capital,
                BASE_COMMISSION_RATE,
                buy_price_up,
                FIXED_BUDGET_CASH_RESERVE,
                sell_price_down=sell_price_down,
            )
            impossible_symbols = list(
                first_build["positive_executable_zero_lot_symbols"]
            )
            initial_summary.append(
                {
                    "scenario_id": scenario_id,
                    "capital": capital,
                    "commission_rate_one_way": BASE_COMMISSION_RATE,
                    "buy_price_up": buy_price_up,
                    "sell_price_down": sell_price_down,
                    "cash_reserve_rate_check": FIXED_BUDGET_CASH_RESERVE,
                    "cash_reserve_amount": capital * FIXED_BUDGET_CASH_RESERVE,
                    "cash_reserve_satisfied": first_build["cash_reserve_satisfied"],
                    "first_build_cash_after": first_build["cash_after"],
                    "first_build_cash_ratio_of_post_nav": (
                        first_build["cash_after"] / first_build["post_nav"]
                    ),
                    "post_build_nav_after_fee": first_build["post_nav"],
                    "gross_traded": first_build["gross_traded"],
                    "commission": first_build["commission"],
                    "funding_adjustment_lots": first_build[
                        "funding_adjustment_lots"
                    ],
                    "max_actual_trade_ratio": first_build[
                        "max_actual_trade_ratio"
                    ],
                    "positive_executable_zero_lot_symbols": _json(
                        first_build["positive_executable_zero_lot_symbols"]
                    ),
                    "rule_impossible_current_target_symbols": _json(
                        impossible_symbols
                    ),
                    "max_abs_weight_error_vs_executable": first_build[
                        "max_abs_weight_error_vs_executable"
                    ],
                    "max_abs_weight_error_vs_desired": first_build[
                        "max_abs_weight_error_vs_desired"
                    ],
                    "strategy_stepwise_cap_symbols": _json(stepwise_cap_symbols),
                    "path_positive_executable_zero_lot_event_count": path[
                        "positive_executable_zero_lot_event_count"
                    ],
                    "path_positive_target_zero_lot_event_count": path[
                        "positive_target_zero_lot_event_count"
                    ],
                    "path_defense_sell_event_count": path[
                        "defense_sell_event_count"
                    ],
                    "path_defense_one_lot_sell_blocked_event_count": path[
                        "defense_one_lot_sell_capital_blocked_event_count"
                    ],
                    "path_one_lot_sell_blocked_event_count": path[
                        "one_lot_sell_capital_blocked_event_count"
                    ],
                    "path_cash_shortfall_adjustment_event_count": path[
                        "cash_shortfall_adjustment_event_count"
                    ],
                    "path_funding_adjustment_lots": path[
                        "funding_adjustment_lots"
                    ],
                    "path_skipped_event_count": path["skipped_event_count"],
                    "path_lot_rounding_event_count": path[
                        "lot_rounding_event_count"
                    ],
                    "path_max_one_lot_sell_ratio": path[
                        "max_one_lot_sell_ratio"
                    ],
                    "path_max_defense_one_lot_sell_ratio": path[
                        "max_defense_one_lot_sell_ratio"
                    ],
                    "path_minimum_cash": path["minimum_cash"],
                    "path_minimum_cash_ratio_of_post_trade_nav": path[
                        "minimum_cash_ratio_of_post_trade_nav"
                    ],
                    "path_first_build_cash": path["first_build_cash"],
                    "path_max_abs_weight_error_vs_executable": path[
                        "max_abs_weight_error_vs_executable"
                    ],
                    "path_max_abs_weight_error_vs_desired": path[
                        "max_abs_weight_error_vs_desired"
                    ],
                    "path_total_commission": path["total_commission"],
                    "path_evidence_class": path["evidence_class"],
                }
            )
            for symbol in (*config.symbols, "CASH"):
                mark_price = latest_prices.get(symbol)
                buy_price = first_build["buy_execution_prices"].get(symbol)
                initial_allocations.append(
                    {
                        "scenario_id": scenario_id,
                        "capital": capital,
                        "symbol": symbol,
                        "target_positive": symbol in positive_symbols,
                        "target_weight": float(desired.get(symbol, 0.0)),
                        "executable_weight": float(executable.get(symbol, 0.0)),
                        "mark_price": mark_price,
                        "buy_execution_price": buy_price,
                        "sell_execution_price": first_build["sell_execution_prices"].get(symbol),
                        "one_lot_notional_at_mark": (
                            None if mark_price is None else mark_price * LOT_SIZE
                        ),
                        "one_lot_15pct_capital_floor": (
                            None
                            if buy_price is None
                            else buy_price * LOT_SIZE / MAX_ASSET_TRADE
                        ),
                        "one_lot_cash_affordable": (
                            None
                            if mark_price is None
                            else capital >= mark_price * LOT_SIZE
                        ),
                        "one_lot_rule_compliant": (
                            None
                            if buy_price is None
                            else capital >= buy_price * LOT_SIZE / MAX_ASSET_TRADE
                        ),
                        "quantity": (
                            None
                            if symbol == "CASH"
                            else float(first_build["target_quantities"].get(symbol, 0.0))
                        ),
                        "actual_weight": float(
                            first_build["actual_weights"].get(symbol, 0.0)
                        ),
                        "actual_minus_executable": float(
                            first_build["actual_weights"].get(symbol, 0.0)
                            - executable.get(symbol, 0.0)
                        ),
                        "actual_minus_target": float(
                            first_build["actual_weights"].get(symbol, 0.0)
                            - desired.get(symbol, 0.0)
                        ),
                        "cash_after": first_build["cash_after"],
                        "evidence_class": first_build["evidence_class"],
                    }
                )
            for row in path["event_rows"]:
                path_events.append(
                    {
                        "scenario_id": scenario_id,
                        "capital": capital,
                        "event_index": row["event_index"],
                        "signal_date": row["signal_date"],
                        "execution_date": row["execution_date"],
                        "turnover_from_current": row.get("turnover_from_current"),
                        "issues": _json(row.get("issues", [])),
                        "after_cash": row.get("after_cash"),
                        "after_quantities": row.get("after_quantities"),
                        "max_abs_weight_error_vs_executable": row.get(
                            "max_abs_weight_error_vs_executable"
                        ),
                        "max_abs_weight_error_vs_desired": row.get(
                            "max_abs_weight_error_vs_desired"
                        ),
                        "funding_adjustment_lots": row.get("funding_adjustment_lots", 0),
                        "defense_sell_symbols": row.get("defense_sell_symbols", "[]"),
                        "blocked_sell_symbols": row.get("blocked_sell_symbols", "[]"),
                        "positive_executable_zero_lot_symbols": row.get(
                            "positive_executable_zero_lot_symbols", "[]"
                        ),
                        "positive_target_zero_lot_symbols": row.get(
                            "positive_target_zero_lot_symbols", "[]"
                        ),
                        "evidence_class": row["evidence_class"],
                    }
                )
            for row in path["issue_duration_rows"]:
                path_durations.append(
                    {
                        "scenario_id": scenario_id,
                        "capital": capital,
                        **row,
                        "evidence_class": path["evidence_class"],
                    }
                )
    return (
        pd.DataFrame(initial_summary),
        pd.DataFrame(initial_allocations),
        pd.DataFrame(path_events),
        pd.DataFrame(path_durations),
    )


def _write_snapshot(frames, output_root: Path, metadata: dict):
    snapshot_root = output_root / "market_snapshot"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    for symbol, frame in frames.items():
        frame.to_parquet(snapshot_root / f"{symbol}.parquet")
    (output_root / "market_snapshot_metadata.json").write_text(
        _json(metadata) + "\n", encoding="utf-8"
    )


def _write_target_weights(
    config,
    market_data,
    latest_calculation,
    latest_prices,
    desired,
    executable,
    output_root: Path,
):
    rows = []
    for symbol in (*config.symbols, "CASH"):
        price = latest_prices.get(symbol)
        rows.append(
            {
                "signal_date": latest_calculation.signal_date.isoformat(),
                "market_data_asof": _date(market_data.sessions[-1]),
                "symbol": symbol,
                "target_weight": float(desired.get(symbol, 0.0)),
                "executable_weight_from_all_cash": float(executable.get(symbol, 0.0)),
                "latest_close": price,
                "one_lot_notional": (
                    None if price is None else float(price) * LOT_SIZE
                ),
                "one_lot_15pct_capital_floor": (
                    None
                    if price is None
                    else float(price) * LOT_SIZE / MAX_ASSET_TRADE
                ),
                "evidence_class": "VERIFIED_LATEST_MARKET_SNAPSHOT",
            }
        )
    pd.DataFrame(rows).to_csv(
        output_root / "latest_target_weights.csv",
        index=False,
        encoding="utf-8-sig",
    )


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--as-of-date",
        default="2026-09-06",
        help="Shanghai date used for completed-data filtering (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="New isolated output directory; never the production data directory.",
    )
    parser.add_argument(
        "--input-dir",
        default=None,
        help="Existing isolated output directory whose market_snapshot is reused; skips a new data request.",
    )
    parser.add_argument(
        "--max-capital",
        type=int,
        default=CAPITAL_SCAN_MAX,
        help="Upper bound for exact integer-CNY first-build scan.",
    )
    return parser.parse_args()


def main():
    args = _parse_args()
    as_of_date = date.fromisoformat(args.as_of_date)
    if args.max_capital < 1:
        raise SystemExit("--max-capital must be positive")
    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    config = get_strategy("theme_alpha")
    if args.input_dir:
        frames, market_data, common_end = _load_isolated_snapshot(
            config, Path(args.input_dir)
        )
        snapshot_source = "EXISTING_ISOLATED_SNAPSHOT"
    else:
        frames, market_data, common_end = _fetch_fresh_snapshot(config, as_of_date)
        snapshot_source = "FRESH_TICKFLOW_SNAPSHOT"
    calculations, warmup_skips = _valid_calculations(config, market_data)
    latest_calculation = calculations[-1]
    latest_timestamp = pd.Timestamp(market_data.sessions[-1])
    latest_prices = {
        symbol: float(market_data.close.at[latest_timestamp, symbol])
        for symbol in config.symbols
    }
    desired = _weights_from_calculation(latest_calculation)
    adapter = _engine_adapter()
    all_cash_weights = {symbol: 0.0 for symbol in config.symbols}
    all_cash_weights["CASH"] = 1.0
    should_execute, turnover = adapter._should_execute(
        config, all_cash_weights, desired
    )
    executable = adapter._executable_weights(
        config, all_cash_weights, desired
    )
    if not should_execute:
        raise RuntimeError("Latest target unexpectedly fails the first-build threshold")

    latest_frontier, latest_allocations, scenario_metrics = _latest_frontier(
        config,
        latest_prices,
        desired,
        executable,
        scan_max=args.max_capital,
    )
    latest_frontier.to_csv(
        output_root / "minimum_capital_frontier.csv",
        index=False,
        encoding="utf-8-sig",
    )
    latest_allocations.to_csv(
        output_root / "minimum_capital_allocations.csv",
        index=False,
        encoding="utf-8-sig",
    )
    _write_target_weights(
        config,
        market_data,
        latest_calculation,
        latest_prices,
        desired,
        executable,
        output_root,
    )

    (
        fixed_budget_summary,
        fixed_budget_allocations,
        fixed_budget_events,
        fixed_budget_durations,
    ) = _fixed_budget_outputs(
        config,
        market_data,
        calculations,
        latest_prices,
        desired,
        executable,
    )
    fixed_budget_summary.to_csv(
        output_root / "fixed_budget_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    fixed_budget_allocations.to_csv(
        output_root / "fixed_budget_initial_allocations.csv",
        index=False,
        encoding="utf-8-sig",
    )
    fixed_budget_events.to_csv(
        output_root / "fixed_budget_historical_events.csv",
        index=False,
        encoding="utf-8-sig",
    )
    fixed_budget_durations.to_csv(
        output_root / "fixed_budget_issue_durations.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Validate the frontier's candidate amounts against the same real-holding
    # event path used by the v2 replay.  This is a path check, not a second NAV
    # engine and not a replacement for the full v2 ledger replay.
    path_rows = []
    path_results = {}
    seen_path_keys = set()
    for row in latest_frontier.to_dict("records"):
        capital = row.get("minimum_capital_cny")
        if capital is None or not bool(row.get("frontier_found")):
            continue
        key = (
            int(capital),
            float(row["commission_rate_one_way"]),
            float(row["buy_price_up"]),
            float(row["sell_price_down"]),
            float(row["cash_reserve"]),
        )
        if key in seen_path_keys:
            continue
        seen_path_keys.add(key)
        path = _historical_path_check(
            config,
            market_data,
            calculations,
            key[0],
            key[1],
            key[2],
            key[4],
            sell_price_down=key[3],
        )
        path_results[key] = path
        path["frontier_source_weight_error_tolerance"] = float(
            row["weight_error_tolerance"]
        )
        path["latest_frontier_scenario_id"] = row["scenario_id"]
        path_rows.append(path)
    path_frame = pd.DataFrame(path_rows)
    if not path_frame.empty:
        path_frame = path_frame.drop(columns=["zero_lot_rows", "event_rows", "issue_duration_rows"])
    path_frame.to_csv(
        output_root / "historical_path_candidate_checks.csv",
        index=False,
        encoding="utf-8-sig",
    )
    path_frontier, path_allocations = _historical_path_frontier(
        config,
        market_data,
        calculations,
        latest_prices,
        desired,
        executable,
        scan_max=args.max_capital,
    )
    path_frontier.to_csv(
        output_root / "historical_path_minimum_frontier.csv",
        index=False,
        encoding="utf-8-sig",
    )
    path_allocations.to_csv(
        output_root / "historical_path_minimum_allocations.csv",
        index=False,
        encoding="utf-8-sig",
    )
    path_execution_block_evidence = [
        {
            "capital": path["capital"],
            "commission_rate_one_way": path["commission_rate_one_way"],
            "buy_price_up": path["buy_price_up"],
            "sell_price_down": path["sell_price_down"],
            "cash_reserve": path["cash_reserve"],
            "execution_block_rows": path["zero_lot_rows"],
        }
        for key, path in sorted(path_results.items())
        if path["zero_lot_rows"]
    ]

    metadata = {
        "runDate": as_of_date.isoformat(),
        "outputType": "minimum_capital_feasibility_snapshot",
        "strategyIdentity": "C: Core80 + Expanded LVT20 + Def200 Cash",
        "strategyBIndependentContractFound": False,
        "source": {
            "provider": "TickFlow",
            "adapter": "trading/backend/analysis_data.py:_fetch_tickflow_daily_batch",
            "endpointContract": "/v1/klines/batch, period=1d, adjust=forward_additive",
            "readOnly": True,
            "writesProductionBackendData": False,
        },
        "requestedDataRange": {
            "start": SNAPSHOT_START.isoformat(),
            "endExclusive": (as_of_date + timedelta(days=1)).isoformat(),
        },
        "data": {
            "commonLatestDate": common_end.isoformat(),
            "alignedSessionsStart": _date(market_data.sessions[0]),
            "alignedSessionsEnd": _date(market_data.sessions[-1]),
            "symbolLatestDates": {
                symbol: _date(frame.index.max()) for symbol, frame in frames.items()
            },
            "symbolRowCounts": {
                symbol: int(len(frame)) for symbol, frame in frames.items()
            },
            "blocked": bool(market_data.blocked),
            "diagnostics": [diagnostic.__dict__ for diagnostic in market_data.diagnostics],
        },
        "signal": {
            "latestValidSignalDate": latest_calculation.signal_date.isoformat(),
            "marketDataDate": latest_calculation.market_data_date.isoformat(),
            "selectedLvt": list(
                latest_calculation.observation.values.get("selected_lvt", ())
            ),
            "turnoverFromAllCash": float(turnover),
            "firstBuildShouldExecute": bool(should_execute),
            "warmupSkippedFormalDates": warmup_skips,
        },
        "executionContract": {
            "execution": "next_close",
            "firstBuild": "cash_only_activation_then_next_signal_next_XSHG_close",
            "rebalanceThreshold": float(config.params["rebalance_threshold"]),
            "maxAssetTrade": MAX_ASSET_TRADE,
            "lotSize": LOT_SIZE,
            "lvtCap": "selected_only_remainder_to_CASH",
            "historicalPathCheck": "uses real integer holdings and cash across current formal events; does not create a second NAV engine",
        },
        "frontierDefinition": {
            "capitalUnit": "integer CNY",
            "positiveTargetAssetMustHaveLot": True,
            "positiveExecutableAssetMustHaveLot": True,
            "oneLotSellMustNotBeBlockedBy15pct": True,
            "finalOrderLimit": "actual integer order notional / pre-trade NAV <= 15%",
            "weightError": "maximum absolute post-lot weight error versus current kernel executable weights",
            "commissionScenarios": list(COMMISSION_RATES),
            "buyPriceUpScenarios": list(BUY_PRICE_UPS),
            "sellPriceDownForFrontier": 0.0,
            "cashReserves": list(CASH_RESERVES),
            "weightErrorTolerances": list(WEIGHT_TOLERANCES),
            "notRecommendation": True,
        },
        "latestFrontierScenarios": scenario_metrics,
        "historicalPathCandidateCount": len(path_rows),
        "historicalPathFrontier": path_frontier.to_dict("records"),
        "historicalPathCandidatesWithExecutionBlockEvidence": path_execution_block_evidence,
        "fixedBudgetComparison": {
            "budgets": list(FIXED_BUDGETS),
            "commissionRateOneWay": BASE_COMMISSION_RATE,
            "cashReserveRateCheck": FIXED_BUDGET_CASH_RESERVE,
            "priceScenarios": [
                {
                    "id": scenario_id,
                    "buyPriceUp": buy_price_up,
                    "sellPriceDown": sell_price_down,
                }
                for scenario_id, buy_price_up, sell_price_down in FIXED_BUDGET_PRICE_SCENARIOS
            ],
            "summaryFile": "fixed_budget_summary.csv",
            "initialAllocationsFile": "fixed_budget_initial_allocations.csv",
            "historicalEventsFile": "fixed_budget_historical_events.csv",
            "issueDurationsFile": "fixed_budget_issue_durations.csv",
        },
        "unverifiedItems": [
            "broker ETF commission and other charges",
            "ETF premium/iNAV, order book, suspension and actual fillability",
            "future price movement beyond the explicit stress buffer",
            "full 2022-01 through 2022-05 defense effect (effective signal starts after MA200 warmup)",
        ],
        "evidenceClass": "VERIFIED_LATEST_MARKET_SNAPSHOT_PLUS_PATH_CHECK",
        "snapshotSource": snapshot_source,
    }
    _write_snapshot(frames, output_root, metadata)
    (output_root / "minimum_capital_audit.json").write_text(
        _json(metadata) + "\n", encoding="utf-8"
    )
    print(
        _json(
            {
                "output": str(output_root),
                "commonLatestDate": common_end.isoformat(),
                "latestSignalDate": latest_calculation.signal_date.isoformat(),
                "frontierRows": int(len(latest_frontier)),
                "pathRows": int(len(path_frame)),
            }
        )
    )


if __name__ == "__main__":
    main()
