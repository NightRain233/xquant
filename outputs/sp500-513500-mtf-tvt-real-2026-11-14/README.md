# 513500 实际人民币口径复测（2026-11-14）

本目录把 MTF-3 和 TVT-50 迁移到真实境内 513500 的人民币收盘价格。研究区间为 2014-10-08 至 2026-09-30；信号使用已完成的 SPY 收盘，按中国交易日可见的最新信号，在下一次 513500 收盘执行；现金年化代理 2%，另测单边 30bp。

513500 的实际交易价格已经包含人民币汇率、二级市场溢价/折价、跟踪误差和基金费用，因此回测不再把这些因素重复乘入价格。`rmb_fx_premium_diagnostic.csv` 和 `diagnostic_summary.json` 保存 CNY=X 与历史估算溢价，仅用于解释和审计。溢价数据的发布时点并不完全可核验，不能当成历史上可实时成交的 IOPV。

- `summary_q3_q5.csv`：Q3/Q5 主结果
- `annual_returns.csv`、`monthly_returns.csv`、`segments.csv`：年度、月度和分段表现
- `dca_summary.csv`、`dca_windows.csv`、`dca_windows_summary.csv`：定投 XIRR、浮亏和 5/10 年窗口收益回撤比
- `sensitivity.csv`、`rmb_fx_premium_diagnostic.csv`：参数、汇率、溢价敏感性/诊断
- `config.json`：数据口径、成本和输入哈希

复现：

```bash
uv run python -I scripts/research_513500_mtf_tvt_real_2026_11_14.py
```
