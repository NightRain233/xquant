# Theme Alpha Dashboard Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Theme Alpha / Core80 LVT20 Def200 Cash as the second static strategy package and make the existing dashboard support multiple strategies.

**Architecture:** The dashboard remains a Vite/React static app. Data builders normalize research CSV outputs into strategy JSON packages plus a strategy catalog, while the UI loads the catalog first and then renders a selected package with shared report and paper-tracking components.

**Tech Stack:** React 18, TypeScript, Vite, Tailwind CSS, ECharts, Papa Parse, Vitest, Testing Library.

---

### Task 1: Data Model Tests

**Files:**
- Modify: `dashboard/scripts/build-data.test.ts`

**Steps:**
1. Add a failing test for `buildThemeAlphaStrategyPackage(repoRoot)`.
2. Assert the package id, display name, as-of date, preferred paper candidate, target weights, liquidity evidence, and source files.
3. Add a failing test for writing both strategies plus `strategies/index.json`.
4. Run `npm test -- scripts/build-data.test.ts` from `dashboard/` and confirm the new tests fail because the functions do not exist.

### Task 2: UI Tests

**Files:**
- Modify: `dashboard/src/App.test.tsx`

**Steps:**
1. Mock fetch for the catalog, BTC package, and Theme Alpha package.
2. Assert the initial strategy hub renders both strategies.
3. Click Theme Alpha and assert the shell renders the Theme Alpha strategy detail.
4. Run `npm test -- src/App.test.tsx` and confirm failure before implementation.

### Task 3: Shared Data Types

**Files:**
- Modify: `dashboard/src/data/types.ts`

**Steps:**
1. Add catalog, highlight, generic signal, and evidence panel types.
2. Keep legacy BTC fields compatible enough for builder tests to compile.
3. Make the strategy package support optional generic evidence arrays.

### Task 4: Shared Builder Helpers

**Files:**
- Modify: `dashboard/scripts/build-data.ts`

**Steps:**
1. Keep existing BTC builder behavior.
2. Extract CSV parsing, numeric parsing, keyed values, time-series normalization, annual return calculation, and monthly stats calculation into reusable helpers.
3. Add helpers for row filtering and metric normalization from Q8/Q12 CSVs.

### Task 5: Theme Alpha Builder

**Files:**
- Modify: `dashboard/scripts/build-data.ts`

**Steps:**
1. Add `buildThemeAlphaStrategyPackage(repoRoot)`.
2. Build candidate metrics from Q12 real ETF full-sample rows.
3. Build NAV and underwater series from Q8 selected 2021-to-date CSVs.
4. Build annual returns and monthly stats from Q12 real ETF rows.
5. Build target weights from Q8 `latest_target_weights.csv`, focused on `BIMONTHLY`.
6. Build stress/evidence panels from Q8 schedule, friction, and liquidity CSVs.
7. Add Theme Alpha paper rules and risk notes from the Q8/Q12 reviews.

### Task 6: Strategy Catalog Writer

**Files:**
- Modify: `dashboard/scripts/build-data.ts`

**Steps:**
1. Add `buildStrategyCatalog(strategies)`.
2. Add `writeAllStrategyPackages(repoRoot, outputRoot)`.
3. Update `main()` to write BTC, Theme Alpha, and `index.json`.
4. Run the build-data tests until green.

### Task 7: Multi-Strategy UI

**Files:**
- Modify: `dashboard/src/data/useStrategyData.ts`
- Modify: `dashboard/src/App.tsx`
- Create: `dashboard/src/components/StrategyHub.tsx`
- Modify: `dashboard/src/components/AppShell.tsx`

**Steps:**
1. Add a catalog loader hook or load state in `App`.
2. Render a strategy hub when no strategy is selected.
3. Add strategy switching in the left rail.
4. Keep loading and error states consistent with the existing dashboard.

### Task 8: Generic Panels

**Files:**
- Modify: `dashboard/src/components/MetricCardGrid.tsx`
- Modify: `dashboard/src/components/DecisionStrip.tsx`
- Modify: `dashboard/src/components/LatestSignalPanel.tsx`
- Modify: `dashboard/src/components/StressSummaryPanel.tsx`
- Modify: `dashboard/src/components/CandidateTable.tsx`

**Steps:**
1. Render highlight cards from data when provided.
2. Render latest signal rows from generic signal data, falling back to BTC fields.
3. Render stress/evidence rows generically.
4. Add optional candidate table columns for turnover and cash where present.

### Task 9: Verification

**Files:**
- Generated: `dashboard/public/data/strategies/index.json`
- Generated: `dashboard/public/data/strategies/theme-alpha-core80-lvt20-def200-cash/strategy.json`

**Steps:**
1. Run `npm run build:data`.
2. Run `npm test`.
3. Run `npm run build`.
4. Start the dev server and inspect the multi-strategy UI in browser on desktop and mobile widths.
