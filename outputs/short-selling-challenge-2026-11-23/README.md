# Outputs: `short-selling-challenge-2026-11-23`

Reproducible offline outputs for the formal research study **"做空策略实战挑战：美股、加密与 A 股全周期检验（2026-11-23）"**.

- **Script**: `scripts/research_short_selling_2026_11_23.py`
- **Notebook**: `research/notebooks/short-selling-challenge-2026-11-23-practice.ipynb`
- **Review Note**: `docs/notes/short-selling-challenge-2026-11-23-review.md`
- **Core Engine**: `src/xquant/sp500_lab.py` (`run_long_short_overlay`)

## Files

| File | Description |
|---|---|
| `config.json` | Frozen windows, wrappers, crypto funding stress rates, and pre-registered pass bars |
| `self_checks.json` | Anti-lookahead perturbation checks, cash conservation (`< 1e-12`), fast-XIRR parity (`< 1e-15`), liquidation flags, and SHA256 hashes of all source datasets |
| `short_market_physics.csv` | First-principles short-selling physics across SPY, QQQ, BTC, ETH, H00300, and 159915 (secular drift, bear-market squeeze concentration, conditional bear return vs friction) |
| `summary_us_short.csv` | Full 2000–2026 + 2000–2012 + 2013–2026 metrics for US SPY & QQQ across Retail Margin, 1x Inverse ETF (`SH`/`PSQ`), and Institutional Futures wrappers |
| `us_short_vs_shields_2005.csv` | Head-to-head comparison of SPY Long/Short vs Cash, Gold (`GLD`), and Bond+Gold shields on real GLD window (2005–2026 & 2013–2026) |
| `summary_crypto_short.csv` | BTC (2015–2026, early/mature split) and zero-tuning ETH (2018–2026) standalone short & long/short metrics at 30bp + 3% borrow |
| `crypto_funding_cost_stress.csv` | Crypto sensitivity matrix across `+6% / +3% / 0% / -3%` annualized borrow/funding and `30bp / 50bp` trading costs |
| `summary_ashare_short.csv` | A-share (`H00300`, `510500`, `159915`) short-selling reality check at 0% ideal friction vs 8.5% retail margin borrow (`融券`) |
| `pairs_relative_short.csv` | Cross-asset market-neutral relative-value long/short pairs (`QQQ/SPY` and `BTC/ETH`) |
| `crisis_anatomy.csv` | Episode-by-episode return & drawdown breakdown across 2000–2026 US & Crypto bear markets and V-bottom squeeze traps |
| `permutation_short_leg.csv` | 200-trial circular-shift permutation tests specifically isolating the short leg across 19 strategy/asset combinations |
| `short_size_sensitivity.csv` | Parameter sweep over short sizing (`0%` to `-100%`) across SPY, QQQ, BTC, and ETH |
| `rolling_dca_short_vs_cash.csv` | Exact rolling 10Y (SPY/QQQ) and 5Y (BTC) monthly DCA XIRR & ratio comparison |
| `rolling_starts_annual.csv` | Every annual starting year (SPY 2000–2024, BTC 2015–2024) comparing Cash vs Long/Short |

## Re-run Offline

```bash
.venv/bin/python -I scripts/research_short_selling_2026_11_23.py
```
