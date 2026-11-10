# main-line-s2-filter-2026-11-10

把标普的半仓趋势规则（S2）作为过滤层放进冻结的主线（三组合加 7.5% BTC 卫星）做叠加测试。解读见 `docs/notes/main-line-s2-filter-2026-11-10-review.md`。

- `config.json`：规则、窗口、通过标准、变体清单和基准文件哈希。写于计算之前。
- `summary.csv`：各变体的年化、波动、夏普、最大回撤、收益回撤比，以及分段夏普和切换统计。
- `verdicts.csv`：C1–C5 判定。`X_all_sleeves_off50` 是事后补充，不计入判定。
- `multipliers_daily.csv`：每个变体的每日持仓乘数。
- `yearly_returns.csv`：基准、主选和事后补充的逐年收益。
- `drawdown_diagnostic.json`：基准最大回撤的峰谷日期，以及主选第一次减仓的日期。
- `selfcheck.json`：基准复现误差、成本压力和主选判定结果。
- 代码：`scripts/research_main_line_s2_filter.py`，函数在 `src/xquant/main_line_overlay.py`，测试在 `tests/test_main_line_overlay.py`。
- 输入：`outputs/btc-satellite-corrected-prices-2026-10-18/`（基准净值、每日权重和修正价格）、`outputs/tqqq-regime-switch-2026-11-10/cache/yf_QQQ.csv`（QQQ 收盘价）。
