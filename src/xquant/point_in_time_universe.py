"""Point-in-time universe construction from information available by each snapshot."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import numpy as np
import pandas as pd


DEFAULT_LIQUIDITY_FLOORS = {
    "a_share": 20_000_000.0,
    "hong_kong": 10_000_000.0,
    "us": 20_000_000.0,
    "crypto": 50_000_000.0,
    "gold": 20_000_000.0,
}

DEFAULT_MARKET_CAPS = {
    "a_share": 30,
    "hong_kong": 5,
    "us": 10,
    "crypto": 2,
    "gold": 2,
}


@dataclass(frozen=True)
class UniverseConfig:
    """Frozen eligibility and capacity rules for a point-in-time universe."""

    min_history_sessions: int = 252
    liquidity_lookback_sessions: int = 63
    max_suspension_rate: float = 0.05
    min_data_completeness: float = 0.95
    liquidity_floors: Mapping[str, float] = field(
        default_factory=lambda: dict(DEFAULT_LIQUIDITY_FLOORS)
    )
    market_caps: Mapping[str, int] = field(
        default_factory=lambda: dict(DEFAULT_MARKET_CAPS)
    )
    turnover_multipliers: Mapping[str, float] = field(default_factory=dict)
    excluded_symbols: frozenset[str] = field(default_factory=frozenset)


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.sort_index().copy()
    result.index = pd.DatetimeIndex(result.index).tz_localize(None).normalize()
    return result[~result.index.duplicated(keep="last")]


def _complete_session_mask(frame: pd.DataFrame) -> pd.Series:
    """Identify rows with finite, positive OHLC and an observed volume value."""
    required = ["Open", "High", "Low", "Close", "Volume"]
    numeric = frame.reindex(columns=required).apply(pd.to_numeric, errors="coerce")
    finite = pd.DataFrame(
        np.isfinite(numeric.to_numpy()), index=numeric.index, columns=numeric.columns
    )
    return finite.all(axis=1) & numeric[["Open", "High", "Low", "Close"]].gt(0).all(axis=1)


def _official_trading_status_mask(frame: pd.DataFrame) -> pd.Series | None:
    """Use an official trading-status field when a supported one is present."""
    candidates = (
        "isTrading", "is_trading", "isTradable", "is_tradable",
        "tradable", "tradeable", "tradeStatus", "trade_status",
    )
    column = next((name for name in candidates if name in frame.columns), None)
    if column is None:
        return None
    status = frame[column]
    if pd.api.types.is_bool_dtype(status):
        return status.fillna(False).astype(bool)
    if pd.api.types.is_numeric_dtype(status):
        return pd.to_numeric(status, errors="coerce").fillna(0).gt(0)
    normalized = status.astype("string").str.strip().str.lower()
    trading_values = {
        "1", "true", "trading", "trade", "normal", "active",
        "交易", "正常", "正常交易",
    }
    return normalized.isin(trading_values).fillna(False)


def _tradable_session_mask(frame: pd.DataFrame) -> pd.Series:
    """Require complete OHLC, positive volume, and official tradable status."""
    complete = _complete_session_mask(frame)
    volume = (
        pd.to_numeric(frame["Volume"], errors="coerce")
        if "Volume" in frame else pd.Series(np.nan, index=frame.index)
    )
    result = complete & volume.gt(0)
    official = _official_trading_status_mask(frame)
    return result & official if official is not None else result


def evaluate_snapshot(
    prices_by_symbol: Mapping[str, pd.DataFrame],
    market_by_symbol: Mapping[str, str],
    reference_calendars: Mapping[str, pd.DatetimeIndex],
    *,
    snapshot_date: pd.Timestamp,
    effective_date: pd.Timestamp,
    config: UniverseConfig = UniverseConfig(),
    reference_calendar_by_symbol: Mapping[str, pd.DatetimeIndex] | None = None,
) -> pd.DataFrame:
    """Evaluate candidates using only rows dated on or before ``snapshot_date``.

    Qualified candidates are ranked by trailing median traded value within each
    market. Selection never inspects returns after the snapshot.
    """
    snapshot_date = pd.Timestamp(snapshot_date).normalize()
    effective_date = pd.Timestamp(effective_date).normalize()
    rows: list[dict[str, object]] = []
    required_columns = ["Open", "High", "Low", "Close", "Volume"]

    for symbol, raw in prices_by_symbol.items():
        market = market_by_symbol[symbol]
        history = _normalize(raw).loc[:snapshot_date]
        valid_history = history.loc[_tradable_session_mask(history)]
        history_sessions = int(len(valid_history))

        symbol_calendar = (
            reference_calendar_by_symbol.get(symbol)
            if reference_calendar_by_symbol is not None else None
        )
        calendar = pd.DatetimeIndex(
            symbol_calendar
            if symbol_calendar is not None
            else reference_calendars.get(market, valid_history.index)
        )
        calendar = calendar[calendar <= snapshot_date]
        trailing_calendar = calendar[-config.liquidity_lookback_sessions :]
        trailing = history.reindex(trailing_calendar)
        expected_sessions = int(len(trailing_calendar))
        complete_sessions = int(_complete_session_mask(trailing).sum())
        observed_sessions = int(_tradable_session_mask(trailing).sum())
        suspension_rate = (
            1.0 - observed_sessions / expected_sessions if expected_sessions else 1.0
        )
        completeness = (
            complete_sessions / expected_sessions
            if expected_sessions else 0.0
        )
        turnover = (
            pd.to_numeric(trailing.get("Close"), errors="coerce")
            * pd.to_numeric(trailing.get("Volume"), errors="coerce")
            * float(config.turnover_multipliers.get(symbol, 1.0))
        )
        turnover = turnover.where(_tradable_session_mask(trailing))
        median_turnover = float(turnover.median()) if turnover.notna().any() else np.nan
        liquidity_floor = float(config.liquidity_floors.get(market, np.inf))

        reasons: list[str] = []
        if symbol in config.excluded_symbols:
            reasons.append("excluded_non_tradable")
        if history_sessions < config.min_history_sessions:
            reasons.append("insufficient_history")
        if expected_sessions < config.liquidity_lookback_sessions:
            reasons.append("insufficient_calendar_history")
        if not np.isfinite(median_turnover) or median_turnover < liquidity_floor:
            reasons.append("below_liquidity_floor")
        if suspension_rate > config.max_suspension_rate:
            reasons.append("excess_suspension_rate")
        if completeness < config.min_data_completeness:
            reasons.append("incomplete_data")

        rows.append({
            "snapshotDate": snapshot_date,
            "effectiveDate": effective_date,
            "symbol": symbol,
            "market": market,
            "historySessions": history_sessions,
            "expectedLookbackSessions": expected_sessions,
            "completeLookbackSessions": complete_sessions,
            "observedLookbackSessions": observed_sessions,
            "medianTradedValue": median_turnover,
            "liquidityFloor": liquidity_floor,
            "suspensionRate": suspension_rate,
            "dataCompleteness": completeness,
            "qualified": not reasons,
            "failureReasons": "|".join(reasons),
        })

    result = pd.DataFrame(rows)
    result["liquidityRank"] = np.nan
    result["selected"] = False
    for market, group in result[result["qualified"]].groupby("market"):
        ranked = group.sort_values(
            ["medianTradedValue", "symbol"], ascending=[False, True]
        )
        result.loc[ranked.index, "liquidityRank"] = np.arange(1, len(ranked) + 1)
        cap = int(config.market_caps.get(market, 0))
        result.loc[ranked.index[:cap], "selected"] = True
    return result.sort_values(["market", "liquidityRank", "symbol"], na_position="last")


def filter_entries_by_membership(
    entries: pd.DataFrame,
    membership: pd.DataFrame,
) -> pd.DataFrame:
    """Keep entry signals selected by the latest universe effective that day."""
    if entries.empty or membership.empty:
        return entries.iloc[0:0].copy()
    selected = membership[membership["selected"]].copy()
    selected["effectiveDate"] = pd.to_datetime(selected["effectiveDate"]).dt.normalize()
    entries = entries.copy()
    entries["signalDate"] = pd.to_datetime(entries["signalDate"]).dt.normalize()
    dates = sorted(selected["effectiveDate"].unique())
    active_by_date = {
        pd.Timestamp(date): set(selected.loc[selected["effectiveDate"].eq(date), "symbol"])
        for date in dates
    }

    def eligible(row: pd.Series) -> bool:
        candidates = [date for date in dates if date <= row["signalDate"]]
        return bool(candidates and row["symbol"] in active_by_date[max(candidates)])

    return entries[entries.apply(eligible, axis=1)].reset_index(drop=True)


def add_membership_transitions(membership: pd.DataFrame) -> pd.DataFrame:
    """Annotate entry, retention, and removal without dropping old records."""
    result = membership.sort_values(["effectiveDate", "symbol"]).copy()
    previous: set[str] = set()
    transitions: dict[tuple[pd.Timestamp, str], str] = {}
    for effective_date, group in result.groupby("effectiveDate", sort=True):
        current = set(group.loc[group["selected"], "symbol"])
        for row in group.itertuples():
            if row.symbol in current and row.symbol in previous:
                event = "retained"
            elif row.symbol in current:
                event = "entered"
            elif row.symbol in previous and not row.qualified:
                event = "exited_ineligible"
            elif row.symbol in previous:
                event = "exited_rank_cap"
            else:
                event = "not_selected"
            transitions[(pd.Timestamp(effective_date), row.symbol)] = event
        previous = current
    result["membershipEvent"] = [
        transitions[(pd.Timestamp(row.effectiveDate), row.symbol)]
        for row in result.itertuples()
    ]
    return result
