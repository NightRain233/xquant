# Theme Alpha Q7 Production Realism Plan

Date: 2026-06-23

## Purpose

Q7 tests whether the shortlisted Theme Alpha candidates survive more realistic implementation assumptions.

This is not a search for a prettier backtest. It tests whether performance remains usable after:

- lower rebalance frequency;
- transaction costs;
- minimum rebalance thresholds;
- max single-period ETF buy/sell limits.

## Candidates

From Q6, carry forward:

- Core80 / Expanded LVT20
- Core80 / Expanded LVT20 Def200 Cash
- Core80 / Expanded LVT20 Def120 Cash
- Core80 / Expanded LVT20 Def210 Gold

## Tests

### Rebalance Frequency

- Every 10 trading days
- Monthly, using the last available trading day each month

### Transaction Costs

One-way costs:

- 0 bps
- 10 bps
- 20 bps
- 30 bps

### Minimum Rebalance Threshold

If target turnover is below the threshold, do not trade:

- 0%
- 2%
- 5%

### Max Single-Period ETF Trade

Limit absolute per-asset target change at each rebalance:

- Unlimited
- 10%
- 15%
- 20%

## Windows

- 2021-to-date
- 2021-2022 bear
- 2022 full
- 2025-to-date
- 2026 YTD

## Outputs

Save under:

- `outputs/theme-alpha-q7-production-realism/`

Required files:

- `summary_all_variants_2021_to_date.csv`
- `summary_all_variants_2022_full.csv`
- `robustness_scorecard.csv`
- `cost_sensitivity.csv`
- `rebalance_frequency_comparison.csv`
- `execution_constraint_comparison.csv`
- selected NAV and underwater charts

## Interpretation Rules

A candidate is practical only if it:

- remains competitive at 20 bps one-way cost;
- does not rely entirely on 10-trading-day rebalancing;
- survives at least a 15% max single-period ETF trade limit;
- keeps drawdown control in 2022 and 2021-2022 bear windows.

If a defense rule only works with high turnover or very frequent signal checks, mark it as fragile.
