# Trading ledger 2026-09-05

这是 2026-09-05 交易账本修复工作的可复现研究包，集中保存恢复的原始 xquant 研究、
修复后 Core90 主策略基准、三资产变种比较，以及完整 CSV、审计 JSON 和封存行情压缩包。

研究层由本仓库负责：读取封存行情、组织回测、比较阶段和成本压力，并保存结果。
执行层由 sibling trading 仓库负责：`backend/portfolio_strategies` 中的
`NextOpenPaperEngine`、账本、策略注册表和共享 `advance_current_contract` 循环是唯一成交、
持仓、现金和 NAV 的实现。这样研究产物可以独立归档，生产代码也不会被历史 CSV 和大压缩包淹没。

## 目录

- `core90_recovery_2026_09_05/`：原始 xquant 研究恢复、封存行情和旧结果核验。
- `core90_current_contract_2026_09_05/`：当前 `core90_ma200_bull10` 2.1.0 合同的完整重算、
  逐笔账本审计和旧版差异。
- `three_asset_variant_comparison_2026_09_05/`：纯三资产、现金保留、整体 SuperTrend 和延迟
  压力等同账本比较。

## 运行边界

回放命令显式接收 `--trading-root`，默认指向同级 trading 目录，也可通过 `TRADING_ROOT`
覆盖。研究代码只使用封存行情，不访问线上行情、不读取生产账本，也不会激活或部署策略。
`source_bundle.zip` 同时保存本次运行使用的 trading 源文件和 xquant 编排脚本，manifest 记录
两边的 SHA256 与 trading 基础提交。

trading 仓库保留轻量的合成执行 golden fixture 和 `test_research_replay.py`，用于确认研究输入仍然
走生产执行内核；历史 CSV、SQLite、原始压缩包和研究测试都在本包内。
