# Theme Alpha Q1 Strong Theme RiskParity Review

Date: 2026-06-22

## Purpose

This note records the Q6 practice research on whether 2025 strong themes continued into 2026.

The confirmed baseline remains the original three-asset RiskParity strategy:

- 510300.SS: CSI 300 ETF
- 513100.SS: Nasdaq 100 ETF
- 518880.SS: Gold ETF

The Q6 theme pool is:

- 513100.SS: Nasdaq 100 ETF
- 512400.SS: Non-ferrous metals ETF
- 159995.SZ: Chip ETF
- 515880.SS: Communication ETF
- 518880.SS: Gold ETF

The practice notebook is:

- `research/notebooks/theme-alpha-q1-strong-theme-screening-practice.ipynb`

Generated result files are under:

- `outputs/theme-alpha-q1-strong-theme-screening/`

## Data And Benchmarks

The notebook uses 2024 data as warmup for trend, momentum, and volatility indicators, then evaluates:

- 2026 YTD: 2026-01-01 to 2026-06-22
- 2025 to date: 2025-01-01 to 2026-06-22

Benchmarks included successfully:

- Original three-asset RiskParity
- CSI 300 ETF
- 60/40 CSI 300 / Gold
- Pure Nasdaq 100 ETF
- Pure Gold ETF

The requested CSI All Share and equity-biased fund index benchmarks were attempted, but the free yfinance source did not provide usable time series. The notebook records this in:

- `outputs/theme-alpha-q1-strong-theme-screening/data_availability.csv`

## Strategy Variants

- Theme equal weight
- Theme RiskParity
- Low-volatility plus trend-filtered RiskParity
- Momentum Top 2 equal weight
- SuperTrend-filtered RiskParity

All strategy weights are shifted by one trading day after signal calculation to reduce same-day close lookahead bias.

## 2026 YTD Results

Low-volatility plus trend-filtered RiskParity was the strongest 2026 YTD result:

- Cumulative return: 24.74%
- Annualized return: 65.95%
- Annualized volatility: 34.70%
- Max drawdown: -23.85%
- Sharpe: 1.90
- Calmar: 2.76

The original three-asset RiskParity baseline was much steadier but lagged in return:

- Cumulative return: 6.58%
- Annualized return: 15.72%
- Annualized volatility: 20.60%
- Max drawdown: -12.78%
- Sharpe: 0.76
- Calmar: 1.23

Pure Nasdaq was also strong in 2026 YTD:

- Cumulative return: 18.17%
- Max drawdown: -13.26%
- Sharpe: 1.74

Momentum Top 2 equal weight failed badly in this window:

- Cumulative return: -21.96%
- Max drawdown: -49.89%
- Sharpe: -0.74

## 2025 To Date Results

Low-volatility plus trend-filtered RiskParity was also the strongest from 2025 to date:

- Cumulative return: 100.88%
- Annualized return: 64.77%
- Annualized volatility: 23.67%
- Max drawdown: -23.85%
- Sharpe: 2.74
- Calmar: 2.72

Theme RiskParity and theme equal weight also benefited from the strong theme sample:

- Theme RiskParity cumulative return: 84.76%, Sharpe: 2.52
- Theme equal weight cumulative return: 92.75%, Sharpe: 2.30

The original three-asset RiskParity baseline remained structurally cleaner:

- Cumulative return: 45.47%
- Annualized return: 30.78%
- Max drawdown: -12.78%
- Sharpe: 1.97
- Calmar: 2.41

## Current Weights

As of the latest available data, low-volatility plus trend-filtered RiskParity selected only:

- Nasdaq 100 ETF: 59.98%
- Chip ETF: 40.02%

Theme RiskParity remained broadly diversified:

- Nasdaq 100 ETF: 21.44%
- Gold ETF: 31.21%
- Non-ferrous metals ETF: 18.85%
- Chip ETF: 14.30%
- Communication ETF: 14.20%

Original three-asset RiskParity held:

- CSI 300 ETF: 45.90%
- Nasdaq 100 ETF: 22.03%
- Gold ETF: 32.07%

## Sensitivity Findings

RiskParity volatility windows were reasonably stable. Theme RiskParity with volatility windows from 10 to 60 trading days stayed profitable, with Sharpe roughly from 2.39 to 2.73 in the 2025-to-date window.

Low-volatility plus trend filtering was strong, but it concentrated into fewer assets. The default MA120 version performed best among the main variants, while MA180 and MA200 were close but not clearly superior.

Momentum was unstable. Shorter lookback variants such as 63-day momentum looked strong in sensitivity tests, but the default 126-day Top 2 version performed poorly, especially in 2026 YTD. This makes momentum the least convincing standalone rule in this pass.

SuperTrend was highly parameter-sensitive. Some parameter pairs, such as ATR 7 / multiplier 3, looked excellent historically, but the default ATR 10 / multiplier 3 had a deeper drawdown than the baseline and weaker 2026 YTD behavior. This should be treated as an overlay worth further testing, not a proven replacement.

## Interpretation

Historical best:

- Low-volatility plus trend-filtered RiskParity.

Risk-adjusted best:

- By Sharpe in both tested windows: low-volatility plus trend-filtered RiskParity.
- By drawdown depth and structural simplicity: original three-asset RiskParity remains competitive.

Most structurally balanced:

- Original three-asset RiskParity remains the cleanest baseline.
- Theme RiskParity is the most useful theme-pool comparison because it does not rely on a narrow filter selecting only the hottest sleeves.

Main sample-period advantage:

- The 2025-to-2026 sample strongly favored technology, Nasdaq, chips, and selected cyclical themes. The strongest variant benefited from concentrating into Nasdaq and chips near the end of the sample.

Main future failure mode:

- If the 2025 strength does not persist, the low-volatility/trend variant can become concentrated in late-cycle winners and suffer from sharp reversals.
- Momentum and SuperTrend can be hurt by whipsaws, delayed exits, and delayed re-entry after rebounds.
- Theme-pool strategies have materially deeper drawdowns than the original three-asset RiskParity baseline.

## Conclusion

The Q6 result supports continuing to study a strong-theme overlay, but it does not justify replacing the original three-asset RiskParity baseline yet.

The low-volatility plus trend-filtered RiskParity variant is the historical winner in both 2026 YTD and 2025-to-date tests. However, it reaches that result by accepting deeper drawdowns and higher concentration in technology sleeves. Theme RiskParity is a better structural comparison candidate because it keeps diversified exposure across Nasdaq, non-ferrous metals, chips, communication, and gold.

## Next Research Direction

- Add transaction costs and slippage.
- Test rolling subperiods instead of only 2025-to-date and 2026 YTD.
- Add a concentration cap to low-volatility plus trend-filtered RiskParity.
- Re-test CSI All Share and equity-biased fund index benchmarks when a stable data source is available.
- Compare whether gold should bypass equity trend filters and remain as a persistent diversifier.
