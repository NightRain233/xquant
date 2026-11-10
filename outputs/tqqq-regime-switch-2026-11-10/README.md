# tqqq-regime-switch-2026-11-10

Review: `docs/notes/tqqq-regime-switch-2026-11-10-review.md`.
Regenerate from the repo root (reads `cache/` here plus the SPY / ^IRX caches of `weinstein-us-sector-2026-10-18`):

    .venv/bin/python scripts/research_tqqq_regime_switch.py

`cache/yf_QQQ.csv` and `cache/yf_TQQQ.csv` were fetched with yfinance (`auto_adjust=True`) on 2026-11-10, cut at 2026-10-16.
TQQQ before 2010-02-11 is synthetic; `synthetic_tracking.csv` compares it with the real fund.
