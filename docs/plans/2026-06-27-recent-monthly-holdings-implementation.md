# Recent Monthly Holdings and Theme Alpha Comparison Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add six-month return and month-end holding detail for both strategies, and split Theme Alpha's reader-facing comparisons into primary and research scopes.

**Architecture:** A tested Python helper converts strategy NAV and executed-weight histories into a common six-month CSV contract. The notebooks export those records, the TypeScript builder normalizes them into a separate static JSON chunk, and the React report page applies one shared comparison scope to candidate, annual, and monthly panels.

**Tech Stack:** Python 3.12, pandas, Jupyter, React 18, TypeScript, Vitest, Testing Library, Vite.

---

### Task 1: Build a tested recent-month export helper

**Files:**
- Create: `src/xquant/research_exports.py`
- Create: `tests/test_research_exports.py`

**Step 1: Write the failing tests**

Cover:

- Six most recent calendar months are returned in chronological order.
- Monthly returns use month-end NAV values.
- Month-end holdings use the last executed-weight row available in each month.
- Only the latest current-calendar month is marked partial.
- Every row's holdings sum to one.

Use a deterministic `as_of=pd.Timestamp("2026-06-27")` argument so tests do not depend on wall-clock time.

**Step 2: Run the tests and verify RED**

Run:

```bash
uv run pytest tests/test_research_exports.py -q
```

Expected: collection fails because `xquant.research_exports` does not exist.

**Step 3: Implement the helper**

Provide:

```python
def build_recent_monthly_records(
    strategy: str,
    nav: pd.Series,
    executed_weights: pd.DataFrame,
    asset_names: Mapping[str, str],
    *,
    count: int = 6,
    as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    ...
```

The returned columns are:

```text
strategy,month,month_end_date,is_partial,return,<named asset columns>
```

Reject empty NAV, missing aligned weights, duplicate dates, and holdings that do not sum to one within tolerance.

**Step 4: Run the tests and verify GREEN**

Run:

```bash
uv run pytest tests/test_research_exports.py -q
```

Expected: all helper tests pass.

### Task 2: Export default-candidate monthly records from both notebooks

**Files:**
- Modify: `research/notebooks/q10-live-readiness-stress-practice.ipynb`
- Modify: `research/notebooks/theme-alpha-q8-signal-live-readiness-practice.ipynb`
- Generate: `outputs/q10-live-readiness-stress/recent_monthly_tracking.csv`
- Generate: `outputs/theme-alpha-q8-signal-live-readiness/recent_monthly_tracking.csv`

**Step 1: Add helper imports**

Import `build_recent_monthly_records` from `xquant.research_exports` after each notebook's repository-root bootstrap cell.

**Step 2: Export BTC records**

Use:

```python
preferred = base_results["BTC7.5%ST卫星"]
```

Pass `preferred["nav"]` and `preferred["weights"]`. Rename symbols with the notebook's display-name mapping and export the last six months.

**Step 3: Export Theme Alpha records**

Use:

```python
preferred_name = "Def200_Cash_BIMONTHLY_next_close_base20_plus_asset"
preferred = portfolios[preferred_name]
```

Build NAV from `preferred["returns"]`, pass `preferred["weights"]`, map symbols through `SYMBOL_NAMES`, and export the last six months.

**Step 4: Execute both notebooks to temporary output notebooks**

Run:

```bash
uv run jupyter nbconvert --to notebook --execute research/notebooks/q10-live-readiness-stress-practice.ipynb --output /tmp/q10-recent-months.ipynb --ExecutePreprocessor.timeout=1800
uv run jupyter nbconvert --to notebook --execute research/notebooks/theme-alpha-q8-signal-live-readiness-practice.ipynb --output /tmp/q8-recent-months.ipynb --ExecutePreprocessor.timeout=1800
```

**Step 5: Validate generated CSVs**

Assert:

- Six rows per file.
- `2026-06` is partial and ends on `2026-06-26`.
- Returns are finite.
- Holdings sum to one.

### Task 3: Add failing dashboard builder tests

**Files:**
- Modify: `dashboard/scripts/build-data.test.ts`

**Step 1: Add recent-month assertions**

For both strategy packages, assert:

- `recentMonthlyRecords` contains six chronological rows.
- The final row is partial.
- Its `monthEndDate` is `2026-06-26`.
- Holdings sum to one.

**Step 2: Add Theme Alpha grouping assertions**

Assert:

```text
primary:
  Original-RiskParity-3Asset
  Core80-LVT20-Def200-Cash
  Expanded-LVT-100

research:
  Core60-LVT40-Def200-Cash
  Core80-LVT20-STEntry-Def200-Cash
  Core80-LVT20-STHalf-Def200-Cash
```

BTC should have no research-only candidates.

**Step 3: Run the builder test and verify RED**

Run:

```bash
cd dashboard
npm test -- --run scripts/build-data.test.ts
```

Expected: failures for missing recent records and comparison groups.

### Task 4: Extend dashboard data types, builder, and split loading

**Files:**
- Modify: `dashboard/src/data/types.ts`
- Modify: `dashboard/scripts/build-data.ts`
- Modify: `dashboard/src/data/useStrategyData.ts`

**Step 1: Add types**

Add:

```ts
export type RecentMonthlyRecord = {
  strategy: string;
  month: string;
  monthEndDate: string;
  isPartial: boolean;
  monthlyReturn: number;
  holdings: Record<string, number>;
};

export type CandidateComparisonGroups = {
  primary: string[];
  research: string[];
};
```

Add `candidateComparisonGroups` to report data and `recentMonthlyRecords` to chart data.

**Step 2: Normalize recent-month CSV rows**

Parse metadata fields and place all asset columns under `holdings`. Preserve zero weights in JSON; the UI decides which holdings are visible.

**Step 3: Build comparison groups**

Set all BTC candidate ids as primary. Set the approved Theme Alpha three-plus-three split.

**Step 4: Write and load a separate JSON chunk**

Write:

```text
dashboard/public/data/strategies/<id>/recent-monthly-records.json
```

Fetch it with the other chart data in `useStrategyReportData`.

**Step 5: Run the builder test and verify GREEN**

Run:

```bash
cd dashboard
npm test -- --run scripts/build-data.test.ts
```

Expected: all builder tests pass.

### Task 5: Add failing UI tests

**Files:**
- Create: `dashboard/src/components/MonthlyStatsPanel.test.tsx`
- Modify: `dashboard/src/pages/ResearchReportPage.test.tsx`

**Step 1: Test recent-month tab behavior**

Render six recent records, click `近期 6 个月`, and assert:

- The default candidate name is visible.
- `2026-06` shows `截至 6/26`.
- Positive and negative returns render.
- Zero holdings are hidden.
- Month-end non-zero holdings are visible.

**Step 2: Test comparison scope behavior**

For Theme Alpha report fixtures, assert:

- Initial `核心对比` excludes Core60, STEntry, and STHalf.
- Clicking `研究候选` shows the current Core80 anchor plus the three research candidates.
- Annual and monthly comparison panels follow the selected scope.

**Step 3: Run tests and verify RED**

Run:

```bash
cd dashboard
npm test -- --run src/components/MonthlyStatsPanel.test.tsx src/pages/ResearchReportPage.test.tsx
```

Expected: failures because the new tab and grouping behavior do not exist.

### Task 6: Implement recent-month UI and comparison scope

**Files:**
- Modify: `dashboard/src/components/MonthlyStatsPanel.tsx`
- Modify: `dashboard/src/components/CandidateTable.tsx`
- Modify: `dashboard/src/components/AnnualReturnsPanel.tsx`
- Modify: `dashboard/src/pages/ResearchReportPage.tsx`

**Step 1: Lift comparison scope into the report page**

Use one local state:

```ts
type ComparisonScope = "primary" | "research";
```

Default to `primary`. If there are no research candidates, omit the scope control.

**Step 2: Filter comparison data consistently**

Primary scope uses the approved primary ids. Research scope shows the current paper candidate as an anchor plus research ids.

Filter:

- Candidate metrics.
- Annual return value columns.
- Monthly summary rows.

Do not filter recent monthly records; they always describe the default paper candidate.

**Step 3: Add the recent-month tab**

Extend the monthly panel view union:

```ts
"overview" | "table" | "recent"
```

Render one bordered row per month with:

- Month and partial label.
- Monthly return.
- Non-zero holdings.
- Month-end date.

Use existing typography, borders, and restrained positive/negative colors. On mobile, holdings use a single-column grid.

**Step 4: Run UI tests and verify GREEN**

Run:

```bash
cd dashboard
npm test -- --run src/components/MonthlyStatsPanel.test.tsx src/pages/ResearchReportPage.test.tsx
```

Expected: all targeted UI tests pass.

### Task 7: Regenerate, verify, and visually inspect

**Files:**
- Generate: `dashboard/public/data/strategies/**`

**Step 1: Run Python verification**

```bash
uv run pytest tests/test_research_exports.py tests/test_portfolio.py tests/test_theme_alpha_script_integration.py
```

**Step 2: Run full dashboard verification**

```bash
make dashboard-check
```

Expected:

- All Vitest tests pass.
- TypeScript type-check passes.
- Vite production build succeeds.

**Step 3: Inspect generated JSON**

Verify both strategy files contain six recent months and Theme Alpha contains the approved comparison grouping.

**Step 4: Browser verification**

Check desktop and 390px widths:

- Recent tab is readable.
- Holdings wrap without page overflow.
- Theme Alpha starts in primary scope.
- Research scope reveals all three hidden candidates.
- BTC does not show an unnecessary comparison-scope control.

**Step 5: Audit the dirty worktree**

Confirm pre-existing staged changes remain staged and unrelated user changes are not overwritten.
