"""Event-driven portfolio backtests for point-in-time decision streams."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PortfolioConfig:
    initial_capital: float = 1_000_000.0
    commission_bps: float = 5.0
    slippage_bps: float = 5.0
    max_position_weight: float = 0.10
    max_concurrent_positions: int = 10
    max_gross_exposure: float = 1.0


@dataclass
class _Position:
    symbol: str
    market: str
    quantity: float
    entry_date: pd.Timestamp
    signal_date: pd.Timestamp
    entry_price: float
    entry_notional: float
    entry_commission: float
    setup: str


def normalize_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Normalize an OHLC/ST frame to unique, timezone-naive daily sessions."""
    result = prices.sort_index().copy()
    result.index = pd.DatetimeIndex(result.index).tz_localize(None).normalize()
    return result[~result.index.duplicated(keep="last")]


def decision_entries(
    decisions: pd.DataFrame,
    variant: str,
) -> pd.DataFrame:
    """Select pre-defined entry candidates without inspecting future prices."""
    clean = decisions[
        ~decisions["dataStale"].fillna(True) & ~decisions["dataGap"].fillna(True)
    ].copy()
    if variant == "all_bull_flip":
        selected = clean[clean["setup"].eq("breakout")].copy()
        selected["maxAcceptablePrice"] = np.nan
    elif variant == "breakout_right_side_5":
        selected = clean[
            clean["setup"].eq("breakout") & clean["permission"].eq("buy")
        ].copy()
    elif variant == "pullback":
        selected = clean[
            clean["setup"].eq("pullback") & clean["permission"].eq("buy")
        ].copy()
    elif variant == "breakout_plus_pullback":
        selected = clean[
            clean["permission"].eq("buy")
            & clean["setup"].isin(["breakout", "pullback"])
        ].copy()
    else:
        raise ValueError(f"unknown decision-stream variant: {variant}")
    selected["signalDate"] = pd.to_datetime(selected["decisionDate"]).dt.normalize()
    selected["score"] = pd.to_numeric(selected.get("readinessScore"), errors="coerce").fillna(0)
    return selected[
        ["signalDate", "symbol", "market", "setup", "score", "maxAcceptablePrice"]
    ].drop_duplicates(["signalDate", "symbol"], keep="first")


def simple_supertrend_entries(
    prices_by_symbol: Mapping[str, pd.DataFrame],
    market_by_symbol: Mapping[str, str],
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    """Create entries on completed bearish-to-bullish SuperTrend flips."""
    rows: list[dict[str, Any]] = []
    for symbol, raw in prices_by_symbol.items():
        prices = normalize_prices(raw)
        if "ST_Dir" not in prices:
            continue
        direction = pd.to_numeric(prices["ST_Dir"], errors="coerce")
        flips = (direction > 0) & (direction.shift(1) <= 0)
        for date in prices.index[flips & (prices.index >= start) & (prices.index <= end)]:
            rows.append({
                "signalDate": date,
                "symbol": symbol,
                "market": market_by_symbol[symbol],
                "setup": "simple_supertrend",
                "score": 0.0,
                "maxAcceptablePrice": np.nan,
            })
    return pd.DataFrame(rows, columns=[
        "signalDate", "symbol", "market", "setup", "score", "maxAcceptablePrice"
    ])


def buy_hold_entry(
    symbol: str,
    market: str,
    *,
    signal_date: pd.Timestamp,
) -> pd.DataFrame:
    return pd.DataFrame([{
        "signalDate": pd.Timestamp(signal_date).normalize(),
        "symbol": symbol,
        "market": market,
        "setup": "buy_hold",
        "score": 0.0,
        "maxAcceptablePrice": np.nan,
    }])


def _next_session(index: pd.DatetimeIndex, date: pd.Timestamp) -> pd.Timestamp | None:
    position = int(index.searchsorted(pd.Timestamp(date).normalize(), side="right"))
    return index[position] if position < len(index) else None


def _next_valid_open_session(
    frame: pd.DataFrame,
    date: pd.Timestamp,
) -> pd.Timestamp | None:
    """Return the first later session with a finite, positive opening price."""
    later = frame.index[frame.index > pd.Timestamp(date).normalize()]
    if later.empty or "Open" not in frame:
        return None
    opens = pd.to_numeric(frame.loc[later, "Open"], errors="coerce")
    valid = opens.notna() & np.isfinite(opens) & opens.gt(0)
    return pd.Timestamp(opens.index[valid][0]) if valid.any() else None


def run_signal_portfolio(
    entries: pd.DataFrame,
    prices_by_symbol: Mapping[str, pd.DataFrame],
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    config: PortfolioConfig = PortfolioConfig(),
    exit_on_supertrend_bear: bool = True,
    benchmark_full_allocation: bool = False,
) -> dict[str, pd.DataFrame]:
    """Backtest next-session entries and next-session SuperTrend exits.

    Signals are ranked only by their point-in-time score, then symbol. Entries
    that cannot be funded within the locked portfolio constraints are rejected.
    """
    start = pd.Timestamp(start).normalize()
    end = pd.Timestamp(end).normalize()
    prices = {
        symbol: normalize_prices(frame).loc[start:end]
        for symbol, frame in prices_by_symbol.items()
    }
    prices = {symbol: frame for symbol, frame in prices.items() if not frame.empty}
    calendar = pd.DatetimeIndex(sorted(set().union(*(frame.index for frame in prices.values()))))
    if calendar.empty:
        raise ValueError("no price sessions in requested backtest window")

    scheduled_entries: dict[pd.Timestamp, list[dict[str, Any]]] = defaultdict(list)
    rejection_rows: list[dict[str, Any]] = []
    for row in entries.to_dict("records"):
        symbol = str(row["symbol"])
        if symbol not in prices:
            continue
        signal_date = pd.Timestamp(row["signalDate"]).normalize()
        execution_date = _next_session(prices[symbol].index, signal_date)
        if execution_date is None or execution_date > end:
            continue
        row["signalDate"] = signal_date
        row["executionDate"] = execution_date
        scheduled_entries[execution_date].append(row)

    cash = float(config.initial_capital)
    positions: dict[str, _Position] = {}
    pending_exits: dict[pd.Timestamp, set[str]] = defaultdict(set)
    latest_close: dict[str, float] = {}
    nav_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    order_rows: list[dict[str, Any]] = []
    entry_cash_cost: dict[str, float] = {}
    turnover_by_date: dict[pd.Timestamp, float] = defaultdict(float)
    commission_rate = config.commission_bps / 10_000.0
    slippage_rate = config.slippage_bps / 10_000.0

    for date in calendar:
        for symbol in list(pending_exits.pop(date, set())):
            position = positions.get(symbol)
            bar = prices[symbol].loc[date] if symbol in prices and date in prices[symbol].index else None
            if position is None:
                continue
            raw_open_value = pd.to_numeric(
                pd.Series([bar.get("Open") if bar is not None else np.nan]),
                errors="coerce",
            ).iloc[0]
            if pd.isna(raw_open_value) or not np.isfinite(raw_open_value) or raw_open_value <= 0:
                delayed_date = _next_valid_open_session(prices[symbol], date)
                if delayed_date is not None and delayed_date <= end:
                    pending_exits[delayed_date].add(symbol)
                continue
            raw_open = float(raw_open_value)
            execution_price = raw_open * (1.0 - slippage_rate)
            notional = position.quantity * execution_price
            commission = notional * commission_rate
            proceeds = notional - commission
            cash += proceeds
            turnover_by_date[date] += notional
            basis = entry_cash_cost.pop(symbol)
            pnl = proceeds - basis
            trade_rows.append({
                "symbol": symbol,
                "market": position.market,
                "setup": position.setup,
                "signalDate": position.signal_date,
                "entryDate": position.entry_date,
                "exitDate": date,
                "entryPrice": position.entry_price,
                "exitPrice": execution_price,
                "quantity": position.quantity,
                "entryNotional": position.entry_notional,
                "exitNotional": notional,
                "entryCommission": position.entry_commission,
                "exitCommission": commission,
                "netPnl": pnl,
                "netReturn": pnl / basis,
                "holdingCalendarDays": (date - position.entry_date).days,
                "exitReason": "supertrend_bear_flip",
            })
            order_rows.append({
                "date": date, "symbol": symbol, "side": "sell", "status": "executed",
                "reason": "supertrend_bear_flip", "rawOpen": raw_open,
                "executionPrice": execution_price, "notional": notional,
                "commission": commission,
            })
            del positions[symbol]

        def opening_mark(symbol: str, position: _Position) -> float:
            frame = prices[symbol]
            if date in frame.index:
                raw_open = pd.to_numeric(
                    pd.Series([frame.at[date, "Open"]]), errors="coerce"
                ).iloc[0]
                if pd.notna(raw_open) and np.isfinite(raw_open) and raw_open > 0:
                    return float(raw_open)
            return latest_close.get(symbol, position.entry_price)

        pre_entry_equity = cash + sum(
            position.quantity * opening_mark(symbol, position)
            for symbol, position in positions.items()
        )
        gross_value = sum(
            position.quantity * opening_mark(symbol, position)
            for symbol, position in positions.items()
        )

        candidates = sorted(
            scheduled_entries.get(date, []),
            key=lambda item: (-float(item.get("score", 0.0)), str(item["symbol"])),
        )
        for candidate in candidates:
            symbol = str(candidate["symbol"])
            bar = prices[symbol].loc[date]
            raw_open = float(bar["Open"])
            maximum = candidate.get("maxAcceptablePrice")
            reason: str | None = None
            if symbol in positions:
                reason = "already_held"
            elif pd.notna(maximum) and raw_open > float(maximum):
                reason = "above_max_acceptable_price"
            elif len(positions) >= config.max_concurrent_positions:
                reason = "concurrency_limit"
            execution_price = raw_open * (1.0 + slippage_rate)
            target_weight = 1.0 if benchmark_full_allocation else config.max_position_weight
            target_notional = pre_entry_equity * target_weight
            gross_room = max(0.0, pre_entry_equity * config.max_gross_exposure - gross_value)
            affordable = cash / (1.0 + commission_rate)
            notional = min(target_notional, gross_room, affordable)
            if reason is None and notional <= 1e-9:
                reason = "capital_limit"
            if reason is not None:
                rejection_rows.append({
                    "date": date, "signalDate": candidate["signalDate"], "symbol": symbol,
                    "market": candidate["market"], "setup": candidate["setup"], "reason": reason,
                })
                order_rows.append({
                    "date": date, "symbol": symbol, "side": "buy", "status": "rejected",
                    "reason": reason, "rawOpen": raw_open, "executionPrice": np.nan,
                    "notional": 0.0, "commission": 0.0,
                })
                continue
            quantity = notional / execution_price
            commission = notional * commission_rate
            cash -= notional + commission
            gross_value += notional
            turnover_by_date[date] += notional
            position = _Position(
                symbol=symbol,
                market=str(candidate["market"]),
                quantity=quantity,
                entry_date=date,
                signal_date=pd.Timestamp(candidate["signalDate"]),
                entry_price=execution_price,
                entry_notional=notional,
                entry_commission=commission,
                setup=str(candidate["setup"]),
            )
            positions[symbol] = position
            entry_cash_cost[symbol] = notional + commission
            order_rows.append({
                "date": date, "symbol": symbol, "side": "buy", "status": "executed",
                "reason": "signal", "rawOpen": raw_open, "executionPrice": execution_price,
                "notional": notional, "commission": commission,
            })

        for symbol, frame in prices.items():
            if date in frame.index and pd.notna(frame.at[date, "Close"]):
                latest_close[symbol] = float(frame.at[date, "Close"])

        market_value = sum(
            position.quantity * latest_close.get(symbol, position.entry_price)
            for symbol, position in positions.items()
        )
        nav = cash + market_value
        nav_rows.append({
            "date": date,
            "nav": nav,
            "cash": cash,
            "marketValue": market_value,
            "grossExposure": market_value / nav if nav else np.nan,
            "positionCount": len(positions),
            "tradedNotional": turnover_by_date[date],
        })

        if exit_on_supertrend_bear:
            for symbol in list(positions):
                frame = prices[symbol]
                if date not in frame.index or pd.isna(frame.at[date, "ST_Dir"]):
                    continue
                if float(frame.at[date, "ST_Dir"]) < 0:
                    exit_date = _next_valid_open_session(frame, date)
                    if exit_date is not None and exit_date <= end:
                        pending_exits[exit_date].add(symbol)

    nav = pd.DataFrame(nav_rows)
    nav["return"] = nav["nav"].pct_change().fillna(nav["nav"].iloc[0] / config.initial_capital - 1.0)
    nav["peak"] = nav["nav"].cummax().clip(lower=config.initial_capital)
    nav["drawdown"] = nav["nav"] / nav["peak"] - 1.0
    open_rows = [{
        "symbol": p.symbol, "market": p.market, "setup": p.setup,
        "signalDate": p.signal_date, "entryDate": p.entry_date,
        "entryPrice": p.entry_price, "quantity": p.quantity,
        "lastClose": latest_close.get(p.symbol, p.entry_price),
        "unrealizedPnl": p.quantity * latest_close.get(p.symbol, p.entry_price) - entry_cash_cost[p.symbol],
    } for p in positions.values()]
    return {
        "nav": nav,
        "trades": pd.DataFrame(trade_rows),
        "orders": pd.DataFrame(order_rows),
        "rejections": pd.DataFrame(rejection_rows),
        "open_positions": pd.DataFrame(open_rows),
    }


def performance_metrics(
    nav: pd.DataFrame,
    trades: pd.DataFrame | None = None,
) -> dict[str, float | int]:
    """Calculate portfolio, utilization, turnover, and round-trip statistics."""
    if nav.empty:
        raise ValueError("NAV is empty")
    first_nav = float(nav.iloc[0]["nav"])
    first_return = float(nav.iloc[0]["return"])
    start_nav = first_nav / (1.0 + first_return) if first_return > -1.0 else first_nav
    end_nav = float(nav.iloc[-1]["nav"])
    elapsed_days = max(1, (pd.Timestamp(nav.iloc[-1]["date"]) - pd.Timestamp(nav.iloc[0]["date"])).days)
    years = elapsed_days / 365.25
    total_return = end_nav / start_nav - 1.0
    cagr = (end_nav / start_nav) ** (1.0 / years) - 1.0 if start_nav > 0 else np.nan
    returns = pd.to_numeric(nav["return"], errors="coerce").dropna()
    observations_per_year = len(returns) / years
    volatility = returns.std(ddof=1) * np.sqrt(observations_per_year) if len(returns) > 1 else np.nan
    sharpe = returns.mean() / returns.std(ddof=1) * np.sqrt(observations_per_year) if returns.std(ddof=1) > 0 else np.nan
    downside = returns[returns < 0]
    sortino = (
        returns.mean() / downside.std(ddof=1) * np.sqrt(observations_per_year)
        if len(downside) > 1 and downside.std(ddof=1) > 0 else np.nan
    )
    max_drawdown = float(nav["drawdown"].min())
    calmar = cagr / abs(max_drawdown) if max_drawdown < 0 else np.nan
    average_nav = float(nav["nav"].mean())
    total_turnover = float(nav["tradedNotional"].sum() / average_nav) if average_nav else np.nan
    result: dict[str, float | int] = {
        "startNav": start_nav,
        "endNav": end_nav,
        "totalReturn": total_return,
        "cagr": cagr,
        "annualizedVolatility": volatility,
        "sharpe": sharpe,
        "sortino": sortino,
        "maxDrawdown": max_drawdown,
        "calmar": calmar,
        "totalTurnover": total_turnover,
        "annualizedTurnover": total_turnover / years,
        "averageGrossExposure": float(nav["grossExposure"].mean()),
        "maxGrossExposure": float(nav["grossExposure"].max()),
        "averagePositionCount": float(nav["positionCount"].mean()),
        "maxPositionCount": int(nav["positionCount"].max()),
    }
    trades = trades if trades is not None else pd.DataFrame()
    if trades.empty:
        result.update({
            "closedTrades": 0, "winRate": np.nan, "averageTradeReturn": np.nan,
            "medianTradeReturn": np.nan, "profitFactor": np.nan,
            "averageHoldingDays": np.nan,
        })
        return result
    pnl = pd.to_numeric(trades["netPnl"], errors="coerce")
    gains = float(pnl[pnl > 0].sum())
    losses = float(-pnl[pnl < 0].sum())
    result.update({
        "closedTrades": int(len(trades)),
        "winRate": float((pnl > 0).mean()),
        "averageTradeReturn": float(trades["netReturn"].mean()),
        "medianTradeReturn": float(trades["netReturn"].median()),
        "profitFactor": gains / losses if losses > 0 else np.nan,
        "averageHoldingDays": float(trades["holdingCalendarDays"].mean()),
    })
    return result


def period_metrics(
    nav: pd.DataFrame,
    grouper: Callable[[pd.Series], Iterable[Any]],
) -> pd.DataFrame:
    """Return compounded return and risk statistics for calendar subperiods."""
    data = nav.copy()
    data["period"] = list(grouper(pd.to_datetime(data["date"])))
    rows = []
    for period, group in data.groupby("period", sort=True):
        compounded = float((1.0 + group["return"]).prod() - 1.0)
        volatility = float(group["return"].std(ddof=1) * np.sqrt(365.25)) if len(group) > 1 else np.nan
        sharpe = (
            float(group["return"].mean() / group["return"].std(ddof=1) * np.sqrt(365.25))
            if group["return"].std(ddof=1) > 0 else np.nan
        )
        rows.append({
            "period": period, "return": compounded, "volatility": volatility,
            "sharpe": sharpe, "maxDrawdownWithinPeriod": float(
                ((1.0 + group["return"]).cumprod() / (1.0 + group["return"]).cumprod().cummax() - 1.0).min()
            ),
        })
    return pd.DataFrame(rows)
