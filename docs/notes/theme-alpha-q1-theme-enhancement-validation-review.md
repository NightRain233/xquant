# Theme Alpha Q1 Theme Enhancement Validation Review

Date: 2026-06-23

## Purpose

This validation pass tests whether the theme-alpha-q1 low-volatility trend RiskParity result is a real candidate strategy/factor or mostly a sample-period concentration artifact.

The validation notebook is:

- `theme-alpha-q1-theme-enhancement-validation-practice.ipynb`

Generated result files are under:

- `outputs/theme-alpha-q1-theme-enhancement-validation/`

The earlier screening notebook remains:

- `theme-alpha-q1-strong-theme-screening-practice.ipynb`

## Method

The validation keeps the same theme universe:

- 513100.SS: Nasdaq 100 ETF
- 512400.SS: Non-ferrous metals ETF
- 159995.SZ: Chip ETF
- 515880.SS: Communication ETF
- 518880.SS: Gold ETF

Main candidates:

- Theme RiskParity
- Theme RiskParity with 40% single-asset cap
- LowVolTrend RiskParity
- LowVolTrend RiskParity with 60%, 50%, and 40% single-asset caps

Benchmarks:

- Original three-asset RiskParity
- Theme equal weight
- Pure Nasdaq 100 ETF
- Pure Gold ETF
- 60/40 CSI300 / Gold

Important implementation detail:

- 2023 data is used as indicator warmup.
- The rebalance schedule is anchored at 2024-01-02 so warmup length does not change the 10-trading-day rebalance phase.
- Weights are shifted by one trading day after signal calculation.
- Transaction costs are charged on one-way turnover.

## Concentration Cap Results

From 2025-01-01 to 2026-06-22:

| Strategy | Cum Return | Max DD | Sharpe | Calmar | Annual Turnover | Avg Max Asset Weight |
|---|---:|---:|---:|---:|---:|---:|
| LowVolTrend RP | 100.88% | -23.85% | 2.74 | 2.72 | 6.31 | 50.68% |
| LowVolTrend RP cap60 | 95.79% | -23.85% | 2.62 | 2.59 | 5.86 | 48.57% |
| LowVolTrend RP cap50 | 94.53% | -23.85% | 2.55 | 2.56 | 5.67 | 45.90% |
| LowVolTrend RP cap40 | 85.91% | -23.78% | 2.45 | 2.35 | 5.24 | 39.81% |
| Theme RiskParity | 84.76% | -24.89% | 2.52 | 2.22 | 2.33 | 33.87% |
| Original three-asset RP | 45.47% | -12.78% | 1.97 | 2.41 | 2.08 | 43.85% |

The cap test is encouraging. LowVolTrend remains competitive after caps, especially at 50%. It does not disappear when concentration is constrained.

The 40% cap is the cleanest structural variant, but it sacrifices return. The 50% cap looks like the best compromise in this pass.

Current latest weights:

- LowVolTrend RP: Nasdaq 59.98%, Chip 40.02%
- LowVolTrend RP cap50: Nasdaq 50%, Chip 50%
- LowVolTrend RP cap40: Nasdaq 40%, Chip 40%, Gold 6.67%, Non-ferrous 6.67%, Communication 6.67%
- Theme RiskParity: Gold 31.21%, Nasdaq 21.44%, Non-ferrous 18.85%, Chip 14.30%, Communication 14.20%

## 2026 YTD Results

From 2026-01-01 to 2026-06-22:

| Strategy | Cum Return | Max DD | Sharpe | Calmar |
|---|---:|---:|---:|---:|
| LowVolTrend RP cap50 | 25.73% | -23.85% | 1.93 | 2.89 |
| LowVolTrend RP | 24.74% | -23.85% | 1.90 | 2.76 |
| LowVolTrend RP cap60 | 23.59% | -23.85% | 1.79 | 2.62 |
| LowVolTrend RP cap40 | 22.84% | -23.78% | 1.78 | 2.53 |
| Pure Nasdaq 100 ETF | 18.17% | -13.26% | 1.74 | 3.51 |
| Theme RiskParity | 13.73% | -24.89% | 1.17 | 1.38 |
| Original three-asset RP | 6.58% | -12.78% | 0.76 | 1.23 |

LowVolTrend still wins on 2026 YTD return and Sharpe, but it does not win on drawdown. Pure Nasdaq and original three-asset RP had much shallower drawdowns.

This means LowVolTrend is a return-enhancing theme sleeve, not a lower-risk core replacement.

## Transaction Cost Findings

LowVolTrend has high turnover:

- LowVolTrend RP annual turnover: 6.31
- LowVolTrend RP cap50 annual turnover: 5.67
- Theme RiskParity annual turnover: 2.33
- Original three-asset RP annual turnover: 2.08

Even after 20 bps one-way cost, LowVolTrend remains strong from 2025 to date:

- LowVolTrend RP: cumulative return falls from 100.88% to 97.39%; Sharpe falls from 2.74 to 2.65
- LowVolTrend RP cap50: cumulative return falls from 94.53% to 91.48%; Sharpe falls from 2.55 to 2.47
- Theme RiskParity: cumulative return falls from 84.76% to 83.56%; Sharpe falls from 2.52 to 2.49

The strategy survives simple cost stress. However, the turnover is meaningfully higher, so future work should test realistic ETF spread, slippage, and limit-up/down execution constraints.

## Rolling Window Findings

Rolling diagnostics from 2025 to date:

| Strategy | Window | Avg Rolling Return | Positive Return Rate | Avg Rolling Sharpe | Worst Rolling DD |
|---|---:|---:|---:|---:|---:|
| LowVolTrend RP | 63d | 10.94% | 87.59% | 3.86 | -23.85% |
| LowVolTrend RP | 126d | 27.16% | 100.00% | 3.61 | -23.85% |
| LowVolTrend RP | 252d | 56.28% | 100.00% | 2.58 | -23.85% |
| LowVolTrend RP cap50 | 63d | 10.07% | 87.24% | 3.65 | -23.85% |
| Theme RiskParity | 63d | 11.09% | 81.72% | 4.06 | -24.89% |
| Original three-asset RP | 63d | 7.18% | 92.07% | 3.07 | -12.78% |

The rolling result supports the factor's persistence within this short sample. It is not only one terminal jump.

But the sample is still narrow and strongly favorable to technology/AI/chip themes. The original three-asset RP has lower rolling return, but clearly better drawdown behavior.

## Out-Of-Sample Parameter Validation

The notebook ranks LowVolTrend parameter variants in 2025, then checks their 2026 YTD rank.

Rank correlations between 2025 and 2026:

- Cumulative return rank correlation: 0.65
- Sharpe rank correlation: 0.67
- Calmar rank correlation: 0.43

This is a positive sign. The 2025 winners did not completely collapse in 2026 YTD.

Top 2025 Sharpe variants:

| Variant | 2025 Sharpe Rank | 2026 Sharpe Rank | 2026 Cum Return | 2026 Sharpe | 2026 Max DD |
|---|---:|---:|---:|---:|---:|
| LVT_MA60_cap60 | 1 | 3 | 30.43% | 2.41 | -26.73% |
| LVT_MA60_cap40 | 2 | 1 | 32.40% | 2.61 | -23.79% |
| LVT_MA60_cap50 | 3 | 2 | 31.21% | 2.48 | -26.30% |
| LVT_MA60_uncapped | 4 | 4 | 28.67% | 2.14 | -29.42% |

The MA60 variants look stronger than the original MA120 default in this validation pass. But this is still a small sample. The right interpretation is not "MA60 is best"; it is "the low-volatility trend idea survives nearby parameter changes and may deserve a larger walk-forward study."

## Interpretation

Historical best:

- LowVolTrend RP from the main fixed-parameter set.
- In parameter validation, MA60 capped variants were strongest.

Risk-adjusted best:

- LowVolTrend RP and capped LowVolTrend variants remain best by Sharpe in the 2025-to-date and 2026 YTD windows.

Most structurally balanced:

- LowVolTrend RP cap50 is the best current compromise between return, concentration control, and not holding too much cash.
- Theme RiskParity remains the better diversified theme-basket benchmark.
- Original three-asset RP remains the safer core allocation benchmark.

Main sample-period advantage:

- The test period strongly favored technology, Nasdaq, chips, and broad strong-theme continuation.
- The factor wins partly because it is willing to concentrate into the strongest surviving trend sleeves.

Main future failure mode:

- Fast factor rotation away from Nasdaq/chips.
- Sideways markets with repeated trend whipsaws.
- Higher real-world trading frictions than the simple bps model.
- A regime where gold or defensive sleeves matter, but the trend filter exits them too early.

## Conclusion

LowVolTrend RiskParity now looks like a credible candidate factor for the theme-alpha-q1 strong-theme enhancement layer.

It passed four first-level validation checks:

- It remained strong after single-asset caps.
- It survived 5 to 20 bps one-way transaction cost stress.
- Rolling windows showed repeated positive behavior inside the tested sample.
- 2025 parameter rankings had positive relationship with 2026 YTD rankings.

But it is not yet a proven core strategy. The evidence is still from a short, theme-friendly sample, and drawdowns are materially deeper than the original three-asset RiskParity baseline.

The most useful next candidate is:

- LowVolTrend RiskParity with a 50% cap.

The most conservative next candidate is:

- LowVolTrend RiskParity with a 40% cap, possibly with rules to avoid excessive cash when fewer than three assets pass the filter.

The benchmark to keep comparing against is:

- Theme RiskParity, because it captures the theme-pool effect without relying on the low-volatility trend filter.

## Next Research Direction

- Run a longer historical proxy using index data if reliable ETF history is too short.
- Add a proper walk-forward loop: choose parameters on a rolling training window, then trade only the next validation window.
- Test cap levels between 40% and 60%, especially 45% and 50%.
- Add ETF-specific spread/slippage assumptions.
- Test whether gold should remain always eligible as a diversifier instead of passing the same trend filter as equity themes.
