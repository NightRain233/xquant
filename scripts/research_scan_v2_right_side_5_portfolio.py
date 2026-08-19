#!/usr/bin/env python3
"""Portfolio-level backtest for the scan_v2_right_side_5 decision stream."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from xquant.signal_portfolio import (  # noqa: E402
    PortfolioConfig,
    buy_hold_entry,
    decision_entries,
    performance_metrics,
    period_metrics,
    run_signal_portfolio,
    simple_supertrend_entries,
)


DECISION_VARIANTS = (
    "all_bull_flip",
    "breakout_right_side_5",
    "pullback",
    "breakout_plus_pullback",
)
ALL_VARIANTS = (*DECISION_VARIANTS, "simple_supertrend", "buy_hold_spy")


def _load_prices(
    symbols: list[str],
    data_dir: Path,
) -> dict[str, pd.DataFrame]:
    prices = {}
    for symbol in symbols:
        path = data_dir / f"{symbol}.parquet"
        prices[symbol] = pd.read_parquet(
            path, columns=["Open", "High", "Low", "Close", "ST_Dir"]
        )
    return prices


def _slice_nav(nav: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    sample = nav[(nav["date"] >= start) & (nav["date"] <= end)].copy()
    if sample.empty:
        return sample
    prior = nav[nav["date"] < start]
    base = float(prior.iloc[-1]["nav"]) if not prior.empty else float(sample.iloc[0]["nav"] / (1 + sample.iloc[0]["return"]))
    sample["nav"] = (1.0 + sample["return"]).cumprod() * base
    sample["peak"] = sample["nav"].cummax().clip(lower=base)
    sample["drawdown"] = sample["nav"] / sample["peak"] - 1.0
    return sample


def _monthly_distribution(monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for strategy, group in monthly.groupby("strategy"):
        returns = group["return"].dropna()
        wins = returns[returns > 0]
        losses = returns[returns < 0]
        rows.append({
            "strategy": strategy,
            "monthCount": len(returns),
            "monthlyWinRate": (returns > 0).mean(),
            "averageWinningMonth": wins.mean(),
            "averageLosingMonth": losses.mean(),
            "monthlyPayoffRatio": wins.mean() / abs(losses.mean()) if len(losses) else np.nan,
            "monthlyProfitFactor": wins.sum() / abs(losses.sum()) if len(losses) else np.nan,
            "bestMonth": returns.max(),
            "worstMonth": returns.min(),
        })
    return pd.DataFrame(rows)


def _drawdown_events(nav: pd.DataFrame, strategy: str) -> pd.DataFrame:
    data = nav[["date", "nav", "drawdown"]].copy().reset_index(drop=True)
    events = []
    in_drawdown = False
    start_index = 0
    for index, value in enumerate(data["drawdown"]):
        if value < 0 and not in_drawdown:
            in_drawdown = True
            start_index = max(0, index - 1)
        recovered = in_drawdown and value >= 0
        is_last = in_drawdown and index == len(data) - 1
        if recovered or is_last:
            end_index = index
            window = data.iloc[start_index : end_index + 1]
            trough_index = int(window["drawdown"].idxmin())
            events.append({
                "strategy": strategy,
                "peakDate": data.at[start_index, "date"],
                "troughDate": data.at[trough_index, "date"],
                "recoveryDate": data.at[end_index, "date"] if recovered else pd.NaT,
                "depth": data.at[trough_index, "drawdown"],
                "daysToTrough": (data.at[trough_index, "date"] - data.at[start_index, "date"]).days,
                "recoveryDays": (data.at[end_index, "date"] - data.at[trough_index, "date"]).days if recovered else np.nan,
                "totalDays": (data.at[end_index, "date"] - data.at[start_index, "date"]).days,
                "recovered": recovered,
            })
            in_drawdown = False
    return pd.DataFrame(events).sort_values("depth").reset_index(drop=True)


def _run_variant(
    variant: str,
    entries_by_variant: dict[str, pd.DataFrame],
    prices: dict[str, pd.DataFrame],
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    config: PortfolioConfig,
) -> dict[str, pd.DataFrame]:
    return run_signal_portfolio(
        entries_by_variant[variant],
        prices,
        start=start,
        end=end,
        config=config,
        exit_on_supertrend_bear=variant != "buy_hold_spy",
        benchmark_full_allocation=variant == "buy_hold_spy",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--decision-metadata", type=Path)
    parser.add_argument("--price-data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--initial-capital", type=float, default=1_000_000.0)
    parser.add_argument("--commission-bps", type=float, default=5.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--max-position-weight", type=float, default=0.10)
    parser.add_argument("--max-concurrent-positions", type=int, default=10)
    args = parser.parse_args()

    decisions = pd.read_parquet(args.decisions)
    decisions["decisionDate"] = pd.to_datetime(decisions["decisionDate"])
    start = decisions["decisionDate"].min().normalize()
    end = decisions["decisionDate"].max().normalize()
    market_by_symbol = decisions.groupby("symbol")["market"].last().to_dict()
    symbols = sorted(decisions["symbol"].unique())
    prices = _load_prices(symbols, args.price_data_dir)
    if "SPY" not in prices:
        prices["SPY"] = _load_prices(["SPY"], args.price_data_dir)["SPY"]
        market_by_symbol["SPY"] = "us"

    config = PortfolioConfig(
        initial_capital=args.initial_capital,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        max_position_weight=args.max_position_weight,
        max_concurrent_positions=args.max_concurrent_positions,
    )
    entries_by_variant = {
        variant: decision_entries(decisions, variant) for variant in DECISION_VARIANTS
    }
    entries_by_variant["simple_supertrend"] = simple_supertrend_entries(
        prices, market_by_symbol, start=start, end=end
    )
    entries_by_variant["buy_hold_spy"] = buy_hold_entry(
        "SPY", "us", signal_date=start - pd.Timedelta(days=1)
    )

    results = {
        variant: _run_variant(
            variant, entries_by_variant, prices, start=start, end=end, config=config
        )
        for variant in ALL_VARIANTS
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)

    metrics_rows = []
    nav_rows = []
    trade_rows = []
    order_rows = []
    open_rows = []
    annual_rows = []
    monthly_rows = []
    drawdown_rows = []
    for variant, result in results.items():
        metrics_rows.append({"strategy": variant, **performance_metrics(result["nav"], result["trades"])})
        nav_rows.append(result["nav"].assign(strategy=variant))
        if not result["trades"].empty:
            trade_rows.append(result["trades"].assign(strategy=variant))
        if not result["orders"].empty:
            order_rows.append(result["orders"].assign(strategy=variant))
        if not result["open_positions"].empty:
            open_rows.append(result["open_positions"].assign(strategy=variant))
        annual_rows.append(
            period_metrics(result["nav"], lambda dates: dates.dt.year).assign(strategy=variant)
        )
        monthly_rows.append(
            period_metrics(result["nav"], lambda dates: dates.dt.to_period("M").astype(str)).assign(strategy=variant)
        )
        drawdown_rows.append(_drawdown_events(result["nav"], variant))

    metrics = pd.DataFrame(metrics_rows)
    nav_all = pd.concat(nav_rows, ignore_index=True)
    trades_all = pd.concat(trade_rows, ignore_index=True) if trade_rows else pd.DataFrame()
    orders_all = pd.concat(order_rows, ignore_index=True) if order_rows else pd.DataFrame()
    open_all = pd.concat(open_rows, ignore_index=True) if open_rows else pd.DataFrame()
    annual = pd.concat(annual_rows, ignore_index=True)
    monthly = pd.concat(monthly_rows, ignore_index=True)
    drawdowns = pd.concat(drawdown_rows, ignore_index=True)

    spy_cagr = float(metrics.loc[metrics["strategy"].eq("buy_hold_spy"), "cagr"].iloc[0])
    metrics["cagrMinusSpy"] = metrics["cagr"] - spy_cagr
    benchmark_returns = results["buy_hold_spy"]["nav"].set_index("date")["return"]
    alpha_rows = []
    for variant, result in results.items():
        strategy_returns = result["nav"].set_index("date")["return"]
        aligned = pd.concat(
            [strategy_returns.rename("strategy"), benchmark_returns.rename("benchmark")],
            axis=1,
        ).dropna()
        beta = aligned.cov().loc["strategy", "benchmark"] / aligned["benchmark"].var()
        elapsed_years = max(1 / 365.25, (aligned.index.max() - aligned.index.min()).days / 365.25)
        observations_per_year = len(aligned) / elapsed_years
        alpha_rows.append({
            "strategy": variant,
            "betaVsSpy": beta,
            "annualizedAlphaVsSpy": (aligned["strategy"].mean() - beta * aligned["benchmark"].mean()) * observations_per_year,
            "returnCorrelationVsSpy": aligned["strategy"].corr(aligned["benchmark"]),
        })
    metrics = metrics.merge(pd.DataFrame(alpha_rows), on="strategy", how="left")
    metrics.to_csv(args.output_dir / "portfolio_metrics.csv", index=False)
    nav_all.to_csv(args.output_dir / "nav_daily.csv", index=False)
    nav_all[["date", "strategy", "drawdown"]].to_csv(args.output_dir / "drawdown_daily.csv", index=False)
    trades_all.to_csv(args.output_dir / "trades.csv", index=False)
    orders_all.to_csv(args.output_dir / "orders.csv", index=False)
    open_all.to_csv(args.output_dir / "open_positions_at_end.csv", index=False)
    annual.to_csv(args.output_dir / "annual_metrics.csv", index=False)
    monthly.to_csv(args.output_dir / "monthly_metrics.csv", index=False)
    _monthly_distribution(monthly).to_csv(args.output_dir / "monthly_distribution.csv", index=False)
    drawdowns.groupby("strategy", group_keys=False).head(10).to_csv(
        args.output_dir / "top_drawdowns.csv", index=False
    )
    drawdowns.groupby("strategy").agg(
        drawdownEventCount=("depth", "size"),
        maxDrawdownDepth=("depth", "min"),
        averageDrawdownDepth=("depth", "mean"),
        averageDaysToTrough=("daysToTrough", "mean"),
        averageRecoveryDays=("recoveryDays", "mean"),
    ).reset_index().to_csv(args.output_dir / "drawdown_summary.csv", index=False)

    execution_funnel = []
    for variant in ALL_VARIANTS:
        result = results[variant]
        orders = result["orders"]
        buy_orders = orders[orders["side"].eq("buy")] if not orders.empty else orders
        row = {
            "strategy": variant,
            "candidateSignals": len(entries_by_variant[variant]),
            "executedEntries": int((buy_orders["status"] == "executed").sum()) if not buy_orders.empty else 0,
            "rejectedEntries": int((buy_orders["status"] == "rejected").sum()) if not buy_orders.empty else 0,
            "closedTrades": len(result["trades"]),
            "openPositionsAtEnd": len(result["open_positions"]),
        }
        if not buy_orders.empty:
            for reason, count in buy_orders[buy_orders["status"].eq("rejected")].groupby("reason").size().items():
                row[f"rejected_{reason}"] = int(count)
        execution_funnel.append(row)
    pd.DataFrame(execution_funnel).fillna(0).to_csv(
        args.output_dir / "execution_funnel.csv", index=False
    )

    trade_market = []
    if not trades_all.empty:
        for (strategy, market), group in trades_all.groupby(["strategy", "market"]):
            pnl = group["netPnl"]
            trade_market.append({
                "strategy": strategy, "market": market, "closedTrades": len(group),
                "winRate": (pnl > 0).mean(), "netPnl": pnl.sum(),
                "averageTradeReturn": group["netReturn"].mean(),
                "medianTradeReturn": group["netReturn"].median(),
                "profitFactor": pnl[pnl > 0].sum() / abs(pnl[pnl < 0].sum()) if (pnl < 0).any() else np.nan,
                "averageHoldingDays": group["holdingCalendarDays"].mean(),
            })
    pd.DataFrame(trade_market).to_csv(args.output_dir / "trade_metrics_by_market.csv", index=False)

    market_metrics = []
    for variant in ALL_VARIANTS[:-1]:
        for market in sorted(set(market_by_symbol.values())):
            market_entries = entries_by_variant[variant].query("market == @market")
            if market_entries.empty:
                continue
            market_symbols = set(market_entries["symbol"])
            market_prices = {symbol: prices[symbol] for symbol in market_symbols}
            result = run_signal_portfolio(
                market_entries, market_prices, start=start, end=end, config=config
            )
            market_metrics.append({
                "strategy": variant, "market": market,
                **performance_metrics(result["nav"], result["trades"]),
            })
    pd.DataFrame(market_metrics).to_csv(args.output_dir / "portfolio_metrics_by_market.csv", index=False)

    folds = [
        ("wf_2024", pd.Timestamp("2023-03-01"), pd.Timestamp("2023-12-31"), pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31")),
        ("wf_2025", pd.Timestamp("2023-03-01"), pd.Timestamp("2024-12-31"), pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31")),
        ("wf_2026_ytd", pd.Timestamp("2023-03-01"), pd.Timestamp("2025-12-31"), pd.Timestamp("2026-01-01"), end),
    ]
    walk_forward = []
    for fold, train_start, train_end, test_start, test_end in folds:
        for variant, result in results.items():
            test_nav = _slice_nav(result["nav"], test_start, min(test_end, end))
            if test_nav.empty:
                continue
            fold_trades = result["trades"]
            if not fold_trades.empty:
                fold_trades = fold_trades[
                    (fold_trades["exitDate"] >= test_start) & (fold_trades["exitDate"] <= test_end)
                ]
            walk_forward.append({
                "fold": fold, "trainStart": train_start, "trainEnd": train_end,
                "testStart": test_start, "testEnd": min(test_end, end),
                "selectionRule": "locked_base_parameters_no_refit",
                "strategy": variant, **performance_metrics(test_nav, fold_trades),
            })
    pd.DataFrame(walk_forward).to_csv(args.output_dir / "walk_forward_metrics.csv", index=False)

    sensitivity_configs = [
        ("cost_0bps", 0.0, 0.0, 0.10, 10),
        ("base_20bps", args.commission_bps, args.slippage_bps, 0.10, 10),
        ("cost_50bps", 12.5, 12.5, 0.10, 10),
        ("cap_5pct_concurrent_20", args.commission_bps, args.slippage_bps, 0.05, 20),
        ("cap_20pct_concurrent_5", args.commission_bps, args.slippage_bps, 0.20, 5),
    ]
    sensitivity = []
    for scenario, commission, slippage, cap, concurrent in sensitivity_configs:
        scenario_config = PortfolioConfig(
            initial_capital=args.initial_capital, commission_bps=commission,
            slippage_bps=slippage, max_position_weight=cap,
            max_concurrent_positions=concurrent,
        )
        for variant in ALL_VARIANTS[:-1]:
            result = _run_variant(
                variant, entries_by_variant, prices, start=start, end=end, config=scenario_config
            )
            sensitivity.append({
                "scenario": scenario, "strategy": variant,
                "roundTripCostBps": 2 * (commission + slippage),
                "maxPositionWeight": cap, "maxConcurrentPositions": concurrent,
                **performance_metrics(result["nav"], result["trades"]),
            })
    pd.DataFrame(sensitivity).to_csv(args.output_dir / "sensitivity_metrics.csv", index=False)

    fig, axes = plt.subplots(2, 1, figsize=(13, 10), sharex=True)
    for variant, result in results.items():
        frame = result["nav"]
        axes[0].plot(frame["date"], frame["nav"] / config.initial_capital, label=variant)
        axes[1].plot(frame["date"], frame["drawdown"], label=variant)
    axes[0].set_ylabel("NAV (initial = 1)")
    axes[0].set_title("scan_v2_right_side_5 portfolio comparison")
    axes[0].legend(ncol=2, fontsize=8)
    axes[0].grid(alpha=0.2)
    axes[1].set_ylabel("Drawdown")
    axes[1].grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(args.output_dir / "nav_and_drawdown.png", dpi=180)
    plt.close(fig)

    decision_metadata_path = args.decision_metadata or args.decisions.with_suffix(".metadata.json")
    decision_metadata = json.loads(decision_metadata_path.read_text()) if decision_metadata_path.exists() else {}
    metadata = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "decisionSource": str(args.decisions.resolve()),
        "decisionMetadata": decision_metadata,
        "priceDataDir": str(args.price_data_dir.resolve()),
        "sampleStart": start.date().isoformat(),
        "sampleEnd": end.date().isoformat(),
        "execution": "completed close signal; next symbol session open; raw open checked against max acceptable price",
        "exit": "first completed ST_Dir < 0 close after entry; next symbol session open",
        "configuration": config.__dict__,
        "costInterpretation": "commission and adverse slippage charged independently on both entry and exit",
        "allocation": "signals ranked by point-in-time readinessScore then symbol; fixed fraction of current equity; rejected when cash, gross exposure, or concurrency is exhausted",
        "buyHoldBenchmark": "SPY next-open buy and hold, fully allocated; comparator is exempt from the signal portfolio's 10% single-position cap",
        "walkForward": "locked parameters, expanding historical context, calendar-year test folds; no fold-specific selection or refit",
        "oosCaveat": "policy was developed with awareness of the historical sample; folds are temporal pseudo-OOS stability checks, not untouched prospective evidence",
    }
    (args.output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
