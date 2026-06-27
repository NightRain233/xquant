# Q9 BTC SuperTrend Satellite Robustness Review

Date: 2026-06-23

## Purpose

Q9 validates the Q8 candidate:

- Original three-asset RiskParity core + BTC 10% SuperTrend satellite

The two central questions are:

1. Does BTC10% SuperTrend satellite improve the holding experience versus original RiskParity?
2. Does it depend on a magic SuperTrend parameter or a magic 10% cap?

The practice notebook is:

- `research/notebooks/q9-btc-supertrend-satellite-robustness-practice.ipynb`

Generated result files are under:

- `outputs/q9-btc-supertrend-satellite-robustness/`

## Sample And Method

- Period: 2016-06-21 to 2026-06-23
- Calendar: BTC sampled on the ETF common trading calendar
- Core baseline: original three-asset RiskParity
- Main candidate: BTC 10% SuperTrend satellite, ATR 10 and multiplier 3
- SuperTrend parameter grid: ATR 7/10/14 and multiplier 2/3/4
- Cap grid: 5%, 7.5%, 10%, 12.5%, 15%
- Combined grid: 45 cap/parameter combinations
- Rolling windows: 7 overlapping subperiods from 2016H2-2020 through 2022-YTD
- Cost and execution stress: next-close and next-open, with 0/10/20/50 bps one-way cost

Q9 adds three missing evaluation tables:

- `underwater_stats.csv`
- `recovery_stats.csv`
- `relative_comparison_vs_rp.csv`

## Main Results

Original RiskParity:

- Cumulative return: 307.15%
- Annualized return: 15.71%
- Max drawdown: -13.53%
- Sharpe: 1.36
- Calmar: 1.16

BTC10% SuperTrend satellite:

- Cumulative return: 512.93%
- Annualized return: 20.73%
- Max drawdown: -12.81%
- Sharpe: 1.73
- Calmar: 1.62

This remains a strong headline result. The candidate improved return, Sharpe, Calmar, and max drawdown versus original RiskParity.

## Monthly Experience

Original RiskParity:

- Monthly win rate: 65.00%
- Average winning month: 2.78%
- Average losing month: -1.68%
- Profit factor: 3.08
- Worst month: -7.50%

BTC10% SuperTrend satellite:

- Monthly win rate: 68.33%
- Average winning month: 3.12%
- Average losing month: -1.78%
- Profit factor: 3.79
- Worst month: -6.76%

The monthly experience improved overall. The candidate had a higher win rate, better profit factor, stronger winning months, and a better worst month. Average losing month was slightly worse, but not enough to outweigh the broader improvement.

## Underwater Experience

Original RiskParity:

- Underwater time: 84.87%
- Average underwater depth: -3.65%
- Longest underwater stretch: 653 trading days
- Days below -10% drawdown: 83
- Current drawdown: -4.67%

BTC10% SuperTrend satellite:

- Underwater time: 83.39%
- Average underwater depth: -3.48%
- Longest underwater stretch: 334 trading days
- Days below -10% drawdown: 89
- Current drawdown: -4.25%

The holding experience improved, but not perfectly.

The strongest improvements were:

- Longest underwater stretch was cut from 653 to 334 trading days
- Average underwater depth improved from -3.65% to -3.48%
- Current drawdown was slightly shallower
- Underwater time was slightly lower

The blemish:

- Days below -10% increased from 83 to 89

So the right interpretation is not "BTC10% SuperTrend improves every waterline metric." The better interpretation is:

It materially improved the length and average depth of underwater periods, while leaving one severity-count metric roughly unchanged to slightly worse.

## Recovery Quality

Original RiskParity:

- Average recovery days: 12.40
- Median recovery days: 4
- Longest recovery days: 376
- Current unresolved drawdown depth: -6.99%

BTC10% SuperTrend satellite:

- Average recovery days: 11.13
- Median recovery days: 4
- Longest recovery days: 179
- Current unresolved drawdown depth: -6.36%

Recovery quality improved.

The most important change is the longest recovery time: 376 days for original RiskParity versus 179 days for BTC10% SuperTrend satellite. This is a meaningful holding-experience improvement because long unrecovered drawdowns are usually more psychologically damaging than a short, sharp dip.

## Magic Parameter Check

For BTC10% satellite, Q9 tested 9 SuperTrend parameter combinations:

- ATR: 7, 10, 14
- Multiplier: 2, 3, 4

The default ATR 10 / multiplier 3 was not the best by either Calmar or Sharpe:

- Default Calmar rank: 4 out of 9
- Default Sharpe rank: 7 out of 9

Best Calmar was ATR 7 / multiplier 2:

- Cumulative return: 529.75%
- Annualized return: 21.07%
- Max drawdown: -12.33%
- Sharpe: 1.78
- Calmar: 1.71

The default still performed well:

- Cumulative return: 512.93%
- Annualized return: 20.73%
- Max drawdown: -12.81%
- Sharpe: 1.73
- Calmar: 1.62

This is a good sign. The result does not depend on exactly ATR 10 / multiplier 3. Nearby and even meaningfully different settings also worked.

However, parameter choice still matters. The spread in days below -10% drawdown ranged from 50 to 145 across the grid. So the signal is not parameter-free; it is just not a one-point magic result.

## Magic Cap Check

Using the default ATR 10 / multiplier 3:

- 5% cap: Calmar 1.41, max drawdown -12.93%
- 7.5% cap: Calmar 1.53, max drawdown -12.75%
- 10% cap: Calmar 1.62, max drawdown -12.81%
- 12.5% cap: Calmar 1.65, max drawdown -13.31%
- 15% cap: Calmar 1.55, max drawdown -15.00%

The 10% cap is not a magic point. The shape is fairly smooth from 5% through 12.5%. But robustness deteriorates as cap rises.

In the combined 45-case cap/parameter grid, pass rates against core robustness gates were:

- 5% cap: 9/9 parameter combinations passed
- 7.5% cap: 8/9 passed
- 10% cap: 5/9 passed
- 12.5% cap: 3/9 passed
- 15% cap: 0/9 passed

This changes the conclusion slightly:

- 10% remains the best balanced historical candidate.
- 5%-7.5% is more robust if the priority is parameter resilience.
- 15% is too BTC-dependent for a robust satellite.

## Rolling-Window Results

BTC10% SuperTrend satellite versus original RiskParity:

- Return win rate: 7/7 windows
- Calmar win rate: 6/7 windows
- Drawdown non-worse rate: 6/7 windows
- Underwater-time non-worse rate: 7/7 windows
- Days-below--10% non-worse rate: 4/7 windows

BTC5% SuperTrend satellite was even more robust:

- Return win rate: 7/7
- Calmar win rate: 7/7
- Drawdown non-worse rate: 6/7
- Underwater-time non-worse rate: 7/7
- Days-below--10% non-worse rate: 7/7

This reinforces the cap interpretation:

- 10% is the better growth/risk balance.
- 5% is the more conservative robustness candidate.

## Cost And Execution Stress

BTC10% SuperTrend satellite remained ahead under conservative assumptions.

At next-open execution with 20 bps one-way cost:

- Original RiskParity cumulative return: 293.17%
- Original RiskParity Calmar: 1.10
- BTC10% SuperTrend cumulative return: 482.42%
- BTC10% SuperTrend Calmar: 1.57

At next-open execution with 50 bps one-way cost:

- Original RiskParity cumulative return: 271.29%
- Original RiskParity Calmar: 0.99
- BTC10% SuperTrend cumulative return: 442.88%
- BTC10% SuperTrend Calmar: 1.49

The candidate is not fragile to reasonable cost and next-open execution assumptions.

## Answer To The Main Question

Does BTC10% SuperTrend satellite improve holding experience?

Yes, mostly.

It improved:

- Annualized return
- Sharpe
- Calmar
- Max drawdown
- Monthly win rate
- Worst month
- Worst year
- Average underwater depth
- Longest underwater stretch
- Average recovery days
- Longest recovery days

It did not improve every metric:

- Days below -10% drawdown rose slightly from 83 to 89
- Average losing month was slightly worse
- Current unresolved drawdown remains present

The honest conclusion is:

BTC10% SuperTrend satellite improves the overall holding experience, but it is not a free lunch. It adds a controlled BTC trend exposure that improves most risk and recovery measures, while leaving some drawdown-severity measures only flat or slightly worse.

## Interpretation

Historical best:

- BTC15% SuperTrend had the highest return among the Q9 main candidates, but it carried more BTC dependence and worse drawdown behavior.

Risk-adjusted best:

- BTC10% SuperTrend satellite by the balanced view of Calmar, recovery, drawdown, and return.

Most structurally balanced:

- BTC10% SuperTrend satellite for growth-oriented research.
- BTC5% SuperTrend satellite for more conservative robustness.

Main sample-period advantage:

- BTC had very strong long-run upside in the sample.
- The SuperTrend filter avoided enough BTC downtrends to make the satellite improve the core portfolio.

Main future failure mode:

- BTC forward returns may be much lower than the historical sample.
- Sideways crypto markets can whipsaw SuperTrend.
- Larger caps make the strategy increasingly dependent on BTC.
- BTC-USD implementation assumptions may not match a real investable product.

## Conclusion

Q9 supports keeping BTC10% SuperTrend satellite as the leading candidate, but with a refined interpretation:

- It is not dependent on the exact ATR 10 / multiplier 3 parameter.
- It is somewhat sensitive to cap size.
- 10% is a good historical balance point, not an untouchable rule.
- 5%-7.5% deserves attention if future research prioritizes robustness over return.

The next research step should not add another asset yet. It should test BTC return haircuts and real implementation constraints.

## What To Test Next

- BTC return haircut scenarios: 25%, 50%, and 75% lower BTC returns
- More conservative slippage and spread assumptions
- Replace BTC-USD with a more realistic investable proxy if available
- Compare 5%, 7.5%, and 10% caps under the same stress tests
- Test whether BTC satellite remains useful when Nasdaq and gold forward returns are reduced
