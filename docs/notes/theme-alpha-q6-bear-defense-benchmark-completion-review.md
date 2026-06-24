# Theme Alpha Q6 Bear Defense Benchmark Completion Review

Date: 2026-06-23

## Purpose

Q6 completes the missing bear-market benchmarks from Q5 and tests simple core-defense rules.

The practice notebook is:

- `theme-alpha-q6-bear-defense-benchmark-completion-practice.ipynb`

Generated outputs are under:

- `outputs/theme-alpha-q6-bear-defense-benchmark-completion/`

## Setup

Primary baseline:

- Original three-asset RiskParity core: CSI 300 ETF, Nasdaq 100 ETF, Gold ETF

Main candidate from Q5:

- Core80 / Expanded LVT20

Benchmark completion:

- Core equal weight
- Original theme equal weight
- Original theme RiskParity
- Expanded equal weight
- Expanded RiskParity
- Expanded LVT
- Single-asset and 60/40 benchmarks

Core-defense tests:

- 120-day MA defense
- 200-day MA defense
- 210-day MA defense, used as an approximate 10-month rule

Risk-off destinations:

- Cash
- Gold

## Benchmark Completion Result

Q6 confirms that expanded LVT is not just an expanded-pool accident, especially in 2022.

### 2022 Full Year

| Strategy | Cum Return | Max DD | Sharpe | Days Below -10% |
|---|---:|---:|---:|---:|
| Core RP | -7.50% | -11.66% | -0.70 | 23 |
| Core EW | -12.26% | -15.75% | -0.91 | 132 |
| Original Theme EW | -20.39% | -23.21% | -1.10 | 179 |
| Original Theme RP | -15.01% | -18.23% | -1.03 | 168 |
| Expanded EW | -15.11% | -19.90% | -0.81 | 133 |
| Expanded RP | -12.92% | -16.54% | -0.82 | 103 |
| Expanded LVT | 9.38% | -11.18% | 0.56 | 2 |
| Core80 / Expanded LVT20 | -4.21% | -9.70% | -0.38 | 0 |

Interpretation:

- Expanded EW and Expanded RP did not protect 2022.
- Original-theme EW/RP were worse than the core in 2022.
- Expanded LVT was the only full-theme approach that produced a positive 2022.
- Core80 / Expanded LVT20 improved the core without inheriting the full drawdown of standalone LVT.

This is meaningful evidence that the LVT factor contributed beyond simple asset-pool exposure.

### 2021-2022 Bear Window

| Strategy | Cum Return | Max DD | Sharpe | Days Below -10% |
|---|---:|---:|---:|---:|
| Core RP | -11.55% | -12.23% | -0.68 | 26 |
| Core EW | -14.74% | -16.49% | -0.74 | 106 |
| Original Theme EW | -6.49% | -24.99% | -0.22 | 166 |
| Original Theme RP | -5.93% | -19.84% | -0.26 | 138 |
| Expanded EW | -13.00% | -24.80% | -0.47 | 183 |
| Expanded RP | -8.11% | -19.04% | -0.34 | 137 |
| Expanded LVT | -6.29% | -22.56% | -0.22 | 156 |
| Core80 / Expanded LVT20 | -10.28% | -11.58% | -0.59 | 6 |

Interpretation:

- Standalone LVT was not the clean winner in the full 2021-2022 bear window.
- Original theme RP had slightly better standalone return and drawdown than Expanded LVT in this specific window.
- But all standalone theme-like approaches had much worse underwater quality than Core80 / Expanded LVT20.
- The core/satellite structure remains more important than choosing a standalone theme engine.

## Defense Result

The core-defense rules work, but the destination matters.

### 2022 Full Year Defense Variants

| Strategy | Cum Return | Max DD | Sharpe | Avg Cash |
|---|---:|---:|---:|---:|
| Core80 / Expanded LVT20 | -4.21% | -9.70% | -0.38 | 0.00% |
| Def120 Cash | 1.59% | -4.96% | 0.23 | 33.51% |
| Def120 Gold | 5.73% | -7.25% | 0.54 | 0.00% |
| Def200 Cash | 3.96% | -3.93% | 0.62 | 39.03% |
| Def200 Gold | 7.62% | -6.51% | 0.73 | 0.00% |
| Def210 Cash | 3.96% | -3.93% | 0.62 | 39.03% |
| Def210 Gold | 7.62% | -6.51% | 0.73 | 0.00% |

Interpretation:

- Cash defense provides the cleanest drawdown reduction.
- Gold defense gives better 2022 return, but with more exposure risk.
- 200-day and 210-day rules behaved the same in 2022.

### 2021-To-Date Defense Variants

| Strategy | Cum Return | Max DD | Sharpe | Calmar | Days Below -10% |
|---|---:|---:|---:|---:|---:|
| Core80 / Expanded LVT20 | 126.67% | -11.71% | 1.41 | 1.44 | 8 |
| Def120 Cash | 105.39% | -9.21% | 1.46 | 1.59 | 0 |
| Def120 Gold | 125.97% | -14.22% | 1.37 | 1.18 | 8 |
| Def200 Cash | 115.88% | -10.46% | 1.52 | 1.51 | 1 |
| Def200 Gold | 139.95% | -14.56% | 1.50 | 1.25 | 10 |
| Def210 Cash | 112.64% | -11.71% | 1.47 | 1.32 | 1 |
| Def210 Gold | 142.32% | -11.71% | 1.55 | 1.57 | 1 |

Interpretation:

- Def120 Cash is the cleanest risk-control rule: lowest drawdown and zero days below -10%, but it gives up the most return.
- Def200 Cash is the best cash-defense compromise: it reduces drawdown, keeps only 1 day below -10%, and has the highest Sharpe among cash rules.
- Def210 Gold is the best return-preserving defense: highest long-window return and Sharpe among the tested defense variants, but it is not a true cash brake.
- Def120/200 Gold can worsen drawdown in some windows because it concentrates risk into gold instead of reducing exposure.

## 2025-To-Date Check

| Strategy | Cum Return | Max DD | Sharpe | Days Below -10% |
|---|---:|---:|---:|---:|
| Core80 / Expanded LVT20 | 48.82% | -11.71% | 2.12 | 1 |
| Def120 Cash | 43.29% | -9.21% | 2.14 | 0 |
| Def200 Cash | 44.72% | -10.46% | 2.10 | 1 |
| Def210 Gold | 44.99% | -11.71% | 1.97 | 1 |

Interpretation:

- All defense rules reduce 2025-to-date return versus the base Core80 / Expanded LVT20.
- Def120 Cash improves drawdown the most but has meaningful upside drag.
- Def200 Cash is less aggressive and has a smaller drag.
- Def210 Gold keeps exposure but does not improve 2025 drawdown.

## What Q6 Changes

Q5 said:

- LVT is useful, but it did not protect by going to cash.
- The core layer probably needs a brake.

Q6 refines that:

- Expanded LVT really does add factor value versus expanded EW/RP in 2022.
- But standalone theme engines are still too path-risky.
- Core80 / Expanded LVT20 remains the best base structure.
- Core defense should be researched further, but not all defense rules are equal.

## Current Best Candidates

Best base strategy:

- Core80 / Expanded LVT20

Best cash-defense candidate:

- Core80 / Expanded LVT20 Def200 Cash

Best drawdown-control candidate:

- Core80 / Expanded LVT20 Def120 Cash

Best return-preserving defensive candidate:

- Core80 / Expanded LVT20 Def210 Gold

## Honest Interpretation

The expanded ETF pool is helpful, but it is not sufficient by itself.

Simple expanded equal weight and expanded RiskParity were weak in 2022 and had poor long-window underwater quality. That means LVT is doing real work.

However, LVT is not enough by itself either. Standalone Expanded LVT has high return but much worse drawdown quality than the core/satellite versions.

The most structurally robust framework is still:

- core allocation first;
- LVT as a satellite;
- optional core defense for risk-off regimes.

## Next Research Direction

Theme Alpha Q7 should test production realism for the shortlisted candidates:

- Core80 / Expanded LVT20
- Core80 / Expanded LVT20 Def200 Cash
- Core80 / Expanded LVT20 Def120 Cash
- Core80 / Expanded LVT20 Def210 Gold

Q7 should test:

- 10-trading-day versus monthly rebalance;
- transaction costs and slippage;
- minimum rebalance threshold;
- max single-period buy/sell limit;
- whether defense signals should be checked daily, every 10 trading days, or monthly.
