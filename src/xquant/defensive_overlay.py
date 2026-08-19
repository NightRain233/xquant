"""Defensive entry gates and core/satellite portfolio helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from xquant.portfolio import inverse_volatility_weights
from xquant.signal_portfolio import normalize_prices


@dataclass(frozen=True)
class CorePortfolioConfig:
    initial_capital: float = 1_000_000.0
    volatility_window: int = 20
    rebalance_sessions: int = 10
    one_way_cost_bps: float = 10.0


def filter_entries_by_market_ma(
    entries: pd.DataFrame,
    reference_prices: Mapping[str, pd.DataFrame],
    reference_symbol_by_market: Mapping[str, str],
    *,
    window: int = 200,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Allow new entries only when the market reference closes above its MA.

    The latest completed reference close on or before the entry signal date is
    used. Existing positions are unaffected because this function only filters
    entry candidates.
    """
    reference_state: dict[str, pd.DataFrame] = {}
    for symbol, raw in reference_prices.items():
        frame = normalize_prices(raw)
        close = pd.to_numeric(frame["Close"], errors="coerce")
        reference_state[symbol] = pd.DataFrame({
            "referenceClose": close,
            "referenceMa": close.rolling(window, min_periods=window).mean(),
        })

    audit_rows = []
    for row in entries.to_dict("records"):
        signal_date = pd.Timestamp(row["signalDate"]).normalize()
        market = str(row["market"])
        reference_symbol = reference_symbol_by_market.get(market)
        state = reference_state.get(str(reference_symbol))
        reference_date = pd.NaT
        reference_close = np.nan
        reference_ma = np.nan
        if state is not None:
            available = state.index[state.index <= signal_date]
            if len(available):
                reference_date = pd.Timestamp(available[-1])
                reference_close = state.at[reference_date, "referenceClose"]
                reference_ma = state.at[reference_date, "referenceMa"]
        has_history = bool(
            pd.notna(reference_close)
            and pd.notna(reference_ma)
            and np.isfinite(reference_close)
            and np.isfinite(reference_ma)
        )
        risk_on = bool(has_history and float(reference_close) > float(reference_ma))
        reason = (
            "market_above_ma"
            if risk_on else "insufficient_reference_history"
            if not has_history else "market_at_or_below_ma"
        )
        audit_rows.append({
            "signalDate": signal_date,
            "symbol": str(row["symbol"]),
            "market": market,
            "referenceSymbol": reference_symbol,
            "referenceDate": reference_date,
            "referenceClose": reference_close,
            "referenceMa": reference_ma,
            "maWindow": window,
            "riskOn": risk_on,
            "gateReason": reason,
        })
    audit = pd.DataFrame(audit_rows)
    if audit.empty:
        return entries.iloc[0:0].copy(), audit
    keep = audit["riskOn"].to_numpy(dtype=bool)
    return entries.loc[keep].reset_index(drop=True), audit


def run_inverse_volatility_core(
    prices_by_symbol: Mapping[str, pd.DataFrame],
    symbols: Sequence[str],
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    config: CorePortfolioConfig = CorePortfolioConfig(),
) -> dict[str, pd.DataFrame]:
    """Run a next-open, inverse-volatility core on a common session calendar."""
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    frames = {
        symbol: normalize_prices(prices_by_symbol[symbol]).loc[:end]
        for symbol in symbols
    }
    full_common = pd.DatetimeIndex(sorted(set.intersection(*(
        set(frame.index) for frame in frames.values()
    ))))
    full_common = full_common[full_common <= end]
    if full_common.empty:
        raise ValueError("no common core sessions")
    close = pd.DataFrame({s: frames[s].reindex(full_common)["Close"] for s in symbols})
    open_ = pd.DataFrame({s: frames[s].reindex(full_common)["Open"] for s in symbols})
    valid = close.notna().all(axis=1) & open_.notna().all(axis=1)
    close, open_ = close.loc[valid], open_.loc[valid]
    returns = close.pct_change()
    gaps = open_.div(close.shift(1)).sub(1.0)
    intraday = close.div(open_).sub(1.0)
    common = close.index[(close.index >= start) & (close.index <= end)]
    if common.empty:
        raise ValueError("no common core sessions in requested sample")

    asset_columns = list(symbols)
    weights = pd.Series(0.0, index=[*symbols, "CASH"])
    weights["CASH"] = 1.0
    pending: tuple[pd.Timestamp, pd.Series] | None = None
    first_full_index = int(close.index.get_loc(common[0]))
    if first_full_index >= config.volatility_window:
        history = returns.iloc[
            first_full_index - config.volatility_window:first_full_index
        ][list(symbols)]
        target_dict = inverse_volatility_weights(history, list(symbols))
        target = pd.Series(target_dict).reindex(weights.index).fillna(0.0)
        pending = (common[0], target)
    cost_rate = config.one_way_cost_bps / 10_000.0
    nav = float(config.initial_capital)
    nav_rows, weight_rows = [], []
    for index, date in enumerate(common):
        nav_before = nav
        turnover = 0.0
        if pending is not None and pending[0] == date:
            target = pending[1]
            gap_factors = pd.Series(1.0, index=weights.index)
            gap_factors.loc[asset_columns] = (
                1.0 + gaps.loc[date, asset_columns].fillna(0.0)
            )
            open_contributions = weights * gap_factors
            value_after_gap = nav * float(open_contributions.sum())
            open_weights = open_contributions / float(open_contributions.sum())
            turnover = float((target - open_weights).abs().sum() / 2.0)
            value_after_cost = value_after_gap * (1.0 - turnover * cost_rate)
            intraday_factors = pd.Series(1.0, index=weights.index)
            intraday_factors.loc[asset_columns] = (
                1.0 + intraday.loc[date, asset_columns].fillna(0.0)
            )
            close_contributions = target * intraday_factors
            close_factor = float(close_contributions.sum())
            nav = value_after_cost * close_factor
            weights = close_contributions / close_factor
            pending = None
        else:
            close_factors = pd.Series(1.0, index=weights.index)
            close_factors.loc[asset_columns] = (
                1.0 + returns.loc[date, asset_columns].fillna(0.0)
            )
            close_contributions = weights * close_factors
            close_factor = float(close_contributions.sum())
            nav *= close_factor
            weights = close_contributions / close_factor

        nav_rows.append({
            "date": date,
            "nav": nav,
            "return": nav / nav_before - 1.0,
            "cash": nav * float(weights["CASH"]),
            "marketValue": nav * float(weights[list(symbols)].sum()),
            "grossExposure": float(weights[list(symbols)].sum()),
            "positionCount": int(weights[list(symbols)].gt(0).sum()),
            "tradedNotional": value_after_gap * turnover if turnover else 0.0,
        })
        weight_rows.append({"date": date, **weights.to_dict()})

        if (
            (index + 1) % config.rebalance_sessions == 0
            and index + 1 < len(common)
        ):
            full_index = int(returns.index.get_loc(date))
            history = returns.iloc[
                full_index - config.volatility_window + 1:full_index + 1
            ][list(symbols)]
            target_dict = inverse_volatility_weights(history, list(symbols))
            target = pd.Series(target_dict).reindex(weights.index).fillna(0.0)
            pending = (common[index + 1], target)

    nav_frame = pd.DataFrame(nav_rows)
    nav_frame["peak"] = nav_frame["nav"].cummax().clip(lower=config.initial_capital)
    nav_frame["drawdown"] = nav_frame["nav"] / nav_frame["peak"] - 1.0
    return {"nav": nav_frame, "weights": pd.DataFrame(weight_rows)}


def align_nav_to_calendar(nav: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """Forward-fill NAV state to a union calendar and set inactive returns to zero."""
    source = nav.copy()
    first_nav = float(source.iloc[0]["nav"])
    first_return = float(source.iloc[0].get("return", 0.0))
    initial_nav = first_nav / (1.0 + first_return) if first_return > -1.0 else first_nav
    first_source_date = pd.Timestamp(source.iloc[0]["date"]).normalize()
    data = source.set_index(pd.to_datetime(source["date"]).dt.normalize())
    data = data.drop(columns=["date"]).reindex(calendar)
    leading = data.index < first_source_date
    data["nav"] = data["nav"].ffill()
    data.loc[leading, "nav"] = initial_nav
    data["cash"] = data["cash"].ffill()
    data.loc[leading, "cash"] = initial_nav
    for column in ("marketValue", "grossExposure", "positionCount"):
        data[column] = data[column].ffill()
        data.loc[leading, column] = 0.0
    data["tradedNotional"] = data["tradedNotional"].fillna(0.0)
    data["return"] = data["nav"].pct_change().fillna(0.0)
    if not leading.any() and calendar[0] == first_source_date:
        data.at[calendar[0], "return"] = first_return
    data["peak"] = data["nav"].cummax()
    data["drawdown"] = data["nav"] / data["peak"] - 1.0
    return data.reset_index(names="date")


def combine_core_satellite(
    core_nav: pd.DataFrame,
    satellite_nav: pd.DataFrame,
    *,
    core_weight: float,
    rebalance_dates: pd.DatetimeIndex,
    initial_capital: float = 1_000_000.0,
    sleeve_rebalance_cost_bps: float = 10.0,
) -> dict[str, pd.DataFrame]:
    """Combine two net-return sleeves with periodic budget rebalancing."""
    satellite_weight = 1.0 - float(core_weight)
    if not 0 <= core_weight <= 1:
        raise ValueError("core_weight must be between zero and one")
    core = core_nav.set_index("date")
    satellite = satellite_nav.set_index("date")
    calendar = core.index.union(satellite.index).sort_values()
    core = align_nav_to_calendar(core.reset_index(), calendar).set_index("date")
    satellite = align_nav_to_calendar(satellite.reset_index(), calendar).set_index("date")
    rebalances = set(pd.DatetimeIndex(rebalance_dates).intersection(calendar))

    core_value = initial_capital * core_weight
    satellite_value = initial_capital * satellite_weight
    nav_rows, weight_rows = [], []
    previous_total = initial_capital
    for index, date in enumerate(calendar):
        total_before = core_value + satellite_value
        current_core_weight = core_value / total_before if total_before else core_weight
        sleeve_turnover = 0.0
        if index > 0 and date in rebalances:
            sleeve_turnover = abs(current_core_weight - core_weight)
            cost = total_before * sleeve_turnover * sleeve_rebalance_cost_bps / 10_000.0
            total_before -= cost
            core_value = total_before * core_weight
            satellite_value = total_before * satellite_weight
            current_core_weight = core_weight

        core_return = float(core.at[date, "return"])
        satellite_return = float(satellite.at[date, "return"])
        core_value *= 1.0 + core_return
        satellite_value *= 1.0 + satellite_return
        total = core_value + satellite_value
        effective_core = core_value / total if total else core_weight
        effective_satellite = 1.0 - effective_core
        internal_turnover_rate = (
            current_core_weight
            * float(core.at[date, "tradedNotional"])
            / max(float(core.at[date, "nav"]), 1e-12)
            + (1.0 - current_core_weight)
            * float(satellite.at[date, "tradedNotional"])
            / max(float(satellite.at[date, "nav"]), 1e-12)
        )
        gross_exposure = (
            effective_core * float(core.at[date, "grossExposure"])
            + effective_satellite * float(satellite.at[date, "grossExposure"])
        )
        nav_rows.append({
            "date": date,
            "nav": total,
            "return": total / previous_total - 1.0,
            "cash": total * (1.0 - gross_exposure),
            "marketValue": total * gross_exposure,
            "grossExposure": gross_exposure,
            "positionCount": int(core.at[date, "positionCount"] + satellite.at[date, "positionCount"]),
            "tradedNotional": total_before * (sleeve_turnover + internal_turnover_rate),
        })
        weight_rows.append({
            "date": date,
            "coreWeight": effective_core,
            "satelliteWeight": effective_satellite,
            "sleeveTurnover": sleeve_turnover,
        })
        previous_total = total
    result = pd.DataFrame(nav_rows)
    result["peak"] = result["nav"].cummax().clip(lower=initial_capital)
    result["drawdown"] = result["nav"] / result["peak"] - 1.0
    return {"nav": result, "weights": pd.DataFrame(weight_rows)}
