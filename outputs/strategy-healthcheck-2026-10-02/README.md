# Strategy health check — 2026-10-02

This directory contains an independent review of frozen strategy parameters using an isolated market snapshot. The replay and execution checks use the recorded strategy definitions and do not modify production configuration. The snapshot contains 83 parquet market files. A-share data and 2800.HK end on 2026-09-30; most other overseas assets, BTC, and FX data end on 2026-10-01. The frozen core replay ends on the last A-share session, 2026-09-30. The fetch cutoff (`--as-of 2026-10-01`) is one day earlier than the review as-of timestamp (`2026-10-02`).

## Contents

- `market_data/`: market snapshot used by the review; `cache/` and `fetch_*.json`: provider responses and fetch manifests.
- `replay/theme/`, `replay/btc/`: frozen-parameter replay outputs, summaries, monthly and annual returns, cost sensitivity, and execution audits.
- `next_open/`: native next-open core results, fills, summary, and audit; Bull10 uses the same directory and writes separate `summary_bull.csv` and `audit_bull.json` files.
- Root CSV/JSON files: source coverage and revisions, overlap review, asset observations, BTC correlations, and legacy execution diagnostics.
- `multi_asset_full.md` and `multi_asset_full.json.gz`: complete 96-variant multi-asset review and its compressed machine-readable result. The uncompressed JSON is retained locally and ignored by Git; the notebook and renderer can also read the compressed result.
- [Practice notebook](../../research/notebooks/strategy-healthcheck-2026-10-02-practice.ipynb): tables and diagnostics read from these saved outputs.
- [Review note](../../docs/notes/strategy-healthcheck-2026-10-02-review.md): research context and methodology.

## Reproduction

Run commands from the `xquant/` directory. These use the repository's trading environment. The fetcher only requests missing snapshot symbols and skips existing parquet files.

```bash
PY=../trading/backend/.venv/bin/python
OUT=outputs/strategy-healthcheck-2026-10-02

$PY scripts/fetch_strategy_healthcheck_data.py --as-of 2026-10-01 --source tickflow --output "$OUT"
$PY scripts/fetch_strategy_healthcheck_data.py --as-of 2026-10-01 --source yahoo --output "$OUT"
$PY scripts/review_frozen_strategies.py --snapshot "$OUT/market_data" --output "$OUT/replay" --as-of 2026-10-02 --families theme btc
$PY scripts/review_next_open_strategies.py --snapshot "$OUT/market_data" --output "$OUT/next_open" --end 2026-09-30
$PY scripts/strategy_healthcheck_diagnostics.py --root "$OUT"
```

For the Bull10 next-open result, reuse the same output directory; its summary and audit use the `bull` suffix:

```bash
$PY scripts/review_next_open_strategies.py --snapshot "$OUT/market_data" --output "$OUT/next_open" --end 2026-09-30 --bull-only
```

The multi-asset full research command also runs from `xquant/`; set `PYTHONPATH` to the sibling backend and write both machine-readable results and the report into this run directory:

```bash
PYTHONPATH=../trading/backend $PY ../trading/scripts/research_multi_asset_balanced_portfolio.py \
  --data-dir "$OUT/market_data" --end 2026-09-30 \
  --output "$OUT/multi_asset_full.json" --report "$OUT/multi_asset_full.md"
```

Reproduction requires the same frozen inputs and should retain the generated fetch manifests and source hashes with the outputs.

After all replays complete, rerun the diagnostics to include Bull10's overlap audit, then render the review:

```bash
$PY scripts/strategy_healthcheck_diagnostics.py --root "$OUT"
$PY scripts/render_strategy_healthcheck_review.py
```

To refresh the portable full result after rerunning the multi-asset study:

```bash
gzip -c "$OUT/multi_asset_full.json" > "$OUT/multi_asset_full.json.gz"
```

This material reports implementation checks and historical diagnostics; it does not provide investment conclusions.
