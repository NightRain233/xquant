# Theme Alpha Q6 Bear Defense Benchmark Completion Plan

Date: 2026-06-23

## Purpose

Q6 completes the missing bear-market benchmarks from Q5 and tests whether the core layer should have a defensive rule.

Q6 answers two questions:

1. Is expanded LowVolTrend better than simple expanded equal weight or expanded RiskParity in bear-market windows?
2. Can a simple core defense rule improve bear-market drawdown without destroying 2023-2026 upside?

## Baseline

Primary baseline:

- Original three-asset RiskParity core
- Assets: CSI 300 ETF, Nasdaq 100 ETF, Gold ETF

Main candidate from Q5:

- Core80 / Expanded LVT20

## Benchmark Completion

Add missing benchmarks:

- Core equal weight
- Original theme equal weight
- Original theme RiskParity
- Expanded ETF pool equal weight
- Expanded ETF pool RiskParity

Keep existing benchmarks:

- CSI 300 ETF
- Nasdaq 100 ETF
- Gold ETF
- 60/40 CSI 300 / Gold

## Core Defense Tests

Use Core80 / Expanded LVT20 as the base.

For CSI 300 and Nasdaq inside the core sleeve:

- 120-day moving average defense
- 200-day moving average defense
- 10-month approximate moving average defense, implemented as 210 trading days

Risk-off destinations:

- Cash
- Gold

Defense variants:

- Core80 / LVT20 Def120 Cash
- Core80 / LVT20 Def200 Cash
- Core80 / LVT20 Def210 Cash
- Core80 / LVT20 Def120 Gold
- Core80 / LVT20 Def200 Gold
- Core80 / LVT20 Def210 Gold

## Fixed Parameters

Use Q5/Q4 LowVolTrend settings:

- Rebalance every 10 trading days
- MA window: 60
- Momentum window: 63
- Volatility window: 60
- Top N: 3
- Satellite cap: 50%
- RiskParity volatility window: 20

## Windows

- 2021-to-date
- 2021-2022 bear
- 2022 full
- 2023 full
- 2024 full
- 2025-to-date
- 2026 YTD

## Outputs

Save under:

- `outputs/theme-alpha-q6-bear-defense-benchmark-completion/`

Required files:

- `data_availability.csv`
- `summary_<window>.csv`
- `monthly_diagnostics_<window>.csv`
- `underwater_recovery_<window>.csv`
- `benchmark_completion_scorecard.csv`
- `defense_scorecard.csv`
- `latest_weights.csv`
- `average_weights.csv`
- NAV and underwater charts for the main windows

## Interpretation Rules

Do not accept a defense rule only because it wins in 2022.

A viable defense rule should:

- reduce 2021-2022 and 2022 drawdowns;
- not materially damage 2023 and 2024 upside;
- keep 2021-to-date Sharpe/Calmar competitive;
- be simple enough to explain and maintain.

If expanded equal weight or expanded RiskParity performs similarly to LVT, the conclusion must credit the asset pool more than the LVT factor.
