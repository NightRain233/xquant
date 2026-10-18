# weinstein-quick-checks-2026-10-18

单一标的的趋势规则补充测试，补齐温斯坦系列：美股指数（SPY、QQQ）、A 股指数（沪深300全收益、红利低波全收益、中证2000）和 BTC。总结见 [温斯坦测试总结](../../docs/notes/weinstein-summary-2026-10-18.md)。

## 复现

```sh
python scripts/research_weinstein_quick_checks.py
```

需要 pandas、numpy、pyarrow。脚本不联网，只读下列已保存的快照（SHA256 见 `data_manifest.csv`）：

| 输入 | 来源 |
|---|---|
| SPY | `outputs/weinstein-us-sector-2026-10-18/cache/yf_SPY.csv` |
| QQQ | `cache/yf_QQQ.csv`，yfinance `auto_adjust=True`，2026-10-18 抓取 |
| 沪深300全收益、红利低波全收益、中证2000 | `outputs/dividend-lowvol-csi2000-2026-10-18/cache/csindex_*.csv`（中证指数官网，经 akshare） |
| BTC-USD | `outputs/btc-satellite-corrected-prices-2026-10-18/market_data/BTC-USD.parquet`（时序修正研究的冻结数据） |

`cache/` 被 Git 忽略。干净克隆需要先运行对应研究的取数脚本，或另行提供这些快照。

## 规则

- **站上 30 周线持有**：周收盘高于 30 周均线就持有。
- **温斯坦**：周收盘高于 30 周均线、且均线比 4 周前高时买入；周收盘跌破均线时卖出。
- **SuperTrend**：SMA-ATR(10) × 3，日线或周线；向上时持有。"周线+日线"要求两者都向上。
- 信号只用已完成的 K 线，下一个交易日开盘成交。中证全收益指数没有开盘价，改为下一个交易日收盘成交，略偏保守。
- 成本：美股和 A 股单边 10bp，BTC 单边 30bp。空仓现金收益按 0 计。

## 文件

| 文件 | 内容 |
|---|---|
| `research_summary.csv` | 每个标的、每种规则的年化、最大回撤、年均换仓次数、持仓时间占比 |
| `period_windows.csv` | 熊市、牛市等关键时段的收益和回撤 |
| `data_manifest.csv` | 输入文件路径和 SHA256 |

## 限制

这些是会话中的快速验证，比两份行业 ETF 研究的自检少：没有逐笔成交表，没有截断数据重算信号的检查。测试 `tests/test_weinstein_quick_checks.py` 只覆盖成交时点、成本、均线上翘条件和休市周处理。QQQ 起点在 2000 年泡沫顶部附近，会放大买入持有的回撤；BTC 起点 2015 年处于低位，年化数字不能当作未来预期。
