# btc-satellite-corrected-prices-2026-10-18

用比例前复权（总回报）核心 ETF 价格重跑 `strategy-healthcheck-clock-correction-2026-10-03` 的 BTC 卫星研究（BTC_0/5/7.5/10）。BTC 数据、参数、时序、成本冻结，只换 510300/513100/518880 价格。报告：`docs/notes/btc-satellite-corrected-prices-2026-10-18-review.md`。旧报告与旧输出未改动。

## 文件
- `config.json`：冻结项与改动项。`data_manifest.json`：数据来源、区间、SHA256（含所有输出）。`self_checks.json`：自检。
- `inputs/`：TickFlow 原始响应（forward 为主，none 仅审计）。`market_data/`：回测用 parquet（三只修正 ETF + 复制的 BTC）。
- `summary.csv`、`annual_returns.csv`、`rolling_3y_5y.csv`、`nav_BTC_*.csv`、`fills_BTC_*.json`：新口径结果。
- `old_vs_new.csv`、`annual_old_vs_new.csv`、`rolling_old_vs_new.csv`：新旧对比。`btc_increment.csv`、`btc_increment_by_year.csv`：BTC 增益。
- `price_consistency.csv`、`price_additive_vs_corrected_top_diffs.csv`、`core_target_weights_old_vs_new.csv`、`signals_corrected.json`：价格与权重差异。
- `harness_reproduction.csv`：旧价格重跑复现旧净值。`inventory.csv`：加法复权旧研究盘点。
- 代码：`scripts/rerun_btc_satellite_corrected_prices.py`、`scripts/finalize_btc_satellite_corrected_prices.py`（需 `../trading/backend/.venv`，依赖 `portfolio_strategies`、`exchange_calendars`）。
