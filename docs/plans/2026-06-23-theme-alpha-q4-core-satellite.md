# Theme Alpha Q4 Core Satellite Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Test whether the expanded LowVolTrend sleeve is useful as a satellite allocation alongside the original three-asset RiskParity core.

**Architecture:** Create a Q4 notebook that builds the original three-asset RiskParity core and the expanded LowVolTrend cap50 satellite, then combines them at fixed satellite weights. Evaluate Q3/Q5 metrics, monthly diagnostics, underwater/recovery diagnostics, cost stress, latest weights, and whether the combined portfolio improves the core without unacceptable drawdown deterioration.

**Tech Stack:** Python, pandas, numpy, matplotlib, yfinance, nbformat, jupyter nbconvert.

---

### Task 1: Create Q4 Notebook

**Files:**
- Create: `research/notebooks/theme-alpha-q4-core-satellite-practice.ipynb`
- Runtime output: `outputs/theme-alpha-q4-core-satellite/`

**Steps:**
1. Download the same ETF universe used in Q3.
2. Build the original three-asset RiskParity core.
3. Build the expanded LowVolTrend cap50 satellite.
4. Build original-theme LowVolTrend cap50 as an aggressive satellite comparison.

### Task 2: Build Core/Satellite Portfolios

**Files:**
- Modify: `research/notebooks/theme-alpha-q4-core-satellite-practice.ipynb`

**Variants:**
- 100% core.
- 90/10 core / expanded LVT.
- 80/20 core / expanded LVT.
- 70/30 core / expanded LVT.
- 60/40 core / expanded LVT.
- 80/20 core / original LVT for comparison.
- 100% expanded LVT.

### Task 3: Evaluate

**Files:**
- Modify: `research/notebooks/theme-alpha-q4-core-satellite-practice.ipynb`

**Outputs:**
- Summary tables for 2025-to-date, 2026 YTD, and 2025-only.
- Monthly diagnostics.
- Underwater and recovery diagnostics.
- Cost stress at 0, 10, and 20 bps.
- Latest and average combined weights.
- NAV and underwater charts.

### Task 4: Review Note

**Files:**
- Create: `docs/notes/theme-alpha-q4-core-satellite-review.md`

**Steps:**
1. Identify the best core/satellite allocation by return, Sharpe, Calmar, and underwater quality.
2. State whether expanded LVT works better as a satellite than a standalone sleeve.
3. Compare 80/20 expanded LVT against 80/20 original LVT.
4. Recommend a next candidate allocation for deeper execution testing.

### Task 5: Verify

**Commands:**
- Run: `.venv/bin/jupyter nbconvert --to notebook --execute research/notebooks/theme-alpha-q4-core-satellite-practice.ipynb --inplace --ExecutePreprocessor.timeout=900`
- Check outputs:
  - `outputs/theme-alpha-q4-core-satellite/summary_2025_to_date.csv`
  - `outputs/theme-alpha-q4-core-satellite/monthly_diagnostics_2025_to_date.csv`
  - `outputs/theme-alpha-q4-core-satellite/underwater_recovery_2025_to_date.csv`
  - `outputs/theme-alpha-q4-core-satellite/cost_sensitivity_2025_to_date.csv`
  - `docs/notes/theme-alpha-q4-core-satellite-review.md`

Expected: notebook executes with exit code 0 and all key outputs exist.
