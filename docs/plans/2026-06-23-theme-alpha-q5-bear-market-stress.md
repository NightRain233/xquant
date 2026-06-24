# Theme Alpha Q5 Bear Market Stress Plan

Date: 2026-06-23

## Purpose

Q5 tests whether the Theme Alpha core/satellite structure survives worse historical regimes.

The main questions are:

- Does the expanded LowVolTrend satellite actually move to cash when there are no eligible trends?
- Does core/satellite reduce drawdown versus the original three-asset RiskParity core during weak markets?
- Is the original core layer still the main source of bear-market risk?
- Do we need a separate defensive rule for the core layer?

## Baseline

Baseline is the original three-asset RiskParity core:

- 510300.SS CSI 300 ETF
- 513100.SS Nasdaq 100 ETF
- 518880.SS Gold ETF

## Strategy Variants

- Core 100
- Expanded LVT 100
- Core80 / Expanded LVT20
- Core70 / Expanded LVT30
- Core60 / Expanded LVT40
- Defensive prototype: Core80 / Expanded LVT20 with risk-off stock weight redirected to cash

Benchmarks:

- CSI 300 ETF
- Nasdaq 100 ETF
- Gold ETF
- 60/40 CSI 300 / Gold

## Fixed Parameters

Use the Q4 LowVolTrend setup unless explicitly stress-testing it:

- Rebalance every 10 trading days
- MA window: 60
- Momentum window: 63
- Volatility window: 60
- Top N: 3
- Satellite asset cap: 50%
- RiskParity volatility window: 20

## Windows

- 2021_to_date
- 2021_2022_bear
- 2022_full
- 2023_full
- 2024_full
- 2025_to_date
- 2026_ytd

## Outputs

Save under:

- `outputs/theme-alpha-q5-bear-market-stress/`

Required files:

- `data_availability.csv`
- `summary_<window>.csv`
- `monthly_diagnostics_<window>.csv`
- `underwater_recovery_<window>.csv`
- `satellite_cash_diagnostics.csv`
- `stress_scorecard.csv`
- NAV and underwater charts for the main stress windows

## Interpretation Rules

Do not treat 2025-to-date as proof of robustness.

The strategy only passes this research stage if:

- Core/satellite drawdown does not materially worsen versus Core 100 in stress windows.
- Expanded LVT shows meaningful cash behavior or rotation away from weak assets.
- The result is not only driven by a single lucky asset.

If the core layer dominates downside risk, Q6 should test a core defensive rule before production realism.
