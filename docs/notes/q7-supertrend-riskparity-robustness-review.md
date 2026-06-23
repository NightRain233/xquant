# Q7 SuperTrend RiskParity Robustness Review

Date: 2026-06-23

## Purpose

Q7 validates the Q6 candidate `SuperTrend + RiskParity`.

The research question is not whether SuperTrend can produce the prettiest full-sample backtest. The question is whether it remains useful after rolling-window checks, explicit out-of-sample checks, transaction costs, next-open execution, and an asset-role variant where gold stays permanently eligible.

The baseline remains the original three-asset RiskParity strategy:

- 510300.SS: CSI 300 ETF
- 513100.SS: Nasdaq 100 ETF
- 518880.SS: Gold ETF

The practice notebook is:

- `q7-supertrend-riskparity-robustness-practice.ipynb`

Generated result files are under:

- `outputs/q7-supertrend-riskparity-robustness/`

## Sample And Method

- Data period: 2016-06-21 to 2026-06-22
- Rebalance frequency: every 10 trading days
- RiskParity volatility window: 20 trading days
- Default SuperTrend: ATR 10, multiplier 3
- Parameter grid: ATR 7/10/14 and multiplier 2/3/4
- Main execution assumption: signal after close, position effective from next close-to-close return
- Conservative execution check: signal after close, trade at next open
- Transaction cost checks: 0, 5, 10, and 20 bps one-way cost

## Main Strategy Variants

- Original three-asset RiskParity
- SuperTrend all-assets + RiskParity
- SuperTrend equities-only, gold always eligible + RiskParity

The third variant tests an asset-role idea: trend filters may make more sense on equity sleeves, while gold may be better treated as a persistent diversifier.

## Full-Sample Results

Original RiskParity:

- Cumulative return: 318.64%
- Annualized return: 16.05%
- Annualized volatility: 11.19%
- Max drawdown: -13.53%
- Sharpe: 1.39
- Calmar: 1.19
- Annualized turnover: 1.98

SuperTrend all-assets + RiskParity:

- Cumulative return: 514.78%
- Annualized return: 20.78%
- Annualized volatility: 13.48%
- Max drawdown: -18.38%
- Sharpe: 1.47
- Calmar: 1.13
- Annualized turnover: 10.95
- Average cash: 12.37%

SuperTrend equities-only, gold always eligible + RiskParity:

- Cumulative return: 426.29%
- Annualized return: 18.84%
- Annualized volatility: 12.53%
- Max drawdown: -21.69%
- Sharpe: 1.44
- Calmar: 0.87
- Annualized turnover: 5.09
- Average gold weight: 60.34%

The full-sample historical and Sharpe winner remains SuperTrend all-assets + RiskParity.
The Calmar and drawdown winner remains original RiskParity.

## Rolling-Window Findings

Rolling windows:

- 2016H2-2020
- 2017-2021
- 2018-2022
- 2019-2023
- 2020-2024
- 2021-2025
- 2022-YTD

SuperTrend all-assets + RiskParity:

- Return win rate versus original RiskParity: 6/7 windows
- Sharpe win rate: 4/7 windows
- Drawdown non-worse rate: 3/7 windows
- Failed most clearly in 2021-2025: lower return, lower Sharpe, and deeper drawdown than original RiskParity

SuperTrend equities-only, gold always eligible + RiskParity:

- Return win rate versus original RiskParity: 7/7 windows
- Sharpe win rate: 7/7 windows
- Drawdown non-worse rate: 6/7 windows

This is the most important Q7 result. The all-assets SuperTrend version remains the full-sample winner, but the gold-always variant is more stable across rolling windows.

However, the gold-always variant still had the deepest full-sample max drawdown at -21.69%, so it is not automatically a safer replacement. Its stability comes with a different exposure profile: materially higher average gold weight and less cash.

## Explicit Out-Of-Sample Check

Train/observation period:

- 2016-06-21 to 2021-12-31

Test period:

- 2022-01-01 to 2026-06-22

The best training-period SuperTrend parameter by Sharpe was the same as the default:

- ATR 10, multiplier 3

Test-period comparison:

- Original RiskParity cumulative return: 107.32%
- Original RiskParity Sharpe: 1.47
- Original RiskParity max drawdown: -12.54%
- Default SuperTrend all-assets + RiskParity cumulative return: 129.40%
- Default SuperTrend all-assets + RiskParity Sharpe: 1.45
- Default SuperTrend all-assets + RiskParity max drawdown: -11.16%

This is supportive but not decisive.

The default parameter survived out-of-sample and beat original RiskParity on cumulative return and max drawdown in the 2022-2026 test period. But it did not beat original RiskParity on Sharpe. In the test-period parameter grid, the default ranked 4th out of 9 by Sharpe, so the result is not a single perfect parameter, but neither is it the most stable point in every view.

## Transaction Cost And Execution Findings

SuperTrend all-assets + RiskParity has much higher turnover:

- Original RiskParity annualized turnover: 1.98
- SuperTrend all-assets + RiskParity annualized turnover: 10.95
- Gold-always SuperTrend variant annualized turnover: 5.09

This matters.

At 10 bps one-way cost with next-close execution:

- Original RiskParity cumulative return: 310.74%
- SuperTrend all-assets + RiskParity cumulative return: 453.31%
- Gold-always SuperTrend variant cumulative return: 401.15%

At 10 bps one-way cost with next-open execution:

- Original RiskParity cumulative return: 312.05%
- SuperTrend all-assets + RiskParity cumulative return: 451.13%
- Gold-always SuperTrend variant cumulative return: 353.43%

The SuperTrend all-assets variant still keeps a large cumulative-return advantage under 10 bps costs and next-open execution. At 20 bps, it still has positive alpha versus original RiskParity, but the Sharpe advantage weakens.

This means costs do not invalidate SuperTrend, but they do narrow the case. Any future SuperTrend research should keep cost and execution assumptions in the default report, not as an optional appendix.

## Interpretation

Historical best:

- SuperTrend all-assets + RiskParity.

Risk-adjusted best:

- By full-sample Sharpe: SuperTrend all-assets + RiskParity.
- By full-sample Calmar and drawdown control: original three-asset RiskParity.
- By rolling-window consistency: SuperTrend equities-only, gold always eligible + RiskParity.

Most structurally balanced:

- Original three-asset RiskParity remains the cleanest deployable baseline.
- SuperTrend all-assets + RiskParity is a strong enhancement candidate, not a replacement.
- SuperTrend equities-only, gold always eligible + RiskParity is the most interesting structural variant, but the full-sample max drawdown needs more investigation before it can be preferred.

Main sample-period advantage:

- SuperTrend benefited from strong, persistent trend phases, especially periods where Nasdaq or gold trends were clean.
- The all-assets version also benefited from moving to cash when assets failed the trend filter.
- The gold-always version benefited from keeping a persistent diversifier rather than timing gold.

Main future failure mode:

- Choppy, sideways markets with repeated false SuperTrend flips.
- Higher trading costs or poor execution around signal changes.
- A regime where gold trends down persistently while remaining permanently eligible in the gold-always variant.
- A rebound-led regime where SuperTrend exits late and re-enters late.

## Q8 BTC Decision

Q8 should do BTC, but only as a satellite stress test, not as a core replacement experiment.

Q7 gives enough evidence that SuperTrend is not merely a one-cell backtest artifact:

- It survives the 2022-2026 out-of-sample check reasonably well.
- It remains ahead after 10 bps cost and next-open execution.
- The default ATR 10 / multiplier 3 was also the best training-period Sharpe parameter.

But Q7 also shows SuperTrend is not clean enough to replace the original baseline:

- Full-sample drawdown is deeper than original RiskParity.
- Rolling-window drawdown behavior is inconsistent for the all-assets version.
- The strongest full-sample version has high turnover.

Therefore BTC should not be added as a new core sleeve. The better Q8 question is:

Can a small BTC satellite, controlled by trend filtering, add convex upside without damaging the original RiskParity core?

Recommended Q8 structure:

- Keep original three-asset RiskParity as the core baseline.
- Test BTC only as a capped satellite: 5%, 10%, and 15%.
- Compare BTC MA200 versus BTC SuperTrend.
- Include a naive four-asset RiskParity version only as a warning/control case.
- Keep transaction cost and next-open execution checks.
- Judge BTC by Calmar, worst year, worst month, drawdown depth, recovery time, and parameter/cap sensitivity, not by cumulative return alone.

## Final Conclusion

Q7 strengthens the case for studying SuperTrend further, but it does not promote SuperTrend to the main baseline.

The best current research stance is:

- Core baseline: original three-asset RiskParity.
- Main enhancement candidate: SuperTrend all-assets + RiskParity.
- Most interesting structural variant: SuperTrend on equities only, with gold always eligible.
- Next research direction: BTC as a small trend-filtered satellite, not as a full fourth core asset.
