#!/usr/bin/env python3
"""Long-sample robustness study for policy-eligible SuperTrend bull flips."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
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
    buy_hold_entry,
    decision_entries,
    performance_metrics,
    period_metrics,
    run_signal_portfolio,
    simple_supertrend_entries,
)


REFERENCE_SYMBOLS = {
    "a_share": "510300.SS",
    "hong_kong": "2800.HK",
    "us": "SPY",
    "crypto": "BTC-USD",
    "gold": "GC=F",
}
PRIMARY_VARIANTS = (
    "policy_bull_flip_frozen_2015",
    "policy_bull_flip_rolling_pit",
    "raw_supertrend_rolling_pit",
    "spy_buy_hold",
    "csi300_buy_hold",
)


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


def _non_crypto_calendar(
    prices: dict[str, pd.DataFrame], market_by_symbol: dict[str, str]
) -> pd.DatetimeIndex:
    dates: set[pd.Timestamp] = set()
    for symbol, frame in prices.items():
        if market_by_symbol[symbol] != "crypto":
            dates.update(pd.DatetimeIndex(frame.index).tz_localize(None).normalize())
    return pd.DatetimeIndex(sorted(dates))


def _next_session(calendar: pd.DatetimeIndex, date: pd.Timestamp) -> pd.Timestamp:
    position = int(calendar.searchsorted(pd.Timestamp(date).normalize(), side="right"))
    if position >= len(calendar):
        raise ValueError(f"no next session after {date}")
    return pd.Timestamp(calendar[position])


def _symbol_calendars(
    prices: dict[str, pd.DataFrame], market_by_symbol: dict[str, str]
) -> dict[str, pd.DatetimeIndex]:
    china = pd.DatetimeIndex(prices["510300.SS"].index).tz_localize(None).normalize()
    hk = pd.DatetimeIndex(prices["2800.HK"].index).tz_localize(None).normalize()
    us = pd.DatetimeIndex(prices["SPY"].index).tz_localize(None).normalize()
    crypto = pd.DatetimeIndex(prices["BTC-USD"].index).tz_localize(None).normalize()
    result = {}
    for symbol in prices:
        if symbol.endswith((".SS", ".SZ")):
            result[symbol] = china
        elif symbol.endswith(".HK"):
            result[symbol] = hk
        elif market_by_symbol[symbol] == "crypto":
            result[symbol] = crypto
        elif symbol == "GC=F":
            result[symbol] = pd.DatetimeIndex(
                prices[symbol].index
            ).tz_localize(None).normalize()
        else:
            result[symbol] = us
    return result


def _membership_schedule(
    prices: dict[str, pd.DataFrame],
    market_by_symbol: dict[str, str],
    *,
    initial_snapshot: pd.Timestamp,
    end: pd.Timestamp,
    rolling: bool,
    config: UniverseConfig,
) -> pd.DataFrame:
    global_calendar = _non_crypto_calendar(prices, market_by_symbol)
    references = {
        market: pd.DatetimeIndex(prices[symbol].index).tz_localize(None).normalize()
        for market, symbol in REFERENCE_SYMBOLS.items()
    }
    by_symbol = _symbol_calendars(prices, market_by_symbol)
    snapshots = [initial_snapshot]
    if rolling:
        first_month_end = initial_snapshot.to_period("M").end_time.normalize()
        snapshots.extend(pd.date_range(first_month_end, end, freq="ME"))
    frames = []
    for snapshot in sorted(set(pd.Timestamp(value).normalize() for value in snapshots)):
        effective = _next_session(global_calendar, snapshot)
        if effective > end:
            continue
        frames.append(evaluate_snapshot(
            prices,
            market_by_symbol,
            references,
            snapshot_date=snapshot,
            effective_date=effective,
            config=config,
            reference_calendar_by_symbol=by_symbol,
        ))
    return add_membership_transitions(pd.concat(frames, ignore_index=True))


def _drawdown_events(nav: pd.DataFrame, strategy: str) -> pd.DataFrame:
    data = nav[["date", "drawdown"]].reset_index(drop=True)
    events = []
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
                "strategy": strategy,
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
                "totalDays": (
                    pd.Timestamp(data.at[index, "date"])
                    - pd.Timestamp(data.at[peak_index, "date"])
                ).days,
                "recovered": recovered,
            })
            peak_index = index
            trough_index = None
        elif value >= 0:
            peak_index = index
    return pd.DataFrame(events)


def _monthly_distribution(monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for strategy, group in monthly.groupby("strategy"):
        values = pd.to_numeric(group["return"], errors="coerce").dropna()
        wins = values[values > 0]
        losses = values[values < 0]
        rows.append({
            "strategy": strategy,
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


def _slice_nav(nav: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    sample = nav[(nav["date"] >= start) & (nav["date"] <= end)].copy()
    if sample.empty:
        return sample
    prior = nav[nav["date"] < start]
    base = float(prior.iloc[-1]["nav"]) if not prior.empty else float(
        sample.iloc[0]["nav"] / (1.0 + sample.iloc[0]["return"])
    )
    sample["nav"] = (1.0 + sample["return"]).cumprod() * base
    sample["peak"] = sample["nav"].cummax().clip(lower=base)
    sample["drawdown"] = sample["nav"] / sample["peak"] - 1.0
    return sample


def _rolling_windows(
    results: dict[str, dict[str, pd.DataFrame]],
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    rows = []
    for years in (1, 3, 5):
        first_end = start + pd.DateOffset(years=years)
        for window_end in pd.date_range(first_end, end, freq="ME"):
            window_start = window_end - pd.DateOffset(years=years) + pd.Timedelta(days=1)
            for strategy, result in results.items():
                nav = _slice_nav(result["nav"], window_start, window_end)
                if len(nav) < 20:
                    continue
                rows.append({
                    "windowYears": years,
                    "windowStart": window_start,
                    "windowEnd": window_end,
                    "strategy": strategy,
                    **performance_metrics(nav),
                })
    return pd.DataFrame(rows)


def _run(
    entries: pd.DataFrame,
    prices: dict[str, pd.DataFrame],
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    config: PortfolioConfig,
    exit_on_supertrend_bear: bool = True,
    benchmark_full_allocation: bool = False,
) -> dict[str, pd.DataFrame]:
    return run_signal_portfolio(
        entries,
        prices,
        start=start,
        end=end,
        config=config,
        exit_on_supertrend_bear=exit_on_supertrend_bear,
        benchmark_full_allocation=benchmark_full_allocation,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--candidate-catalog", type=Path, required=True)
    parser.add_argument("--price-data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default="2026-07-10")
    args = parser.parse_args()

    start = pd.Timestamp(args.start).normalize()
    end = pd.Timestamp(args.end).normalize()
    initial_snapshot = start - pd.Timedelta(days=1)
    decisions = pd.read_parquet(args.decisions)
    decisions["decisionDate"] = pd.to_datetime(decisions["decisionDate"]).dt.normalize()
    catalog = json.loads(args.candidate_catalog.read_text())["symbols"]
    policy_market = decisions.groupby("symbol")["market"].last().to_dict()
    market_by_symbol = {
        symbol: _normalized_market(symbol, policy_market[symbol])
        for symbol in catalog
    }
    decisions["market"] = decisions["symbol"].map(market_by_symbol)
    prices = _load_prices(catalog, args.price_data_dir)

    universe_config = UniverseConfig(
        turnover_multipliers={"GC=F": 100.0},
        excluded_symbols=frozenset({"000001.SS", "000300.SS"}),
    )
    frozen = _membership_schedule(
        prices, market_by_symbol, initial_snapshot=initial_snapshot, end=end,
        rolling=False, config=universe_config,
    )
    rolling = _membership_schedule(
        prices, market_by_symbol, initial_snapshot=initial_snapshot, end=end,
        rolling=True, config=universe_config,
    )
    membership = pd.concat([
        frozen.assign(universe="frozen_2015"),
        rolling.assign(universe="rolling_monthly_pit"),
    ], ignore_index=True)

    config = PortfolioConfig(
        initial_capital=1_000_000.0,
        commission_bps=5.0,
        slippage_bps=5.0,
        max_position_weight=0.10,
        max_concurrent_positions=10,
        max_gross_exposure=1.0,
    )
    policy_entries = decision_entries(decisions, "all_bull_flip")
    raw_entries = simple_supertrend_entries(
        prices, market_by_symbol, start=start, end=end
    )
    entries = {
        "policy_bull_flip_frozen_2015": filter_entries_by_membership(policy_entries, frozen),
        "policy_bull_flip_rolling_pit": filter_entries_by_membership(policy_entries, rolling),
        "raw_supertrend_rolling_pit": filter_entries_by_membership(raw_entries, rolling),
        "spy_buy_hold": buy_hold_entry("SPY", "us", signal_date=initial_snapshot),
        "csi300_buy_hold": buy_hold_entry("510300.SS", "a_share", signal_date=initial_snapshot),
    }
    results = {}
    for strategy in PRIMARY_VARIANTS:
        benchmark = strategy.endswith("buy_hold")
        results[strategy] = _run(
            entries[strategy], prices, start=start, end=end, config=config,
            exit_on_supertrend_bear=not benchmark,
            benchmark_full_allocation=benchmark,
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    membership.to_csv(args.output_dir / "universe_membership_history.csv", index=False)
    metrics = pd.DataFrame([
        {"strategy": strategy, **performance_metrics(result["nav"], result["trades"])}
        for strategy, result in results.items()
    ])
    metrics.to_csv(args.output_dir / "portfolio_metrics.csv", index=False)

    nav_rows = []
    trade_rows = []
    order_rows = []
    annual_rows = []
    monthly_rows = []
    drawdown_rows = []
    market_rows = []
    funnel_rows = []
    for strategy, result in results.items():
        nav_rows.append(result["nav"].assign(strategy=strategy))
        if not result["trades"].empty:
            trade_rows.append(result["trades"].assign(strategy=strategy))
        if not result["orders"].empty:
            order_rows.append(result["orders"].assign(strategy=strategy))
        annual_rows.append(period_metrics(
            result["nav"], lambda dates: dates.dt.year
        ).assign(strategy=strategy))
        monthly_rows.append(period_metrics(
            result["nav"], lambda dates: dates.dt.to_period("M").astype(str)
        ).assign(strategy=strategy))
        drawdown_rows.append(_drawdown_events(result["nav"], strategy))
        buys = result["orders"].query("side == 'buy'") if not result["orders"].empty else result["orders"]
        funnel_rows.append({
            "strategy": strategy,
            "candidateSignals": len(entries[strategy]),
            "executedEntries": int(buys["status"].eq("executed").sum()) if not buys.empty else 0,
            "rejectedEntries": int(buys["status"].eq("rejected").sum()) if not buys.empty else 0,
            "closedTrades": len(result["trades"]),
            "openPositionsAtEnd": len(result["open_positions"]),
        })

    for strategy in ("policy_bull_flip_frozen_2015", "policy_bull_flip_rolling_pit"):
        for market in sorted(set(entries[strategy]["market"])):
            market_entries = entries[strategy].query("market == @market")
            market_result = _run(
                market_entries, prices, start=start, end=end, config=config
            )
            market_rows.append({
                "strategy": strategy,
                "market": market,
                **performance_metrics(market_result["nav"], market_result["trades"]),
            })

    nav = pd.concat(nav_rows, ignore_index=True)
    annual = pd.concat(annual_rows, ignore_index=True)
    monthly = pd.concat(monthly_rows, ignore_index=True)
    drawdowns = pd.concat(drawdown_rows, ignore_index=True)
    nav.to_csv(args.output_dir / "nav_daily.csv", index=False)
    nav[["date", "strategy", "drawdown"]].to_csv(
        args.output_dir / "underwater_daily.csv", index=False
    )
    pd.concat(trade_rows, ignore_index=True).to_csv(args.output_dir / "trades.csv", index=False)
    pd.concat(order_rows, ignore_index=True).to_csv(args.output_dir / "orders.csv", index=False)
    annual.to_csv(args.output_dir / "annual_metrics.csv", index=False)
    monthly.to_csv(args.output_dir / "monthly_metrics.csv", index=False)
    _monthly_distribution(monthly).to_csv(
        args.output_dir / "monthly_distribution.csv", index=False
    )
    drawdowns.sort_values("depth").groupby("strategy", group_keys=False).head(10).to_csv(
        args.output_dir / "top_drawdowns.csv", index=False
    )
    drawdowns.groupby("strategy").agg(
        drawdownEventCount=("depth", "size"),
        maxDrawdownDepth=("depth", "min"),
        averageDrawdownDepth=("depth", "mean"),
        averageRecoveryDays=("recoveryDays", "mean"),
        maxRecoveryDays=("recoveryDays", "max"),
    ).reset_index().to_csv(args.output_dir / "drawdown_summary.csv", index=False)
    pd.DataFrame(market_rows).to_csv(args.output_dir / "portfolio_metrics_by_market.csv", index=False)
    pd.DataFrame(funnel_rows).to_csv(args.output_dir / "execution_funnel.csv", index=False)

    rolling_windows = _rolling_windows(results, start=start, end=end)
    rolling_windows.to_csv(args.output_dir / "rolling_window_metrics.csv", index=False)
    rolling_windows.groupby(["strategy", "windowYears"]).agg(
        windowCount=("cagr", "size"),
        positiveWindowRate=("totalReturn", lambda values: float((values > 0).mean())),
        medianCagr=("cagr", "median"),
        worstCagr=("cagr", "min"),
        medianSharpe=("sharpe", "median"),
        worstMaxDrawdown=("maxDrawdown", "min"),
    ).reset_index().to_csv(args.output_dir / "rolling_window_summary.csv", index=False)

    cost_rows = []
    for scenario, commission, slippage in (
        ("0bps", 0.0, 0.0),
        ("20bps", 5.0, 5.0),
        ("50bps", 12.5, 12.5),
    ):
        stress_config = PortfolioConfig(
            initial_capital=1_000_000.0,
            commission_bps=commission,
            slippage_bps=slippage,
            max_position_weight=0.10,
            max_concurrent_positions=10,
            max_gross_exposure=1.0,
        )
        result = _run(
            entries["policy_bull_flip_rolling_pit"], prices,
            start=start, end=end, config=stress_config,
        )
        cost_rows.append({
            "scenario": scenario,
            "roundTripCostBps": 2 * (commission + slippage),
            **performance_metrics(result["nav"], result["trades"]),
        })
    pd.DataFrame(cost_rows).to_csv(args.output_dir / "cost_sensitivity.csv", index=False)

    fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    for strategy, result in results.items():
        axes[0].plot(
            result["nav"]["date"], result["nav"]["nav"] / config.initial_capital,
            label=strategy,
        )
        axes[1].plot(result["nav"]["date"], result["nav"]["drawdown"], label=strategy)
    axes[0].set_title("All bull flip long-sample robustness (2015-2026)")
    axes[0].set_ylabel("NAV (initial = 1)")
    axes[0].legend(ncol=2, fontsize=8)
    axes[0].grid(alpha=0.2)
    axes[1].set_ylabel("Drawdown")
    axes[1].grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(args.output_dir / "nav_and_drawdown.png", dpi=180)
    plt.close(fig)

    universe_meta = asdict(universe_config)
    universe_meta["excluded_symbols"] = sorted(universe_config.excluded_symbols)
    metadata = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sampleStart": start.date().isoformat(),
        "sampleEnd": end.date().isoformat(),
        "warmupStart": min(pd.Timestamp(frame.index.min()) for frame in prices.values()).date().isoformat(),
        "decisionSource": str(args.decisions.resolve()),
        "candidateCatalog": str(args.candidate_catalog.resolve()),
        "priceDataDir": str(args.price_data_dir.resolve()),
        "candidateCount": len(catalog),
        "universeConfiguration": universe_meta,
        "portfolioConfiguration": asdict(config),
        "primaryStrategy": "policy_bull_flip_rolling_pit",
        "execution": "completed bull-flip close; next symbol session open",
        "exit": "first completed ST_Dir < 0 close after entry; next finite positive symbol Open",
        "cost": "5 bps commission plus 5 bps adverse slippage per side; 20 bps round trip",
        "rollingUniverse": "month-end point-in-time eligibility and within-market liquidity rank; next non-crypto business session effective",
        "frozenUniverse": "2014-12-31 point-in-time snapshot, effective first 2015 non-crypto business session",
        "dataCaveat": "long-sample proxy over 81 locally observable instruments, not a complete historical exchange security master; delisted/liquidated/never-cached instruments remain absent",
        "parameterPolicy": "production SuperTrend 7/3 and policy are locked; no full-sample refit",
        "tradableSessionDefinition": "finite positive OHLC, Volume > 0, and official tradable status when available",
    }
    (args.output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
