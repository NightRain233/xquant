# Repository Guidelines

## Current Research Stance (2026-11)

- **Main line (frozen core)**: Three-asset inverse-volatility core (`510300` / `513100` / `518880`) plus a 7.5% BTC daily SuperTrend(10, 3) satellite, running as a paper account in the sibling `trading` repo. Overlaying S2 trend filtering onto the main line failed (`docs/notes/main-line-s2-filter-2026-11-10-review.md`).
- **Standalone S&P 500 enhancement options (2026-11 validated, separate from main line)**:
  - Low-turnover cross-asset pair (best for high-friction crypto-exchange tokenized US stocks and simple domestic `513500+518880` accounts): `75% S&P 500 + 25% Gold` quarterly rebalanced (`GOLD_75_25_Q` / `CN_75_25_Q`). Note gold bear-market risk (underperforms SPY during multi-year gold drawdowns like 2011–2015).
  - Low-fee USD trend shield (`≤10bp`): `S2_GOLD`, `S2_BOND_GOLD`, gold-bear-safe `S2_GOLD_TREND` / `S2_CASH`, and the newly validated **daily buffered MTF-3 (`±2%～3%` hysteresis around 150d rising SMA + 210d SMA; `MTF3_BUF2`/`MTF3_BUF3` with cash, `GOLD`, or `BOND_GOLD`)** on US `SPY`/`QQQ` (`docs/notes/mtf3-daily-buffer-2026-11-23-review.md`; circular shift `p <= 0.03`, 2–3 trades/yr, 0% 5Y/10Y loss rate in cash mode; `MTF3_BUF3_BOND_GOLD` Sharpe `0.781`). Note: daily buffered MTF-3 still fails on domestic `513500` self-price and adding a separate gold 30W filter (`MTF3_BUF*_GOLD_TREND`) underperforms pure cash in gold bear markets.
  - Domestic `513500` defensive volatility control: self-signal `TVT-50` (to cash or `518880` gold), paired with decision-time QDII premium discipline (`>3%` DCA cash parking; `>6%` trim is a premium-only guard, not bear protection).
  - **Standalone BTC three-tier buffered trend & MA families (2026-11-23 validated, separate from frozen Plan A's 7.5% BTC daily ST satellite)**: `HYB_ST_MA150_B5` (`Daily SuperTrend(10,3) + 150d SMA ±5%`, 100%/50%/0%) remains the #1 all-weather BTC choice (full Sharpe `1.397`, MaxDD `-55.5%`, ETH `-45.9%` / `p = 0.005`, 5Y DCA worst float loss `-23.4%`); `MTF3_100_200_B5/B8` is the low-turnover 3-tier pure dual-MA option. Deep MA-family follow-up (`docs/notes/btc-ma-and-dlv-mean-reversion-2026-11-23-review.md`) confirmed plain Dual SMA/EMA fail BTC permutation (`p > 0.05`) and raw Zero-Lag MAs (`ZLEMA/DEMA/TEMA/HMA`) suffer 19–38 trades/yr churn (and `KAMA` fails), while **Zero-Lag + ±5% buffer (`DEMA_150_B5`)** uniquely passed BTC full (`p=0.005`), BTC 2021–26 mature (`37.2% / Sharpe 0.994 / p=0.050`), and ETH (`p=0.035`) with 4.8 trades/yr (`SMA_100_B5` also strong), recorded as a simpler binary alternative (deeper `-64%` DD & `-35.7%` DCA float loss) without replacing `HYB_ST_MA150_B5`.
  - **Standalone Gold quantitative enhancement (2026-11-23 validated, separate from frozen Plan A)**: Across 55Y monthly post-Bretton-Woods gold (1972–2026), 21Y real `GLD` (through the 2026 `-34.9%` crash), 25Y `GC=F`, 12.3Y domestic `518880`, and `PAXG`/`XAUT`, the #1 standalone single-asset gold rule is **low-turnover `TVT-50` (`15%` target vol + 30W-SMA 50% bear cap, weekly 15% deadband or monthly 10% deadband; 4.6–6.0 trades/yr)** — beats BH Sharpe across **140/140 (100%)** parameter combos and **18/18** annual starts, passes circular-shift permutation on `GLD` (`p=0.010`), `GC=F` (`p=0.015`), and `518880` (`p=0.015`), and de-risked on the exact `2026-01-29` parabolic peak (`-18.2%` vs `-34.9%`). Pure 0/100 trend (`M10`/`M12`) excels in 55Y high-rate bears (`1980–2001`, `p=0.005`) but suffered whipsaw in `2011–2019` ZIRP chop. For breaking gold's 9-year underwater drag, validated cross-asset structures are `GLD60_SPY40_Q`, `GLD50_IEF25_SPY25_Q` (0% 5Y loss rate), and `TVT50_15_W_DB10_SPY_TREND` (`10.56%` CAGR / Sharpe `0.686` / `-24.8%` DD / 98.5% 10Y DCA beat); domestic `518880` must use self RMB signals + `511010` bond parking (far superior to lagged US `GLD` signals); crypto `PAXG`/`XAUT` enjoy 0% annual fee edge over `GLD` (use limit orders). Gold/Silver Ratio (`GSR >80/<60`) is conditional/high-DD satellite only (7 trades in 25Y, `-52%` to `-60%` DD). See `docs/notes/gold-enhance-2026-11-23-review.md` and `docs/strategies/gold-enhance.md`.
  - See `docs/strategies/sp500-enhance.md`, `docs/strategies/gold-enhance.md`, `docs/notes/sp500-four-directions-2026-11-22-review.md`, `docs/notes/mtf3-daily-buffer-2026-11-23-review.md`, `docs/notes/btc-ashare-buffered-mtf3-2026-11-23-review.md`, `docs/notes/btc-ma-and-dlv-mean-reversion-2026-11-23-review.md`, and `docs/notes/gold-enhance-2026-11-23-review.md`.
- **Archived comparisons (unified status)**: Theme Alpha, `Core90 / Bull10`, RS rotation, JoinQuant Top-1 momentum rotation (parameter-sensitive, >40% DD), and TQQQ regime switching (small-size reference only) are archived comparisons, not active recommendations.
- **Frozen negative findings (do not re-propose unless the user asks)**:
  - A-share timing & mean-reversion rules: Trend timing (Weinstein 30W, Bollinger, daily buffered MTF-3 across Dividend Low-Vol `H20269`/`510880`/`512890`, `H00300`, `510500`, `159915`) failed due to negative post-MA trend spread (`-0.5%` to `-4.1%`); buffered volatility throttling (`VOL3`) failed on real `512890`. Mean-reversion / reverse-MA audit (`docs/notes/btc-ma-and-dlv-mean-reversion-2026-11-23-review.md`) also failed full-cycle bars: `RSI(2)`, `KDJ` (`p = 0.64–0.96`), raw unbuffered reverse-MA, broad-index MR (`H00300`/`510500`), and budget-neutral MR-DCA all failed vs plain monthly DCA; slow core-tilt MR (`BIAS_MA120_6PCT_CORE`, `RSI14_CORE_70`) is conditional/single-regime only (strong in 2020–2026 `512890` `p=0.005`, but collapsed in 2014–2019 `p=0.65–0.91` vs fixed 50/50 DLV+Bond). For A-share Dividend Low-Vol, stick to plain DCA + bond/gold quarterly allocation;
  - S&P 500 single-factor replacements (`SPHQ`, `SPLV`, `RSP`), VIX/VIX3M term-structure brakes, credit-spread brakes (`BAA10Y`, `HYG/IEF`), smart DCA (`SD1`), calendar rules (`HAL`, `TOM`), RSI(2), and domestic `513500` self-signal discrete trend rules failed;
  - Gold trend filtering on IV20 (`test_iv20_gold_defense.py`) degraded diversification, whereas conditional gold-trend gating on S2 defensive sleeves (`S2_GOLD_TREND`) serves only as a gold-bear-market safeguard;
  - Retail short-selling strategies across US equities (`SPY`/`QQQ`, across retail margin, daily-reset inverse ETFs `SH`/`PSQ`, and institutional futures), Crypto (`BTC-USD`/`ETH-USD`, even under favorable `-3%/yr` perp funding), A-shares (`H00300`/`510500`/`159915`), fast tactical 50d+ST shorts, and cross-asset market-neutral pairs (`QQQ/SPY`, `BTC/ETH`) all failed (`docs/notes/short-selling-challenge-2026-11-23-review.md`): 95%–100% of SPY's top-20 single-day rallies occur below the 200d SMA, shorting lost `0/25` starting years on SPY and `0/10` on BTC vs plain cash defense (`p = 0.50–0.97`), and optimal short allocation is `0%` (use cash or Gold/Bond+Gold shields instead);
  - Crypto perpetual contracts (funding drag) and non-dividend tokenized US stocks materially erode long-term S&P 500 compounding;
  - Standalone gold myths falsified (`docs/notes/gold-enhance-2026-11-23-review.md`): gold-miner ETFs (`GDX`: 3.6% CAGR / `-80.6%` DD), 2x leveraged gold ETFs (`UGL`: 5.1% vs 1x 6.0% / `-75.9%` DD), Zero-Lag MAs on gold (`DEMA`/`ZLEMA` `p=0.80`), gold mean-reversion (`RSI`/`Bollinger`/`Reverse-MA`) & budget-neutral smart DCA, single macro-factor gold timing (`TIP` real-yield proxy / `DXY` / `TIP÷IEF` breakeven, severely whipsawed in 2022–2025 central-bank bull), calendar seasonality timing, and gold/silver momentum chasing (`GS_DUAL_MOM`).
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
