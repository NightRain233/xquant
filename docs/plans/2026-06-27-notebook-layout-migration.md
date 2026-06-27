# Notebook Layout Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move all practice notebooks out of the repository root without changing where they read or write research data.

**Architecture:** Add a tested repository-root locator to `xquant`, then inject a small bootstrap as the first code cell of every notebook. The bootstrap restores the repository root as the working directory, allowing the existing relative `outputs/`, `docs/`, and `scripts/` paths to keep working after notebooks move to `research/notebooks/`.

**Tech Stack:** Python 3.12, pathlib, pytest, Jupyter Notebook JSON, Git.

---

### Task 1: Repository-root locator via TDD

**Files:**
- Create: `tests/test_project.py`
- Create: `src/xquant/project.py`

**Steps:**

1. Write failing tests for locating a parent containing both `pyproject.toml` and `.git`, accepting a file path as the starting point, and raising a clear error outside a repository.
2. Run `uv run pytest tests/test_project.py -v` and confirm the module is missing.
3. Implement `find_repo_root(start=None)`.
4. Re-run the focused and full Python test suites.

### Task 2: Inject a portable Notebook bootstrap

**Files:**
- Modify: all 18 root `*-practice.ipynb`
- Create: `tests/test_notebook_layout.py`

**Steps:**

1. Write a failing repository test requiring every practice notebook under `research/notebooks/`, no root-level notebooks, valid Notebook JSON, and the standard bootstrap as its first code cell.
2. Insert a code cell that imports `find_repo_root`, stores `REPO_ROOT`, and calls `os.chdir(REPO_ROOT)`.
3. Use `git mv` to move every root practice notebook into `research/notebooks/`.
4. Run the layout test.

### Task 3: Update generated Notebook paths and documentation

**Files:**
- Modify: `scripts/theme_alpha_q12_long_sample_proxy_validation.py`
- Create: `research/README.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `AGENTS-CN.md`
- Modify: `docs/repository-structure.md`
- Modify: matching files under `docs/notes/` and `docs/plans/`

**Steps:**

1. Resolve Q12 output, note, and notebook paths from `find_repo_root()`.
2. Make the generated Q12 notebook include the same bootstrap and `%run` entrypoint.
3. Add a Chinese research index grouping BTC and Theme Alpha notebooks in reading order.
4. Replace root-level notebook references with `research/notebooks/<name>`.
5. Update contributor rules so new notebooks use the new directory.

### Task 4: Verification and commit

**Steps:**

1. Run `uv run pytest`.
2. Parse all moved notebooks and confirm every one has the bootstrap.
3. Confirm no root-level `*.ipynb` remains and no accidental nested `outputs/` directory exists.
4. Run `uv run python -m compileall -q src scripts check_env.py`.
5. Run `make dashboard-test` and `make dashboard-build`.
6. Check Markdown links, trailing whitespace, Git rename detection, and final status.
7. Commit the migration separately from the baseline commits.
