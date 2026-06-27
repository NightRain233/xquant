# Theme Alpha Q1 Theme Enhancement Validation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Validate whether the theme-alpha-q1 low-volatility trend RiskParity sleeve is a robust theme-enhancement strategy or mostly a sample-period concentration result.

**Architecture:** Create a new validation notebook instead of expanding the first theme-alpha-q1 screening notebook. Reuse the same ETF universe and metric definitions, then add concentration caps, transaction costs, rolling-window diagnostics, and simple out-of-sample checks focused on Theme RiskParity and Low-Vol Trend RiskParity.

**Tech Stack:** Python, pandas, numpy, matplotlib, yfinance, nbformat, jupyter nbconvert.

---

### Task 1: Create Validation Notebook

**Files:**
- Create: `research/notebooks/theme-alpha-q1-theme-enhancement-validation-practice.ipynb`
- Create output folder at runtime: `outputs/theme-alpha-q1-theme-enhancement-validation/`

**Steps:**
1. Load the same theme-alpha-q1 theme universe and baseline assets.
2. Download OHLC data with yfinance from 2023-01-01 for indicator warmup.
3. Build common close/high/low/return matrices.
4. Implement equal weight, RiskParity, capped RiskParity, low-volatility trend selector, and backtest helpers.
5. Keep signal-date weights shifted by one trading day.

### Task 2: Add Strategy Variants

**Files:**
- Modify: `research/notebooks/theme-alpha-q1-theme-enhancement-validation-practice.ipynb`

**Steps:**
1. Include benchmark strategies: original three-asset RiskParity, theme equal weight, theme RiskParity, pure Nasdaq, pure gold, 60/40 CSI300/Gold.
2. Include candidate strategies:
   - LowVolTrend RiskParity uncapped
   - LowVolTrend RiskParity capped at 60%
   - LowVolTrend RiskParity capped at 50%
   - LowVolTrend RiskParity capped at 40%
   - Theme RiskParity capped at 40%
3. Export latest and average weights.

### Task 3: Add Transaction Cost Tests

**Files:**
- Modify: `research/notebooks/theme-alpha-q1-theme-enhancement-validation-practice.ipynb`

**Steps:**
1. Compute daily turnover from shifted portfolio weights.
2. Deduct costs at 0, 5, 10, and 20 bps per one-way turnover.
3. Export cost sensitivity tables for 2025-to-date and 2026 YTD.

### Task 4: Add Rolling And Out-of-Sample Checks

**Files:**
- Modify: `research/notebooks/theme-alpha-q1-theme-enhancement-validation-practice.ipynb`

**Steps:**
1. Compute rolling 63-day, 126-day, and 252-day returns, Sharpe, and max drawdown where enough data exists.
2. Export rolling summary tables and charts.
3. Treat 2025 as the parameter observation period and 2026 YTD as a simple out-of-sample check.
4. Rank parameter variants in 2025 and compare their 2026 YTD ranks.

### Task 5: Write Review Note

**Files:**
- Create: `docs/notes/theme-alpha-q1-theme-enhancement-validation-review.md`

**Steps:**
1. Summarize whether low-vol trend remains strong after caps and costs.
2. Compare capped low-vol trend against theme RiskParity and original three-asset RiskParity.
3. State whether it looks like a robust new factor or a sample-period concentration result.
4. Record next research direction.

### Task 6: Verify

**Commands:**
- Run: `.venv/bin/jupyter nbconvert --to notebook --execute research/notebooks/theme-alpha-q1-theme-enhancement-validation-practice.ipynb --inplace --ExecutePreprocessor.timeout=600`
- Check key outputs:
  - `outputs/theme-alpha-q1-theme-enhancement-validation/summary_2025_to_date.csv`
  - `outputs/theme-alpha-q1-theme-enhancement-validation/cost_sensitivity_2025_to_date.csv`
  - `outputs/theme-alpha-q1-theme-enhancement-validation/oos_parameter_validation.csv`
  - `outputs/theme-alpha-q1-theme-enhancement-validation/rolling_summary.csv`

Expected: notebook executes with exit code 0 and all key outputs exist.
