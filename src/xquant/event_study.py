"""Point-in-time event-study helpers for production decision streams."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class EventStudyConfig:
    horizons: tuple[int, ...] = (5, 10, 20)
    round_trip_cost_bps: float = 20.0
    independent_gap_sessions: int = 20


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def _compression_execution(row: pd.Series, next_bar: pd.Series) -> tuple[str, float | None]:
    trigger = _finite(row.get("triggerPrice"))
    maximum = _finite(row.get("maxAcceptablePrice"))
    invalidation = _finite(row.get("invalidationPrice"))
    next_open = _finite(next_bar.get("Open"))
    next_high = _finite(next_bar.get("High"))
    next_low = _finite(next_bar.get("Low"))
    if None in (trigger, maximum, next_open, next_high, next_low):
        return "missing_execution_data", None
    if next_open > maximum:
        return "above_max", None
    if invalidation is not None and next_open < invalidation:
        return "invalidated_at_open", None
    if next_open >= trigger:
        return "triggered", next_open
    if next_high < trigger:
        return "not_triggered", None
    if invalidation is not None and next_low < invalidation:
        return "ambiguous_intraday_order", None
    return "triggered", trigger


def _entry_for_event(row: pd.Series, next_bar: pd.Series) -> tuple[str, float | None]:
    permission = str(row.get("permission") or "")
    setup = str(row.get("setup") or "")
    next_open = _finite(next_bar.get("Open"))
    if next_open is None:
        return "missing_execution_data", None
    if setup == "compression_breakout" and permission == "conditional":
        return _compression_execution(row, next_bar)
    maximum = _finite(row.get("maxAcceptablePrice"))
    if permission == "buy" and maximum is not None and next_open > maximum:
        return "above_max", None
    if permission == "buy":
        return "executed", next_open
    return "hypothetical_control", next_open


def attach_forward_outcomes(
    decisions: pd.DataFrame,
    price_loader: Callable[[str], pd.DataFrame],
    *,
    config: EventStudyConfig = EventStudyConfig(),
    setups: Iterable[str] = ("breakout", "pullback", "compression_breakout"),
) -> pd.DataFrame:
    """Attach next-session execution and forward path outcomes to decisions.

    Decisions are assumed to be point-in-time outputs. Future prices are read
    only after selecting the decision row and are never fed back into policy.
    """
    selected = decisions[
        decisions["setup"].isin(tuple(setups))
        & ~decisions["dataStale"].fillna(True)
        & ~decisions["dataGap"].fillna(True)
    ].copy()
    if selected.empty:
        return selected
    selected["decisionDate"] = pd.to_datetime(selected["decisionDate"])
    rows: list[dict[str, Any]] = []
    max_horizon = max(config.horizons)
    cost_pct = config.round_trip_cost_bps / 100.0

    for symbol, symbol_events in selected.groupby("symbol", sort=False):
        prices = price_loader(str(symbol)).sort_index().copy()
        prices.index = pd.DatetimeIndex(prices.index).tz_localize(None).normalize()
        prices = prices[~prices.index.duplicated(keep="last")]
        required = {"Open", "High", "Low", "Close"}
        if prices.empty or not required.issubset(prices.columns):
            continue
        for _, event in symbol_events.sort_values("decisionDate").iterrows():
            decision_date = pd.Timestamp(event["decisionDate"]).normalize()
            future = prices.loc[prices.index > decision_date]
            if future.empty:
                continue
            next_bar = future.iloc[0]
            execution_status, entry_price = _entry_for_event(event, next_bar)
            output = event.to_dict()
            output.update({
                "nextSessionDate": future.index[0].date().isoformat(),
                "executionOutcome": execution_status,
                "entryPrice": entry_price,
                "formalSignal": str(event.get("permission")) in {"buy", "conditional"},
            })
            path = future.iloc[:max_horizon]
            if entry_price is not None and entry_price > 0:
                for horizon in config.horizons:
                    if len(future) >= horizon:
                        exit_close = float(future.iloc[horizon - 1]["Close"])
                        gross = (exit_close / entry_price - 1.0) * 100.0
                        output[f"grossReturn{horizon}Pct"] = gross
                        output[f"netReturn{horizon}Pct"] = gross - cost_pct
                        output[f"positive{horizon}"] = gross - cost_pct > 0
                    else:
                        output[f"grossReturn{horizon}Pct"] = None
                        output[f"netReturn{horizon}Pct"] = None
                        output[f"positive{horizon}"] = None
                if not path.empty:
                    output["mfe20Pct"] = (float(path["High"].max()) / entry_price - 1.0) * 100.0
                    output["mae20Pct"] = (float(path["Low"].min()) / entry_price - 1.0) * 100.0
                    signal_st = _finite(event.get("stVal"))
                    output["fixedSignalStBroken20"] = (
                        bool((path["Close"] < signal_st).any()) if signal_st is not None else None
                    )
                else:
                    output["mfe20Pct"] = None
                    output["mae20Pct"] = None
                    output["fixedSignalStBroken20"] = None
            else:
                for horizon in config.horizons:
                    output[f"grossReturn{horizon}Pct"] = None
                    output[f"netReturn{horizon}Pct"] = None
                    output[f"positive{horizon}"] = None
                output["mfe20Pct"] = None
                output["mae20Pct"] = None
                output["fixedSignalStBroken20"] = None
            output["decisionPosition"] = int(prices.index.searchsorted(decision_date, side="right") - 1)
            rows.append(output)

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result = result.sort_values(["symbol", "setup", "permission", "decisionDate"]).reset_index(drop=True)
    result["independentEvent"] = False
    for _, indices in result.groupby(["symbol", "setup", "permission"], sort=False).groups.items():
        previous_position: int | None = None
        for index in indices:
            position = int(result.at[index, "decisionPosition"])
            independent = previous_position is None or position - previous_position >= config.independent_gap_sessions
            result.at[index, "independentEvent"] = independent
            if independent:
                previous_position = position
    return result


def summarize_events(
    events: pd.DataFrame,
    *,
    group_columns: Iterable[str] = ("setup", "permission", "stage"),
    horizons: Iterable[int] = (5, 10, 20),
    independent_only: bool = True,
) -> pd.DataFrame:
    data = events[events["independentEvent"]].copy() if independent_only else events.copy()
    if data.empty:
        return pd.DataFrame()
    group_columns = list(group_columns)
    rows: list[dict[str, Any]] = []
    for keys, group in data.groupby(group_columns, dropna=False):
        keys = keys if isinstance(keys, tuple) else (keys,)
        row = dict(zip(group_columns, keys))
        row.update({
            "eventCount": int(len(group)),
            "formalSignalCount": int(group["formalSignal"].sum()),
            "executableCount": int(group["entryPrice"].notna().sum()),
            "executionRate": float(group["entryPrice"].notna().mean()),
            "avgMfe20Pct": group["mfe20Pct"].mean(),
            "avgMae20Pct": group["mae20Pct"].mean(),
            "fixedSignalStBreakRate20": group["fixedSignalStBroken20"].mean(),
        })
        for horizon in horizons:
            values = group[f"netReturn{horizon}Pct"].dropna()
            row[f"sample{horizon}"] = int(len(values))
            row[f"avgNetReturn{horizon}Pct"] = values.mean()
            row[f"medianNetReturn{horizon}Pct"] = values.median()
            row[f"hitRate{horizon}"] = (values > 0).mean() if not values.empty else None
        rows.append(row)
    return pd.DataFrame(rows).sort_values(group_columns).reset_index(drop=True)
