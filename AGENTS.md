# Repository Guidelines

## Current Research Stance (2026-11)

- **Main line (frozen core)**: Three-asset inverse-volatility core (`510300` / `513100` / `518880`) plus a 7.5% BTC daily SuperTrend(10, 3) satellite, running as a paper account in the sibling `trading` repo. Overlaying S2 trend filtering onto the main line failed (`docs/notes/main-line-s2-filter-2026-11-10-review.md`).
- **Standalone S&P 500 enhancement options (2026-11 validated, separate from main line)**:
  - Low-turnover cross-asset pair (best for high-friction crypto-exchange tokenized US stocks and simple domestic `513500+518880` accounts): `75% S&P 500 + 25% Gold` quarterly rebalanced (`GOLD_75_25_Q` / `CN_75_25_Q`). Note gold bear-market risk (underperforms SPY during multi-year gold drawdowns like 2011–2015).
  - Low-fee USD trend shield (`≤10bp`): `S2_GOLD`, `S2_BOND_GOLD`, gold-bear-safe `S2_GOLD_TREND` / `S2_CASH`, and the newly validated **daily buffered MTF-3 (`±2%～3%` hysteresis around 150d rising SMA + 210d SMA; `MTF3_BUF2`/`MTF3_BUF3` with cash, `GOLD`, or `BOND_GOLD`)** on US `SPY`/`QQQ` (`docs/notes/mtf3-daily-buffer-2026-11-23-review.md`; circular shift `p <= 0.03`, 2–3 trades/yr, 0% 5Y/10Y loss rate in cash mode; `MTF3_BUF3_BOND_GOLD` Sharpe `0.781`). Note: daily buffered MTF-3 still fails on domestic `513500` self-price and adding a separate gold 30W filter (`MTF3_BUF*_GOLD_TREND`) underperforms pure cash in gold bear markets.
  - Domestic `513500` defensive volatility control: self-signal `TVT-50` (to cash or `518880` gold), paired with decision-time QDII premium discipline (`>3%` DCA cash parking; `>6%` trim is a premium-only guard, not bear protection).
  - See `docs/strategies/sp500-enhance.md`, `docs/notes/sp500-four-directions-2026-11-22-review.md`, and `docs/notes/mtf3-daily-buffer-2026-11-23-review.md`.
- **Archived comparisons (unified status)**: Theme Alpha, `Core90 / Bull10`, RS rotation, JoinQuant Top-1 momentum rotation (parameter-sensitive, >40% DD), and TQQQ regime switching (small-size reference only) are archived comparisons, not active recommendations.
- **Frozen negative findings (do not re-propose unless the user asks)**:
  - A-share timing rules (Weinstein 30W, Bollinger bands) did not beat buy-and-hold;
  - S&P 500 single-factor replacements (`SPHQ`, `SPLV`, `RSP`), VIX/VIX3M term-structure brakes, credit-spread brakes (`BAA10Y`, `HYG/IEF`), smart DCA (`SD1`), calendar rules (`HAL`, `TOM`), RSI(2), and domestic `513500` self-signal discrete trend rules failed;
  - Gold trend filtering on IV20 (`test_iv20_gold_defense.py`) degraded diversification, whereas conditional gold-trend gating on S2 defensive sleeves (`S2_GOLD_TREND`) serves only as a gold-bear-market safeguard;
  - Crypto perpetual contracts (funding drag) and non-dividend tokenized US stocks materially erode long-term S&P 500 compounding.
- Use proportional (total-return) adjusted prices. The old additive forward adjustment overstated `510300`'s history; see `docs/notes/btc-satellite-corrected-prices-2026-10-18-review.md`.
- Write conclusions for a non-technical reader in plain Chinese; keep dated reports immutable and add new notes instead of rewriting them.

## Project Structure & Module Organization

- `research/notebooks/*-practice.ipynb` contains strategy experiments; use aligned slugs such as `<topic>-YYYY-MM-DD-practice.ipynb` or `q17-<topic>-practice.ipynb`.
- `src/xquant/` holds tested portfolio, indicator, overlay, and metric code (including shared multi-asset lab `sp500_lab.py`); `tests/` mirrors it.
- `scripts/` holds reproducible research jobs and the read-only live signal checker `scripts/check_live_sp500_signals.py`.
- `outputs/<experiment>/` stores CSVs, manifests, and charts.
- `docs/notes/` contains immutable dated research reviews matching each experiment; `docs/strategies/` holds plain-Chinese evergreen guides (`two-three-asset.md`, `sp500-enhance.md`, `holding-experience.md`, `research-index.md`); `docs/research-ledger.md` is the master index.
- `dashboard/src/` contains React pages, components, data adapters, styles, and colocated tests.
- `dashboard/scripts/` converts research outputs into static dashboard data under `dashboard/public/data/`.

Preserve reference notebooks. Keep each practice notebook, output directory, and review note aligned by slug. Do not remove the tagged repository-root bootstrap cell. Extract reusable calculations into `src/xquant/`; notebooks should orchestrate experiments and present results.

## Build, Test, and Development Commands

- `uv sync` creates `.venv` from `pyproject.toml` and the committed `uv.lock`.
- `uv run python check_env.py` checks Python, research packages, Jupyter, and live data access.
- `uv run python scripts/check_live_sp500_signals.py` prints current S&P 500 / Nasdaq-100 / Gold / BTC 30W-SMA and volatility states (read-only).
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
