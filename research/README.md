# Notebook 研究索引

所有实践 Notebook 位于 [`research/notebooks/`](notebooks/)。每个 Notebook 的第一个代码单元会把工作目录切换到仓库根目录，因此原有 `outputs/`、`docs/` 和 `scripts/` 相对路径保持不变。请从仓库根目录运行 `uv sync`，再用 `uv run jupyter lab` 打开。

## 当前核心实验

普通读者先读[策略专题](../docs/strategies/two-three-asset.md)和[一次性投入／定投持有体验](../docs/strategies/holding-experience.md)，再进入下面的Notebook与日期报告。

先从这五项近期实验及其复核报告开始；它们是当前研究入口，不代表已证明的实盘策略：

1. [纯三资产核心（2026-10-03）](notebooks/three-asset-core-2026-10-03-practice.ipynb) · [复核](../docs/notes/three-asset-core-2026-10-03-review.md)
2. [纳指与黄金消融（2026-10-03）](notebooks/nasdaq-gold-ablation-2026-10-03-practice.ipynb) · [复核](../docs/notes/nasdaq-gold-ablation-2026-10-03-review.md)
3. [定投比较（2026-10-04）](notebooks/dca-comparison-2026-10-04-practice.ipynb) · [复核](../docs/notes/dca-comparison-2026-10-04-review.md)
4. [境内ETF小额账户（2026-10-04）](notebooks/domestic-etf-small-account-2026-10-04-practice.ipynb) · [复核](../docs/notes/domestic-etf-small-account-2026-10-04-review.md)
5. [ETF分红估值修正（2026-10-04）](notebooks/etf-dividend-valuation-2026-10-04-practice.ipynb) · [复核](../docs/notes/etf-dividend-valuation-2026-10-04-review.md)

分红修正报告已确认交付，三组合及其20日逆波动结果应先看该报告。它修订了510300的历史分红会计口径；涉及510300的旧实验需逐项核对实际代码与价格字段，不能自动视为已经继承修订。海外ETF估值监测目前只有0/20个有效交易日，尚未验证过滤暂停频率或可靠盘中估值区间。

更完整的策略脉络、BTC卫星、多资产模型、Core90/Bull10历史账本和旧实验入口见[策略研究索引](../docs/strategies/research-index.md)。

## 2026-10-18 趋势跟踪与价格口径复核

这一批没有单独的 Notebook，结论在复核报告里，数据和脚本在对应的 `outputs/` 与 `scripts/`。先读[温斯坦测试总结](../docs/notes/weinstein-summary-2026-10-18.md)。

| 实验 | 报告 | 输出 |
|---|---|---|
| 温斯坦 · A 股行业 ETF | [复核](../docs/notes/weinstein-etf-stage-2026-10-18-review.md) | [outputs](../outputs/weinstein-etf-stage-2026-10-18/README.md) |
| 温斯坦 · 美股行业 ETF 轮动 | [复核](../docs/notes/weinstein-us-sector-2026-10-18-review.md) | [outputs](../outputs/weinstein-us-sector-2026-10-18/README.md) |
| 温斯坦 · 单个指数与 BTC 快速测试 | 见总结 | [outputs](../outputs/weinstein-quick-checks-2026-10-18/README.md) |
| 红利低波 + 中证2000 | [复核](../docs/notes/dividend-lowvol-csi2000-2026-10-18-review.md) | [outputs](../outputs/dividend-lowvol-csi2000-2026-10-18/README.md) |
| BTC 卫星价格口径修正重跑 | [复核](../docs/notes/btc-satellite-corrected-prices-2026-10-18-review.md) | [outputs](../outputs/btc-satellite-corrected-prices-2026-10-18/README.md) |

## BTC SuperTrend 研究线

建议按以下顺序阅读：

1. [Q3：RiskParity 与 BTC](notebooks/q3-riskparity-btc-practice.ipynb)
2. [Q6：动量、趋势与 RiskParity](notebooks/q6-momentum-trend-riskparity-practice.ipynb)
3. [Q7：SuperTrend 稳健性](notebooks/q7-supertrend-riskparity-robustness-practice.ipynb)
4. [Q8：BTC 趋势卫星](notebooks/q8-btc-trend-satellite-practice.ipynb)
5. [Q9：BTC SuperTrend 卫星稳健性](notebooks/q9-btc-supertrend-satellite-robustness-practice.ipynb)
6. [Q10：实盘化压力测试](notebooks/q10-live-readiness-stress-practice.ipynb)

Q10 是当时阶段的研究记录，不是当前推荐。其 7.5% BTC 卫星 19.49% 年化来自旧 next-close 时序实现，把成交前收益记入新权重；该数字不能作为当前收益。后续修正与未关闭交付问题见[策略研究索引](../docs/strategies/research-index.md)。

## Theme Alpha 研究线

基础结构与实盘化研究：

1. [Q1：强主题筛选](notebooks/theme-alpha-q1-strong-theme-screening-practice.ipynb)
2. [Q1：主题增强验证](notebooks/theme-alpha-q1-theme-enhancement-validation-practice.ipynb)
3. [Q2：低波趋势 Walk-Forward](notebooks/theme-alpha-q2-lowvol-trend-walkforward-practice.ipynb)
4. [Q3：结构稳健性](notebooks/theme-alpha-q3-structure-robustness-practice.ipynb)
5. [Q4：核心—卫星组合](notebooks/theme-alpha-q4-core-satellite-practice.ipynb)
6. [Q5：熊市压力](notebooks/theme-alpha-q5-bear-market-stress-practice.ipynb)
7. [Q6：防守基准补全](notebooks/theme-alpha-q6-bear-defense-benchmark-completion-practice.ipynb)
8. [Q7：生产现实性](notebooks/theme-alpha-q7-production-realism-practice.ipynb)
9. [Q8：信号稳定与准实盘规则](notebooks/theme-alpha-q8-signal-live-readiness-practice.ipynb)

SuperTrend 交叉验证与长样本：

1. [Q11：SuperTrend 与 LVT 交叉验证](notebooks/q11-supertrend-lvt-cross-validation-practice.ipynb)
2. [Q12：SuperTrend 替代 LVT 趋势确认](notebooks/q12-supertrend-replace-lvt-trend-confirmation-practice.ipynb)
3. [Q12：长样本与代理验证](notebooks/theme-alpha-q12-long-sample-proxy-validation-practice.ipynb)

Q12 的结论记录了当时阶段的候选，不应读作当前默认推荐。该历史主题线与510300分红修订的承接边界见[策略研究索引](../docs/strategies/research-index.md)。

## 新实验约定

新 Notebook 使用 `research/notebooks/<slug>-practice.ipynb`，并同时创建：

- `outputs/<slug>/`
- `docs/notes/<slug>-review.md`

跨实验复用的计算放入 `src/xquant/`，不要继续复制到新的 Notebook。

## Trading ledger 复现包

`trading-ledger-2026-09-05/` 保存交易仓库执行修复对应的历史证据：原始 xquant 研究恢复、
当前 Core90 2.1.0 合同基准、三资产变种的统一账本比较，以及封存行情和审计产物。
回测编排在本仓库，成交和 NAV 通过同级 `trading/backend/portfolio_strategies` 的执行内核完成；
具体边界、运行命令和限制见该目录的 [包说明](trading-ledger-2026-09-05/README.md)。
