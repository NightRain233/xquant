# Notebook 研究索引

所有实践 Notebook 位于 [`research/notebooks/`](notebooks/)。每个 Notebook 的第一个代码单元都带有 `repository-root-bootstrap` 标签并调用 `find_repo_root()` 切换工作目录到仓库根目录，确保 `outputs/`、`docs/` 和 `scripts/` 相对路径一致。请从仓库根目录运行 `uv sync`，再用 `uv run jupyter lab` 打开。

## 2026 年 11 月：标普 500 增强、国内实盘与轮动实验

普通读者先读[标普 500 增强实战指南](../docs/strategies/sp500-enhance.md)与[研究台账](../docs/research-ledger.md)，再查阅对应 Notebook 与复核报告：

1. [MTF-3 日频防抖缓冲带（±2%～3%）全面验证（2026-11-23）](notebooks/mtf3-daily-buffer-2026-11-23-practice.ipynb) · [复核](../docs/notes/mtf3-daily-buffer-2026-11-23-review.md)
2. [标普 500 四方向联合研究与统一收口（2026-11-22）](notebooks/sp500-four-directions-2026-11-22-practice.ipynb) · [总复盘](../docs/notes/sp500-four-directions-2026-11-22-review.md)
3. [513500 自身信号与 SPY 信号对照（2026-11-15）](notebooks/sp500-513500-direct-signal-2026-11-15-practice.ipynb) · [复核](../docs/notes/sp500-513500-direct-signal-2026-11-15-review.md)
4. [MTF-3 与 TVT-50 统一体检（2026-11-15）](notebooks/mtf-tvt-healthcheck-2026-11-15-practice.ipynb) · [复核](../docs/notes/mtf-tvt-healthcheck-2026-11-15-review.md)
5. [MTF-3 / TVT-50 与既有策略比较（2026-11-15）](notebooks/mtf-tvt-existing-comparison-2026-11-15-practice.ipynb) · [复核](../docs/notes/mtf-tvt-existing-comparison-2026-11-15-review.md)
6. [SPY + QQQ 组合策略（2026-11-15）](notebooks/spy-qqq-combo-2026-11-15-practice.ipynb) · [复核](../docs/notes/spy-qqq-combo-2026-11-15-review.md)
7. [Q17：聚宽核心资产轮动与黄金熊市验证（2026-11-15，归档对照）](notebooks/q17-joinquant-core-rotation-practice.ipynb) · [复核](../docs/notes/joinquant-core-rotation-2026-11-15-review.md)
8. [标普 500 新候选 MTF-3 / TVT-50（2026-11-14）](notebooks/sp500-new-enhance-2026-11-14-practice.ipynb) · [复核](../docs/notes/sp500-new-enhance-2026-11-14-review.md)
9. [513500 真实口径复测（2026-11-14）](notebooks/sp500-513500-mtf-tvt-real-2026-11-14-practice.ipynb) · [复核](../docs/notes/sp500-513500-mtf-tvt-real-2026-11-14-review.md)
10. [QQQ 新增强规则（2026-11-14）](notebooks/qqq-new-enhance-2026-11-14-practice.ipynb) · [复核](../docs/notes/qqq-new-enhance-2026-11-14-review.md)

*(2026-11-05 与 2026-11-10 的首轮标普增强、参数敏感性、持有体验、境内溢价、主线 S2 过滤和 TQQQ 研究采用“脚本 + 输出 + 复核笔记”形式，无单独 Notebook，入口见[研究台账](../docs/research-ledger.md)。)*

## 当前核心实验（三资产主线基线）

普通读者先读[两组合与三组合](../docs/strategies/two-three-asset.md)和[一次投入／定投持有体验](../docs/strategies/holding-experience.md)，再进入下面的 Notebook 与复核报告：

1. [纯三资产核心（2026-10-03）](notebooks/three-asset-core-2026-10-03-practice.ipynb) · [复核](../docs/notes/three-asset-core-2026-10-03-review.md)
2. [纳指与黄金消融（2026-10-03）](notebooks/nasdaq-gold-ablation-2026-10-03-practice.ipynb) · [复核](../docs/notes/nasdaq-gold-ablation-2026-10-03-review.md)
3. [定投比较（2026-10-04）](notebooks/dca-comparison-2026-10-04-practice.ipynb) · [复核](../docs/notes/dca-comparison-2026-10-04-review.md)
4. [境内 ETF 小额账户（2026-10-04）](notebooks/domestic-etf-small-account-2026-10-04-practice.ipynb) · [复核](../docs/notes/domestic-etf-small-account-2026-10-04-review.md)
5. [ETF 分红估值修正（2026-10-04）](notebooks/etf-dividend-valuation-2026-10-04-practice.ipynb) · [复核](../docs/notes/etf-dividend-valuation-2026-10-04-review.md)

更完整的策略脉络、BTC 卫星、历史归档和证据边界见[策略研究索引](../docs/strategies/research-index.md)。

## 2026-10-18 趋势跟踪与价格口径复核

这一批采用脚本 + 报告形式，先读[温斯坦测试总结](../docs/notes/weinstein-summary-2026-10-18.md)：

| 实验 | 报告 | 输出 |
|---|---|---|
| 温斯坦 · A 股行业 ETF | [复核](../docs/notes/weinstein-etf-stage-2026-10-18-review.md) | [outputs](../outputs/weinstein-etf-stage-2026-10-18/README.md) |
| 温斯坦 · 美股行业 ETF 轮动 | [复核](../docs/notes/weinstein-us-sector-2026-10-18-review.md) | [outputs](../outputs/weinstein-us-sector-2026-10-18/README.md) |
| 温斯坦 · 单个指数与 BTC 快速测试 | 见总结 | [outputs](../outputs/weinstein-quick-checks-2026-10-18/README.md) |
| 红利低波 + 中证2000 | [复核](../docs/notes/dividend-lowvol-csi2000-2026-10-18-review.md) | [outputs](../outputs/dividend-lowvol-csi2000-2026-10-18/README.md) |
| BTC 卫星价格口径修正重跑 | [复核](../docs/notes/btc-satellite-corrected-prices-2026-10-18-review.md) | [outputs](../outputs/btc-satellite-corrected-prices-2026-10-18/README.md) |

## BTC SuperTrend 研究线

1. [Q3：RiskParity 与 BTC](notebooks/q3-riskparity-btc-practice.ipynb)
2. [Q6：动量、趋势与 RiskParity](notebooks/q6-momentum-trend-riskparity-practice.ipynb)
3. [Q7：SuperTrend 稳健性](notebooks/q7-supertrend-riskparity-robustness-practice.ipynb)
4. [Q8：BTC 趋势卫星](notebooks/q8-btc-trend-satellite-practice.ipynb)
5. [Q9：BTC SuperTrend 卫星稳健性](notebooks/q9-btc-supertrend-satellite-robustness-practice.ipynb)
6. [Q10：实盘化压力测试](notebooks/q10-live-readiness-stress-practice.ipynb)
7. [总体策略体检（2026-10-02）](notebooks/strategy-healthcheck-2026-10-02-practice.ipynb) 与 [时序修正（2026-10-03）](notebooks/strategy-healthcheck-clock-correction-2026-10-03-practice.ipynb)

Q10 的 19.49% 年化来自旧 next-close 时序缺陷，已废止；当前口径以 10-18 价格口径修正复核为准。

## Theme Alpha 与 Core90/Bull10 研究线（归档对照）

1. [Q1：强主题筛选](notebooks/theme-alpha-q1-strong-theme-screening-practice.ipynb) · [主题增强验证](notebooks/theme-alpha-q1-theme-enhancement-validation-practice.ipynb)
2. [Q2：低波趋势 Walk-Forward](notebooks/theme-alpha-q2-lowvol-trend-walkforward-practice.ipynb) · [Q3：结构稳健性](notebooks/theme-alpha-q3-structure-robustness-practice.ipynb) · [Q4：核心—卫星组合](notebooks/theme-alpha-q4-core-satellite-practice.ipynb)
3. [Q5：熊市压力](notebooks/theme-alpha-q5-bear-market-stress-practice.ipynb) · [Q6：防守基准补全](notebooks/theme-alpha-q6-bear-defense-benchmark-completion-practice.ipynb) · [Q7：生产现实性](notebooks/theme-alpha-q7-production-realism-practice.ipynb) · [Q8：信号稳定](notebooks/theme-alpha-q8-signal-live-readiness-practice.ipynb)
4. [Q11：SuperTrend 与 LVT 交叉验证](notebooks/q11-supertrend-lvt-cross-validation-practice.ipynb) · [Q12：SuperTrend 替代 LVT](notebooks/q12-supertrend-replace-lvt-trend-confirmation-practice.ipynb) · [Q12：长样本验证](notebooks/theme-alpha-q12-long-sample-proxy-validation-practice.ipynb) · [近期 LVT 3 个月复核](notebooks/theme-alpha-lvt-recent-3m-2026-09-06-practice.ipynb)
5. [Q13：右侧扫描组合](notebooks/q13-scan-v2-right-side-5-portfolio-practice.ipynb) · [Q14：无前视样本池](notebooks/q14-scan-v2-pit-universe-practice.ipynb) · [Q15：全牛市长样本](notebooks/q15-all-bull-flip-long-sample-practice.ipynb) · [Q16：全牛市防守](notebooks/q16-all-bull-flip-defense-practice.ipynb)

## Trading ledger 复现包与迁入脚本

- `trading-ledger-2026-09-05/` 保存交易仓库执行修复对应的历史证据与 Core90 归档账本（见[包说明](trading-ledger-2026-09-05/README.md)）。
- 原 `trading/scripts/research_*.py` 已迁入 [`scripts/trading_research/`](../scripts/trading_research/)，需同级 `trading` 仓库支持，统一入口为 `uv run python scripts/run_trading_research.py --list`。
