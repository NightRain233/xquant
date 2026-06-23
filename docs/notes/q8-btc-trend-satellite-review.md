# Q8 BTC Trend Satellite Review

Date: 2026-06-23

## Purpose

Q8 tests the Q7 decision: BTC should be studied only as a small, trend-filtered satellite, not as a new core sleeve.

The baseline remains the original three-asset RiskParity strategy:

- 510300.SS: CSI 300 ETF
- 513100.SS: Nasdaq 100 ETF
- 518880.SS: Gold ETF

BTC is represented by:

- BTC-USD

The practice notebook is:

- `q8-btc-trend-satellite-practice.ipynb`

Generated result files are under:

- `outputs/q8-btc-trend-satellite/`

## Sample And Method

- Period: 2016-06-21 to 2026-06-23
- Calendar: BTC was sampled on the ETF common trading calendar
- Rebalance frequency: every 10 trading days
- Core portfolio: original three-asset RiskParity
- BTC satellite caps: 5%, 10%, 15%
- BTC filters:
  - No filter
  - 200-day moving average
  - SuperTrend, ATR 10 and multiplier 3
- Main execution assumption: signal after close, effective from next close-to-close return
- Stress checks: next-open execution and 10/20 bps one-way transaction costs

The satellite rule is intentionally simple:

- Core RiskParity receives `1 - cap`
- BTC receives `cap` only when its filter is active
- If BTC filter is inactive, the satellite sleeve goes to cash

This keeps BTC out of the core RiskParity engine.

## Key Results

Original three-asset RiskParity:

- Cumulative return: 308.38%
- Annualized return: 15.74%
- Annualized volatility: 11.22%
- Max drawdown: -13.53%
- Sharpe: 1.36
- Calmar: 1.16

Q7 SuperTrend three-asset reference:

- Cumulative return: 496.75%
- Annualized return: 20.40%
- Max drawdown: -18.38%
- Sharpe: 1.44
- Calmar: 1.11

Naive four-asset RiskParity:

- Cumulative return: 450.43%
- Annualized return: 19.39%
- Max drawdown: -17.44%
- Sharpe: 1.54
- Calmar: 1.11
- Average BTC weight: 8.28%

The naive four-asset version improved return and Sharpe, but it did not improve drawdown or Calmar versus the original RiskParity baseline. It is useful as a control case, not as the preferred structure.

## BTC Satellite Results

BTC 5% satellite:

- No filter: cumulative return 431.63%, max drawdown -15.51%, Calmar 1.22
- MA200: cumulative return 410.83%, max drawdown -13.46%, Calmar 1.37
- SuperTrend: cumulative return 402.54%, max drawdown -12.93%, Calmar 1.41

BTC 10% satellite:

- No filter: cumulative return 584.36%, max drawdown -18.86%, Calmar 1.17
- MA200: cumulative return 534.18%, max drawdown -14.68%, Calmar 1.44
- SuperTrend: cumulative return 514.60%, max drawdown -12.81%, Calmar 1.62

BTC 15% satellite:

- No filter: cumulative return 771.15%, max drawdown -22.78%, Calmar 1.11
- MA200: cumulative return 681.39%, max drawdown -16.71%, Calmar 1.43
- SuperTrend: cumulative return 647.03%, max drawdown -15.00%, Calmar 1.55

The historical return winner was BTC 15% with no filter. That is not the structurally best candidate because drawdown worsened sharply.

The best structural candidate was BTC 10% SuperTrend satellite:

- Cumulative return: 514.60%
- Annualized return: 20.77%
- Annualized volatility: 11.25%
- Max drawdown: -12.81%
- Sharpe: 1.73
- Calmar: 1.62
- Average BTC weight: 5.44%
- Average cash: 5.30%

This candidate improved return, Sharpe, Calmar, max drawdown, worst month, and worst year versus the original RiskParity baseline.

## Cap And Filter Interpretation

The BTC filter mattered more than BTC itself.

Unfiltered BTC satellite:

- Produced the highest historical return at 15%
- Consistently worsened drawdown as cap increased
- Failed the risk-quality test

MA200 BTC satellite:

- Reduced drawdown relative to unfiltered BTC
- Produced strong Calmar ratios
- Was useful, but generally less clean than SuperTrend in this sample

SuperTrend BTC satellite:

- Had the best drawdown control
- Had the best Calmar at 10%
- Gave up some upside versus unfiltered BTC, but improved the strategy shape

The cap shape was also informative:

- 5% SuperTrend satellite was conservative and robust
- 10% SuperTrend satellite had the best balance of return and risk
- 15% SuperTrend satellite still worked, but drawdown rose and the strategy became more BTC-dependent

## Cost And Execution Checks

The key 10% SuperTrend BTC satellite survived transaction cost and next-open checks.

At 10 bps one-way cost with next-close execution:

- Original RiskParity cumulative return: 300.68%
- BTC 10% SuperTrend satellite cumulative return: 500.40%
- BTC 10% SuperTrend satellite max drawdown: -12.84%
- BTC 10% SuperTrend satellite Calmar: 1.59

At 10 bps one-way cost with next-open execution:

- Original RiskParity cumulative return: 301.96%
- BTC 10% SuperTrend satellite cumulative return: 497.85%
- BTC 10% SuperTrend satellite max drawdown: -12.80%
- BTC 10% SuperTrend satellite Calmar: 1.59

At 20 bps one-way cost with next-open execution:

- BTC 10% SuperTrend satellite cumulative return: 484.00%
- Max drawdown: -12.83%
- Calmar: 1.57

Costs did not invalidate the BTC 10% SuperTrend satellite result. Its annualized turnover was also far below the full three-asset SuperTrend strategy, because only the BTC satellite sleeve switches.

## Decision Scorecard

The scorecard checked six conditions versus original RiskParity:

- Higher cumulative return
- Higher Sharpe
- Calmar not lower
- Max drawdown not deeper
- Worst month not worse
- Worst year not worse

Only two BTC candidates passed all six:

- BTC 5% SuperTrend satellite
- BTC 10% SuperTrend satellite

BTC 10% SuperTrend satellite was the stronger candidate because it had much higher return while still improving the full risk-quality checklist.

## Interpretation

Historical best:

- BTC 15% unfiltered satellite.

Risk-adjusted best:

- BTC 10% SuperTrend satellite by Calmar.
- BTC 15% SuperTrend satellite by Sharpe, but with more drawdown and more BTC dependence.

Most structurally balanced:

- BTC 10% SuperTrend satellite.

Main sample-period advantage:

- BTC had a very strong long-run return profile over the sample.
- Trend filtering avoided enough BTC drawdowns to improve the whole portfolio, especially at 5% and 10% caps.

Main future failure mode:

- BTC may have much lower forward returns than the sample period.
- SuperTrend may whipsaw during sideways crypto markets.
- BTC-USD is not the same as a directly investable local ETF sleeve; currency, access, custody, and execution assumptions matter.
- A 15% BTC cap can make the strategy too dependent on BTC's historical upside.

## Conclusion

Q8 supports doing BTC, but only in a disciplined satellite form.

Directly adding BTC to RiskParity is not the preferred structure. Unfiltered BTC can create attractive historical return, but it worsens drawdown as the cap rises. The better structure is:

- Keep original three-asset RiskParity as the core
- Add BTC as a capped satellite
- Use SuperTrend to decide whether the satellite is active
- Keep cap around 5% to 10%

The current best Q8 candidate is:

- Original three-asset RiskParity core + BTC 10% SuperTrend satellite

This should not yet be treated as a finished strategy. It should be the next candidate for robustness validation.

## What To Test Next

- Rolling-window validation for BTC 10% SuperTrend satellite
- Explicit train/test split for BTC SuperTrend parameters
- BTC cap grid around 5%, 7.5%, 10%, 12.5%
- Compare BTC SuperTrend with BTC MA200 under choppy crypto regimes
- Test BTC satellite using more conservative transaction cost and slippage assumptions
- Check whether the result survives if BTC forward return expectations are haircut
