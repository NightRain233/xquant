# Paper Tracking Refresh and Sleeve Attribution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refresh both paper-tracking strategies through 2026-06-26 and show an auditable Theme Alpha LVT20 sleeve breakdown.

**Architecture:** The Q8 practice notebook exports explicit sleeve and snapshot CSVs alongside aggregate targets. The TypeScript builder normalizes those files into the static paper package, and the existing target-weight panel renders an optional sleeve-attribution table.

**Tech Stack:** Python, Jupyter, pandas, yfinance, React 18, TypeScript, Vitest, Testing Library.

---

### Task 1: Add failing builder contract tests

**Files:**
- Modify: `dashboard/scripts/build-data.test.ts`

**Steps:**
1. Assert Theme Alpha `asOfDate` and latest signal rows use the refreshed market-data, signal, and execution dates.
2. Assert the LVT sleeve allocation is `0.20`, its internal weights sum to `1.0`, and its portfolio contributions sum to `0.20`.
3. Run `cd dashboard && npm test -- --run scripts/build-data.test.ts`.
4. Confirm failure because the snapshot and sleeve contracts do not exist.

### Task 2: Add failing component tests

**Files:**
- Create: `dashboard/src/components/TargetWeightsPanel.test.tsx`

**Steps:**
1. Render aggregate rows plus an LVT sleeve fixture.
2. Assert the LVT heading, overlap explanation, internal percentages, and portfolio contributions.
3. Run `cd dashboard && npm test -- --run src/components/TargetWeightsPanel.test.tsx`.
4. Confirm failure because the component does not accept sleeve data.

### Task 3: Export explicit Theme Alpha paper data

**Files:**
- Modify: `research/notebooks/theme-alpha-q8-signal-live-readiness-practice.ipynb`
- Generate: `outputs/theme-alpha-q8-signal-live-readiness/latest_sleeve_weights.csv`
- Generate: `outputs/theme-alpha-q8-signal-live-readiness/paper_tracking_snapshot.csv`

**Steps:**
1. Retain Core and LVT signal-weight frames while building aggregate candidates.
2. Export internal sleeve weights and allocation for each candidate and schedule.
3. Export the latest market-data date, BIMONTHLY signal date, and next-trading-day execution date.
4. Execute the notebook to a temporary notebook file so source outputs refresh without rewriting stored cell outputs.
5. Verify the Theme Alpha market date is 2026-06-26, signal date is 2026-06-25, and execution date is 2026-06-26.

### Task 4: Refresh BTC paper data

**Files:**
- Generate: `outputs/q10-live-readiness-stress/*.csv`

**Steps:**
1. Execute the Q10 notebook to a temporary notebook file.
2. Verify `latest_signal_summary.csv` reports 2026-06-26.
3. Verify refreshed BTC target weights sum to 100% for every candidate.

### Task 5: Extend dashboard types and builder

**Files:**
- Modify: `dashboard/src/data/types.ts`
- Modify: `dashboard/scripts/build-data.ts`

**Steps:**
1. Add a generic target-weight sleeve type with candidate, sleeve name, allocation, and internal weights.
2. Add optional sleeve data to `StrategyPaperData`.
3. Add the two new Q8 CSVs to the Theme Alpha source list.
4. Normalize snapshot dates and sleeve rows.
5. Use the paper market-data date for the strategy package `asOfDate`.
6. Add market-data, signal, and execution rows to the latest signal panel.
7. Run the builder test and confirm it passes.

### Task 6: Render the sleeve attribution

**Files:**
- Modify: `dashboard/src/components/TargetWeightsPanel.tsx`
- Modify: `dashboard/src/pages/PaperTrackingPage.tsx`

**Steps:**
1. Pass optional sleeve rows from the paper page.
2. Render non-zero LVT assets with internal and whole-portfolio percentages.
3. Render the overlap explanation.
4. Run the component test and confirm it passes.

### Task 7: Rebuild and verify

**Files:**
- Generate: `dashboard/public/data/strategies/**`

**Steps:**
1. Run `make dashboard-check`.
2. Run the relevant Python tests with `uv run pytest tests/test_portfolio.py tests/test_theme_alpha_script_integration.py`.
3. Inspect generated Theme Alpha and BTC strategy and paper JSON dates and weight totals.
4. Review `git diff` to ensure existing staged user changes remain intact.
