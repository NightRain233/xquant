# Q6 Momentum And Trend RiskParity Review

Date: 2026-06-22

## Purpose

This note records the Q6 practice research on momentum filters, trend filters, SuperTrend, and RiskParity layering.

The baseline remains the original three-asset RiskParity strategy confirmed in the Q3 review:

- 510300.SS: CSI 300 ETF
- 513100.SS: Nasdaq 100 ETF
- 518880.SS: Gold ETF

The practice notebook is:

- `research/notebooks/q6-momentum-trend-riskparity-practice.ipynb`

Generated result files are under:

- `outputs/q6-momentum-trend-riskparity/`

## Sample And Method

- Period: 2016-06-21 to 2026-06-22
- Rebalance frequency: every 10 trading days
- Baseline RiskParity volatility window: 20 trading days
- Momentum default: 126 trading-day lookback, Top 2 assets, positive momentum only
- Trend default: 200-day moving average
- SuperTrend default: ATR 10, multiplier 3
- Filtered-out capital is held as cash with zero daily return
- Weights are shifted by one trading day after signal calculation to reduce same-day close lookahead bias

## Strategy Variants

- Original three-asset RiskParity
- Momentum filter equal weight
- 200-day moving-average trend filter equal weight
- SuperTrend filter equal weight
- Momentum + RiskParity
- 200-day moving-average trend filter + RiskParity
- Momentum + 200-day moving-average trend filter + RiskParity
- SuperTrend + RiskParity

## Key Q3/Q5 Results

The original RiskParity baseline remained very strong:

- Cumulative return: 318.64%
- Annualized return: 16.05%
- Annualized volatility: 11.19%
- Max drawdown: -13.53%
- Sharpe: 1.39
- Calmar: 1.19

SuperTrend + RiskParity was the historical and Sharpe winner:

- Cumulative return: 514.78%
- Annualized return: 20.78%
- Annualized volatility: 13.48%
- Max drawdown: -18.38%
- Sharpe: 1.47
- Calmar: 1.13

MA200 trend + RiskParity was close to the baseline on return, but not on drawdown quality:

- Cumulative return: 322.56%
- Annualized return: 16.16%
- Max drawdown: -19.04%
- Sharpe: 1.21
- Calmar: 0.85

Momentum + RiskParity did not improve the baseline:

- Cumulative return: 266.79%
- Annualized return: 14.47%
- Max drawdown: -19.09%
- Sharpe: 0.98
- Calmar: 0.76

Momentum + MA200 + RiskParity was worse than either layer alone:

- Cumulative return: 225.44%
- Annualized return: 13.05%
- Max drawdown: -20.42%
- Sharpe: 0.88
- Calmar: 0.64

## Sensitivity Findings

RiskParity volatility-window sensitivity was stable. Volatility windows from 10 to 60 trading days all kept cumulative return around 322% to 356%, Sharpe around 1.37 to 1.46, and max drawdown around -13% to -15%. This supports the original RiskParity baseline as a robust reference.

Momentum sensitivity was less convincing. Top 1 momentum was fragile and had much deeper drawdowns. Top 2 improved, but still generally lagged the baseline. Top 3 often looked better because it effectively moved back toward holding the full three-asset universe, which weakens the case that the momentum filter itself is adding robust value.

MA trend sensitivity was interpretable but not clearly superior. MA150, MA200, and MA250 were directionally similar, but all accepted deeper drawdowns than the original RiskParity baseline. MA200 had the best return in that group, but it did not improve the risk-adjusted profile enough to replace the baseline.

SuperTrend sensitivity produced the best historical results, but the grid was uneven. ATR 10 / multiplier 3 was strongest, while nearby settings such as ATR 14 / multiplier 4 were much weaker and had larger drawdowns. This means SuperTrend is worth further study, but should be treated as a candidate timing overlay, not yet as a proven replacement.

## Interpretation

Historical best:

- SuperTrend + RiskParity.

Risk-adjusted best:

- By Sharpe: SuperTrend + RiskParity.
- By Calmar and drawdown control: original three-asset RiskParity.

Most structurally balanced:

- Original three-asset RiskParity remains the cleanest baseline. It has the shallowest max drawdown, the strongest Calmar ratio, low parameter dependence, and clear economic interpretation.

Main sample-period advantage:

- The full period still benefited from strong Nasdaq 100 and gold trends. SuperTrend appears to have captured some major upside regimes while avoiding some weak periods, but the result may depend heavily on this specific decade's trend shape and the chosen ATR/multiplier pair.

Main future failure mode:

- Momentum and trend filters can be hurt by sideways markets, whipsaws, late exits, and late re-entry after sharp rebounds. SuperTrend is especially exposed to parameter instability and may look better in a clean-trending sample than it will in a noisier future regime.

## Conclusion

The Q6 result does not justify replacing the original RiskParity baseline yet.

SuperTrend + RiskParity is the most interesting historical winner and deserves a second research pass. However, the original three-asset RiskParity strategy still looks more structurally balanced because it reaches strong returns with lower drawdown, better Calmar, and simpler assumptions.

Momentum filtering was not persuasive in this three-asset universe. It often reduced diversification without reliably reducing drawdown. The combined momentum + trend + RiskParity layer was too restrictive and performed worse than the simpler variants.

## Next Research Direction

- Test SuperTrend + RiskParity with rolling subperiods and explicit out-of-sample splits.
- Add transaction-cost and slippage assumptions, especially because trend filters can trade more often around regime boundaries.
- Compare close-to-close execution with next-open execution.
- Test whether trend filters should apply only to equity sleeves, while gold remains a diversifier.
- Re-run the same framework on different market regimes or longer data if reliable ETF histories are available.
