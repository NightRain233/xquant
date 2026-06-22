# Q3 RiskParity BTC Review

Date: 2026-06-22

## Purpose

This record captures the first complete Q3/Q5-style strategy review in this workspace.
The starting point was the xquant-learning Q3 RiskParity strategy:

- 510300.SS: CSI 300 ETF
- 513100.SS: Nasdaq 100 ETF
- 518880.SS: Gold ETF

The practice notebook is:

- `q3-riskparity-btc-practice.ipynb`

Generated result files are under:

- `outputs/q3-riskparity-btc/`

## Main Finding

The original three-asset RiskParity strategy was the strongest historical baseline in the tests.

Ten-year sample:

- Period: 2016-06-21 to 2026-06-18
- Original three-asset RiskParity cumulative return: 314.17%
- Annualized return: 15.93%
- Annualized volatility: 11.23%
- Max drawdown: -13.79%
- Sharpe: 1.38
- Calmar: 1.15

The result is impressive, but it should not be treated as a stable future expectation.
The strategy benefited heavily from the last decade's strong Nasdaq 100 and gold performance.

## BTC Tests

Adding BTC-USD directly did not improve the core RiskParity strategy.

From the 2021-2026 test:

- Original three-asset RiskParity cumulative return: 114.53%
- BTC RiskParity cumulative return: 96.28%
- BTC average RiskParity weight: 9.05%

RiskParity naturally reduced BTC weight because BTC volatility was high. This lowered risk slightly but did not add enough return.

More disciplined BTC variants were also tested:

- BTC capped at 10%
- BTC capped at 10% with a 200-day trend filter
- BTC cap sensitivity from 5% to 20%

The best BTC interpretation was: if BTC is used, it should be a small satellite allocation, around 5%, not a core sleeve.

## SP500 And Nasdaq Variants

The following variants were tested:

- CSI 300 + SP500 + Gold
- CSI 300 + Nasdaq 100 capped at 15% + Gold
- CSI 300 + SP500 + Gold + Nasdaq 100 capped at 10%

In the 2021-2026 sample, the SP500 core plus Nasdaq 10% satellite portfolio was structurally appealing:

- Cumulative return: 106.43%
- Max drawdown: -11.91%
- Sharpe: 1.28
- Calmar: 1.25

But in the ten-year sample it still lagged the original three-asset RiskParity strategy:

- Cumulative return: 260.13%
- Max drawdown: -16.85%
- Sharpe: 1.27
- Calmar: 0.85

The original strategy remained the historical winner, mostly because Nasdaq 100 was extraordinarily strong.

## Removing CSI 300

Removing CSI 300 and using only Nasdaq 100 + Gold RiskParity improved historical return:

- Cumulative return: 478.24%
- Annualized return: 20.02%
- Sharpe: 1.52

But it also increased drawdown:

- Max drawdown worsened from -13.79% to -18.69%

CSI 300 acted less like a return engine and more like a diversifier. In the past decade it looked like a drag on return, but it may still reduce dependence on overseas growth assets and gold.

## Interpretation

The original strategy is a strong baseline, not a finished system.

Its historical success came from:

- Nasdaq 100 as the main return engine
- Gold as both return engine and diversifier
- RiskParity reducing concentration in the most volatile assets
- CSI 300 providing a different risk source, though with weaker return

Future results may be much lower than the backtest. A more realistic expectation should discount the historical 15% annualized result.

## Next Research Direction

The next clean experiment should start in a new notebook or thread:

- Momentum filtering
- SuperTrend or moving-average trend filtering
- RiskParity after filtering weak assets
- Q5-style validation: annual returns, monthly distribution, drawdown events, underwater curves, and parameter sensitivity

The goal should not be to maximize past return. The goal should be to test whether the strategy becomes more robust when Nasdaq, gold, or overseas assets stop working.

