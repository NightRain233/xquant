# Repository Guidelines

## Project Structure & Module Organization

This repository combines quantitative research with a TypeScript dashboard.

- Root `*-practice.ipynb` files contain strategy experiments; use names such as `q13-<topic>-practice.ipynb`.
- `src/xquant/` holds tested portfolio, indicator, and metric code; `tests/` mirrors it.
- `scripts/` holds reproducible research jobs.
- `outputs/<experiment>/` stores CSVs and charts.
- `docs/notes/` contains research reviews matching each experiment.
- `dashboard/src/` contains React pages, components, data adapters, styles, and colocated tests.
- `dashboard/scripts/` converts research outputs into static dashboard data under `dashboard/public/data/`.

Preserve reference notebooks. Keep each practice notebook, output directory, and review note aligned by slug. Extract reusable calculations into `src/xquant/`; notebooks should orchestrate experiments and present results.

## Build, Test, and Development Commands

- `uv sync` creates `.venv` from `pyproject.toml` and the committed `uv.lock`.
- `uv run python check_env.py` checks Python, research packages, Jupyter, and live data access.
- `uv run jupyter lab` opens the research notebooks.
- `uv run pytest` runs the Python unit and integration tests.
- `make dashboard-install` installs dashboard dependencies.
- `make dashboard` rebuilds data and starts Vite on `127.0.0.1`.
- `make dashboard-test` runs Vitest once.
- `make dashboard-build` type-checks and creates the production bundle.
- `make dashboard-check` rebuilds data, tests, and builds; run this before submitting dashboard changes.
- `make dashboard-dev-fresh` refreshes external benchmarks and requires network access.

## Coding Style & Naming Conventions

Use four-space indentation and `snake_case` for Python functions and variables; use `UPPER_SNAKE_CASE` for constants. TypeScript uses strict mode, two-space indentation, semicolons, `camelCase` values, and `PascalCase` React components. Keep component filenames descriptive, for example `BenchmarkScorecardPanel.tsx`. Tests use `*.test.ts` or `*.test.tsx`.

Do not mix asset-pool, weighting, and timing hypotheses without clearly separating them. Compare variants over identical windows and metric definitions.

## Testing Guidelines

Pytest covers shared Python calculations and script integration. Vitest, Testing Library, and jsdom cover dashboard behavior and data builders. Protect calculations, data contracts, loading/error states, and generated-file structure. For research changes, record baseline, Q3/Q5 metrics, drawdowns, monthly/annual behavior, and parameter sensitivity in the notebook and review note.

## Commit & Pull Request Guidelines

History favors short, imperative subjects, often using `feat:`, `fix:`, `docs:`, `chore:`, or a concise Chinese equivalent. Keep each commit scoped to one research pass or dashboard change. Pull requests should summarize the hypothesis or UI change, list validation commands, identify regenerated outputs, and include screenshots for visual dashboard changes. Link the related issue or research note when available.
