# Gold Quantitative Enhancement Research Outputs (`gold-enhance-2026-11-23`)

Reproducible artifacts for the 9-module + 5-deep-dive gold quantitative enhancement study spanning 55 years of post-Bretton-Woods monthly gold (1972–2026), 25 years of COMEX futures (`GC=F`/`SI=F`), 21 years of real US ETFs (`GLD`/`IAU`/`SLV`/`GDX`/`UGL`/`IEF`/`TIP`/`TLT`/`SPY`), 12.3 years of domestic RMB ETFs (`518880`/`511010`/`511260`), and 6.7 years of crypto gold (`PAXG`/`XAUT`) through `2026-11-20`.

## Reproduction Commands

```sh
# 1. Fetch & freeze market cache (network required only if cache/ is absent)
.venv/bin/python scripts/fetch_gold_enhance_data_2026_11_23.py

# 2. Run Round-1 9-module research study (offline sandbox)
.venv/bin/python -I scripts/research_gold_enhance_2026_11_23.py

# 3. Run Round-2 5-item deep-dive verification (offline sandbox)
.venv/bin/python -I scripts/research_gold_enhance_deepdive_2026_11_23.py
```

## Key Output Files

- **Config & Integrity**: `config.json`, `fetch_manifest.json`, `self_checks.json` (`anti_lookahead_max_diff = 0.0`, `max_cash_residual = 8.88e-16`, `cross_market_min_lag_days = 1`), `gold_live_snapshot_2026_11_20.json`
- **Module 1 (Physics & Seasonality)**: `gold_physics_fingerprint.csv`, `gold_seasonality_audit.csv`
- **Module 2 (55Y Long Cycle)**: `gold_55y_long_cycle.csv`, `dd2_55y_rate_regimes.csv`, `gold_55y_long_cycle.png`
- **Module 3 & 4 (GLD Single-Asset Arena, Permutation, 2x UGL, Parameter Plateau, Rolling Starts)**: `gold_gld_strategies_summary.csv`, `gold_gld_permutation.csv`, `gold_gld_key_periods.csv`, `gold_ugl_2x_leverage.csv`, `gold_param_sensitivity.csv`, `gold_rolling_starts.csv`, `dd1_tvt_low_turnover_gld.csv`, `dd1_tvt_param_plateau.csv`
- **Module 5 (Macro Factors)**: `gold_macro_timing.csv`
- **Module 6 (Precious Metals Rotation & 25Y GSR Audit)**: `gold_precious_metals_rotation.csv`, `dd3_gsr_25y_audit.csv`
- **Module 7 (Cross-Asset Shields & Digital Gold BTC)**: `gold_cross_asset_shields.csv`, `dd4_gold_btc_regimes.csv`
- **Module 8 (Rolling 5Y/10Y DCA & Smart DCA)**: `gold_dca_rolling.csv`, `gold_dca_smart_budget_neutral.csv`
- **Module 9 (Domestic RMB 518880 & Crypto PAXG/XAUT)**: `gold_domestic_518880.csv`, `dd1_tvt_low_turnover_cn518880.csv`, `gold_crypto_paxg_audit.csv`, `gold_fx_and_crypto_summary.json`
- **Charts**: `gold_gld_21y_nav_dd.png`, `gold_55y_long_cycle.png`, `gold_2026_crash_zoom.png`, `gold_tvt50_and_cn518880.png`

Full plain-Chinese review: [`docs/notes/gold-enhance-2026-11-23-review.md`](../../docs/notes/gold-enhance-2026-11-23-review.md)  
Practical reader guide: [`docs/strategies/gold-enhance.md`](../../docs/strategies/gold-enhance.md)
