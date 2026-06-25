# Strategy Dashboard Design

Date: 2026-06-25

## Goal

Build a local research dashboard for xquant strategy results. The first release focuses on the BTC SuperTrend satellite strategy, while the architecture must support adding Theme Alpha later without rebuilding the app.

The dashboard has two jobs:

1. Help the researcher decide whether a strategy is ready for paper tracking or live capital.
2. Explain the research result clearly enough that another person can understand the recommendation, evidence, and risks.

## Product Positioning

This is not a marketing page and not a notebook replacement. It is a research decision cockpit.

The page should answer these questions quickly:

- What is the current recommendation?
- Which candidate should be tracked first?
- Which candidate is historically strongest but psychologically or structurally riskier?
- What evidence supports the recommendation?
- What can break the strategy in the future?
- What should be checked at the next paper-trading review?

## First Strategy Scope

The first release uses BTC SuperTrend satellite research, especially the Q10 live-readiness outputs.

Primary source files:

- `docs/notes/q10-live-readiness-stress-review.md`
- `outputs/q10-live-readiness-stress/research_summary.csv`
- `outputs/q10-live-readiness-stress/base_candidate_metrics.csv`
- `outputs/q10-live-readiness-stress/base_candidate_nav.csv`
- `outputs/q10-live-readiness-stress/base_candidate_underwater.csv`
- `outputs/q10-live-readiness-stress/implementation_stress_summary.csv`
- `outputs/q10-live-readiness-stress/btc_return_haircut_stress.csv`
- `outputs/q10-live-readiness-stress/core_return_haircut_stress.csv`
- `outputs/q10-live-readiness-stress/latest_signal_summary.csv`
- `outputs/q10-live-readiness-stress/latest_target_weights.csv`
- `outputs/q10-live-readiness-stress/paper_trading_rule_draft.csv`

Supplemental historical files:

- `docs/notes/q8-btc-trend-satellite-review.md`
- `outputs/q8-btc-trend-satellite/q3_metrics.csv`
- `outputs/q8-btc-trend-satellite/q5_metrics.csv`
- `outputs/q8-btc-trend-satellite/nav_all_strategies.csv`
- `outputs/q8-btc-trend-satellite/underwater_curves.csv`
- `outputs/q8-btc-trend-satellite/decision_scorecard.csv`

## Recommendation Narrative

The first release should state the conclusion plainly:

- Paper tracking: recommended.
- Immediate live trading: not recommended before paper tracking.
- Preferred paper candidates: BTC 5% and BTC 7.5% SuperTrend satellite.
- Growth observation candidate: BTC 10% SuperTrend satellite.
- Current BTC signal as of 2026-06-23: off, so the BTC sleeve is held as cash.

The page must avoid presenting BTC 10% as the default simply because it has the best historical return. The important distinction is:

- BTC 10% is the historical and risk-adjusted winner.
- BTC 5% and 7.5% are better first paper-tracking candidates because they reduce BTC dependence and are easier to execute psychologically.
- The whole structure still needs BTC to provide some future trend return. If BTC has no future trend contribution, the satellite is not worth adding.

## Information Architecture

### 1. Overview

Purpose: give the user the answer before the charts.

Content:

- Current recommendation badge.
- Live-trading status badge.
- Preferred paper caps.
- Growth candidate cap.
- Latest BTC signal.
- One concise recommendation paragraph.

### 2. Research Report Mode

Purpose: explain the evidence and conclusion.

Sections:

- Strategy logic: original three-asset RiskParity core plus limited BTC trend satellite.
- Candidate comparison: original RP, BTC5%, BTC7.5%, BTC10%.
- Historical metrics: annual return, volatility, max drawdown, Sharpe, Calmar, longest underwater days, days below -10%.
- NAV and underwater charts.
- Stress tests: implementation friction, BTC return haircut, core return haircut.
- Recommendation reasoning and future failure modes.

### 3. Paper Tracking Mode

Purpose: support near-live review.

Sections:

- Latest signal panel.
- Target weights table.
- Paper-trading rules.
- Execution assumptions.
- Pause and review conditions.
- Candidate watchlist.

### 4. Strategy Comparison Mode

Purpose: prepare for adding Theme Alpha later.

First release:

- Show only `btc-supertrend-satellite`.
- Keep the strategy selector visible but with one enabled option.

Future release:

- Add `theme-alpha-core-lvt`.
- Compare BTC satellite and Theme Alpha at the portfolio-decision level.

### 5. Risk Review Mode

Purpose: keep the conclusion honest.

Risks:

- BTC has no future positive trend return.
- BTC signal whipsaws in high volatility.
- Core RiskParity assets enter a weak or highly correlated regime.
- Actual BTC execution instrument differs from backtest assumptions.
- Transaction costs, slippage, premium/discount, tax, and trading-hour mismatch reduce realized return.

## Visual Design Direction

The interface should feel like a quiet institutional research cockpit:

- Dense enough for repeated review.
- Clear enough for a non-quant reader.
- No marketing hero.
- No decorative gradients or generic finance imagery.
- Use restrained contrast, compact metric cards, clear tables, and chart-first evidence.

Suggested layout:

- Left sidebar for strategy and mode navigation.
- Top decision strip for recommendation status.
- Main content grid with charts and analysis panels.
- Right-side or lower review panel for current signal and target weights on desktop.
- Single-column stack on mobile.

## Architecture

Use one React app in `dashboard/`.

Recommended structure:

```text
dashboard/
  package.json
  index.html
  src/
    App.tsx
    main.tsx
    data/
      types.ts
      strategyRegistry.ts
    components/
    pages/
    styles/
  scripts/
    build-data.ts
  public/
    data/
      strategies/
        btc-supertrend-satellite/
          strategy.json
```

Data flow:

```text
outputs/ + docs/notes/
        -> dashboard/scripts/build-data.ts
        -> dashboard/public/data/strategies/*/strategy.json
        -> React components
```

The frontend should not read arbitrary CSV files directly. It should load normalized strategy JSON. This keeps the UI stable when raw research files evolve.

## Data Model

Each strategy package should contain:

- `id`
- `name`
- `status`
- `recommendation`
- `asOfDate`
- `candidateMetrics`
- `navSeries`
- `underwaterSeries`
- `stressSummaries`
- `latestSignal`
- `targetWeights`
- `paperTradingRules`
- `riskNotes`
- `sourceFiles`

BTC-specific fields can exist under `strategySpecific`, but shared components should use generic fields when possible.

## Testing And Verification

Minimum first-release checks:

- Data builder reads source CSV files and writes valid strategy JSON.
- Strategy JSON includes all required top-level fields.
- React renders the dashboard with generated data.
- Metric cards format percentages and ratios correctly.
- Charts render non-empty series.
- Layout works at desktop and mobile widths.

Manual visual QA:

- Run local dev server.
- Open the app in browser.
- Check desktop and mobile screenshots.
- Confirm no text overlaps, charts are visible, and target weights are readable.

## Future Theme Alpha Integration

Theme Alpha should be added as a second strategy package, not a second app.

Likely source files:

- `docs/notes/theme-alpha-q8-signal-live-readiness-review.md`
- `docs/notes/theme-alpha-q12-long-sample-proxy-validation-review.md`
- `outputs/theme-alpha-q8-signal-live-readiness/summary_all_windows.csv`
- `outputs/theme-alpha-q8-signal-live-readiness/latest_target_weights.csv`
- `outputs/theme-alpha-q8-signal-live-readiness/liquidity_participation_summary.csv`
- `outputs/theme-alpha-q12-long-sample-proxy-validation/summary_all_layers.csv`

The dashboard should later support a portfolio-level homepage that lists all paper-tracking candidates across BTC satellite and Theme Alpha.

