# Strategy Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Vite React dashboard under `dashboard/` that presents the BTC SuperTrend satellite strategy and leaves a clean data path for adding Theme Alpha later.

**Architecture:** Generate normalized strategy JSON from existing research CSV files, then render a static local React app from that JSON. Keep strategy-specific data in `public/data/strategies/<strategy-id>/strategy.json` and keep UI components generic enough for a second strategy package.

**Tech Stack:** Vite, React, TypeScript, ECharts, Tailwind CSS, PapaParse, Vitest, React Testing Library, Playwright.

---

### Task 1: Scaffold Dashboard App

**Files:**
- Create: `dashboard/package.json`
- Create: `dashboard/index.html`
- Create: `dashboard/tsconfig.json`
- Create: `dashboard/tsconfig.node.json`
- Create: `dashboard/vite.config.ts`
- Create: `dashboard/postcss.config.js`
- Create: `dashboard/tailwind.config.ts`
- Create: `dashboard/src/main.tsx`
- Create: `dashboard/src/App.tsx`
- Create: `dashboard/src/styles/global.css`
- Create: `dashboard/src/vite-env.d.ts`

**Step 1: Create the Vite React TypeScript app files**

Create the app manually or with Vite, then keep only the minimal files needed for a single dashboard.

**Step 2: Install dependencies**

Run:

```bash
cd dashboard
npm install
npm install echarts echarts-for-react papaparse lucide-react
npm install -D vite typescript react react-dom @vitejs/plugin-react tailwindcss postcss autoprefixer vitest @testing-library/react @testing-library/jest-dom jsdom playwright @types/react @types/react-dom @types/papaparse
```

Expected: `package-lock.json` is created and install completes without errors.

**Step 3: Add placeholder app**

Implement a minimal shell that renders:

```tsx
export default function App() {
  return <div>XQuant Strategy Dashboard</div>;
}
```

**Step 4: Verify**

Run:

```bash
cd dashboard
npm run build
```

Expected: TypeScript and Vite build pass.

**Step 5: Commit**

```bash
git add dashboard .gitignore docs/plans/2026-06-25-strategy-dashboard-design.md docs/plans/2026-06-25-strategy-dashboard-implementation.md
git commit -m "feat: scaffold strategy dashboard"
```

### Task 2: Define Strategy Data Contract

**Files:**
- Create: `dashboard/src/data/types.ts`
- Create: `dashboard/src/data/formatters.ts`
- Create: `dashboard/src/data/formatters.test.ts`

**Step 1: Write formatter tests**

Test percentage, ratio, integer, and date display helpers.

Example:

```ts
import { describe, expect, it } from "vitest";
import { formatPercent, formatRatio } from "./formatters";

describe("formatters", () => {
  it("formats decimal percentages", () => {
    expect(formatPercent(0.1570815707)).toBe("15.71%");
  });

  it("formats ratios", () => {
    expect(formatRatio(1.35607555)).toBe("1.36");
  });
});
```

**Step 2: Run tests and verify failure**

Run:

```bash
cd dashboard
npm test -- --run
```

Expected: FAIL because `formatters.ts` is not implemented.

**Step 3: Implement data types and formatters**

Define:

- `StrategyPackage`
- `StrategyStatus`
- `CandidateMetric`
- `TimeSeriesPoint`
- `StressSummary`
- `LatestSignal`
- `TargetWeightRow`
- `PaperTradingRule`
- `RiskNote`

Implement simple display helpers in `formatters.ts`.

**Step 4: Verify**

Run:

```bash
cd dashboard
npm test -- --run
```

Expected: formatter tests pass.

**Step 5: Commit**

```bash
git add dashboard/src/data
git commit -m "feat: define dashboard data contract"
```

### Task 3: Build BTC Strategy Data

**Files:**
- Create: `dashboard/scripts/build-data.ts`
- Create: `dashboard/scripts/build-data.test.ts`
- Create: `dashboard/public/data/strategies/btc-supertrend-satellite/strategy.json`
- Modify: `dashboard/package.json`

**Step 1: Write data builder tests**

Test that the builder can parse sample rows and produce:

- `id = "btc-supertrend-satellite"`
- recommendation status is paper tracking recommended and live trading not recommended
- four candidate metric rows
- latest BTC signal is off
- target weights for 5%, 7.5%, and 10%

**Step 2: Run tests and verify failure**

Run:

```bash
cd dashboard
npm test -- --run
```

Expected: FAIL because the data builder is not implemented.

**Step 3: Implement data builder**

Read these files from the repository root:

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

Write:

- `dashboard/public/data/strategies/btc-supertrend-satellite/strategy.json`

Add script:

```json
"build:data": "tsx scripts/build-data.ts"
```

If `tsx` is used, add it as a dev dependency. If not, compile the script with TypeScript before running.

**Step 4: Verify**

Run:

```bash
cd dashboard
npm run build:data
npm test -- --run
```

Expected: strategy JSON is generated and tests pass.

**Step 5: Commit**

```bash
git add dashboard/package.json dashboard/package-lock.json dashboard/scripts dashboard/public/data
git commit -m "feat: generate BTC strategy dashboard data"
```

### Task 4: Render Dashboard Shell And Navigation

**Files:**
- Create: `dashboard/src/data/useStrategyData.ts`
- Create: `dashboard/src/components/AppShell.tsx`
- Create: `dashboard/src/components/ModeTabs.tsx`
- Create: `dashboard/src/components/DecisionStrip.tsx`
- Modify: `dashboard/src/App.tsx`
- Create: `dashboard/src/App.test.tsx`

**Step 1: Write render test**

Test that the app renders:

- `BTC SuperTrend Satellite`
- `Paper tracking recommended`
- `Live trading not yet`
- mode tabs for report and paper tracking

**Step 2: Run test and verify failure**

Run:

```bash
cd dashboard
npm test -- --run
```

Expected: FAIL because components are not implemented.

**Step 3: Implement shell**

Load `/data/strategies/btc-supertrend-satellite/strategy.json` and render a responsive dashboard shell with a left navigation/sidebar on desktop and compact top navigation on mobile.

**Step 4: Verify**

Run:

```bash
cd dashboard
npm test -- --run
npm run build
```

Expected: tests and build pass.

**Step 5: Commit**

```bash
git add dashboard/src
git commit -m "feat: render strategy dashboard shell"
```

### Task 5: Build Report Mode

**Files:**
- Create: `dashboard/src/pages/ResearchReportPage.tsx`
- Create: `dashboard/src/components/MetricCardGrid.tsx`
- Create: `dashboard/src/components/CandidateTable.tsx`
- Create: `dashboard/src/components/NavChart.tsx`
- Create: `dashboard/src/components/UnderwaterChart.tsx`
- Create: `dashboard/src/components/StressSummaryPanel.tsx`
- Modify: `dashboard/src/App.tsx`

**Step 1: Write component tests**

Test that candidate names, annual return, max drawdown, Sharpe, Calmar, and implementation pass rate render correctly.

**Step 2: Run tests and verify failure**

Run:

```bash
cd dashboard
npm test -- --run
```

Expected: FAIL because report components are not implemented.

**Step 3: Implement report page**

Render:

- recommendation summary
- candidate table
- metric card grid
- NAV chart
- underwater chart
- implementation stress summary
- BTC/core return haircut notes

Use ECharts for charts and keep chart containers at stable heights.

**Step 4: Verify**

Run:

```bash
cd dashboard
npm test -- --run
npm run build
```

Expected: tests and build pass.

**Step 5: Commit**

```bash
git add dashboard/src
git commit -m "feat: add BTC research report mode"
```

### Task 6: Build Paper Tracking Mode

**Files:**
- Create: `dashboard/src/pages/PaperTrackingPage.tsx`
- Create: `dashboard/src/components/LatestSignalPanel.tsx`
- Create: `dashboard/src/components/TargetWeightsPanel.tsx`
- Create: `dashboard/src/components/PaperRulesPanel.tsx`
- Create: `dashboard/src/components/RiskReviewPanel.tsx`
- Modify: `dashboard/src/App.tsx`

**Step 1: Write component tests**

Test that the app renders:

- latest date `2026-06-23`
- BTC signal off
- BTC close and SuperTrend line
- target weights for the three BTC caps
- paper-trading rules

**Step 2: Run tests and verify failure**

Run:

```bash
cd dashboard
npm test -- --run
```

Expected: FAIL because paper tracking components are not implemented.

**Step 3: Implement paper tracking page**

Render latest signal, target weights, rules, pause conditions, and candidate watchlist. Keep it operational and concise.

**Step 4: Verify**

Run:

```bash
cd dashboard
npm test -- --run
npm run build
```

Expected: tests and build pass.

**Step 5: Commit**

```bash
git add dashboard/src
git commit -m "feat: add paper tracking mode"
```

### Task 7: Visual QA And Browser Verification

**Files:**
- Modify as needed: `dashboard/src/**/*.tsx`
- Modify as needed: `dashboard/src/styles/global.css`

**Step 1: Start dev server**

Run:

```bash
cd dashboard
npm run dev -- --host 127.0.0.1
```

Expected: local URL is printed.

**Step 2: Browser QA**

Use the in-app browser to check:

- desktop viewport
- mobile viewport
- mode switching
- chart visibility
- no overlapping text
- all key recommendation text is visible without scrolling inside tiny panels

**Step 3: Fix visual issues**

Adjust spacing, chart heights, responsive grid columns, and typography as needed.

**Step 4: Final verification**

Run:

```bash
cd dashboard
npm test -- --run
npm run build
```

Expected: all tests pass and build passes.

**Step 5: Commit**

```bash
git add dashboard
git commit -m "polish: verify strategy dashboard layout"
```

