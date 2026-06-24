# Theme Alpha Q7 Production Realism Review

Date: 2026-06-23

## Purpose

Q7 tests whether the shortlisted Theme Alpha candidates survive practical implementation assumptions.

The practice notebook is:

- `theme-alpha-q7-production-realism-practice.ipynb`

Generated outputs are under:

- `outputs/theme-alpha-q7-production-realism/`

## Candidates

From Q6, Q7 carries forward:

- Base Core80 / Expanded LVT20
- Def200 Cash
- Def120 Cash
- Def210 Gold

## Tests

Q7 tests:

- 10-trading-day rebalance versus monthly rebalance
- 0, 10, 20, and 30 bps one-way transaction costs
- 0%, 2%, and 5% minimum rebalance thresholds
- unlimited, 10%, 15%, and 20% max single-period ETF trade limits

The practical default stress setting is:

- 20 bps one-way cost
- 2% minimum rebalance threshold
- 15% max single-period ETF trade per asset

## Practical Default Results

### 2021-To-Date

| Candidate | Freq | Return | Max DD | Sharpe | Days Below -10% | Ann Turnover |
|---|---:|---:|---:|---:|---:|---:|
| Base Core80 / LVT20 | 10D | 119.24% | -11.86% | 1.35 | 29 | 2.85 |
| Base Core80 / LVT20 | Monthly | 105.57% | -16.92% | 1.22 | 225 | 2.07 |
| Def200 Cash | 10D | 107.43% | -11.44% | 1.43 | 1 | 3.47 |
| Def200 Cash | Monthly | 101.53% | -10.61% | 1.33 | 2 | 2.46 |
| Def120 Cash | 10D | 92.76% | -9.85% | 1.32 | 0 | 4.04 |
| Def120 Cash | Monthly | 77.90% | -12.99% | 1.15 | 188 | 2.94 |
| Def210 Gold | 10D | 136.93% | -11.77% | 1.52 | 1 | 3.11 |
| Def210 Gold | Monthly | 117.50% | -10.61% | 1.36 | 2 | 2.12 |

Interpretation:

- 10D rebalance is materially better than monthly for the base and Def120 Cash.
- Monthly rebalance reduces turnover, but can badly worsen underwater behavior.
- Def210 Gold has the best long-window return and Sharpe under practical assumptions.
- Def200 Cash is the best cash-defense compromise.
- Def120 Cash controls drawdown, but gives up too much return and has high turnover.

### 2022 Full Year

| Candidate | Freq | Return | Max DD | Sharpe | Days Below -10% | Ann Turnover |
|---|---:|---:|---:|---:|---:|---:|
| Base Core80 / LVT20 | 10D | -4.76% | -9.82% | -0.43 | 0 | 2.81 |
| Base Core80 / LVT20 | Monthly | -9.79% | -12.96% | -0.91 | 37 | 2.28 |
| Def200 Cash | 10D | 3.40% | -4.01% | 0.53 | 0 | 2.72 |
| Def200 Cash | Monthly | -0.92% | -4.29% | -0.15 | 0 | 2.10 |
| Def120 Cash | 10D | 0.74% | -5.13% | 0.11 | 0 | 3.95 |
| Def120 Cash | Monthly | -3.38% | -6.14% | -0.51 | 0 | 2.88 |
| Def210 Gold | 10D | 7.14% | -6.74% | 0.68 | 0 | 2.26 |
| Def210 Gold | Monthly | 3.03% | -8.28% | 0.30 | 0 | 1.50 |

Interpretation:

- 10D rebalance matters in stress periods.
- Def200 Cash remains a strong real-world candidate after costs and execution limits.
- Def210 Gold has the best 2022 return, but it is not true cash defense.
- The base strategy survives 2022 but is weaker than the defensive variants.

## Cost Sensitivity

Under 10D rebalance, no threshold, unlimited single-period trades:

| Candidate | Cost | 2021-To-Date Return | Max DD | Sharpe | Ann Turnover |
|---|---:|---:|---:|---:|---:|
| Base Core80 / LVT20 | 0 bps | 126.67% | -11.71% | 1.41 | 2.89 |
| Base Core80 / LVT20 | 20 bps | 119.89% | -11.86% | 1.36 | 2.89 |
| Def200 Cash | 0 bps | 115.88% | -10.46% | 1.52 | 3.71 |
| Def200 Cash | 20 bps | 107.64% | -10.57% | 1.44 | 3.71 |
| Def120 Cash | 0 bps | 105.39% | -9.21% | 1.46 | 4.52 |
| Def120 Cash | 20 bps | 95.86% | -9.33% | 1.36 | 4.52 |
| Def210 Gold | 0 bps | 142.32% | -11.71% | 1.55 | 3.32 |
| Def210 Gold | 20 bps | 134.02% | -11.77% | 1.49 | 3.32 |

Interpretation:

- All candidates survive 20 bps cost.
- Def120 Cash is the most cost-sensitive because it has the highest turnover.
- Def210 Gold remains strongest on return after cost.
- Def200 Cash remains strongest among true cash-defense candidates.

## Rebalance Frequency

At 20 bps cost, no threshold, unlimited trades:

| Candidate | 10D Return | Monthly Return | 10D Max DD | Monthly Max DD |
|---|---:|---:|---:|---:|
| Base Core80 / LVT20 | 119.89% | 107.90% | -11.86% | -17.23% |
| Def200 Cash | 107.64% | 86.66% | -10.57% | -10.61% |
| Def120 Cash | 95.86% | 73.78% | -9.33% | -15.22% |
| Def210 Gold | 134.02% | 108.39% | -11.77% | -10.61% |

Interpretation:

- Monthly rebalance is not a free simplification.
- It reduces turnover, but often gives up too much return.
- The base strategy and Def120 Cash are especially hurt by monthly rebalance.
- Def200 Cash and Def210 Gold are more monthly-tolerant, but still weaker than 10D.

## Execution Constraints

At 20 bps cost and 10D rebalance:

- 2% minimum rebalance threshold barely changes results.
- 15% max single-period ETF trade generally does not break the strategies.
- 10% max single-period ETF trade can slightly improve some results by slowing aggressive reallocations, but this may be sample luck.
- 5% threshold is not consistently helpful.

This means the candidate strategies do not appear to rely on unrealistic all-at-once trading.

## Current Ranking

Best practical return candidate:

- Def210 Gold, 10D

Best true cash-defense candidate:

- Def200 Cash, 10D

Best max-drawdown control:

- Def120 Cash, 10D

Best simple base strategy:

- Base Core80 / Expanded LVT20, 10D

Most fragile practical variant:

- Def120 Cash monthly

## Honest Interpretation

Q7 supports the Theme Alpha framework under realistic friction.

The key finding is not that every variant works. The key finding is that the main candidates still make sense after adding:

- 20 bps one-way cost;
- 2% minimum rebalance threshold;
- 15% max single-period ETF trade.

However, Q7 also shows that the strategy is timing-sensitive. Monthly rebalance is often too slow, especially in bear/stress windows. The current strategy wants a roughly biweekly rhythm.

## Conclusion

The most practical current candidate is:

- Core80 / Expanded LVT20 Def200 Cash, 10D rebalance

Why:

- It is a real cash-defense rule.
- It survives 20 bps cost.
- It survives 15% max single-period trade limits.
- It improves 2022 drawdown materially.
- It does not sacrifice as much return as Def120 Cash.

The strongest return candidate is:

- Core80 / Expanded LVT20 Def210 Gold, 10D rebalance

But it should be treated as more aggressive because it redirects risk into gold rather than reducing risk into cash.

The clean fallback remains:

- Core80 / Expanded LVT20, 10D rebalance

## Next Research Direction

Theme Alpha Q8 should test signal stability and live-readiness:

- Whether 10D rebalance can be replaced by twice-monthly fixed calendar dates.
- Whether defense signals should use close data and trade next day.
- Whether ETF liquidity, spread, and premium/discount assumptions change conclusions.
- Whether a portfolio-level kill switch is needed when all major sleeves are below trend.
