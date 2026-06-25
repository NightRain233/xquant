# Theme Alpha Dashboard Integration Design

## Goal

Extend the existing static dashboard into a multi-strategy research cockpit and add Theme Alpha / Core80 LVT20 Def200 Cash as the second strategy package.

## Scope

- Keep the current `dashboard/` app.
- Keep a static data model under `dashboard/public/data/strategies/`.
- Do not add backend services, live market refresh, or automatic trading hooks.
- Preserve the current dashboard visual language: dense, operational, and research-oriented.

## Information Architecture

The app should support:

- A strategy catalog at `public/data/strategies/index.json`.
- One static package per strategy at `public/data/strategies/<strategy-id>/strategy.json`.
- A compact multi-strategy entry view when no strategy is selected.
- The current two-mode detail view for a selected strategy:
  - Research report.
  - Paper tracking.

The left rail remains the persistent navigation surface. It should include the XQuant label, the current strategy, strategy switching, mode tabs, and the package as-of date.

## Theme Alpha Strategy Package

Strategy id:

`theme-alpha-core80-lvt20-def200-cash`

Display name:

`Theme Alpha / Core80 LVT20 Def200 Cash`

The default evidence should use the Q8 near-live assumptions:

- `Def200_Cash`
- `BIMONTHLY`
- `next_close`
- `base20_plus_asset`

Q12 should be used as robustness evidence and risk review context, not as a directly tradable proxy result.

Primary source files:

- `docs/notes/theme-alpha-q8-signal-live-readiness-review.md`
- `docs/notes/theme-alpha-q12-long-sample-proxy-validation-review.md`
- `outputs/theme-alpha-q8-signal-live-readiness/*.csv`
- `outputs/theme-alpha-q12-long-sample-proxy-validation/*.csv`

## Data Model Direction

Keep the existing `StrategyPackage` surface but make BTC-specific fields optional or data-driven:

- Add a strategy catalog type.
- Add data-driven highlight cards.
- Add a generic latest signal panel model.
- Add optional evidence panels for schedule, liquidity, and robustness notes.
- Keep candidate metrics, NAV series, underwater series, annual returns, monthly stats, target weights, rules, and risk notes reusable.

BTC should continue to render from the same package after the model is generalized.

## Component Reuse

Reusable with little change:

- Metric cards.
- Candidate table.
- NAV chart.
- Underwater chart.
- Annual returns.
- Monthly stats.
- Target weights.
- Paper rules.
- Risk review.

Needs generalization:

- Decision strip.
- Latest signal panel.
- Stress summary panel.

Needs Theme Alpha evidence support:

- Schedule comparison.
- Liquidity participation.
- Def200 Cash defense explanation.
- LVT satellite and long-sample robustness evidence.

## Testing Strategy

- Data builder tests should cover both BTC and Theme Alpha packages.
- UI tests should cover the strategy catalog, multi-strategy entry, and selecting Theme Alpha.
- Existing BTC assertions should continue to pass.
- Full verification should run `npm run build:data`, `npm test`, and `npm run build` from `dashboard/`.
