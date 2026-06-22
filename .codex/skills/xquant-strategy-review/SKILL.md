---
name: xquant-strategy-review
description: Use when researching, backtesting, extending, or comparing xquant-learning trading strategies. Enforces the project review discipline: preserve reference notebooks, create practice notebooks, compare against a baseline, evaluate Q3/Q5 metrics, annual and monthly behavior, drawdowns, parameter sensitivity, and write a concise review note for future study.
---

# XQuant Strategy Review

Use this skill before changing or creating notebooks for xquant strategy research.

## Core Rule

Do not optimize for the prettiest backtest. Optimize for a strategy conclusion that can survive future review.

Every experiment must answer two different questions:

1. What worked best historically?
2. What looks structurally robust enough to keep studying?

These are not always the same answer.

## Workflow

1. **Preserve references**
   - Do not edit course reference notebooks.
   - Create or update a practice notebook in the current project.
   - Keep generated outputs under an experiment-specific folder in `outputs/`.

2. **Start from a baseline**
   - Name one baseline strategy before adding variants.
   - For Q3-style allocation work, default baseline is the current best RiskParity strategy unless the user says otherwise.
   - Keep the same data window, rebalance frequency, and metric definitions across compared strategies.

3. **Separate experiment types**
   - Asset-pool changes, weighting changes, and timing filters are separate hypotheses.
   - Avoid mixing them unless the notebook clearly labels each layer.
   - When a notebook becomes crowded, recommend starting a new practice notebook.

4. **Run Q3 metrics**
   - Cumulative return
   - Annualized return
   - Annualized volatility
   - Max drawdown
   - Sharpe
   - Calmar
   - Current and average weights

5. **Run Q5 checks**
   - Benchmark and Alpha when a meaningful benchmark exists
   - Sortino
   - Annual returns
   - Monthly win rate
   - Average winning month and average losing month
   - Payoff ratio
   - Profit factor
   - Best and worst month
   - Top drawdown events
   - Drawdown summary: max depth, average depth, recovery time
   - Underwater curve

6. **Run sensitivity checks**
   - For RiskParity: volatility window sensitivity.
   - For momentum: lookback window and Top-N sensitivity.
   - For trend filters: moving-average or SuperTrend parameter sensitivity.
   - For capped assets: cap-level sensitivity.
   - Prefer small grids that explain the shape of the result over large grids that invite overfitting.

7. **Interpret honestly**
   - Identify historical winner.
   - Identify risk-adjusted winner.
   - Identify the most structurally balanced candidate.
   - State which result may be sample-period luck.
   - State what future market regime would hurt the strategy.
   - Do not claim a strategy is better only because one metric improved.

8. **Record the work**
   - Write a short note under `docs/notes/`.
   - Include sample period, asset list, strategy variants, key metrics, interpretation, and next research direction.
   - Export CSV tables and charts that support the conclusion.

## Preferred Notebook Structure

Use this order when practical:

1. Setup and data loading
2. Baseline strategy
3. Strategy variants
4. Q3 summary table
5. Q5 summary table
6. Annual returns
7. Monthly distribution
8. Drawdown events and underwater curve
9. Parameter sensitivity
10. Plain-language conclusion

## Conclusion Template

End each research pass with concise answers:

- Historical best:
- Risk-adjusted best:
- Most structurally balanced:
- Main sample-period advantage:
- Main future failure mode:
- What to test next:

## XQuant Lessons Learned

From the Q3 RiskParity review:

- Strong historical results can come from selecting assets that happened to be excellent in the sample.
- RiskParity is a weighting method, not a return engine.
- A low-return asset may still reduce concentration risk, but it can also drag performance.
- Adding a high-volatility asset like BTC is not automatically useful; position sizing and regime filters matter.
- A more diversified structure can be preferable for future research even when it is not the historical winner.

