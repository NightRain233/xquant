# Python Project Structure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the Python research environment reproducible with `uv`, introduce tested reusable research modules, and document a scalable repository structure without breaking existing notebooks.

**Architecture:** Keep the existing practice notebooks and research outputs in place during this phase. Add an installable `src/xquant` package for stable calculations, migrate the standalone Theme Alpha validation script to those modules, and establish explicit policies for future notebooks and generated outputs.

**Tech Stack:** Python 3.12, uv, pandas, NumPy, pytest, Jupyter, existing React/Vitest dashboard.

---

### Task 1: Reproducible Python environment

**Files:**
- Create: `pyproject.toml`
- Create: `uv.lock`
- Modify: `check_env.py`

**Steps:**

1. Declare Python 3.12+, the six direct research dependencies, the pinned `open-xquant` Git revision, and a `dev` dependency group containing pytest.
2. Configure the `src/` package layout and pytest discovery.
3. Run `uv lock` and verify the lock records the pinned Git revision.
4. Run `uv sync --frozen` to prove a declared environment can be installed.
5. Update `check_env.py` so its remediation message uses `uv sync` first and reserves `uv add` for adding a genuinely new dependency.

### Task 2: Portfolio utilities via TDD

**Files:**
- Create: `tests/test_portfolio.py`
- Create: `src/xquant/__init__.py`
- Create: `src/xquant/portfolio.py`

**Steps:**

1. Write failing tests for negative-weight cleanup, automatic cash allocation, over-allocation normalization, cap redistribution, and infeasible caps.
2. Run `uv run pytest tests/test_portfolio.py -v`; confirm failure because `xquant.portfolio` does not exist.
3. Implement `normalize_weights`, `apply_weight_cap`, and `inverse_volatility_weights`.
4. Re-run the tests and refactor only after they pass.

### Task 3: Indicator utilities via TDD

**Files:**
- Create: `tests/test_indicators.py`
- Create: `src/xquant/indicators.py`

**Steps:**

1. Write failing tests for true range, SuperTrend warm-up and direction, and low-volatility trend selection.
2. Verify the selector requires price above MA60 and positive 63-day momentum, then chooses the three lowest 60-day volatility candidates.
3. Implement `true_range`, `supertrend_direction`, and `select_low_vol_trend`.
4. Run `uv run pytest tests/test_indicators.py -v`.

### Task 4: Performance utilities via TDD

**Files:**
- Create: `tests/test_metrics.py`
- Create: `src/xquant/metrics.py`

**Steps:**

1. Write failing tests for NAV construction, initial-capital-aware drawdown, empty input, and recovery to a new high.
2. Implement `nav_from_returns` and `drawdown_series`.
3. Run `uv run pytest tests/test_metrics.py -v`.

### Task 5: Migrate one reproducible research script

**Files:**
- Modify: `scripts/theme_alpha_q12_long_sample_proxy_validation.py`

**Steps:**

1. Import the tested portfolio, indicator, and metric helpers from `xquant`.
2. Keep script-level wrappers only where the script supplies experiment-specific windows or market context.
3. Remove duplicate implementations.
4. Run the full Python test suite and a compile/import check without downloading or rewriting research outputs.

### Task 6: Document the target structure and artifact policy

**Files:**
- Create: `docs/repository-structure.md`
- Create: `outputs/README.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `AGENTS-CN.md`

**Steps:**

1. Explain why notebooks remain at the root in this phase and how future migrations should preserve repository-root-relative paths.
2. Define which summaries, decision tables, and charts belong in Git versus transient caches.
3. Replace manual environment setup with `uv sync` and `uv run`.
4. Document `src/xquant`, `tests`, and the rule that notebooks orchestrate experiments rather than own reusable calculations.

### Task 7: Full verification

**Steps:**

1. Run `uv lock --check`.
2. Run `uv run pytest`.
3. Run `uv run python -m compileall src scripts check_env.py`.
4. Run `make dashboard-test`.
5. Run `make dashboard-build`.
6. Check Markdown links, trailing whitespace, Git status, and the final diff.

Implementation will remain uncommitted because the working tree already contains staged user changes that must not be bundled into an automatic commit.
