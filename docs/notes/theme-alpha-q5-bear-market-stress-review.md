# Theme Alpha Q5 Bear Market Stress Review

Date: 2026-06-23

## Purpose

Q5 tests whether the Theme Alpha core/satellite structure survives worse historical regimes.

The practice notebook is:

- `theme-alpha-q5-bear-market-stress-practice.ipynb`

Generated outputs are under:

- `outputs/theme-alpha-q5-bear-market-stress/`

Important note:

- Q5 uses a 2020-01-02 rebalance anchor so the 10-trading-day rebalance cadence can cover 2021-2022.
- Because the rebalance phase differs from Q4, 2025-to-date numbers are not expected to match Q4 exactly. The directional conclusion remains comparable.

## Setup

Baseline:

- Original three-asset RiskParity core: CSI 300 ETF, Nasdaq 100 ETF, Gold ETF

Satellite:

- Expanded LowVolTrend cap50 from Q4

Main variants:

- Core 100
- Expanded LVT 100
- Core80 / Expanded LVT20
- Core70 / Expanded LVT30
- Core60 / Expanded LVT40

Diagnostic variant:

- Core80 / Expanded LVT20 with a defensive core rule
- The defensive rule redirects CSI 300 and Nasdaq core weights to cash when each asset is below its 120-day moving average at a rebalance date.
- This is not the official Q4 strategy. It is included to test whether the core layer needs its own brake.

Benchmarks:

- CSI 300 ETF
- Nasdaq 100 ETF
- Gold ETF
- 60/40 CSI 300 / Gold

## Key Surprise

Expanded LVT did not go to cash in the tested stress windows.

Satellite cash diagnostics:

| Window | Avg Satellite Cash | Zero-Selection Rebalances | Avg Selected Count |
|---|---:|---:|---:|
| 2021-to-date | 0.00% | 0 | 2.68 |
| 2021-2022 bear | 0.00% | 0 | 2.54 |
| 2022 full | 0.00% | 0 | 2.17 |
| 2023 full | 0.00% | 0 | 2.75 |
| 2024 full | 0.00% | 0 | 2.76 |
| 2025-to-date | 0.00% | 0 | 2.86 |
| 2026 YTD | 0.00% | 0 | 2.82 |

This means LVT's bear-market value in this test did not come from holding cash.

It came from rotating into relative-strength assets, especially:

- Gold ETF
- Nasdaq 100 ETF
- Dividend ETF
- Energy ETF

Selection counts from 2021-to-date:

| Asset | Selected Rebalances |
|---|---:|
| Gold ETF | 100 |
| Nasdaq 100 ETF | 79 |
| Dividend ETF | 78 |
| Energy ETF | 56 |
| Healthcare ETF | 25 |
| Communication ETF | 20 |
| Chip ETF | 13 |
| Nonferrous ETF | 11 |
| HK Tech ETF | 10 |
| Broker ETF | 9 |

## 2021-2022 Bear Window

Window:

- 2021-02-18 to 2022-10-31

| Strategy | Cum Return | Max DD | Sharpe | Worst Month | Days Below -10% |
|---|---:|---:|---:|---:|---:|
| Core 100 | -11.55% | -12.23% | -0.68 | -6.11% | 26 |
| Expanded LVT 100 | -6.29% | -22.56% | -0.22 | -8.42% | 156 |
| Core80 / Expanded20 | -10.28% | -11.58% | -0.59 | -6.45% | 6 |
| Core70 / Expanded30 | -9.68% | -12.86% | -0.54 | -6.63% | 20 |
| Core60 / Expanded40 | -9.11% | -14.14% | -0.48 | -6.80% | 29 |
| Core80 / Expanded20 Defensive Core | -6.15% | -8.17% | -0.47 | -5.39% | 0 |
| CSI 300 | -37.65% | -37.65% | -1.32 | -8.23% | 383 |
| Nasdaq 100 ETF | -6.76% | -27.50% | -0.17 | -14.34% | 183 |
| Gold ETF | 1.36% | -11.38% | 0.07 | -6.37% | 8 |

Interpretation:

- Core80 / Expanded20 improved the core slightly: smaller loss, smaller drawdown, and far fewer days below -10%.
- Increasing the satellite to 30% or 40% improved return but worsened max drawdown versus Core80 / Expanded20.
- Standalone Expanded LVT had a smaller total loss than the core but a much worse path: -22.56% max drawdown and 156 days below -10%.
- The defensive core prototype was the clearest bear-market improvement.

## 2022 Full Year

| Strategy | Cum Return | Max DD | Sharpe | Worst Month | Days Below -10% |
|---|---:|---:|---:|---:|---:|
| Core 100 | -7.50% | -11.66% | -0.70 | -6.11% | 23 |
| Expanded LVT 100 | 9.38% | -11.18% | 0.56 | -7.84% | 2 |
| Core80 / Expanded20 | -4.21% | -9.70% | -0.38 | -6.45% | 0 |
| Core70 / Expanded30 | -2.55% | -9.88% | -0.23 | -6.63% | 0 |
| Core60 / Expanded40 | -0.87% | -10.06% | -0.07 | -6.80% | 1 |
| Core80 / Expanded20 Defensive Core | 1.59% | -4.96% | 0.23 | -2.96% | 0 |
| CSI 300 | -20.14% | -27.70% | -1.04 | -7.83% | 193 |
| Nasdaq 100 ETF | -25.52% | -26.93% | -0.93 | -14.34% | 225 |
| Gold ETF | 9.42% | -11.38% | 0.84 | -1.81% | 8 |

Interpretation:

- 2022 is the best evidence that expanded LVT adds useful rotation value.
- It found non-equity or lower-stress winners often enough to produce a positive year.
- Core/satellite variants improved over Core 100, with Core60 / Expanded40 nearly flat for the year.
- However, the defensive core prototype was still the best risk-control version.

## 2021-To-Date

| Strategy | Cum Return | Max DD | Sharpe | Calmar | Days Below -10% |
|---|---:|---:|---:|---:|---:|
| Core 100 | 115.06% | -12.54% | 1.31 | 1.25 | 38 |
| Expanded LVT 100 | 171.01% | -22.56% | 1.30 | 0.93 | 166 |
| Core80 / Expanded20 | 126.67% | -11.71% | 1.41 | 1.44 | 8 |
| Core70 / Expanded30 | 132.43% | -12.86% | 1.44 | 1.36 | 21 |
| Core60 / Expanded40 | 138.15% | -14.14% | 1.45 | 1.27 | 30 |
| Core80 / Expanded20 Defensive Core | 105.39% | -9.21% | 1.46 | 1.59 | 0 |

Interpretation:

- Standalone Expanded LVT has the highest long-window return but also much worse drawdown quality.
- Core80 / Expanded20 is the best official Q4-style balance in this stress pass.
- Core70 / Expanded30 and Core60 / Expanded40 add more return, but they give back too much drawdown stability.
- The defensive core prototype has lower return but the best drawdown and underwater quality.

## What Q5 Changes

Before Q5, the working mental model was:

- LVT may protect bear markets by going to cash.

After Q5, the better model is:

- LVT protects partly by rotating into relative winners.
- In the tested windows, it did not rely on cash at all.
- The expanded asset pool is useful because it gives LVT somewhere else to go.

This is good and bad.

Good:

- LVT is not just a cash timing trick.
- Expanded pool added real cross-asset rotation value.
- Core80 / Expanded20 improved long-window return and drawdown versus Core 100.

Bad:

- If all assets in the expanded pool trend down together, LVT may not protect enough.
- Standalone LVT still has painful drawdown risk.
- The current core layer remains exposed because it does not have a real risk-off switch.

## Conclusion

Q5 supports the expanded LVT satellite, but with a more sober interpretation.

Updated conclusion:

- LowVolTrend is useful as a relative-strength rotation factor.
- Expanded asset pool is useful because it gives the factor defensive and cyclical alternatives.
- Core/satellite remains the right structure.
- Core80 / Expanded20 is the most balanced official candidate after stress testing.
- Core60 / Expanded40 is too aggressive for a bear-market-aware default.
- Standalone Expanded LVT should not be treated as a whole-portfolio solution.

The biggest Q5 finding is that the strategy's next improvement should probably come from the core layer, not from increasing the satellite layer.

## Next Research Direction

Theme Alpha Q6 should test a core defensive layer:

- Keep Core80 / Expanded LVT20 as the base.
- Test simple core defense rules for CSI 300 and Nasdaq.
- Compare 120-day MA, 200-day MA, and 10-month MA.
- Redirect risk-off equity weight to cash versus gold.
- Check whether defensive rules reduce drawdown without destroying 2024-2026 upside.

Only after this should production realism be tested:

- 10-day versus monthly rebalance.
- Trading cost and slippage.
- Minimum rebalance threshold.
- Single-period max buy/sell limit.
