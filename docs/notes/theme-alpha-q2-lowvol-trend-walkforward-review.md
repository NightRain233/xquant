# Theme Alpha Q2 LowVol Trend Walk-Forward Review

Date: 2026-06-23

## Purpose

Q1 found that LowVolTrend RiskParity looked like a credible strong-theme enhancement candidate.

Q2 asks a stricter question:

- If parameters are selected only from trailing historical data, does LowVolTrend still work in the next validation window?
- Does cap45/cap50/cap55 form a stable platform, or is the result dependent on a narrow magic parameter?

The practice notebook is:

- `theme-alpha-q2-lowvol-trend-walkforward-practice.ipynb`

Generated result files are under:

- `outputs/theme-alpha-q2-lowvol-trend-walkforward/`

## Setup

Theme universe:

- 513100.SS: Nasdaq 100 ETF
- 512400.SS: Non-ferrous metals ETF
- 159995.SZ: Chip ETF
- 515880.SS: Communication ETF
- 518880.SS: Gold ETF

LowVolTrend fixed components:

- Momentum window: 63 trading days
- Volatility window: 60 trading days
- Top-N: 3
- Rebalance frequency: every 10 trading days
- Rebalance anchor: 2024-01-02
- Signal weights shifted by one trading day

Q2 parameter family:

- Moving-average windows: 60, 90, 120, 180, 200
- Single-asset caps: 45%, 50%, 55%

Walk-forward variants:

- Train 126 trading days, validate 21 trading days, rank by Sharpe
- Train 252 trading days, validate 21 trading days, rank by Sharpe
- Train 252 trading days, validate 63 trading days, rank by Sharpe
- Train 252 trading days, validate 21 trading days, rank by Calmar
- Train 252 trading days, validate 21 trading days, rank by a composite score

## Static Parameter Platform

From 2025-01-01 to latest available data:

| Strategy | Cum Return | Max DD | Sharpe | Calmar | Annual Turnover | Avg Cash |
|---|---:|---:|---:|---:|---:|---:|
| LVT_MA60_cap55 | 118.06% | -26.39% | 3.11 | 2.82 | 6.59 | 2.83% |
| LVT_MA60_cap45 | 114.97% | -25.21% | 3.07 | 2.88 | 6.41 | 3.97% |
| LVT_MA60_cap50 | 115.64% | -26.30% | 3.05 | 2.78 | 6.56 | 2.83% |
| LVT_MA120_cap50 | 88.65% | -23.85% | 2.38 | 2.40 | 5.66 | 0.00% |
| Theme RiskParity | 77.68% | -24.89% | 2.29 | 2.04 | 2.32 | 0.00% |
| Original three-asset RP | 41.57% | -12.78% | 1.78 | 2.20 | 2.07 | 0.00% |

The important finding is that cap45/cap50/cap55 around MA60 forms a strong cluster. This is better than seeing one isolated winner.

The less favorable finding is that the MA60 family has higher turnover and deeper drawdown than the original three-asset baseline.

## 2026 YTD Static Check

From 2026-01-01 to latest available data:

| Strategy | Cum Return | Max DD | Sharpe | Calmar |
|---|---:|---:|---:|---:|
| LVT_MA60_cap45 | 26.91% | -25.21% | 2.07 | 2.85 |
| LVT_MA60_cap55 | 26.96% | -26.39% | 2.06 | 2.72 |
| LVT_MA60_cap50 | 26.96% | -26.30% | 2.05 | 2.73 |
| Pure Nasdaq 100 ETF | 14.55% | -13.26% | 1.33 | 2.72 |
| Theme RiskParity | 9.37% | -24.89% | 0.76 | 0.91 |
| Original three-asset RP | 3.72% | -12.78% | 0.41 | 0.68 |

The MA60 cap45/50/55 platform continued to work in 2026 YTD. It did not collapse out of sample.

But it still has a materially deeper drawdown than pure Nasdaq or original three-asset RP.

## Walk-Forward Results

From 2025-01-01 to latest available data, 0 bps cost:

| Strategy | Cum Return | Max DD | Sharpe | Calmar | Annual Turnover | Avg Cash |
|---|---:|---:|---:|---:|---:|---:|
| LVT_MA60_cap55 | 118.06% | -26.39% | 3.11 | 2.82 | 6.59 | 2.83% |
| LVT_MA60_cap45 | 114.97% | -25.21% | 3.07 | 2.88 | 6.41 | 3.97% |
| LVT_MA60_cap50 | 115.64% | -26.30% | 3.05 | 2.78 | 6.56 | 2.83% |
| WF_12m_1m_sharpe | 114.69% | -25.24% | 3.04 | 2.87 | 7.37 | 3.12% |
| WF_12m_3m_sharpe | 110.86% | -26.39% | 2.93 | 2.66 | 7.69 | 3.12% |
| WF_6m_1m_sharpe | 108.88% | -26.39% | 2.88 | 2.62 | 7.61 | 3.26% |
| Theme RiskParity | 77.68% | -24.89% | 2.29 | 2.04 | 2.32 | 0.00% |
| Original three-asset RP | 41.57% | -12.78% | 1.78 | 2.20 | 2.07 | 0.00% |

Interpretation:

- Walk-forward selection worked.
- It did not beat the best static MA60 cap variants.
- The best walk-forward variant, 12-month train / 1-month validation by Sharpe, came very close to the static winners.
- This supports LowVolTrend as a factor family, but does not yet prove that dynamic parameter selection adds value.

## Transaction Cost Stress

At 20 bps one-way cost:

| Strategy | Cum Return | Max DD | Sharpe | Calmar |
|---|---:|---:|---:|---:|
| LVT_MA60_cap55 | 114.08% | -26.54% | 3.02 | 2.72 |
| LVT_MA60_cap45 | 111.15% | -25.35% | 2.98 | 2.78 |
| LVT_MA60_cap50 | 111.72% | -26.45% | 2.95 | 2.68 |
| WF_12m_1m_sharpe | 110.31% | -25.38% | 2.93 | 2.76 |
| Theme RiskParity | 76.53% | -24.95% | 2.26 | 2.01 |
| Original three-asset RP | 40.75% | -12.82% | 1.75 | 2.16 |

The factor survives simple cost stress. However, walk-forward variants have higher turnover than the static family because switching selected parameter sets adds additional movement.

## Added Q5 Diagnostics

Additional Q5-style diagnostics were added after review:

- `outputs/theme-alpha-q2-lowvol-trend-walkforward/comparison_theme_lvt_2025_to_date.csv`
- `outputs/theme-alpha-q2-lowvol-trend-walkforward/monthly_diagnostics_theme_lvt_2025_to_date.csv`
- `outputs/theme-alpha-q2-lowvol-trend-walkforward/underwater_recovery_theme_lvt_2025_to_date.csv`

These compare:

- Theme equal weight
- Theme RiskParity
- LVT_MA60_cap45
- LVT_MA60_cap50
- LVT_MA60_cap55

The added diagnostics include monthly win rate, average winning month, average losing month, worst month, profit factor, underwater time ratio, average underwater depth, longest underwater period, days below -10%, average recovery days, longest recovery days, and unresolved drawdown.

The key read is consistent with the main Q2 conclusion: LVT cap45/50/55 improves profit factor and Sharpe versus theme equal weight and theme RiskParity, but still spends a large share of time underwater. Cap45 has the best Calmar among the three cap variants, while cap55 has the highest return and Sharpe in this sample.

## Parameter Selection Behavior

The best walk-forward selector, WF_12m_1m_sharpe, selected:

- LVT_MA60_cap55: 8 times
- LVT_MA60_cap45: 4 times
- LVT_MA120_cap55: 4 times
- LVT_MA200_cap55: 1 time

Across all walk-forward selectors, MA60 and cap55 appeared frequently, with cap45 also common.

This suggests the parameter family is not random noise. The selector repeatedly prefers the faster MA60 family, especially cap55 or cap45.

But it also raises a caution: the current sample is strongly favorable to fast trend-following in tech-heavy themes. A longer or more regime-diverse sample is still needed.

## Interpretation

Historical best:

- Static LVT_MA60_cap55.

Risk-adjusted best:

- Static LVT_MA60_cap55 by Sharpe.
- LVT_MA60_cap45 by Calmar among the strongest candidates.

Most structurally balanced:

- LVT_MA60_cap45 looks slightly more conservative than cap50/cap55 due to lower average max asset weight and better Calmar.
- LVT_MA60_cap50 remains the simpler middle-ground candidate.
- Theme RiskParity remains the best diversified theme-basket benchmark.
- Original three-asset RP remains the safer core baseline.

Main sample-period advantage:

- The 2025-to-2026 sample strongly favored strong-theme continuation, especially Nasdaq/chips.
- Faster MA60 trend windows benefited from quickly staying with the current theme.

Main future failure mode:

- Sideways or choppy markets could hurt MA60 more than slower trend windows.
- The strategy has higher turnover and may be more sensitive to real execution costs.
- A sudden leadership reversal away from Nasdaq/chips could create larger drawdowns.

## Conclusion

Q2 strengthens the case that LowVolTrend is a real Theme Alpha candidate, not just a single magic-parameter backtest.

The cap45/cap50/cap55 cluster around MA60 is strong across 2025-to-date and 2026 YTD. Walk-forward selection using trailing data also performs well and remains close to the best static variants.

However, Q2 does not prove that walk-forward parameter selection is superior. The current best choice is probably not a dynamic selector, but a simple fixed candidate from the stable parameter platform:

- Main candidate: LVT_MA60_cap50
- More conservative candidate: LVT_MA60_cap45
- More aggressive candidate: LVT_MA60_cap55

The strategy should still be treated as a theme enhancement sleeve, not a replacement for the original three-asset RiskParity baseline.

## Next Research Direction

Q3 should test whether the factor survives structural changes:

- Gold always eligible as a diversifier versus gold filtered like equities.
- Broader theme pool with red dividend, energy, brokers, Hong Kong tech, and healthcare/biotech.
- Longer proxy history if reliable index data can be obtained.
- More realistic ETF execution model: bid/ask spread, premium/discount, and liquidity constraints.
