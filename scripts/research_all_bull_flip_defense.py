#!/usr/bin/env python3
"""Test defensive entry gating and fixed-budget core/bull-flip sleeves."""

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

from xquant.defensive_overlay import (  # noqa: E402
    CorePortfolioConfig,
    align_nav_to_calendar,
    combine_core_satellite,
    filter_entries_by_market_ma,
    run_inverse_volatility_core,
)
from xquant.point_in_time_universe import filter_entries_by_membership  # noqa: E402
from xquant.signal_portfolio import (  # noqa: E402
    PortfolioConfig,
    decision_entries,
    performance_metrics,
    period_metrics,
    run_signal_portfolio,
)


REFERENCE_SYMBOL_BY_MARKET = {
    "a_share": "510300.SS",
    "hong_kong": "2800.HK",
    "us": "SPY",
    "crypto": "BTC-USD",
    "gold": "GC=F",
}
CORE_SYMBOLS = ("510300.SS", "513100.SS", "518880.SS")
PRIMARY_STRATEGIES = (
    "bull_flip_baseline",
    "bull_flip_def200_entry_gate",
    "risk_parity_core",
    "core90_bull10",
    "core90_def200_bull10",
    "core80_bull20",
    "core70_bull30",
)


def _drawdown_events(nav: pd.DataFrame, strategy: str) -> pd.DataFrame:
    data = nav[["date", "drawdown"]].reset_index(drop=True)
    events, peak_index, trough_index = [], 0, None
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
            peak_index, trough_index = index, None
        elif value >= 0:
            peak_index = index
    return pd.DataFrame(events)


def _monthly_distribution(monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for strategy, group in monthly.groupby("strategy"):
        values = pd.to_numeric(group["return"], errors="coerce").dropna()
        wins, losses = values[values > 0], values[values < 0]
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


def _window_metrics(nav: pd.DataFrame, years: int) -> list[dict[str, object]]:
    rows = []
    start, end = pd.Timestamp(nav["date"].min()), pd.Timestamp(nav["date"].max())
    for window_end in pd.date_range(start + pd.DateOffset(years=years), end, freq="ME"):
        window_start = window_end - pd.DateOffset(years=years) + pd.Timedelta(days=1)
        before = nav[nav["date"] < window_start]
        sample = nav[(nav["date"] >= window_start) & (nav["date"] <= window_end)].copy()
        if len(sample) < 20:
            continue
        base = float(before.iloc[-1]["nav"]) if not before.empty else float(
            sample.iloc[0]["nav"] / (1.0 + sample.iloc[0]["return"])
        )
        sample["nav"] = (1.0 + sample["return"]).cumprod() * base
        sample["peak"] = sample["nav"].cummax().clip(lower=base)
        sample["drawdown"] = sample["nav"] / sample["peak"] - 1.0
        rows.append({
            "windowYears": years,
            "windowStart": window_start,
            "windowEnd": window_end,
            **performance_metrics(sample),
        })
    return rows


def _slice_nav(nav: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Reset a NAV slice to its own starting capital and drawdown path."""
    data = nav.copy()
    data["date"] = pd.to_datetime(data["date"])
    before = data[data["date"] < start]
    sample = data[(data["date"] >= start) & (data["date"] <= end)].copy()
    if sample.empty:
        raise ValueError("NAV slice is empty")
    initial_nav = (
        float(before.iloc[-1]["nav"])
        if not before.empty else float(sample.iloc[0]["nav"] / (1.0 + sample.iloc[0]["return"]))
    )
    sample["return"] = sample["nav"].pct_change()
    sample.iloc[0, sample.columns.get_loc("return")] = (
        float(sample.iloc[0]["nav"]) / initial_nav - 1.0
    )
    sample["peak"] = sample["nav"].cummax().clip(lower=initial_nav)
    sample["drawdown"] = sample["nav"] / sample["peak"] - 1.0
    return sample


def _portfolio_config(round_trip_bps: float = 20.0) -> PortfolioConfig:
    per_component = round_trip_bps / 4.0
    return PortfolioConfig(
        initial_capital=1_000_000.0,
        commission_bps=per_component,
        slippage_bps=per_component,
        max_position_weight=0.10,
        max_concurrent_positions=10,
        max_gross_exposure=1.0,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--candidate-catalog", type=Path, required=True)
    parser.add_argument("--price-data-dir", type=Path, required=True)
    parser.add_argument("--membership", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default="2026-07-10")
    args = parser.parse_args()

    start, end = pd.Timestamp(args.start), pd.Timestamp(args.end)
    symbols = json.loads(args.candidate_catalog.read_text())["symbols"]
    prices = {
        symbol: pd.read_parquet(
            args.price_data_dir / f"{symbol}.parquet",
            columns=["Open", "High", "Low", "Close", "Volume", "ST_Dir"],
        )
        for symbol in symbols
    }
    membership = pd.read_csv(args.membership)
    membership = membership[membership["universe"].eq("rolling_monthly_pit")]
    market_by_symbol = membership.groupby("symbol")["market"].last().to_dict()
    decisions = pd.read_parquet(args.decisions)
    decisions["market"] = decisions["symbol"].map(market_by_symbol)
    base_entries = filter_entries_by_membership(
        decision_entries(decisions, "all_bull_flip"), membership
    )

    reference_prices = {
        symbol: prices[symbol] for symbol in set(REFERENCE_SYMBOL_BY_MARKET.values())
    }
    def200_entries, gate_audit = filter_entries_by_market_ma(
        base_entries,
        reference_prices,
        REFERENCE_SYMBOL_BY_MARKET,
        window=200,
    )
    config = _portfolio_config()
    baseline = run_signal_portfolio(
        base_entries, prices, start=start, end=end, config=config
    )
    def200 = run_signal_portfolio(
        def200_entries, prices, start=start, end=end, config=config
    )

    core_config = CorePortfolioConfig(
        initial_capital=1_000_000.0,
        volatility_window=20,
        rebalance_sessions=10,
        one_way_cost_bps=10.0,
    )
    core = run_inverse_volatility_core(
        prices, CORE_SYMBOLS, start=start, end=end, config=core_config
    )
    union_calendar = pd.DatetimeIndex(baseline["nav"]["date"])
    core_nav = align_nav_to_calendar(core["nav"], union_calendar)
    core_result = {"nav": core_nav, "trades": pd.DataFrame()}
    rebalance_dates = pd.DatetimeIndex(core["nav"]["date"].iloc[::10])

    combinations = {}
    for core_weight in (0.9, 0.8, 0.7):
        name = f"core{round(core_weight * 100)}_bull{round((1 - core_weight) * 100)}"
        combinations[name] = combine_core_satellite(
            core_nav,
            baseline["nav"],
            core_weight=core_weight,
            rebalance_dates=rebalance_dates,
            initial_capital=1_000_000.0,
            sleeve_rebalance_cost_bps=10.0,
        )
    combinations["core90_def200_bull10"] = combine_core_satellite(
        core_nav,
        def200["nav"],
        core_weight=0.9,
        rebalance_dates=rebalance_dates,
        initial_capital=1_000_000.0,
        sleeve_rebalance_cost_bps=10.0,
    )

    results = {
        "bull_flip_baseline": baseline,
        "bull_flip_def200_entry_gate": def200,
        "risk_parity_core": core_result,
        **{name: {"nav": value["nav"], "trades": pd.DataFrame()} for name, value in combinations.items()},
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    gate_audit.to_csv(args.output_dir / "def200_entry_gate_audit.csv", index=False)
    core["weights"].to_csv(args.output_dir / "risk_parity_core_weights.csv", index=False)
    pd.concat([
        value["weights"].assign(strategy=name)
        for name, value in combinations.items()
    ], ignore_index=True).to_csv(args.output_dir / "core_satellite_weights.csv", index=False)

    metrics, nav_rows, annual_rows, monthly_rows, drawdown_rows = [], [], [], [], []
    rolling_rows = []
    for strategy in PRIMARY_STRATEGIES:
        result = results[strategy]
        nav = result["nav"].copy()
        trades = result.get("trades", pd.DataFrame())
        events = _drawdown_events(nav, strategy)
        metric = {
            "strategy": strategy,
            **performance_metrics(nav, trades),
            "maxRecoveryDays": float(events["recoveryDays"].max()) if not events.empty else 0.0,
            "maxUnderwaterDays": float(events["totalDays"].max()) if not events.empty else 0.0,
        }
        metrics.append(metric)
        nav_rows.append(nav.assign(strategy=strategy))
        annual_rows.append(period_metrics(nav, lambda dates: dates.dt.year).assign(strategy=strategy))
        monthly_rows.append(period_metrics(
            nav, lambda dates: dates.dt.to_period("M").astype(str)
        ).assign(strategy=strategy))
        drawdown_rows.append(events)
        for years in (1, 3, 5):
            rolling_rows.extend([
                {"strategy": strategy, **row} for row in _window_metrics(nav, years)
            ])

    metrics_frame = pd.DataFrame(metrics)
    nav_frame = pd.concat(nav_rows, ignore_index=True)
    annual = pd.concat(annual_rows, ignore_index=True)
    monthly = pd.concat(monthly_rows, ignore_index=True)
    drawdowns = pd.concat(drawdown_rows, ignore_index=True)
    rolling = pd.DataFrame(rolling_rows)
    metrics_frame.to_csv(args.output_dir / "portfolio_metrics.csv", index=False)
    metrics_frame[metrics_frame["strategy"].isin([
        "core90_bull10", "core90_def200_bull10",
    ])].to_csv(
        args.output_dir / "core90_satellite_filter_comparison.csv", index=False
    )
    nav_frame.to_csv(args.output_dir / "nav_daily.csv", index=False)
    annual.to_csv(args.output_dir / "annual_metrics.csv", index=False)
    monthly.to_csv(args.output_dir / "monthly_metrics.csv", index=False)
    _monthly_distribution(monthly).to_csv(
        args.output_dir / "monthly_distribution.csv", index=False
    )
    drawdowns.to_csv(args.output_dir / "drawdown_events.csv", index=False)
    drawdowns.groupby("strategy").agg(
        drawdownEventCount=("depth", "size"),
        maxDrawdownDepth=("depth", "min"),
        averageDrawdownDepth=("depth", "mean"),
        averageRecoveryDays=("recoveryDays", "mean"),
        maxRecoveryDays=("recoveryDays", "max"),
        maxUnderwaterDays=("totalDays", "max"),
    ).reset_index().to_csv(args.output_dir / "drawdown_summary.csv", index=False)
    rolling.to_csv(args.output_dir / "rolling_window_metrics.csv", index=False)
    rolling.groupby(["strategy", "windowYears"]).agg(
        windowCount=("cagr", "size"),
        positiveWindowRate=("totalReturn", lambda values: float((values > 0).mean())),
        medianCagr=("cagr", "median"),
        worstCagr=("cagr", "min"),
        medianSharpe=("sharpe", "median"),
        worstMaxDrawdown=("maxDrawdown", "min"),
    ).reset_index().to_csv(args.output_dir / "rolling_window_summary.csv", index=False)

    recent_end = end
    recent_start = recent_end - pd.DateOffset(years=3) + pd.Timedelta(days=1)
    recent_rows = []
    for strategy in PRIMARY_STRATEGIES:
        result = results[strategy]
        nav = _slice_nav(result["nav"], recent_start, recent_end)
        trades = result.get("trades", pd.DataFrame()).copy()
        if not trades.empty and "exitDate" in trades:
            exit_dates = pd.to_datetime(trades["exitDate"])
            trades = trades[(exit_dates >= recent_start) & (exit_dates <= recent_end)]
        recent_rows.append({
            "strategy": strategy,
            "windowStart": recent_start,
            "windowEnd": recent_end,
            **performance_metrics(nav, trades),
        })
    pd.DataFrame(recent_rows).to_csv(
        args.output_dir / "recent_3y_metrics.csv", index=False
    )

    benchmark_rows = []
    core_returns = results["risk_parity_core"]["nav"].set_index("date")["return"]
    for strategy in PRIMARY_STRATEGIES:
        if strategy == "risk_parity_core":
            continue
        candidate = results[strategy]["nav"].set_index("date")["return"]
        pair = pd.concat([
            candidate.rename("candidate"), core_returns.rename("benchmark")
        ], axis=1).dropna()
        years = max(1 / 365.25, (pair.index[-1] - pair.index[0]).days / 365.25)
        observations_per_year = len(pair) / years
        beta = pair["candidate"].cov(pair["benchmark"]) / pair["benchmark"].var()
        excess = pair["candidate"] - pair["benchmark"]
        benchmark_rows.append({
            "strategy": strategy,
            "benchmark": "risk_parity_core",
            "returnCorrelation": pair["candidate"].corr(pair["benchmark"]),
            "beta": beta,
            "annualizedArithmeticAlpha": (
                pair["candidate"].mean() - beta * pair["benchmark"].mean()
            ) * observations_per_year,
            "annualizedExcessReturn": excess.mean() * observations_per_year,
            "informationRatio": (
                excess.mean() / excess.std(ddof=1) * np.sqrt(observations_per_year)
                if excess.std(ddof=1) > 0 else np.nan
            ),
        })
    pd.DataFrame(benchmark_rows).to_csv(
        args.output_dir / "benchmark_comparison.csv", index=False
    )

    gate_summary = gate_audit.groupby(["market", "gateReason"]).size().rename(
        "candidateSignals"
    ).reset_index()
    gate_summary.to_csv(args.output_dir / "def200_entry_gate_summary.csv", index=False)

    ma_sensitivity_rows = []
    for window in (150, 200, 250):
        filtered, audit = filter_entries_by_market_ma(
            base_entries, reference_prices, REFERENCE_SYMBOL_BY_MARKET, window=window
        )
        for cost_bps in (20.0, 50.0):
            result = run_signal_portfolio(
                filtered, prices, start=start, end=end,
                config=_portfolio_config(cost_bps),
            )
            ma_sensitivity_rows.append({
                "maWindow": window,
                "roundTripCostBps": cost_bps,
                "allowedSignals": int(audit["riskOn"].sum()),
                "blockedSignals": int((~audit["riskOn"]).sum()),
                **performance_metrics(result["nav"], result["trades"]),
            })
    pd.DataFrame(ma_sensitivity_rows).to_csv(
        args.output_dir / "defense_parameter_cost_sensitivity.csv", index=False
    )

    core_sensitivity_rows = []
    for vol_window in (15, 20, 30):
        scenario_core = run_inverse_volatility_core(
            prices, CORE_SYMBOLS, start=start, end=end,
            config=CorePortfolioConfig(
                initial_capital=1_000_000.0,
                volatility_window=vol_window,
                rebalance_sessions=10,
                one_way_cost_bps=10.0,
            ),
        )
        scenario_nav = align_nav_to_calendar(scenario_core["nav"], union_calendar)
        combined = combine_core_satellite(
            scenario_nav, baseline["nav"], core_weight=0.8,
            rebalance_dates=pd.DatetimeIndex(scenario_core["nav"]["date"].iloc[::10]),
            sleeve_rebalance_cost_bps=10.0,
        )
        core_sensitivity_rows.append({
            "volatilityWindow": vol_window,
            "strategy": "risk_parity_core",
            **performance_metrics(scenario_nav),
        })
        core_sensitivity_rows.append({
            "volatilityWindow": vol_window,
            "strategy": "core80_bull20",
            **performance_metrics(combined["nav"]),
        })
    pd.DataFrame(core_sensitivity_rows).to_csv(
        args.output_dir / "core_volatility_window_sensitivity.csv", index=False
    )

    fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    for strategy in PRIMARY_STRATEGIES:
        nav = results[strategy]["nav"]
        axes[0].plot(nav["date"], nav["nav"] / 1_000_000.0, label=strategy)
        axes[1].plot(nav["date"], nav["drawdown"], label=strategy)
    axes[0].set_title("Bull flip defensive structures (2015-2026)")
    axes[0].set_ylabel("NAV (initial = 1)")
    axes[0].legend(ncol=2, fontsize=8)
    axes[0].grid(alpha=0.2)
    axes[1].set_ylabel("Drawdown")
    axes[1].grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(args.output_dir / "nav_and_drawdown.png", dpi=180)
    plt.close(fig)

    metadata = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "decisionEventInput": str(args.decisions),
        "candidateCatalogInput": str(args.candidate_catalog),
        "priceDataInput": str(args.price_data_dir),
        "membershipInput": str(args.membership),
        "sampleStart": start.date().isoformat(),
        "sampleEnd": end.date().isoformat(),
        "baseline": "policy_eligible_bull_flip rolling monthly PIT",
        "defenseHypothesis": "market reference close above its 200-session moving average gates new entries only",
        "referenceSymbols": REFERENCE_SYMBOL_BY_MARKET,
        "coreSymbols": list(CORE_SYMBOLS),
        "coreConfiguration": asdict(core_config),
        "satelliteBudgets": [0.10, 0.20, 0.30],
        "sleeveRebalance": "every 10 core sessions; 10 bps one-way resizing cost",
        "separationRule": (
            "defensive entry gate and core/satellite structures are evaluated separately; "
            "the pre-specified core90/def200-bull10 cross is reported as a supplemental test"
        ),
        "parameterPolicy": "7/3 bull flip and PIT universe frozen; MA and core grids are sensitivity checks, not full-sample selection",
    }
    (args.output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )
    print(metrics_frame[[
        "strategy", "cagr", "sharpe", "calmar", "maxDrawdown",
        "maxRecoveryDays", "annualizedTurnover", "averageGrossExposure",
    ]].to_string(index=False))


if __name__ == "__main__":
    main()
