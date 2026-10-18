# weinstein-etf-stage-2026-10-18

简化版温斯坦"第二阶段"周线趋势策略在 A 股 ETF 池上的冻结规则回测。复盘见
`docs/notes/weinstein-etf-stage-2026-10-18-review.md`。本实验与主账户策略无关，没有改动任何主策略代码或已有产物。

## 复现

```sh
# 1) 抓取（联网一次；原始响应写入 cache/，已被 .gitignore 忽略）
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with requests python scripts/fetch_weinstein_etf_data.py
# 2) 回测（离线；会先核对 cache/ 原始文件 SHA256）
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 python scripts/research_weinstein_etf_stage.py
# 3) 单元测试
PYTHONPATH=src uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pytest==9.0.2 python -m pytest tests/test_weinstein_stage.py -q
```

项目 `.venv` 同步需要访问 GitHub 上的 open-xquant 依赖，本机不可达，因此用 `--no-project` 临时环境；未改动 `uv.lock`。

## 数据

- 来源：TickFlow 免费接口 `/v1/klines/batch`，日线，2013-01-01 至 2026-10-16，2026-10-18 抓取。
- 收益口径：`adjust=forward`（比例前复权，等价于现金分红再投资、份额拆分已抹平）。同时抓了 `adjust=none` 原价，仅用于核对分红/拆分事件（`data_manifest.csv` 的 `adjustment_event_days`）。
- 没有使用仓库已有的 `strategy-healthcheck-2026-10-02/market_data` 冻结快照：它是 `forward_additive`（加法前复权），本次核对发现与比例复权的单日收益差最大达 28.7 个百分点（510880），会扭曲均线和涨幅。
- 每个原始文件的 SHA256 见 `fetch_manifest.json`，回测脚本运行时逐一校验。
- 池子：`trading/backend/universes/a_share_etf_core.json` 共 28 只，剔除跟踪港股的 513010/513120/513910，剩 25 只。是"今天的池子"，有幸存者/选择偏差。

## 文件

| 文件 | 内容 |
|---|---|
| `config.json` | 冻结参数、成本、区间、熊市窗口、敏感性网格 |
| `fetch_manifest.json` | 抓取记录与原始文件 SHA256 |
| `data_manifest.csv` | 每只 ETF 的数据起止、首个可交易信号周、是否纳入 |
| `research_summary.csv` | 主策略 + 三个对照的全部指标（含熊市窗口） |
| `annual_returns.csv` | 每年收益（含 20 周敏感性一列） |
| `bear_windows.csv` | 2015/2018/2022/2021-24 熊市窗口收益和区间内回撤 |
| `sensitivity.csv` | 20/26/30/40 周均线、最多 3/8 只、成本翻倍；仅作敏感性检查，不用于选参数 |
| `trades.csv` / `trades_ma20.csv` | 30 周主策略 / 20 周敏感性的逐笔买卖（`status=open` 为期末未平仓，按最后收盘估值、未扣卖出成本） |
| `fills.csv` | 主策略每笔成交（信号周、成交日、开盘价、成交价） |
| `strategy_yearly_activity.csv` | 主策略每年新开仓数、胜率、平均敞口 |
| `nav_daily.csv` | 四条净值（起始 1.0）与主策略每日敞口、持仓数 |
| `latest_signal.csv` | 截至 2026-10-16 周线收盘的各 ETF 条件状态（仅供学习，不是交易建议） |
| `self_checks.json` | 自检：现金+持仓=净值、成交都在信号后下一交易日开盘、截断数据重算信号不变 |
