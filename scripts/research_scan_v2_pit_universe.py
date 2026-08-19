#!/usr/bin/env python3
"""Compare current-backfill, frozen, and rolling point-in-time universes."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from xquant.point_in_time_universe import (  # noqa: E402
    UniverseConfig,
    add_membership_transitions,
    evaluate_snapshot,
    filter_entries_by_membership,
)
from xquant.signal_portfolio import (  # noqa: E402
    PortfolioConfig,
    decision_entries,
    performance_metrics,
    period_metrics,
    run_signal_portfolio,
)


SIGNALS = {
    "policy_eligible_bull_flip": "all_bull_flip",
    "scan_v2_right_side_5": "breakout_right_side_5",
}
UNIVERSES = ("current_47_backfill", "frozen_2023_03_01", "rolling_monthly_pit")
REFERENCE_SYMBOLS = {
    "a_share": "000300.SS",
    "hong_kong": "513180.SS",
    "us": "SPY",
    "crypto": "BTC-USD",
    "gold": "GC=F",
}


def _normalized_market(symbol: str, policy_market: str) -> str:
    if symbol in {"GC=F", "GLD", "518880.SS"}:
        return "gold"
    if symbol.endswith(".HK"):
        return "hong_kong"
    return policy_market


def _load_prices(symbols: list[str], data_dir: Path) -> dict[str, pd.DataFrame]:
    columns = ["Open", "High", "Low", "Close", "Volume", "ST_Dir"]
    return {
        symbol: pd.read_parquet(data_dir / f"{symbol}.parquet", columns=columns)
        for symbol in symbols
    }


def _business_calendar(
    prices: dict[str, pd.DataFrame], market_by_symbol: dict[str, str]
) -> pd.DatetimeIndex:
    dates: set[pd.Timestamp] = set()
    for symbol, frame in prices.items():
        if market_by_symbol[symbol] != "crypto":
            dates.update(pd.DatetimeIndex(frame.index).tz_localize(None).normalize())
    return pd.DatetimeIndex(sorted(dates))


def _next_session(calendar: pd.DatetimeIndex, date: pd.Timestamp) -> pd.Timestamp:
    index = int(calendar.searchsorted(pd.Timestamp(date).normalize(), side="right"))
    if index >= len(calendar):
        raise ValueError(f"no session after {date}")
    return pd.Timestamp(calendar[index])


def _membership_schedule(
    prices: dict[str, pd.DataFrame],
    market_by_symbol: dict[str, str],
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    rolling: bool,
    config: UniverseConfig,
) -> pd.DataFrame:
    business_calendar = _business_calendar(prices, market_by_symbol)
    references = {
        market: pd.DatetimeIndex(prices[symbol].index).tz_localize(None).normalize()
        for market, symbol in REFERENCE_SYMBOLS.items()
        if symbol in prices
    }
    china_calendar = pd.DatetimeIndex(prices["000300.SS"].index).tz_localize(None).normalize()
    hong_kong_calendar = pd.DatetimeIndex(prices["2800.HK"].index).tz_localize(None).normalize()
    us_calendar = pd.DatetimeIndex(prices["SPY"].index).tz_localize(None).normalize()
    crypto_calendar = pd.DatetimeIndex(prices["BTC-USD"].index).tz_localize(None).normalize()
    symbol_calendars = {}
    for symbol in prices:
        if symbol.endswith((".SS", ".SZ")):
            symbol_calendars[symbol] = china_calendar
        elif symbol.endswith(".HK"):
            symbol_calendars[symbol] = hong_kong_calendar
        elif market_by_symbol[symbol] == "crypto":
            symbol_calendars[symbol] = crypto_calendar
        elif symbol == "GC=F":
            symbol_calendars[symbol] = pd.DatetimeIndex(
                prices[symbol].index
            ).tz_localize(None).normalize()
        else:
            symbol_calendars[symbol] = us_calendar
    snapshots = [start]
    if rolling:
        month_ends = pd.date_range(start.to_period("M").end_time.normalize(), end, freq="ME")
        snapshots.extend(pd.Timestamp(value).normalize() for value in month_ends)

    frames = []
    for snapshot in snapshots:
        effective = _next_session(business_calendar, snapshot)
        if effective > end:
            continue
        frames.append(evaluate_snapshot(
            prices,
            market_by_symbol,
            references,
            snapshot_date=snapshot,
            effective_date=effective,
            config=config,
            reference_calendar_by_symbol=symbol_calendars,
        ))
    return add_membership_transitions(pd.concat(frames, ignore_index=True))


def _max_recovery_days(nav: pd.DataFrame) -> float:
    drawdown = pd.to_numeric(nav["drawdown"], errors="coerce")
    dates = pd.to_datetime(nav["date"])
    in_drawdown = False
    trough_date: pd.Timestamp | None = None
    trough_value = 0.0
    recoveries: list[int] = []
    for date, value in zip(dates, drawdown, strict=True):
        if value < 0:
            if not in_drawdown:
                in_drawdown = True
                trough_date = date
                trough_value = value
            elif value < trough_value:
                trough_date = date
                trough_value = value
        elif in_drawdown:
            recoveries.append(int((date - trough_date).days))
            in_drawdown = False
            trough_date = None
            trough_value = 0.0
    return float(max(recoveries)) if recoveries else np.nan


def _drawdown_events(
    nav: pd.DataFrame, signal: str, universe: str
) -> pd.DataFrame:
    data = nav[["date", "drawdown"]].reset_index(drop=True)
    events: list[dict[str, object]] = []
    peak_index = 0
    trough_index: int | None = None
    for index, value in enumerate(data["drawdown"]):
        if value < 0 and trough_index is None:
            trough_index = index
        elif value < 0 and value < data.at[trough_index, "drawdown"]:
            trough_index = index
        recovered = trough_index is not None and value >= 0
        final = trough_index is not None and index == len(data) - 1
        if recovered or final:
            events.append({
                "signal": signal,
                "universe": universe,
                "peakDate": data.at[peak_index, "date"],
                "troughDate": data.at[trough_index, "date"],
                "recoveryDate": data.at[index, "date"] if recovered else pd.NaT,
                "depth": data.at[trough_index, "drawdown"],
                "daysToTrough": (
                    pd.Timestamp(data.at[trough_index, "date"])
                    - pd.Timestamp(data.at[peak_index, "date"])
                ).days,
                "recoveryDays": (
                    pd.Timestamp(data.at[index, "date"])
                    - pd.Timestamp(data.at[trough_index, "date"])
                ).days if recovered else np.nan,
                "recovered": recovered,
            })
            peak_index = index
            trough_index = None
        elif value >= 0:
            peak_index = index
    return pd.DataFrame(events)


def _monthly_distribution(monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (signal, universe), group in monthly.groupby(["signal", "universe"]):
        values = pd.to_numeric(group["return"], errors="coerce").dropna()
        wins = values[values > 0]
        losses = values[values < 0]
        rows.append({
            "signal": signal,
            "universe": universe,
            "monthCount": len(values),
            "monthlyWinRate": float((values > 0).mean()),
            "averageWinningMonth": float(wins.mean()),
            "averageLosingMonth": float(losses.mean()),
            "monthlyPayoffRatio": wins.mean() / abs(losses.mean()) if len(losses) else np.nan,
            "monthlyProfitFactor": wins.sum() / abs(losses.sum()) if len(losses) else np.nan,
            "bestMonth": float(values.max()),
            "worstMonth": float(values.min()),
        })
    return pd.DataFrame(rows)


def _run(
    entries: pd.DataFrame,
    prices: dict[str, pd.DataFrame],
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    config: PortfolioConfig,
) -> dict[str, pd.DataFrame]:
    return run_signal_portfolio(
        entries,
        prices,
        start=start,
        end=end,
        config=config,
    )


def _metrics_row(
    result: dict[str, pd.DataFrame], signal: str, universe: str
) -> dict[str, object]:
    return {
        "signal": signal,
        "universe": universe,
        **performance_metrics(result["nav"], result["trades"]),
        "maxRecoveryDays": _max_recovery_days(result["nav"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-decisions", type=Path, required=True)
    parser.add_argument("--broad-decisions", type=Path, required=True)
    parser.add_argument("--price-data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    current = pd.read_parquet(args.current_decisions)
    broad = pd.read_parquet(args.broad_decisions)
    for frame in (current, broad):
        frame["decisionDate"] = pd.to_datetime(frame["decisionDate"]).dt.normalize()
    start = pd.Timestamp(current["decisionDate"].min()).normalize()
    end = pd.Timestamp(current["decisionDate"].max()).normalize()
    broad = broad[(broad["decisionDate"] >= start) & (broad["decisionDate"] <= end)]
    policy_market_by_symbol = broad.groupby("symbol")["market"].last().to_dict()
    market_by_symbol = {
        symbol: _normalized_market(symbol, market)
        for symbol, market in policy_market_by_symbol.items()
    }
    broad["market"] = broad["symbol"].map(market_by_symbol)
    prices = _load_prices(sorted(market_by_symbol), args.price_data_dir)

    universe_config = UniverseConfig(
        turnover_multipliers={"GC=F": 100.0},
        excluded_symbols=frozenset({"000001.SS", "000300.SS"}),
    )
    frozen = _membership_schedule(
        prices, market_by_symbol, start=start, end=end, rolling=False,
        config=universe_config,
    )
    rolling = _membership_schedule(
        prices, market_by_symbol, start=start, end=end, rolling=True,
        config=universe_config,
    )
    memberships = pd.concat([
        frozen.assign(universe="frozen_2023_03_01"),
        rolling.assign(universe="rolling_monthly_pit"),
    ], ignore_index=True)

    portfolio_config = PortfolioConfig(
        initial_capital=1_000_000.0,
        commission_bps=5.0,
        slippage_bps=5.0,
        max_position_weight=0.10,
        max_concurrent_positions=10,
        max_gross_exposure=1.0,
    )
    results: dict[tuple[str, str], dict[str, pd.DataFrame]] = {}
    entries_used: dict[tuple[str, str], pd.DataFrame] = {}
    for signal, variant in SIGNALS.items():
        current_entries = decision_entries(current, variant)
        broad_entries = decision_entries(broad, variant)
        entries_by_universe = {
            "current_47_backfill": current_entries,
            "frozen_2023_03_01": filter_entries_by_membership(broad_entries, frozen),
            "rolling_monthly_pit": filter_entries_by_membership(broad_entries, rolling),
        }
        for universe, entries in entries_by_universe.items():
            entries_used[(signal, universe)] = entries
            results[(signal, universe)] = _run(
                entries, prices, start=start, end=end, config=portfolio_config
            )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    memberships.to_csv(args.output_dir / "universe_membership_history.csv", index=False)
    metrics = pd.DataFrame([
        _metrics_row(result, signal, universe)
        for (signal, universe), result in results.items()
    ])
    metrics.to_csv(args.output_dir / "portfolio_metrics.csv", index=False)

    nav_rows = []
    trade_rows = []
    order_rows = []
    annual_rows = []
    monthly_rows = []
    market_rows = []
    funnel_rows = []
    drawdown_rows = []
    for (signal, universe), result in results.items():
        nav_rows.append(result["nav"].assign(signal=signal, universe=universe))
        if not result["trades"].empty:
            trade_rows.append(result["trades"].assign(signal=signal, universe=universe))
        if not result["orders"].empty:
            order_rows.append(result["orders"].assign(signal=signal, universe=universe))
        annual_rows.append(period_metrics(
            result["nav"], lambda dates: dates.dt.year
        ).assign(signal=signal, universe=universe))
        monthly_rows.append(period_metrics(
            result["nav"], lambda dates: dates.dt.to_period("M").astype(str)
        ).assign(signal=signal, universe=universe))
        drawdown_rows.append(_drawdown_events(result["nav"], signal, universe))
        buys = result["orders"].query("side == 'buy'") if not result["orders"].empty else result["orders"]
        funnel_rows.append({
            "signal": signal,
            "universe": universe,
            "candidateSignals": len(entries_used[(signal, universe)]),
            "executedEntries": int(buys["status"].eq("executed").sum()) if not buys.empty else 0,
            "rejectedEntries": int(buys["status"].eq("rejected").sum()) if not buys.empty else 0,
            "closedTrades": len(result["trades"]),
            "openPositionsAtEnd": len(result["open_positions"]),
        })
        for market in sorted(set(entries_used[(signal, universe)]["market"])):
            market_entries = entries_used[(signal, universe)].query("market == @market")
            market_result = _run(
                market_entries, prices, start=start, end=end, config=portfolio_config
            )
            market_rows.append({
                "signal": signal,
                "universe": universe,
                "market": market,
                **performance_metrics(market_result["nav"], market_result["trades"]),
                "maxRecoveryDays": _max_recovery_days(market_result["nav"]),
            })

    pd.concat(nav_rows, ignore_index=True).to_csv(args.output_dir / "nav_daily.csv", index=False)
    pd.concat(trade_rows, ignore_index=True).to_csv(args.output_dir / "trades.csv", index=False)
    pd.concat(order_rows, ignore_index=True).to_csv(args.output_dir / "orders.csv", index=False)
    pd.concat(annual_rows, ignore_index=True).to_csv(args.output_dir / "annual_metrics.csv", index=False)
    monthly = pd.concat(monthly_rows, ignore_index=True)
    monthly.to_csv(args.output_dir / "monthly_metrics.csv", index=False)
    _monthly_distribution(monthly).to_csv(
        args.output_dir / "monthly_distribution.csv", index=False
    )
    drawdowns = pd.concat(drawdown_rows, ignore_index=True)
    drawdowns.sort_values("depth").groupby(
        ["signal", "universe"], group_keys=False
    ).head(10).to_csv(args.output_dir / "top_drawdowns.csv", index=False)
    drawdowns.groupby(["signal", "universe"]).agg(
        drawdownEventCount=("depth", "size"),
        maxDrawdownDepth=("depth", "min"),
        averageDrawdownDepth=("depth", "mean"),
        averageDaysToTrough=("daysToTrough", "mean"),
        averageRecoveryDays=("recoveryDays", "mean"),
    ).reset_index().to_csv(args.output_dir / "drawdown_summary.csv", index=False)
    pd.DataFrame(market_rows).to_csv(args.output_dir / "portfolio_metrics_by_market.csv", index=False)
    pd.DataFrame(funnel_rows).to_csv(args.output_dir / "execution_funnel.csv", index=False)

    attribution_rows = []
    for signal in SIGNALS:
        by_universe = metrics[metrics["signal"].eq(signal)].set_index("universe")
        current_cagr = float(by_universe.at["current_47_backfill", "cagr"])
        rolling_cagr = float(by_universe.at["rolling_monthly_pit", "cagr"])
        frozen_cagr = float(by_universe.at["frozen_2023_03_01", "cagr"])
        attribution_rows.append({
            "signal": signal,
            "currentBackfillCagr": current_cagr,
            "frozenPitCagr": frozen_cagr,
            "rollingPitCagr": rolling_cagr,
            "descriptiveSignalComponent": rolling_cagr,
            "currentPoolBackfillUplift": current_cagr - rolling_cagr,
            "backfillUpliftShareOfCurrentCagr": (
                (current_cagr - rolling_cagr) / current_cagr if current_cagr else np.nan
            ),
            "frozenToRollingCagrDifference": frozen_cagr - rolling_cagr,
            "causalInterpretation": "descriptive_not_causal",
        })
    pd.DataFrame(attribution_rows).to_csv(args.output_dir / "cagr_attribution.csv", index=False)

    stress_configs = {
        "base": universe_config,
        "history_504": replace(universe_config, min_history_sessions=504),
        "liquidity_floor_2x": replace(
            universe_config,
            liquidity_floors={key: value * 2 for key, value in universe_config.liquidity_floors.items()},
        ),
        "completeness_98pct": replace(
            universe_config, max_suspension_rate=0.02, min_data_completeness=0.98
        ),
    }
    stress_rows = []
    broad_entries_by_signal = {
        signal: decision_entries(broad, variant) for signal, variant in SIGNALS.items()
    }
    for scenario, stress_config in stress_configs.items():
        stress_membership = _membership_schedule(
            prices, market_by_symbol, start=start, end=end, rolling=True,
            config=stress_config,
        )
        for signal, broad_entries in broad_entries_by_signal.items():
            stress_entries = filter_entries_by_membership(broad_entries, stress_membership)
            stress_result = _run(
                stress_entries, prices, start=start, end=end, config=portfolio_config
            )
            stress_rows.append({
                "scenario": scenario,
                "signal": signal,
                "averageSelectedSymbols": float(
                    stress_membership.groupby("effectiveDate")["selected"].sum().mean()
                ),
                **performance_metrics(stress_result["nav"], stress_result["trades"]),
            })
    pd.DataFrame(stress_rows).to_csv(args.output_dir / "universe_sensitivity.csv", index=False)

    fig, axes = plt.subplots(2, 1, figsize=(13, 10), sharex=True)
    for (signal, universe), result in results.items():
        label = f"{signal} | {universe}"
        axes[0].plot(result["nav"]["date"], result["nav"]["nav"] / 1_000_000, label=label)
        axes[1].plot(result["nav"]["date"], result["nav"]["drawdown"], label=label)
    axes[0].set_title("scan_v2 universe robustness: same execution and portfolio rules")
    axes[0].set_ylabel("NAV (initial = 1)")
    axes[0].legend(ncol=2, fontsize=7)
    axes[0].grid(alpha=0.2)
    axes[1].set_ylabel("Drawdown")
    axes[1].grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(args.output_dir / "nav_and_drawdown.png", dpi=180)
    plt.close(fig)

    universe_metadata = asdict(universe_config)
    universe_metadata["excluded_symbols"] = sorted(universe_config.excluded_symbols)
    metadata = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "currentDecisionSource": str(args.current_decisions.resolve()),
        "broadDecisionSource": str(args.broad_decisions.resolve()),
        "priceDataDir": str(args.price_data_dir.resolve()),
        "sampleStart": start.date().isoformat(),
        "sampleEnd": end.date().isoformat(),
        "signals": SIGNALS,
        "universeVersions": list(UNIVERSES),
        "universeConfiguration": universe_metadata,
        "portfolioConfiguration": asdict(portfolio_config),
        "rankingRule": "qualified candidates ranked only by trailing median Close*Volume within market, then symbol",
        "rollingRule": "snapshot at each calendar month end using data through snapshot; effective next non-crypto business session",
        "initialFrozenRule": "snapshot at 2023-03-01 close; effective next non-crypto business session and never updated",
        "removalRule": "membership removal blocks new entries only; existing positions retain real next-session SuperTrend bear exit",
        "costRule": "5 bps commission plus 5 bps adverse slippage each side = 20 bps round trip",
        "selectionProhibitions": "no future return, future eligibility, full-sample performance, or signal result used in selection",
        "sensitivityPolicy": "predefined stricter stresses reported; no scenario used to refit or choose the base rules",
        "limitations": [
            "candidate catalog is the locally cached instrument history, not a complete historical exchange security master",
            "listing history means locally observable valid sessions; true listing and delisting master dates are unavailable",
            "traded value uses native-currency Close*Volume and is only compared within each market",
            "current-47 version intentionally preserves backfilled and potentially non-tradable index symbols as the optimistic upper bound",
        ],
    }
    (args.output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
