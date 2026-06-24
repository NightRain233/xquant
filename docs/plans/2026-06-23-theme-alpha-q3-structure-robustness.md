# Theme Alpha Q3 Structure Robustness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Test whether the Theme Alpha LowVolTrend factor survives structural changes to gold treatment and the theme universe, rather than depending mainly on Nasdaq/chip continuation.

**Architecture:** Create a Q3 notebook focused on structure robustness. Keep the Q2-selected LowVolTrend settings fixed at MA60, momentum 63, volatility 60, Top-N 3, and cap50. Compare normal gold filtering, gold always eligible, gold floor allocations, removing Nasdaq/chip sleeves, and expanding the theme pool.

**Tech Stack:** Python, pandas, numpy, matplotlib, yfinance, nbformat, jupyter nbconvert.

---

### Task 1: Create Q3 Notebook

**Files:**
- Create: `theme-alpha-q3-structure-robustness-practice.ipynb`
- Runtime output: `outputs/theme-alpha-q3-structure-robustness/`

**Steps:**
1. Load base theme ETFs and extended theme ETFs.
2. Download OHLC data from 2023-01-01 for warmup.
3. Anchor rebalance dates at 2024-01-02.
4. Implement LowVolTrend selector, gold-always selector, gold-floor allocator, capped RiskParity, turnover, cost, and metrics.

### Task 2: Gold Structure Tests

**Files:**
- Modify: `theme-alpha-q3-structure-robustness-practice.ipynb`

**Variants:**
- Base LowVolTrend cap50 with gold filtered like every other asset.
- Gold always eligible.
- Gold always eligible with 10% floor.
- Gold always eligible with 15% floor.
- Theme RiskParity benchmark.
- Original three-asset RiskParity benchmark.

### Task 3: Universe Dependency Tests

**Files:**
- Modify: `theme-alpha-q3-structure-robustness-practice.ipynb`

**Universes:**
- Original theme pool.
- Original pool without Nasdaq.
- Original pool without Chip.
- Original pool without Nasdaq and Chip.
- Expanded pool: original plus dividend, energy, securities, Hong Kong tech, and healthcare.

### Task 4: Evaluation

**Files:**
- Modify: `theme-alpha-q3-structure-robustness-practice.ipynb`

**Outputs:**
- Summary tables for 2025-to-date, 2026 YTD, and 2025 only.
- Cost stress at 0 and 20 bps.
- Latest and average weights.
- Monthly returns and underwater curves.
- Structure scorecard classifying whether each variant supports or weakens the factor thesis.

### Task 5: Review Note

**Files:**
- Create: `docs/notes/theme-alpha-q3-structure-robustness-review.md`

**Steps:**
1. Explain whether LowVolTrend survives removing Nasdaq/chip sleeves.
2. Explain whether gold should be filtered, always eligible, or floored.
3. Explain whether the expanded pool improves robustness or dilutes the factor.
4. Recommend whether Q4 should study execution constraints, longer history, or production candidate construction.

### Task 6: Verify

**Commands:**
- Run: `.venv/bin/jupyter nbconvert --to notebook --execute theme-alpha-q3-structure-robustness-practice.ipynb --inplace --ExecutePreprocessor.timeout=900`
- Check outputs:
  - `outputs/theme-alpha-q3-structure-robustness/summary_2025_to_date.csv`
  - `outputs/theme-alpha-q3-structure-robustness/gold_structure_summary.csv`
  - `outputs/theme-alpha-q3-structure-robustness/universe_dependency_summary.csv`
  - `outputs/theme-alpha-q3-structure-robustness/structure_scorecard.csv`
  - `docs/notes/theme-alpha-q3-structure-robustness-review.md`

Expected: notebook executes with exit code 0 and all key outputs exist.
