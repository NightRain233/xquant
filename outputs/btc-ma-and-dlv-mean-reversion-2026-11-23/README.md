# Outputs: `btc-ma-and-dlv-mean-reversion-2026-11-23`

Reproducible offline outputs for the formal two-track research study **"BTC 均线家族（双均线 / 双 EMA / Zero-Lag MA）做多对比与红利低波均值回归 / 反均线策略深度研究（2026-11-23）"**.

- **Script**: `scripts/research_btc_ma_and_dlv_mean_reversion_2026_11_23.py`
- **Notebook**: `research/notebooks/btc-ma-and-dlv-mean-reversion-2026-11-23-practice.ipynb`
- **Review Note**: `docs/notes/btc-ma-and-dlv-mean-reversion-2026-11-23-review.md`
- **Shared Indicators**: `src/xquant/indicators.py` (`ema`, `dema`, `tema`, `zlema`, `wma`, `hma`, `kama`, `rsi_wilder`, `kdj`, `bollinger_zscore`)

## Files

| File | Description |
|---|---|
| `config.json` | Frozen windows, cost stress levels, cash assumptions, and pre-registered pass bars for both tracks |
| `self_checks.json` | Anti-lookahead perturbation tests across all 42 Track-1 + 24 Track-2 strategies, cash conservation (`< 1e-12`), and SHA256 hashes of source datasets |
| `track1_btc_ma_families.csv` | BTC-USD (2015–2026, Early 2015–2020 & Mature 2021–2026, 10bp/30bp/50bp cost stress) across 42 strategies: Dual SMA, Single SMA, Dual EMA, 3-Tier EMA, ZLEMA, Dual ZLEMA, 3-Tier ZLEMA, DEMA, TEMA, HMA, KAMA vs BH / ST(10,3) / `HYB_ST_MA150_B5` / `MTF3_100_200_B5` |
| `track1_eth_oos_ma_families.csv` | Zero-tuning out-of-asset ETH-USD (2018–2026 & 2021–2026 mature) evaluation across the exact same 42 MA strategies |
| `track1_btc_ma_param_grid.csv` | 60-cell `(fast, slow)` parameter grid comparing Dual SMA, Dual EMA, Dual ZLEMA, and Dual DEMA across BTC and ETH |
| `track1_btc_eth_permutation.csv` | 200-trial circular-shift permutation tests across 26 representative Track-1 strategies on BTC Full, BTC Mature (2021–2026), and ETH OOS |
| `track1_btc_rolling_dca_5y.csv` | Exact 5Y rolling monthly DCA (76 windows) across 22 Track-1 strategies on BTC-USD |
| `track2_dlv_conditional_returns.csv` | Conditional forward 5d/20d/60d/120d returns & win rates for oversold vs overbought zones (RSI6, RSI14, KDJ-J, Boll20, MA120, BIAS120/150) on H20269 (Full/14–19/20–26), 510880, and 512890 |
| `track2_dlv_mean_reversion_summary.csv` | 24 mean-reversion & reverse-MA strategies + fixed 50%/70% controls across H20269, 510880, 512890, H00300, and 510500, with matched-exposure fixed quarterly deltas, Early/Ex-15/Modern splits, 2015 crash & 2018 bear falling-knife audit, and 30bp cost stress |
| `track2_dlv_bond_paired.csv` | Core-tilt mean-reversion rules with idle cash parked in CN Treasury Bond (`511010`) vs fixed quarterly 70/30 and 50/50 DLV+Bond allocations |
| `track2_dlv_permutation.csv` | 200-trial circular-shift permutation tests across 15 representative Track-2 strategies on H20269 (Full / Early 14–19 / Ex-15 16–26), 510880, and 512890 |
| `track2_dlv_mr_dca.csv` | Budget-neutral monthly mean-reversion DCA (identical 1.0/month salary inflow) vs plain monthly DCA across H20269, 510880, and 512890 |

## Re-run Offline

```bash
.venv/bin/python -I scripts/research_btc_ma_and_dlv_mean_reversion_2026_11_23.py
```
