# weinstein-us-sector-2026-10-18

把 A 股版（`weinstein-etf-stage-2026-10-18`）的温斯坦"第二阶段"周线趋势策略，原样搬到美国 SPDR 11 个行业 ETF 上回测。
规则、撮合引擎、成本、指标定义完全相同，只换了数据（yfinance）和基准（SPY）。复盘见
`docs/notes/weinstein-us-sector-2026-10-18-review.md`。没有改动 A 股版的任何输出和复盘。

## 复现

```sh
# 1) 抓取（联网一次；走系统代理 https_proxy=127.0.0.1:7890；原始 CSV 写入 cache/，已被 .gitignore 忽略）
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with yfinance python scripts/fetch_weinstein_us_sector_data.py
# 2) 回测（离线；会先核对 cache/ 原始文件 SHA256）
PYTHONPATH=src uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 python scripts/research_weinstein_us_sector.py
# 3) 单元测试（A 股版原有 7 个 + 本次新增 6 个）
PYTHONPATH=src uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pytest==9.0.2 \
    python -m pytest tests/test_weinstein_stage.py tests/test_weinstein_us_sector.py -q
```

项目 `.venv` 同步需要访问 GitHub 依赖，本机不可达，因此和 A 股版一样用 `--no-project` 临时环境；未改动 `uv.lock`。

## 数据

- 来源：Yahoo Finance，经 `yfinance 1.x`（版本号见 `fetch_manifest.json`）`Ticker.history(auto_adjust=True, actions=True)`，日线，2026-10-18 抓取。
- 区间：SPY 与 9 只老行业 ETF 1998-12-22 起（XLRE 2015-10-08 起，XLC 2018-06-19 起），到 2026-10-16（最新完整周的周五）。
- 收益口径：`auto_adjust=True`，开盘价和收盘价都按拆分和分红调整（相当于分红再投资、未扣股息预扣税）。
  2016-09 XLF 向持有人派发 XLRE 份额，Yahoo 把它记为 1.231 的"拆分"，复权序列连续。
- `^IRX`（13 周美国国债收益率，%）只用于"现金按国债计息"敏感性；主结果现金收益为 0。
- 每个原始文件的 SHA256 见 `fetch_manifest.json` / `data_manifest.csv`，回测脚本运行时逐一校验。
- 首次成交日 1999-08-16：9 只老 ETF 全部攒够 30 周均线 + 4 周斜率所需的 34 周数据（1999-08-13 那周）后的下一个交易日。
  XLRE、XLC 同样要攒满 34 周才参与。

## 文件

| 文件 | 内容 |
|---|---|
| `config.json` | 冻结参数、成本、区间、分析窗口、敏感性网格、现金口径 |
| `fetch_manifest.json` | 抓取记录（来源、yfinance 版本、代理、每个文件行数/起止/SHA256） |
| `data_manifest.csv` | 每只 ETF 的数据起止、首个可交易信号周、分红/拆分事件数、源文件与 SHA256 |
| `research_summary.csv` | 30 周主策略、20 周敏感性、三个对照的全部指标（含分时段窗口） |
| `annual_returns.csv` | 每年收益（1999 年从 08-16 起；2026 年到 10-16） |
| `period_windows.csv` | 2000-2002、2007-09 金融危机、2008、2010-2021、2020 疫情急跌/全年、2022 的收益和区间内最大回撤 |
| `sensitivity.csv` | 20/26/30/40 周均线、最多 3/5/8 只、成本翻倍；仅作敏感性检查，不用于选参数 |
| `cash_tbill_sensitivity.csv` / `cash_tbill_annual_returns.csv` | 空仓现金按 13 周国债收益率计息时的结果和每年收益 |
| `us_vs_a_share.csv` | 美股版 vs A 股版：相对各自买入持有/池子等权的年化差距、胜率、盈亏比、年均交易次数（A 股数字只读自 A 股版输出） |
| `trades.csv` / `trades_ma20.csv` | 30 周主策略 / 20 周敏感性逐笔交易（`status=open` 为期末持仓，按最后收盘估值、未扣卖出成本） |
| `trades_by_symbol.csv` | 主策略按 ETF 汇总的笔数、胜率、盈亏 |
| `fills.csv` | 主策略每笔成交（信号周、成交日、开盘价、成交价） |
| `strategy_yearly_activity.csv` | 主策略每年新开仓数、胜率、平均敞口 |
| `nav_daily.csv` | 五条净值（起始 1.0）与主策略每日敞口、持仓数 |
| `latest_signal.csv` | 截至 2026-10-16 周线收盘各 ETF 条件状态（仅供学习，不是交易建议） |
| `self_checks.json` | 自检：现金+持仓=净值、SPY 从不被买入、成交都在信号周后下一交易日开盘、截断数据重算信号不变 |
