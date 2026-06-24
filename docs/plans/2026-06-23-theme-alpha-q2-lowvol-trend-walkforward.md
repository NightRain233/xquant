# Theme Alpha Q2 LowVol Trend Walk-Forward Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Test whether the Theme Alpha Q1 low-volatility trend RiskParity factor remains useful under a rolling train/validation process rather than fixed full-sample parameters.

**Architecture:** Create a new Q2 notebook that precomputes a small grid of LowVolTrend RiskParity variants, then uses only trailing training-window performance to select the next validation-window variant. Compare walk-forward stitched portfolios against static LowVolTrend cap45/cap50/cap55, Theme RiskParity, original three-asset RiskParity, and buy-and-hold benchmarks.

**Tech Stack:** Python, pandas, numpy, matplotlib, yfinance, nbformat, jupyter nbconvert.

---

### Task 1: Create Q2 Notebook

**Files:**
- Create: `theme-alpha-q2-lowvol-trend-walkforward-practice.ipynb`
- Runtime output: `outputs/theme-alpha-q2-lowvol-trend-walkforward/`

**Steps:**
1. Load the same theme-alpha universe and baseline assets.
2. Download OHLC data from 2023-01-01 for warmup.
3. Anchor rebalance dates at 2024-01-02.
4. Implement LowVolTrend selector, capped RiskParity, turnover, cost, and metrics.

### Task 2: Precompute Parameter Grid

**Files:**
- Modify: `theme-alpha-q2-lowvol-trend-walkforward-practice.ipynb`

**Steps:**
1. Fix momentum window at 63, volatility window at 60, Top-N at 3.
2. Test MA windows: 60, 90, 120, 180, 200.
3. Test cap levels: 45%, 50%, 55%.
4. Export parameter grid metrics for 2025-only, 2026-YTD, and 2025-to-date.

### Task 3: Walk-Forward Portfolios

**Files:**
- Modify: `theme-alpha-q2-lowvol-trend-walkforward-practice.ipynb`

**Steps:**
1. Build walk-forward schedules:
   - Train 126 trading days, validate 21 trading days
   - Train 252 trading days, validate 21 trading days
   - Train 252 trading days, validate 63 trading days
2. Rank variants by training Sharpe, Calmar, and a composite score.
3. Stitch selected signal weights for the next validation window.
4. Backtest stitched weights with 0, 10, and 20 bps transaction costs.

### Task 4: Diagnostics

**Files:**
- Modify: `theme-alpha-q2-lowvol-trend-walkforward-practice.ipynb`

**Steps:**
1. Export selection history and selection counts.
2. Export walk-forward summary metrics.
3. Compare walk-forward performance to static cap45/cap50/cap55 and Theme RiskParity.
4. Plot NAV, underwater curves, and selected parameter history.

### Task 5: Write Review Note

**Files:**
- Create: `docs/notes/theme-alpha-q2-lowvol-trend-walkforward-review.md`

**Steps:**
1. State whether rolling selection improves, matches, or weakens the Q1 fixed-parameter result.
2. Identify whether cap45/50/55 forms a stable plateau.
3. Discuss whether the factor looks robust enough for Q3 research.
4. Record next research direction.

### Task 6: Verify

**Commands:**
- Run: `.venv/bin/jupyter nbconvert --to notebook --execute theme-alpha-q2-lowvol-trend-walkforward-practice.ipynb --inplace --ExecutePreprocessor.timeout=900`
- Check outputs:
  - `outputs/theme-alpha-q2-lowvol-trend-walkforward/walkforward_summary_2025_to_date.csv`
  - `outputs/theme-alpha-q2-lowvol-trend-walkforward/selection_counts.csv`
  - `outputs/theme-alpha-q2-lowvol-trend-walkforward/static_parameter_grid_2025_to_date.csv`
  - `docs/notes/theme-alpha-q2-lowvol-trend-walkforward-review.md`

Expected: notebook executes with exit code 0 and all key outputs exist.
