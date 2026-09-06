# Theme Alpha LVT Recent 3-Month Review

Date: 2026-09-06

## 目的

应用户要求，补做最新三个月的独立 LVT 复核。Q12 冻结研究不改写；本次使用当前交易实现同口径的隔离 TickFlow 快照，单独比较全仓 Expanded LVT、Core80/LVT20/Def200 Cash 和原三资产 RiskParity。

## 合约与数据

- 输入快照：`/Users/zz/Desktop/Code/zsd/xquant/outputs/def200-cash-minimum-capital-2026-09-06-v2/market_snapshot`；共同收盘截至 `2026-09-04`，共 1257 个会话。
- 价格契约：本次使用交易侧 TickFlow forward-additive 快照；Q12 冻结研究使用 yfinance auto_adjust 数据，不能把两者的 NAV 直接拼接成一条收益曲线。
- 最近三个月窗口：`2026-06-04` 至 `2026-09-04`，共 66 个收益观测；窗口起点使用前一交易日 NAV 作为归一化基准。
- 当前信号：每月 10/25 日（若非交易日取其后第一个交易日），信号收盘计算，下一交易日收盘执行。
- 当前参数：MA60、63 日动量、60 日波动率、低波 Top3、RP20、LVT cap 50%、Def200、调仓阈值 2%、单资产变化上限 15%。
- 成本按当前纸面实现的 base/asset-extra bps 计入；采用 fractional holdings 研究 NAV，不等同 100 股整数手人工成交结果。
- 最新有效信号：`2026-08-25`，市场收盘截至 `2026-09-04`，LVT 选择 `510880.SS, 518880.SS, 159930.SZ`。

## 最新三个月主结果

| Strategy | 累计收益 | 年化波动 | 最大回撤 | Sharpe | Calmar | 年化换手 | 年化成本拖累 | 水下占比 | 未修复回撤 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Original 3-asset RiskParity | -3.28% | 19.66% | -9.59% | -0.61 | -1.25 | 364.50% | 1.07% | 98.51% | -9.59% |
| Standalone Expanded LVT 100% | -5.80% | 27.84% | -14.18% | -0.73 | -1.44 | 1263.56% | 3.72% | 91.04% | -14.18% |
| Core80 + LVT20 + Def200 Cash | -3.56% | 20.48% | -8.71% | -0.63 | -1.48 | 538.17% | 1.56% | 98.51% | -8.71% |

### 2026 YTD 补充

| Strategy | 累计收益 | 最大回撤 | Sharpe | 年化换手 | 年化成本拖累 |
|---|---:|---:|---:|---:|---:|
| Original 3-asset RiskParity | 4.92% | -12.49% | 0.39 | 325.23% | 1.02% |
| Standalone Expanded LVT 100% | 16.45% | -14.18% | 1.12 | 1201.95% | 4.18% |
| Core80 + LVT20 + Def200 Cash | 7.74% | -10.73% | 0.64 | 548.09% | 1.74% |

## Q5 观察

- 本窗口月度收益、最好/最差月份、盈利因子见 `summary.csv`；逐月结果见 `monthly_returns.csv`。
- 回撤事件和恢复时间见 `drawdown_events_recent_3m.csv`。窗口最后是否仍在水下必须看“未修复回撤”，不能只看已经完成的平均恢复时间。
- 三条策略使用相同收盘、信号日、执行日、调仓阈值和成本实现；差异主要来自资产池/防守结构，不把整数手误差混进收益比较。

## cap 敏感性

本次只把 LVT 单资产 cap 作为独立敏感性轴，保持 MA、动量、Top-N、调仓与防守参数不变。详见 `cap_sensitivity_recent_3m.csv`。

| cap | Standalone LVT 累计收益 | Standalone LVT MDD | Core80/LVT20 累计收益 | Core80/LVT20 MDD |
|---:|---:|---:|---:|---:|
| 45% | -5.80% | -14.39% | -3.56% | -8.73% |
| 50% | -5.80% | -14.18% | -3.56% | -8.71% |
| 55% | -5.90% | -14.13% | -3.56% | -8.70% |

## 通俗结论

- 本次确实补到了最新三个月：独立 LVT 的最新数据不再停在 2026-06-24，而是延伸到 `2026-09-04`。
- 这只是最新三个月的增量验证，不足以推翻 Q12 长样本结论；短窗口的赢家不能自动升级为主策略。
- 最新有效 LVT 选择和信号明细在 `signals.csv`；独立 LVT 没有使用 Core 的 MA200 防守。Def200 只作用于组合里的沪深300/纳指核心仓位。
- 本次 NAV 是当前纸面引擎的 fractional replay，没有生成独立 LVT 的真实账户 forward ledger，也没有证明 8,000 元整数手可按目标成交。
- 下一步若要把独立 LVT 纳入正式观察，应为它建立单独冻结配置、单独纸面账户和独立成交台账；在此之前，Core80/LVT20/Def200 仍应作为默认实盘候选。

## 文件

- Practice notebook: `research/notebooks/theme-alpha-lvt-recent-3m-2026-09-06-practice.ipynb`
- Script: `scripts/theme_alpha_lvt_recent_3m_review.py`
- Outputs: `outputs/theme-alpha-lvt-recent-3m-2026-09-06/`
- Main table: `summary.csv`
- Signal audit: `signals.csv`
- Cost/execution events: `events.csv`
- Frozen reference preserved: `outputs/theme-alpha-q12-long-sample-proxy-validation/`
