"""Refresh the independent LVT performance review through the latest ETF close.

This is a dated, read-only research pass.  It uses the isolated TickFlow
snapshot produced by the current Theme Alpha feasibility audit, preserves the
frozen Q12 artifacts, and compares the standalone LVT sleeve with the current
Core80/LVT20/Def200 contract and the original three-asset RiskParity baseline.

The replay uses the current paper contract: formal signals on the 10th/25th,
next complete XSHG close execution, a 2% turnover threshold, a 15% per-asset
trade limit, and the current asset-specific cost table.  It uses fractional
holdings for research NAV; it is not a replacement for an integer-lot broker
execution ledger.
"""
from __future__ import annotations

import os

from datetime import datetime
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TRADING_BACKEND = Path(os.environ.get("TRADING_ROOT", ROOT.parent / "trading")).expanduser().resolve() / "backend"
if str(TRADING_BACKEND) not in sys.path:
    sys.path.insert(0, str(TRADING_BACKEND))

from portfolio_strategies.indicators import (  # noqa: E402
    InsufficientDataError,
    inverse_volatility_weights,
    select_low_vol_trend,
)
from portfolio_strategies.market_data import build_portfolio_market_data  # noqa: E402
from portfolio_strategies.paper_engine import PortfolioPaperEngine  # noqa: E402
from portfolio_strategies.registry import get_strategy  # noqa: E402
from portfolio_strategies.schedules import bimonthly_signal_dates  # noqa: E402
from portfolio_strategies.theme_alpha import (  # noqa: E402
    _lvt_weights,
    apply_core_defense,
    combine_sleeve_weights,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")
INPUT_ROOT = ROOT / "outputs/def200-cash-minimum-capital-2026-09-06-v2"
SNAPSHOT_ROOT = INPUT_ROOT / "market_snapshot"
OUTPUT_DIR = ROOT / "outputs/theme-alpha-lvt-recent-3m-2026-09-06"
NOTEBOOK_PATH = ROOT / "research/notebooks/theme-alpha-lvt-recent-3m-2026-09-06-practice.ipynb"
NOTE_PATH = ROOT / "docs/notes/theme-alpha-lvt-recent-3m-2026-09-06-review.md"

MAIN_CAP = 0.50
CAP_SENSITIVITY = (0.45, 0.50, 0.55)
INITIAL_NAV = 100_000.0
TRADING_DAYS = 252

ORIGINAL = "Original_RiskParity_3Asset"
LVT = "Expanded_LVT_100"
COMBINED = "Core80_LVT20_Def200_Cash"
MAIN_STRATEGIES = (ORIGINAL, LVT, COMBINED)
STRATEGY_LABELS = {
    ORIGINAL: "Original 3-asset RiskParity",
    LVT: "Standalone Expanded LVT 100%",
    COMBINED: "Core80 + LVT20 + Def200 Cash",
}


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _target_template(config) -> dict[str, float]:
    return {symbol: 0.0 for symbol in (*config.symbols, "CASH")}


def _ordered_target(config, values) -> dict[str, float]:
    target = _target_template(config)
    for symbol, value in values.items():
        if symbol in target:
            target[symbol] = float(value)
    total = float(sum(target.values()))
    if not np.isfinite(total) or abs(total - 1.0) > 1e-9:
        raise ValueError(f"Target weights do not sum to one: {total}")
    return target


def load_market():
    config = get_strategy("theme_alpha")
    frames = {
        symbol: pd.read_parquet(SNAPSHOT_ROOT / f"{symbol}.parquet")
        for symbol in config.symbols
    }
    market = build_portfolio_market_data(
        config,
        frames,
        datetime(2026, 9, 6, 16, 0, tzinfo=SHANGHAI),
    )
    if market.blocked:
        diagnostics = [diagnostic.__dict__ for diagnostic in market.diagnostics]
        raise RuntimeError(f"Input snapshot is blocked: {_json(diagnostics)}")
    if market.sessions.empty:
        raise RuntimeError("Input snapshot has no aligned sessions")
    return config, frames, market


def _target_for_signal(config, market, signal_date, cap):
    close = market.close
    returns = close.pct_change(fill_method=None)
    core_symbols = ("510300.SS", "513100.SS", "518880.SS")
    defended_symbols = ("510300.SS", "513100.SS")
    lvt_symbols = tuple(
        asset.symbol
        for asset in config.assets
        if asset.sleeve in {"lvt", "core_lvt"}
    )

    location = int(close.index.get_loc(signal_date))
    defense_window = int(config.params["defense_ma_window"])
    result = {"errors": {}}
    core = None
    try:
        core = inverse_volatility_weights(
            returns.loc[:signal_date],
            core_symbols,
            window=int(config.params["risk_parity_window"]),
        )
        result[ORIGINAL] = _ordered_target(config, {**core, "CASH": 0.0})
    except Exception as exc:
        result["errors"][ORIGINAL] = f"{type(exc).__name__}: {exc}"

    selected = None
    lvt = None
    try:
        lvt_warmup = max(
            int(config.params["ma_window"]),
            int(config.params["momentum_window"]),
            int(config.params["volatility_window"]),
        )
        if location < lvt_warmup:
            raise InsufficientDataError("LVT selector has not completed warmup")
        selected = select_low_vol_trend(
            close,
            returns,
            signal_date,
            lvt_symbols,
            ma_window=int(config.params["ma_window"]),
            momentum_window=int(config.params["momentum_window"]),
            volatility_window=int(config.params["volatility_window"]),
            top_n=int(config.params["top_n"]),
        )
        lvt = _lvt_weights(
            returns.loc[:signal_date],
            selected,
            window=int(config.params["risk_parity_window"]),
            cap=float(cap),
        )
        result[LVT] = _ordered_target(config, lvt)
    except Exception as exc:
        result["errors"][LVT] = f"{type(exc).__name__}: {exc}"

    risk_on = {}
    defended_core = None
    if core is not None and lvt is not None:
        if location < defense_window - 1:
            result["errors"][COMBINED] = "InsufficientDataError: Core defense has not completed warmup"
        else:
            risk_on = {
                symbol: bool(
                    close.at[signal_date, symbol]
                    > close[symbol].iloc[
                        location - defense_window + 1 : location + 1
                    ].mean()
                )
                for symbol in defended_symbols
            }
            defended_core = apply_core_defense({**core, "CASH": 0.0}, risk_on)
            result[COMBINED] = _ordered_target(
                config,
                combine_sleeve_weights(
                    defended_core,
                    lvt,
                    symbols=config.symbols,
                    core_allocation=float(config.params["core_allocation"]),
                    lvt_allocation=float(config.params["lvt_allocation"]),
                ),
            )
    elif COMBINED not in result["errors"]:
        result["errors"][COMBINED] = "InsufficientDataError: core or LVT inputs unavailable"

    result.update(
        {
            "selected_lvt": tuple(selected or ()),
            "core_risk_on": risk_on,
            "lvt_cash": float(lvt.get("CASH", 0.0)) if lvt is not None else np.nan,
            "core_cash": (
                float(defended_core.get("CASH", 0.0))
                if defended_core is not None
                else np.nan
            ),
        }
    )
    return result


def build_signal_catalog(config, market, cap):
    rows = []
    targets = {strategy: {} for strategy in MAIN_STRATEGIES}
    dates = sorted(
        bimonthly_signal_dates(
            market.sessions,
            signal_days=tuple(config.params["signal_days"]),
        )
    )
    for signal_date in dates:
        row = {
            "signal_date": signal_date.date().isoformat(),
            "cap": float(cap),
            "valid": False,
            "error": "",
        }
        bundle = _target_for_signal(config, market, signal_date, cap)
        next_position = int(market.sessions.get_loc(signal_date)) + 1
        row.update(
            {
                "valid": bool(any(strategy in bundle for strategy in MAIN_STRATEGIES)),
                "execution_date": (
                    market.sessions[next_position].date().isoformat()
                    if next_position < len(market.sessions)
                    else ""
                ),
                "selected_lvt": _json(bundle["selected_lvt"]),
                "core_risk_on": _json(bundle["core_risk_on"]),
                "lvt_cash": bundle["lvt_cash"],
                "core_cash": bundle["core_cash"],
            }
        )
        for strategy in MAIN_STRATEGIES:
            row[f"valid_{strategy}"] = strategy in bundle
            if strategy in bundle:
                targets[strategy][signal_date] = bundle[strategy]
                row[f"{strategy}_target"] = _json(bundle[strategy])
            else:
                row[f"{strategy}_target"] = ""
        errors = bundle["errors"]
        row["error"] = _json(errors) if errors else ""
        rows.append(row)
    return targets, pd.DataFrame(rows)


def _state_nav(state, prices, symbols):
    values = {
        symbol: float(state["quantities"].get(symbol, 0.0)) * float(prices[symbol])
        for symbol in symbols
    }
    nav = float(state["cash"] + sum(values.values()))
    if nav <= 0 or not np.isfinite(nav):
        raise ValueError("Non-positive or invalid NAV")
    return nav, values


def _weights_from_state(state, prices, symbols):
    nav, values = _state_nav(state, prices, symbols)
    weights = {symbol: values[symbol] / nav for symbol in symbols}
    weights["CASH"] = float(state["cash"]) / nav
    return weights, nav, values


def simulate_strategy(config, market, targets, strategy, cap):
    valid_signal_dates = sorted(targets[strategy])
    if not valid_signal_dates:
        raise RuntimeError(f"No valid signal dates for {strategy}")
    first_signal = valid_signal_dates[0]
    first_position = int(market.sessions.get_loc(first_signal)) - 1
    if first_position < 0:
        raise RuntimeError(f"No activation session before {first_signal}")
    activation_date = market.sessions[first_position]
    target_by_execution = {}
    signal_for_execution = {}
    for signal_date in valid_signal_dates:
        signal_position = int(market.sessions.get_loc(signal_date))
        execution_position = signal_position + 1
        if execution_position >= len(market.sessions):
            continue
        execution_date = market.sessions[execution_position]
        target_by_execution[execution_date] = targets[strategy][signal_date]
        signal_for_execution[execution_date] = signal_date

    engine = PortfolioPaperEngine.__new__(PortfolioPaperEngine)
    state = {
        "cash": float(INITIAL_NAV),
        "quantities": {symbol: 0.0 for symbol in config.symbols},
    }
    nav_rows = []
    event_rows = []
    previous_nav = None
    peak_nav = INITIAL_NAV
    for timestamp in market.sessions[first_position:]:
        if timestamp in target_by_execution:
            signal_date = signal_for_execution[timestamp]
            prices = {
                symbol: float(market.close.at[timestamp, symbol])
                for symbol in config.symbols
            }
            current_weights, gross_nav, current_values = _weights_from_state(
                state, prices, config.symbols
            )
            desired = target_by_execution[timestamp]
            should_execute, turnover = engine._should_execute(
                config, current_weights, desired
            )
            executable = engine._executable_weights(
                config, current_weights, desired
            )
            before = dict(state["quantities"])
            before_cash = float(state["cash"])
            actual_turnover = 0.0
            if should_execute:
                net_nav, target_values, costs = engine._solve_execution(
                    config, current_values, gross_nav, executable
                )
                state["quantities"] = {
                    symbol: target_values[symbol] / prices[symbol]
                    for symbol in config.symbols
                }
                state["cash"] = float(executable["CASH"] * net_nav)
                total_cost = float(
                    sum(fee + slippage for _notional, fee, slippage in costs.values())
                )
                actual_trade_notional = float(
                    sum(notional for notional, _fee, _slippage in costs.values())
                )
                actual_turnover = actual_trade_notional / gross_nav
                status = "executed"
            else:
                total_cost = 0.0
                status = "skipped"

            post_weights, post_nav, _ = _weights_from_state(
                state, prices, config.symbols
            )
            event_rows.append(
                {
                    "strategy": strategy,
                    "cap": float(cap),
                    "signal_date": signal_date.date().isoformat(),
                    "execution_date": timestamp.date().isoformat(),
                    "status": status,
                    "turnover_before_limit": float(turnover),
                    "gross_nav_before": float(gross_nav),
                    "cash_before": before_cash,
                    "cash_after": float(state["cash"]),
                    "post_trade_nav": float(post_nav),
                    "total_cost": total_cost,
                    "actual_turnover": actual_turnover,
                    "selected_lvt": "",
                    "max_weight_error_vs_executable": float(
                        max(
                            abs(
                                post_weights.get(symbol, 0.0)
                                - executable.get(symbol, 0.0)
                            )
                            for symbol in (*config.symbols, "CASH")
                        )
                    ),
                    "evidence_class": "VERIFIED_FRACTIONAL_CURRENT_ENGINE_REPLAY",
                    "before_quantities": _json(before),
                    "after_quantities": _json(state["quantities"]),
                }
            )

        prices = {
            symbol: float(market.close.at[timestamp, symbol])
            for symbol in config.symbols
        }
        nav, values = _state_nav(state, prices, config.symbols)
        daily_return = 0.0 if previous_nav is None else nav / previous_nav - 1.0
        peak_nav = max(peak_nav, nav)
        nav_rows.append(
            {
                "strategy": strategy,
                "cap": float(cap),
                "valuation_date": timestamp.date().isoformat(),
                "nav": nav,
                "daily_return": daily_return,
                "cash": float(state["cash"]),
                "cash_weight": float(state["cash"]) / nav,
                "drawdown_since_activation": nav / peak_nav - 1.0,
                **{f"weight_{symbol}": values[symbol] / nav for symbol in config.symbols},
                "evidence_class": "VERIFIED_FRACTIONAL_CURRENT_ENGINE_REPLAY",
            }
        )
        previous_nav = nav
    nav = pd.DataFrame(nav_rows)
    nav["valuation_date"] = pd.to_datetime(nav["valuation_date"])
    events = pd.DataFrame(event_rows)
    return {
        "strategy": strategy,
        "cap": float(cap),
        "activation_date": activation_date,
        "nav": nav,
        "events": events,
    }


def _drawdown_events(nav_series):
    dd = nav_series / nav_series.cummax() - 1.0
    events = []
    in_drawdown = False
    start = trough = None
    min_dd = 0.0
    for date, value in dd.items():
        value = float(value)
        if value < -1e-12 and not in_drawdown:
            in_drawdown = True
            start = trough = date
            min_dd = value
        elif in_drawdown:
            if value < min_dd:
                min_dd = value
                trough = date
            if value >= -1e-12:
                events.append(
                    {
                        "start": start.date().isoformat(),
                        "trough": trough.date().isoformat(),
                        "recovery": date.date().isoformat(),
                        "max_drawdown": min_dd,
                        "duration_calendar_days": int((date - start).days),
                        "duration_sessions": int(dd.loc[start:date].shape[0] - 1),
                        "recovered": True,
                    }
                )
                in_drawdown = False
    if in_drawdown:
        events.append(
            {
                "start": start.date().isoformat(),
                "trough": trough.date().isoformat(),
                "recovery": "",
                "max_drawdown": min_dd,
                "duration_calendar_days": int((dd.index[-1] - start).days),
                "duration_sessions": int(dd.loc[start:].shape[0] - 1),
                "recovered": False,
            }
        )
    return pd.DataFrame(events)


def _period_bounds(nav, start=None, end=None):
    index = (
        pd.DatetimeIndex(nav["valuation_date"])
        if isinstance(nav, pd.DataFrame)
        else pd.DatetimeIndex(nav.index)
    )
    explicit_start = start is not None
    if end is None:
        end = index.max()
    else:
        end = pd.Timestamp(end)
    if start is None:
        start = index.min()
    else:
        start = pd.Timestamp(start)
    observed_start = index[index >= start][0]
    observed_end = index[index <= end][-1]
    position = int(index.get_loc(observed_start))
    if position == 0 and explicit_start:
        raise RuntimeError("Cannot calculate a period return without a prior NAV")
    pre_start = index[0] if position == 0 else index[position - 1]
    return pre_start, observed_start, observed_end


def period_metrics(nav, strategy, cap, period, start=None, end=None, events=None):
    pre_start, observed_start, observed_end = _period_bounds(nav, start, end)
    series = nav.set_index("valuation_date")["nav"].loc[pre_start:observed_end]
    returns = series.pct_change().dropna()
    returns = returns.loc[returns.index >= observed_start]
    total = float(series.iloc[-1] / series.iloc[0] - 1.0)
    years = max(len(returns) / TRADING_DAYS, 1e-12)
    annualized = float((1.0 + total) ** (1.0 / years) - 1.0)
    volatility = float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS))
    downside = returns[returns < 0].std(ddof=1) * np.sqrt(TRADING_DAYS)
    sharpe = annualized / volatility if volatility > 0 else np.nan
    sortino = annualized / downside if downside > 0 else np.nan
    period_nav = series.loc[pre_start:observed_end]
    drawdown = period_nav / period_nav.cummax() - 1.0
    max_drawdown = float(drawdown.min())
    calmar = annualized / abs(max_drawdown) if max_drawdown < 0 else np.nan
    monthly = returns.resample("ME").apply(lambda x: (1.0 + x).prod() - 1.0)
    gains = monthly[monthly > 0]
    losses = monthly[monthly < 0]
    drawdown_events = _drawdown_events(period_nav)
    recovered = (
        drawdown_events[drawdown_events["recovered"]]
        if not drawdown_events.empty
        else drawdown_events
    )
    execution_events = pd.DataFrame()
    if events is not None:
        execution_events = events.copy()
        if not execution_events.empty:
            execution_events["execution_date"] = pd.to_datetime(
                execution_events["execution_date"]
            )
            execution_events = execution_events[
                (execution_events["execution_date"] >= observed_start)
                & (execution_events["execution_date"] <= observed_end)
            ]
    years_for_cost = max(len(returns) / TRADING_DAYS, 1e-12)
    annualized_turnover = (
        float(execution_events["actual_turnover"].sum() / years_for_cost)
        if not execution_events.empty
        else 0.0
    )
    total_cost_ratio = (
        float(execution_events["total_cost"].sum() / series.iloc[0])
        if not execution_events.empty
        else 0.0
    )
    return {
        "strategy": strategy,
        "label": STRATEGY_LABELS.get(strategy, strategy),
        "cap": float(cap),
        "period": period,
        "start": observed_start.date().isoformat(),
        "end": observed_end.date().isoformat(),
        "observations": int(len(returns)),
        "cumulative_return": total,
        "annualized_return": annualized,
        "annualized_volatility": volatility,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "monthly_win_rate": float((monthly > 0).mean()) if len(monthly) else np.nan,
        "average_winning_month": float(gains.mean()) if len(gains) else 0.0,
        "average_losing_month": float(losses.mean()) if len(losses) else 0.0,
        "profit_factor": float(gains.sum() / abs(losses.sum())) if len(losses) else np.nan,
        "best_month": float(monthly.max()) if len(monthly) else np.nan,
        "worst_month": float(monthly.min()) if len(monthly) else np.nan,
        "underwater_share": float((drawdown < -1e-12).mean()),
        "average_recovery_calendar_days": (
            float(recovered["duration_calendar_days"].mean())
            if len(recovered)
            else 0.0
        ),
        "longest_recovery_calendar_days": (
            int(recovered["duration_calendar_days"].max())
            if len(recovered)
            else 0
        ),
        "unrecovered_drawdown": (
            float(
                drawdown_events.loc[~drawdown_events["recovered"], "max_drawdown"].iloc[-1]
            )
            if not drawdown_events.empty and (~drawdown_events["recovered"]).any()
            else 0.0
        ),
        "unrecovered_duration_calendar_days": (
            int(
                drawdown_events.loc[
                    ~drawdown_events["recovered"], "duration_calendar_days"
                ].iloc[-1]
            )
            if not drawdown_events.empty and (~drawdown_events["recovered"]).any()
            else 0
        ),
        "rebalance_event_count": int(len(execution_events)),
        "executed_event_count": int(
            (execution_events["status"] == "executed").sum()
            if not execution_events.empty
            else 0
        ),
        "skipped_event_count": int(
            (execution_events["status"] == "skipped").sum()
            if not execution_events.empty
            else 0
        ),
        "annualized_turnover": annualized_turnover,
        "transaction_cost_ratio": total_cost_ratio,
        "annualized_cost_drag": float(total_cost_ratio / years_for_cost),
        "final_nav_from_period_start": float(series.iloc[-1] / series.iloc[0] * 100.0),
        "evidence_class": "VERIFIED_FRACTIONAL_CURRENT_ENGINE_REPLAY",
    }


def _format_pct(value):
    return "NA" if pd.isna(value) else f"{float(value):.2%}"


def _format_num(value):
    return "NA" if pd.isna(value) else f"{float(value):.2f}"


def write_notebook():
    notebook = {
        "cells": [
            {
                "cell_type": "markdown",
                "id": "recent-3m-overview",
                "metadata": {},
                "source": [
                    "# Theme Alpha LVT Recent 3-Month Review\n",
                    "\n",
                    "This practice notebook is a reproducible entry point for the dated\n",
                    "2026-09-06 refresh. It reads the isolated TickFlow snapshot and runs\n",
                    "`scripts/theme_alpha_lvt_recent_3m_review.py`; frozen Q12 artifacts are\n",
                    "not overwritten.\n",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "id": "repo-root-bootstrap",
                "metadata": {"tags": ["bootstrap"]},
                "outputs": [],
                "source": [
                    "import os\n",
                    "from xquant.project import find_repo_root\n",
                    "REPO_ROOT = find_repo_root()\n",
                    "os.chdir(REPO_ROOT)\n",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "id": "run-review-script",
                "metadata": {},
                "outputs": [],
                "source": ["%run scripts/theme_alpha_lvt_recent_3m_review.py\n"],
            },
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTEBOOK_PATH.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def write_review_note(summary, sensitivity, contract):
    recent = summary[summary["period"] == "recent_3m"].set_index("strategy")
    ytd = summary[summary["period"] == "2026_ytd"].set_index("strategy")
    latest_signal = contract["latest_valid_signal"]
    lines = [
        "# Theme Alpha LVT Recent 3-Month Review",
        "",
        f"Date: {contract['run_date']}",
        "",
        "## 目的",
        "",
        "应用户要求，补做最新三个月的独立 LVT 复核。Q12 冻结研究不改写；本次使用当前交易实现同口径的隔离 TickFlow 快照，单独比较全仓 Expanded LVT、Core80/LVT20/Def200 Cash 和原三资产 RiskParity。",
        "",
        "## 合约与数据",
        "",
        f"- 输入快照：`{contract['snapshot_root']}`；共同收盘截至 `{contract['market_data_end']}`，共 {contract['session_count']} 个会话。",
        "- 价格契约：本次使用交易侧 TickFlow forward-additive 快照；Q12 冻结研究使用 yfinance auto_adjust 数据，不能把两者的 NAV 直接拼接成一条收益曲线。",
        f"- 最近三个月窗口：`{contract['recent_start']}` 至 `{contract['market_data_end']}`，共 {contract['recent_observations']} 个收益观测；窗口起点使用前一交易日 NAV 作为归一化基准。",
        f"- 当前信号：每月 10/25 日（若非交易日取其后第一个交易日），信号收盘计算，下一交易日收盘执行。",
        f"- 当前参数：MA{contract['ma_window']}、{contract['momentum_window']} 日动量、{contract['volatility_window']} 日波动率、低波 Top{contract['top_n']}、RP{contract['risk_parity_window']}、LVT cap {contract['main_cap']:.0%}、Def{contract['defense_window']}、调仓阈值 {contract['rebalance_threshold']:.0%}、单资产变化上限 {contract['max_asset_trade']:.0%}。",
        "- 成本按当前纸面实现的 base/asset-extra bps 计入；采用 fractional holdings 研究 NAV，不等同 100 股整数手人工成交结果。",
        f"- 最新有效信号：`{latest_signal['signal_date']}`，市场收盘截至 `{latest_signal['market_data_date']}`，LVT 选择 `{', '.join(latest_signal['selected_lvt'])}`。",
        "",
        "## 最新三个月主结果",
        "",
        "| Strategy | 累计收益 | 年化波动 | 最大回撤 | Sharpe | Calmar | 年化换手 | 年化成本拖累 | 水下占比 | 未修复回撤 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for strategy in MAIN_STRATEGIES:
        row = recent.loc[strategy]
        lines.append(
            f"| {STRATEGY_LABELS[strategy]} | {_format_pct(row['cumulative_return'])} | {_format_pct(row['annualized_volatility'])} | {_format_pct(row['max_drawdown'])} | {_format_num(row['sharpe'])} | {_format_num(row['calmar'])} | {_format_pct(row['annualized_turnover'])} | {_format_pct(row['annualized_cost_drag'])} | {_format_pct(row['underwater_share'])} | {_format_pct(row['unrecovered_drawdown'])} |"
        )
    lines.extend([
        "",
        "### 2026 YTD 补充",
        "",
        "| Strategy | 累计收益 | 最大回撤 | Sharpe | 年化换手 | 年化成本拖累 |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for strategy in MAIN_STRATEGIES:
        row = ytd.loc[strategy]
        lines.append(
            f"| {STRATEGY_LABELS[strategy]} | {_format_pct(row['cumulative_return'])} | {_format_pct(row['max_drawdown'])} | {_format_num(row['sharpe'])} | {_format_pct(row['annualized_turnover'])} | {_format_pct(row['annualized_cost_drag'])} |"
        )
    lines.extend([
        "",
        "## Q5 观察",
        "",
        "- 本窗口月度收益、最好/最差月份、盈利因子见 `summary.csv`；逐月结果见 `monthly_returns.csv`。",
        "- 回撤事件和恢复时间见 `drawdown_events_recent_3m.csv`。窗口最后是否仍在水下必须看“未修复回撤”，不能只看已经完成的平均恢复时间。",
        "- 三条策略使用相同收盘、信号日、执行日、调仓阈值和成本实现；差异主要来自资产池/防守结构，不把整数手误差混进收益比较。",
        "",
        "## cap 敏感性",
        "",
        "本次只把 LVT 单资产 cap 作为独立敏感性轴，保持 MA、动量、Top-N、调仓与防守参数不变。详见 `cap_sensitivity_recent_3m.csv`。",
        "",
        "| cap | Standalone LVT 累计收益 | Standalone LVT MDD | Core80/LVT20 累计收益 | Core80/LVT20 MDD |",
        "|---:|---:|---:|---:|---:|",
    ])
    for cap in sorted(sensitivity["cap"].unique()):
        lvt_row = sensitivity[(sensitivity["cap"] == cap) & (sensitivity["strategy"] == LVT)].iloc[0]
        combined_row = sensitivity[(sensitivity["cap"] == cap) & (sensitivity["strategy"] == COMBINED)].iloc[0]
        lines.append(
            f"| {cap:.0%} | {_format_pct(lvt_row['cumulative_return'])} | {_format_pct(lvt_row['max_drawdown'])} | {_format_pct(combined_row['cumulative_return'])} | {_format_pct(combined_row['max_drawdown'])} |"
        )
    lines.extend([
        "",
        "## 通俗结论",
        "",
        f"- 本次确实补到了最新三个月：独立 LVT 的最新数据不再停在 2026-06-24，而是延伸到 `{contract['market_data_end']}`。",
        "- 这只是最新三个月的增量验证，不足以推翻 Q12 长样本结论；短窗口的赢家不能自动升级为主策略。",
        "- 最新有效 LVT 选择和信号明细在 `signals.csv`；独立 LVT 没有使用 Core 的 MA200 防守。Def200 只作用于组合里的沪深300/纳指核心仓位。",
        "- 本次 NAV 是当前纸面引擎的 fractional replay，没有生成独立 LVT 的真实账户 forward ledger，也没有证明 8,000 元整数手可按目标成交。",
        "- 下一步若要把独立 LVT 纳入正式观察，应为它建立单独冻结配置、单独纸面账户和独立成交台账；在此之前，Core80/LVT20/Def200 仍应作为默认实盘候选。",
        "",
        "## 文件",
        "",
        f"- Practice notebook: `{NOTEBOOK_PATH.relative_to(ROOT)}`",
        f"- Script: `scripts/theme_alpha_lvt_recent_3m_review.py`",
        f"- Outputs: `{OUTPUT_DIR.relative_to(ROOT)}/`",
        "- Main table: `summary.csv`",
        "- Signal audit: `signals.csv`",
        "- Cost/execution events: `events.csv`",
        "- Frozen reference preserved: `outputs/theme-alpha-q12-long-sample-proxy-validation/`",
    ])
    NOTE_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTE_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config, frames, market = load_market()
    targets, signal_rows = build_signal_catalog(config, market, MAIN_CAP)
    simulations = {
        strategy: simulate_strategy(config, market, targets, strategy, MAIN_CAP)
        for strategy in MAIN_STRATEGIES
    }

    market_end = market.sessions[-1]
    requested_start = market_end - pd.DateOffset(months=3)
    recent_start = market.sessions[market.sessions >= requested_start][0]
    summary_rows = []
    for strategy, result in simulations.items():
        nav = result["nav"]
        summary_rows.append(
            period_metrics(
                nav,
                strategy,
                MAIN_CAP,
                "recent_3m",
                start=recent_start,
                events=result["events"],
            )
        )
        summary_rows.append(
            period_metrics(
                nav,
                strategy,
                MAIN_CAP,
                "2026_ytd",
                start="2026-01-01",
                events=result["events"],
            )
        )
        summary_rows.append(
            period_metrics(
                nav,
                strategy,
                MAIN_CAP,
                "since_activation",
                events=result["events"],
            )
        )
    summary = pd.DataFrame(summary_rows)

    # Keep the cap grid deliberately small: it is a shape check, not a new
    # optimization pass.
    sensitivity_rows = []
    sensitivity_simulations = {}
    for cap in CAP_SENSITIVITY:
        cap_targets, _ = build_signal_catalog(config, market, cap)
        for strategy in (LVT, COMBINED):
            result = simulate_strategy(config, market, cap_targets, strategy, cap)
            sensitivity_simulations[(cap, strategy)] = result
            sensitivity_rows.append(
                period_metrics(
                    result["nav"],
                    strategy,
                    cap,
                    "recent_3m",
                    start=recent_start,
                    events=result["events"],
                )
            )
    sensitivity = pd.DataFrame(sensitivity_rows)

    nav_full = pd.concat(
        [result["nav"] for result in simulations.values()],
        ignore_index=True,
    )
    events = pd.concat(
        [result["events"] for result in simulations.values()],
        ignore_index=True,
    )
    signal_rows.to_csv(OUTPUT_DIR / "signals.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(OUTPUT_DIR / "summary.csv", index=False, encoding="utf-8-sig")
    sensitivity.to_csv(
        OUTPUT_DIR / "cap_sensitivity_recent_3m.csv",
        index=False,
        encoding="utf-8-sig",
    )
    events.to_csv(OUTPUT_DIR / "events.csv", index=False, encoding="utf-8-sig")
    nav_full.to_csv(OUTPUT_DIR / "nav_full.csv", index=False, encoding="utf-8-sig")

    recent_nav_frames = []
    drawdown_frames = []
    drawdown_event_frames = []
    for strategy, result in simulations.items():
        nav = result["nav"].set_index("valuation_date")
        pre_start, observed_start, observed_end = _period_bounds(
            result["nav"], recent_start
        )
        period = nav.loc[pre_start:observed_end].copy()
        period["normalized_nav"] = period["nav"] / period["nav"].iloc[0] * 100.0
        period["strategy"] = strategy
        recent_nav_frames.append(
            period.reset_index()[["valuation_date", "strategy", "nav", "normalized_nav", "daily_return", "cash_weight"]]
        )
        dd = period["normalized_nav"] / period["normalized_nav"].cummax() - 1.0
        drawdown_frames.append(
            pd.DataFrame(
                {
                    "valuation_date": period.index,
                    "strategy": strategy,
                    "drawdown": dd.values,
                }
            )
        )
        dd_events = _drawdown_events(period["normalized_nav"])
        if not dd_events.empty:
            dd_events.insert(0, "strategy", strategy)
            drawdown_event_frames.append(dd_events)
    pd.concat(recent_nav_frames, ignore_index=True).to_csv(
        OUTPUT_DIR / "nav_recent_3m.csv", index=False, encoding="utf-8-sig"
    )
    pd.concat(drawdown_frames, ignore_index=True).to_csv(
        OUTPUT_DIR / "underwater_recent_3m.csv", index=False, encoding="utf-8-sig"
    )
    pd.concat(drawdown_event_frames, ignore_index=True).to_csv(
        OUTPUT_DIR / "drawdown_events_recent_3m.csv", index=False, encoding="utf-8-sig"
    )

    monthly_rows = []
    annual_rows = []
    latest_rows = []
    average_rows = []
    for strategy, result in simulations.items():
        nav = result["nav"].set_index("valuation_date")
        daily = nav["nav"].pct_change().dropna()
        for month, value in daily.resample("ME").apply(lambda x: (1.0 + x).prod() - 1.0).items():
            monthly_rows.append({"strategy": strategy, "month": month.strftime("%Y-%m"), "return": float(value)})
        for year, value in daily.resample("YE").apply(lambda x: (1.0 + x).prod() - 1.0).items():
            annual_rows.append({"strategy": strategy, "year": int(year.year), "return": float(value)})
        recent_period = nav.loc[recent_start:market_end]
        latest = recent_period.iloc[-1]
        average_rows.append(
            {
                "strategy": strategy,
                "cap": MAIN_CAP,
                "average_cash_weight_recent_3m": float(recent_period["cash_weight"].mean()),
                **{
                    f"average_weight_{symbol}_recent_3m": float(
                        recent_period[f"weight_{symbol}"].mean()
                    )
                    for symbol in config.symbols
                },
            }
        )
        latest_rows.append(
            {
                "strategy": strategy,
                "cap": MAIN_CAP,
                "valuation_date": latest.name.date().isoformat(),
                "cash_weight": float(latest["cash_weight"]),
                **{f"weight_{symbol}": float(latest[f"weight_{symbol}"]) for symbol in config.symbols},
            }
        )
    pd.DataFrame(monthly_rows).to_csv(
        OUTPUT_DIR / "monthly_returns.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(annual_rows).to_csv(
        OUTPUT_DIR / "annual_returns.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(latest_rows).to_csv(
        OUTPUT_DIR / "latest_weights.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(average_rows).to_csv(
        OUTPUT_DIR / "average_weights_recent_3m.csv", index=False, encoding="utf-8-sig"
    )

    availability_rows = []
    for symbol in config.symbols:
        frame = frames[symbol]
        availability_rows.append(
            {
                "symbol": symbol,
                "first_date": pd.Timestamp(frame.index.min()).date().isoformat(),
                "last_date": pd.Timestamp(frame.index.max()).date().isoformat(),
                "rows": int(len(frame)),
            }
        )
    pd.DataFrame(availability_rows).to_csv(
        OUTPUT_DIR / "data_availability.csv", index=False, encoding="utf-8-sig"
    )

    latest_signal_row = signal_rows[signal_rows["valid"]].iloc[-1]
    latest_bundle = _target_for_signal(
        config,
        market,
        pd.Timestamp(latest_signal_row["signal_date"]),
        MAIN_CAP,
    )
    contract = {
        "run_date": "2026-09-06",
        "strategy_identity": "Independent LVT recent performance refresh",
        "snapshot_root": str(SNAPSHOT_ROOT),
        "snapshot_metadata": str(INPUT_ROOT / "market_snapshot_metadata.json"),
        "snapshot_source": "isolated TickFlow snapshot, period=1d, adjust=forward_additive",
        "market_data_start": market.sessions[0].date().isoformat(),
        "market_data_end": market_end.date().isoformat(),
        "session_count": int(len(market.sessions)),
        "recent_start": recent_start.date().isoformat(),
        "recent_observations": int(len(market.sessions[market.sessions >= recent_start])),
        "execution": "next complete XSHG close",
        "signal_days": list(config.params["signal_days"]),
        "ma_window": int(config.params["ma_window"]),
        "momentum_window": int(config.params["momentum_window"]),
        "volatility_window": int(config.params["volatility_window"]),
        "top_n": int(config.params["top_n"]),
        "risk_parity_window": int(config.params["risk_parity_window"]),
        "main_cap": MAIN_CAP,
        "defense_window": int(config.params["defense_ma_window"]),
        "rebalance_threshold": float(config.params["rebalance_threshold"]),
        "max_asset_trade": float(config.params["max_asset_trade"]),
        "costs": {
            "base_bps": float(config.costs.base_bps),
            "slippage_bps": float(config.costs.slippage_bps),
            "asset_extra_bps": dict(config.costs.asset_extra_bps),
        },
        "latest_valid_signal": {
            "signal_date": latest_signal_row["signal_date"],
            "execution_date": latest_signal_row["execution_date"],
            "market_data_date": market_end.date().isoformat(),
            "selected_lvt": list(json.loads(latest_signal_row["selected_lvt"])),
            "core_risk_on": json.loads(latest_signal_row["core_risk_on"]),
            "combined_target": latest_bundle[COMBINED],
        },
        "main_strategies": list(MAIN_STRATEGIES),
        "evidence_class": "VERIFIED_LATEST_MARKET_SNAPSHOT_PLUS_FRACTIONAL_CURRENT_ENGINE_REPLAY",
        "not_proven": [
            "independent LVT live paper account and forward ledger",
            "integer-lot broker fillability at 8,000 CNY",
            "ETF premium/iNAV, order book, suspension and broker-specific charges",
        ],
    }
    (OUTPUT_DIR / "contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # Small, reviewable plots for visual inspection.
    recent_wide = pd.concat(recent_nav_frames, ignore_index=True).pivot(
        index="valuation_date", columns="strategy", values="normalized_nav"
    )
    ax = recent_wide.plot(figsize=(12, 6), linewidth=1.8)
    ax.set_title("Theme Alpha LVT recent 3-month NAV (start = 100)")
    ax.set_ylabel("Normalized NAV")
    ax.grid(True, alpha=0.25)
    ax.legend([STRATEGY_LABELS.get(item, item) for item in recent_wide.columns])
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "nav_recent_3m.png", dpi=160)
    plt.close()

    underwater_wide = pd.concat(drawdown_frames, ignore_index=True).pivot(
        index="valuation_date", columns="strategy", values="drawdown"
    )
    ax = underwater_wide.plot(figsize=(12, 5), linewidth=1.8)
    ax.set_title("Theme Alpha LVT recent 3-month drawdown")
    ax.set_ylabel("Drawdown")
    ax.grid(True, alpha=0.25)
    ax.legend([STRATEGY_LABELS.get(item, item) for item in underwater_wide.columns])
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "underwater_recent_3m.png", dpi=160)
    plt.close()

    write_notebook()
    write_review_note(summary, sensitivity, contract)
    print(summary[summary["period"] == "recent_3m"].to_string(index=False))
    print(f"Wrote {OUTPUT_DIR}")
    print(f"Wrote {NOTEBOOK_PATH}")
    print(f"Wrote {NOTE_PATH}")


if __name__ == "__main__":
    main()
