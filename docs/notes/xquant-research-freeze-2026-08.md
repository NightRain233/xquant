# xquant 研究与回测冻结清单（2026-08）

## 冻结结论

本轮研究资产可以提交并冻结为“研究基线”，但不是把任何一组全样本最优参数宣布为实盘定稿。冻结的含义是：信号定义、SuperTrend、point-in-time 选池、交易执行、成本、仓位上限和评判指标固定；后续新数据只用于前向纸面跟踪和预先登记的增量检验。

## 已落文档的实验

| 实验 | 主要问题 | 复盘文档 | Practice Notebook | 结果目录 | 冻结状态 |
|---|---|---|---|---|---|
| Unified Scan Policy v2 事件研究 | breakout / pullback / compression 的事件级证据 | `unified-scan-policy-v2-event-study-review.md` | 事件研究由脚本编排，暂无单独 Notebook | `outputs/unified-scan-policy-v2/`、`outputs/unified-scan-policy-v2-breakout-r5/` | 冻结为事件研究，不把 compression 当正式策略 |
| scan_v2_right_side_5 组合 | 当前观察池与历史 PIT 选池的策略级差异 | `scan-v2-right-side-5-portfolio-review.md` | `q13-scan-v2-right-side-5-portfolio-practice.ipynb` | `outputs/scan-v2-right-side-5-portfolio/` | 冻结为研究基线，正式 breakout 仅 paper-only |
| scan_v2_right_side_5 PIT 选池 | 当前47、冻结历史选池、滚动月度 PIT 的幸存者偏差 | `scan-v2-right-side-5-pit-universe-review.md` | `q14-scan-v2-pit-universe-practice.ipynb` | `outputs/scan-v2-right-side-5-pit-universe/` | 冻结选池口径，不再用完整样本调参 |
| 全部 bull flip 长样本 | 2015–2026 信号收益与 34.08% CAGR 的拆解 | `all-bull-flip-long-sample-review.md`、`policy-eligible-bull-flip-strategy-and-backtest.md` | `q15-all-bull-flip-long-sample-practice.ipynb` | `outputs/scan-v2-all-bull-flip-long-sample/` | 冻结 21.09% 长样本基线，保持进攻型研究定位 |
| Bull flip 防守结构 | MA200 新仓准入、RiskParity 核心＋卫星 | `all-bull-flip-defense-review.md` | `q16-all-bull-flip-defense-practice.ipynb` | `outputs/scan-v2-all-bull-flip-defense/` | 冻结原始组合与 MA200 90/10 交叉结果，继续纸面并行 |

## 应提交与不应提交

应提交：上述脚本、`src/xquant/` 共用实现、测试、复盘文档、practice Notebook、候选目录，以及每个结果目录中支持结论的 CSV/JSON/图表快照。

不应提交：可重新下载的原始行情缓存、provider 状态、锁文件和调试中间文件。`outputs/**/market_data/` 与 `data/.provider-state/` 已加入 `.gitignore`。结果快照保留了输入路径、样本窗口、参数和审计摘要，足以复核结论；需要完整重跑时重新获取行情即可。

## 冻结后的规则

- 不在 2015–2026 完整样本上继续搜索 SuperTrend、MA 窗口、ADX/MACD、卫星比例或选池阈值。
- 保持次日有效 Open、真实 SuperTrend 翻空退出、成本和仓位上限不变。
- 原始核心90/10、80/20、70/30 与核心90/MA200-bull10 并行纸面跟踪；不能把 MA200 90/10 的结果外推到 20% 或 30%。
- 新研究必须有独立 slug、复盘文档、结果快照和可运行测试；若改变策略定义，另开实验，不覆盖冻结结果。

## 验证记录

冻结前已运行 Python 测试，当前 **51 项全部通过**；Notebook JSON、Python 编译和 `git diff --check` 也已通过。提交前应再次运行同一组测试，并在提交说明中记录结果窗口和数据快照日期。
