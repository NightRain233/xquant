# Theme Alpha Q4 Core Satellite Review

Date: 2026-06-23

## Purpose

Q4 tests whether the expanded LowVolTrend sleeve is useful as a satellite around the original three-asset RiskParity core.

The practice notebook is:

- `research/notebooks/theme-alpha-q4-core-satellite-practice.ipynb`

Generated outputs are under:

- `outputs/theme-alpha-q4-core-satellite/`

## Setup

Core:

- Original three-asset RiskParity: CSI 300 ETF, Nasdaq 100 ETF, Gold ETF

Satellite:

- Expanded LowVolTrend cap50 from Q3
- Original-theme LowVolTrend cap50 as an aggressive comparison

Core/satellite variants:

- Core 100%
- Core 90% / Expanded LVT 10%
- Core 80% / Expanded LVT 20%
- Core 70% / Expanded LVT 30%
- Core 60% / Expanded LVT 40%
- Core 80% / Original LVT 20%
- Expanded LVT 100%
- Original LVT 100%

## 2025-To-Date Results

| Strategy | Cum Return | Max DD | Sharpe | Calmar | Worst Month | Profit Factor | Days Below -10% |
|---|---:|---:|---:|---:|---:|---:|---:|
| Core 100 | 42.04% | -12.77% | 1.77 | 2.22 | -7.49% | 3.71 | 6 |
| Core90 / Expanded10 | 44.32% | -12.34% | 1.90 | 2.42 | -7.25% | 4.05 | 6 |
| Core80 / Expanded20 | 46.60% | -11.90% | 2.02 | 2.63 | -7.01% | 4.46 | 3 |
| Core70 / Expanded30 | 48.87% | -11.47% | 2.12 | 2.85 | -6.77% | 4.95 | 1 |
| Core60 / Expanded40 | 51.14% | -11.04% | 2.20 | 3.10 | -6.53% | 5.53 | 1 |
| Core80 / Original20 | 51.59% | -15.41% | 2.03 | 2.24 | -9.38% | 4.31 | 13 |
| Expanded LVT 100 | 64.47% | -10.77% | 2.31 | 3.94 | -5.21% | 9.66 | 1 |
| Original LVT 100 | 94.54% | -25.45% | 2.55 | 2.38 | -16.66% | 5.14 | 66 |

## Interpretation

Expanded LVT works as a satellite.

As satellite allocation increases from 10% to 40%, the combined portfolio improves monotonically on:

- Cumulative return
- Sharpe
- Calmar
- Worst month
- Profit factor
- Days below -10%

The drawdown also improves relative to the core:

- Core 100 max drawdown: -12.77%
- Core60 / Expanded40 max drawdown: -11.04%
- Expanded LVT 100 max drawdown: -10.77%

This is a strong result. In this sample, adding expanded LVT did not increase drawdown; it improved return and drawdown together.

## Original LVT Versus Expanded LVT As Satellite

The 80/20 comparison is important:

- Core80 / Expanded20: 46.60% return, -11.90% max drawdown, Sharpe 2.02, Calmar 2.63
- Core80 / Original20: 51.59% return, -15.41% max drawdown, Sharpe 2.03, Calmar 2.24

Original LVT gives more return, but it brings materially worse drawdown and a worse worst month.

Expanded LVT is the better satellite if the goal is a smoother core enhancement.

Original LVT remains the more aggressive alpha sleeve.

## 2026 YTD Results

Selected 2026 YTD results:

| Strategy | Cum Return | Max DD | Sharpe | Calmar |
|---|---:|---:|---:|---:|
| Expanded LVT 100 | 17.95% | -10.77% | 1.85 | 4.22 |
| Core60 / Expanded40 | 9.58% | -11.04% | 1.19 | 2.09 |
| Core70 / Expanded30 | 8.16% | -11.47% | 1.00 | 1.70 |
| Core80 / Expanded20 | 6.73% | -11.90% | 0.81 | 1.34 |
| Core 100 | 3.86% | -12.77% | 0.43 | 0.70 |

The 2026 YTD check supports the same conclusion: expanded LVT improves the core as satellite, and standalone expanded LVT remains the strongest risk-adjusted sleeve in this short sample.

## Cost Stress

At 20 bps one-way cost:

- Core60 / Expanded40 cumulative return falls from 51.14% to 49.25%.
- Core80 / Expanded20 cumulative return falls from 46.60% to 45.29%.
- Expanded LVT 100 cumulative return falls from 64.47% to 60.61%.

The combined portfolios survive simple cost stress. Expanded LVT has high turnover, but diluted satellite allocations keep portfolio-level turnover more manageable.

## Current Weights

Latest Core60 / Expanded40 weights:

- CSI 300 ETF: 27.57%
- Nasdaq 100 ETF: 30.31%
- Gold ETF: 19.30%
- Chip ETF: 11.33%
- Communication ETF: 11.50%

Latest Core80 / Expanded20 weights:

- CSI 300 ETF: 36.76%
- Nasdaq 100 ETF: 26.10%
- Gold ETF: 25.73%
- Chip ETF: 5.66%
- Communication ETF: 5.75%

These are easier to live with than a standalone theme sleeve. The core keeps meaningful CSI 300 and gold exposure while the satellite adds current theme strength.

## Conclusion

Q4 supports using expanded LVT as a satellite sleeve.

The best pure core/satellite candidate in this pass is:

- Core60 / Expanded LVT40

It had the strongest return, Sharpe, Calmar, and underwater quality among the fixed core/satellite mixes.

The more conservative candidate is:

- Core70 / Expanded LVT30

It gives most of the improvement while staying closer to a core allocation.

The practical starting candidate is probably:

- Core80 / Expanded LVT20

It improves return, Sharpe, Calmar, and days below -10% versus the core, while keeping satellite risk modest.

Expanded LVT 100 remains excellent in this sample, but it should be treated as a sleeve, not the default whole portfolio, until tested across longer and less theme-friendly regimes.

## Next Research Direction

Theme Alpha Q5 should test production realism:

- ETF spreads, slippage, liquidity, and premium/discount assumptions.
- Rebalance execution timing: close-to-close versus next-open.
- Satellite allocation sensitivity between 20%, 30%, and 40%.
- A defensive rule that reduces satellite allocation when expanded LVT is in cash or when broad trend quality deteriorates.
