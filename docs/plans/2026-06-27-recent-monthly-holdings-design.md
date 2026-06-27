# Recent Monthly Holdings and Theme Alpha Comparison Design

## Goal

Add a reader-friendly six-month performance view with month-end holdings for both dashboard strategies, while reducing Theme Alpha comparison overload without deleting research evidence.

## Recent Monthly View

Add a third tab to the existing monthly statistics panel:

- `体验概览`
- `汇总表`
- `近期 6 个月`

The recent tab shows only the default paper-tracking candidate:

- BTC: `BTC7.5%ST卫星`
- Theme Alpha: `Def200_Cash / BIMONTHLY`

Each month includes:

- Calendar month.
- Monthly return.
- Month-end trading date.
- Month-end executed holdings.
- A partial-period label for the current incomplete month, such as `截至 6/26`.

Only non-zero holdings are displayed. Holdings are executed backtest weights, not raw target weights, so they match the strategy's execution timing and trade constraints.

## Research Output Contract

Each strategy practice notebook exports a compact recent-month tracking CSV under its aligned output directory.

Required columns:

- `strategy`
- `month`
- `month_end_date`
- `is_partial`
- `return`
- One column per asset plus cash.

The CSV keeps the most recent six calendar months, including the current partial month. The dashboard builder normalizes these files into a generic `RecentMonthlyRecord` structure.

## Theme Alpha Comparison Hierarchy

Theme Alpha's primary reader view contains three candidates:

- `Original_RiskParity_3Asset`: internal core baseline.
- `Core80_LVT20_Def200_Cash`: current paper-tracking strategy.
- `Expanded_LVT_100`: thematic risk boundary.

Research-only candidates move to a secondary `研究候选` tab:

- `Core60_LVT40_Def200_Cash`
- `Core80_LVT20_STEntry_Def200_Cash`
- `Core80_LVT20_STHalf_Def200_Cash`

No candidate data is deleted. The hierarchy applies consistently to:

- Candidate metrics.
- Annual returns.
- Monthly statistics.

The recent six-month tab remains focused on the single default paper candidate, because its purpose is operational tracking rather than parameter comparison.

## Dashboard Data Model

The strategy report package gains:

- `primaryCandidateIds`
- `researchCandidateIds`

The chart package gains:

- `recentMonthlyRecords`

BTC may mark all existing comparison candidates as primary because its four-row comparison is still readable. Theme Alpha uses the three-plus-three split above.

The dashboard writes recent monthly records to a separate static JSON file so existing split-package loading remains lightweight.

## UI Behavior

### Monthly statistics

The recent tab uses one row per month. Each row shows the return prominently and a compact holdings grid below it. Positive and negative returns use the dashboard's existing restrained green and red treatments.

On narrow screens, holdings wrap into a single-column list. Wide historical tables retain container-level horizontal scrolling.

### Candidate and annual comparison

Theme Alpha comparison panels receive two tabs:

- `核心对比`
- `研究候选`

The initial view always opens on `核心对比`. BTC does not show the extra tab unless research-only candidates exist.

## Empty and Error Handling

- If recent monthly data is absent, the tab shows a concise unavailable state instead of an empty table.
- If no research-only candidates exist, comparison tabs are omitted.
- Invalid or zero-only holdings remain excluded from the display but still participate in builder validation.

## Testing

- Notebook-output contract tests verify six rows, chronological order, a single partial month, valid month-end dates, and holdings summing to one.
- Builder tests verify candidate grouping and recent-month normalization for both strategies.
- UI tests verify tab switching, partial-month labels, month-end holdings, and Theme Alpha primary/research separation.
- Full validation uses `make dashboard-check` plus the relevant Python integration tests.
