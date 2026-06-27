# Theme Alpha Q3 Structure Robustness Review

Date: 2026-06-23

## Purpose

Q3 tests whether the Theme Alpha LowVolTrend factor survives structural changes.

The main question is no longer whether LowVolTrend is strong in the original pool. Q1 and Q2 already supported that. Q3 asks:

- Does the factor depend mainly on Nasdaq or Chip?
- Should gold be filtered like an equity theme, always eligible, or floored?
- Does a broader theme pool improve or dilute the factor?

The practice notebook is:

- `research/notebooks/theme-alpha-q3-structure-robustness-practice.ipynb`

Generated outputs are under:

- `outputs/theme-alpha-q3-structure-robustness/`

## Method

The main LowVolTrend settings are fixed from Q2's stronger platform:

- MA window: 60 trading days
- Momentum window: 63 trading days
- Volatility window: 60 trading days
- Top-N: 3
- Single-asset cap: 50%
- Rebalance frequency: every 10 trading days
- Rebalance anchor: 2024-01-02

This keeps Q3 focused on structure, not parameter fitting.

Original theme pool:

- Nasdaq 100 ETF
- Non-ferrous metals ETF
- Chip ETF
- Communication ETF
- Gold ETF

Expanded pool adds:

- Dividend ETF
- Energy ETF
- Securities ETF
- Hong Kong Tech ETF
- Healthcare ETF

## Important Data Alignment Fix

The first Q3 run used a single global intersection of all extended-pool trading days. That changed the effective rebalance phase for the original theme pool and produced non-comparable results.

The notebook was corrected to use the union of ETF dates with forward-filled prices. This keeps the original-pool rebalance behavior comparable while still allowing extended-pool tests.

All results below use the corrected alignment.

## Gold Structure Results

From 2025-01-01 to latest available data:

| Strategy | Cum Return | Max DD | Sharpe | Calmar | Annual Turnover | Avg Cash |
|---|---:|---:|---:|---:|---:|---:|
| RP original theme pool | 77.76% | -24.65% | 2.25 | 2.05 | 2.32 | 0.00% |
| LVT original, gold filtered | 94.54% | -25.45% | 2.55 | 2.38 | 6.41 | 5.65% |
| LVT original, gold always eligible | 63.34% | -25.45% | 1.82 | 1.64 | 5.03 | 0.00% |
| LVT original, gold floor 10% | 63.34% | -25.45% | 1.82 | 1.64 | 5.03 | 0.00% |
| LVT original, gold floor 15% | 63.34% | -25.45% | 1.82 | 1.64 | 5.03 | 0.00% |
| Original three-asset RP | 42.04% | -12.77% | 1.77 | 2.22 | 2.12 | 0.00% |

Gold-always and gold-floor variants did not help in this sample. They reduced return and Sharpe while leaving drawdown essentially unchanged.

The floor variants matched gold-always because gold's RiskParity weight was already above the 10% and 15% floors when it was forced into the selected set.

Current interpretation:

- Gold should not be forced into the LowVolTrend sleeve under this rule set.
- Gold still belongs in the core original three-asset RP benchmark.
- For the theme enhancement sleeve, gold should compete like other assets unless a separate defensive-overlay rule is designed.

## Universe Dependency Results

From 2025-01-01 to latest available data:

| Universe | RP Return | LVT Return | RP Sharpe | LVT Sharpe | LVT Max DD | Verdict |
|---|---:|---:|---:|---:|---:|---|
| Original | 77.76% | 94.54% | 2.25 | 2.55 | -25.45% | Supports factor |
| No Nasdaq | 84.15% | 153.99% | 2.03 | 3.34 | -25.58% | Supports factor |
| No Chip | 68.55% | 61.54% | 2.01 | 1.47 | -36.69% | Weakens factor |
| No Nasdaq + No Chip | 71.03% | 96.24% | 1.62 | 2.05 | -36.82% | Mixed |
| Expanded | 27.20% | 64.47% | 1.18 | 2.31 | -10.77% | Supports factor |

The factor is not simply a Nasdaq strategy. Removing Nasdaq did not break it; in this sample, LowVolTrend performed even better without Nasdaq.

The factor is much more dependent on the chip/technology leadership complex. Removing Chip hurt badly. Removing both Nasdaq and Chip still beat RP on return and Sharpe from 2025 to date, but failed in 2026 YTD and had a deep drawdown.

The expanded pool result is the most structurally encouraging result in Q3. It had lower return than the original LowVolTrend variants, but much better drawdown:

- Expanded LVT cumulative return: 64.47%
- Expanded LVT max drawdown: -10.77%
- Expanded LVT Sharpe: 2.31
- Expanded LVT Calmar: 3.94

This suggests broader asset choice can turn LowVolTrend from a pure high-return sleeve into a more balanced theme-rotation sleeve.

## 2026 YTD Check

Selected 2026 YTD results:

| Strategy | Cum Return | Max DD | Sharpe | Calmar |
|---|---:|---:|---:|---:|
| LVT no Nasdaq | 18.78% | -25.58% | 1.24 | 1.87 |
| LVT expanded | 17.95% | -10.77% | 1.85 | 4.22 |
| LVT original | 15.32% | -25.45% | 1.13 | 1.50 |
| Pure Nasdaq ETF | 14.18% | -13.26% | 1.29 | 2.65 |
| RP original theme pool | 9.98% | -24.65% | 0.81 | 0.98 |
| Original three-asset RP | 3.86% | -12.77% | 0.43 | 0.70 |
| LVT no Chip | -6.64% | -36.69% | -0.34 | -0.39 |

The expanded pool again looks structurally attractive: it had comparable 2026 YTD return to the stronger variants, but with much shallower drawdown.

## Cost Stress

At 20 bps one-way transaction cost:

| Strategy | Cum Return | Max DD | Sharpe | Calmar |
|---|---:|---:|---:|---:|
| LVT original | 91.07% | -25.59% | 2.47 | 2.29 |
| LVT no Nasdaq | 150.09% | -25.72% | 3.26 | 3.58 |
| LVT no Chip | 59.13% | -36.77% | 1.42 | 1.07 |
| LVT expanded | 60.61% | -10.89% | 2.18 | 3.68 |
| RP original | 76.61% | -24.71% | 2.21 | 2.02 |
| Original three-asset RP | 41.20% | -12.81% | 1.73 | 2.17 |

The factor survives simple cost stress, but turnover remains high:

- LVT original annual turnover: 6.41
- LVT no Nasdaq annual turnover: 5.53
- LVT expanded annual turnover: 8.45
- RP original annual turnover: 2.32

The expanded pool's higher turnover is a warning for future execution tests.

## Added Q5 Diagnostics

Additional Q5-style diagnostics were added after review:

- `outputs/theme-alpha-q3-structure-robustness/comparison_structure_2025_to_date.csv`
- `outputs/theme-alpha-q3-structure-robustness/monthly_diagnostics_structure_2025_to_date.csv`
- `outputs/theme-alpha-q3-structure-robustness/underwater_recovery_structure_2025_to_date.csv`

These compare the main structure variants:

- RP original theme pool
- LVT original with gold filtered
- LVT original with gold always eligible
- LVT no Nasdaq
- LVT no Chip
- LVT expanded
- RP expanded
- Original three-asset RiskParity

The added diagnostics include monthly win rate, average winning month, average losing month, worst month, profit factor, underwater time ratio, average underwater depth, longest underwater period, days below -10%, average recovery days, longest recovery days, and unresolved drawdown.

The key read strengthens the Q3 interpretation: LVT expanded is not the highest-return version, but it has a much cleaner underwater profile. In 2025-to-date diagnostics, it had only 1 trading day below -10%, a shallower average underwater depth, and the strongest profit factor among the compared structure variants.

## Current Weights

Latest selected weights:

- LVT original: Nasdaq 42.93%, Chip 28.32%, Communication 28.74%
- LVT no Nasdaq: Chip 50%, Communication 50%
- LVT no Chip: Nasdaq 50%, Communication 50%
- LVT no Nasdaq + no Chip: Communication 50%, Gold 25%, Non-ferrous 25%
- LVT expanded: Nasdaq 42.93%, Chip 28.32%, Communication 28.74%
- RP expanded: more diversified, with Healthcare 17.90%, Dividend 17.32%, Gold 10.13%, Hong Kong Tech 10.38%, Energy 9.77%, and smaller technology weights

The expanded LowVolTrend latest weights matched the original selected assets because the current strongest/cleanest trends are still in the original technology set. Its historical drawdown improvement came from having more alternatives during earlier periods, not from the latest allocation.

## Interpretation

Historical best:

- LVT no Nasdaq had the highest cumulative return in this Q3 pass.

Risk-adjusted best:

- LVT no Nasdaq had the highest Sharpe.
- LVT expanded had the best Calmar and the most attractive drawdown profile.

Most structurally balanced:

- LVT expanded is the most structurally balanced Q3 candidate.

Main sample-period advantage:

- The factor still benefits from technology/chip/communication leadership.
- It is not purely Nasdaq-dependent, but it is exposed to the broader technology leadership complex.

Main future failure mode:

- If chip/technology leadership fails, the original LowVolTrend sleeve can degrade materially.
- Forcing gold into the sleeve does not solve this problem under the current rule.
- The expanded pool improves robustness, but at the cost of higher turnover and lower total return than the most aggressive variants.

## Conclusion

Q3 strengthens the LowVolTrend factor, but changes the interpretation.

The factor is not just a Nasdaq continuation rule. Removing Nasdaq did not break it. However, the factor is meaningfully dependent on chip/technology leadership. Removing Chip weakened the result sharply.

The best structural discovery is the expanded-pool LowVolTrend variant. It did not produce the highest return, but it reduced max drawdown to about -10.77% while keeping strong Sharpe and Calmar. That is a more promising direction for a durable theme-rotation sleeve than simply maximizing return in the original pool.

Gold should not be mechanically forced into the theme sleeve. In this sample, gold-always and gold-floor variants reduced performance without reducing drawdown. Gold remains useful in the core three-asset RP benchmark, but the theme enhancement sleeve may need a separate defensive overlay rather than a simple gold floor.

## Next Research Direction

Theme Alpha Q4 should focus on execution and production-candidate construction:

- Compare original LVT cap50, expanded LVT cap50, and original three-asset RP in a combined core/satellite portfolio.
- Test satellite allocations such as 10%, 20%, and 30% to the LowVolTrend sleeve.
- Add realistic ETF friction assumptions, including spread and liquidity.
- Consider a defensive regime rule for the theme sleeve instead of forcing gold eligibility.
