# 策略研究索引

本页汇总各研究线的入口、当前证据边界和历史归档位置。它是面向研究者的导航页，不构成投资建议或实盘批准。普通读者请先从[首页总览](../../README.md)出发，直接看大白话专题：[逆波动三组合指南（方案 A）](two-three-asset.md)、[标普 500 增强指南（方案 B 与方案 C）](sp500-enhance.md)、[真实持有体验](holding-experience.md)与[大白话术语表](../glossary.md)；完整清单见[研究台账](../research-ledger.md)。

## 标普 500 量化增强与实盘摩擦（2026 年 11 月）

- **通俗总指南**：[标普 500 增强指南（方案 B 与方案 C）](sp500-enhance.md)（按账户给结论，含最新信号快照、黄金熊市压力测试与币圈避坑）。
- **做空策略实战挑战（11-23）**：[复核报告](../notes/short-selling-challenge-2026-11-23-review.md)（美股 SPY/QQQ 三套真实工具、BTC/ETH 资金费率压测、A 股 8.5% 融券、快速战术止损做空与市场中性配对全线未通过；所有市场最佳空头仓位均为 0%，空仓拿现金或避险盾全面胜出）。
- **BTC 与 A 股日频防抖三档泛化研究（11-23）**：[复核报告](../notes/btc-ashare-buffered-mtf3-2026-11-23-review.md)（10 大资产市场物理指纹；BTC 混合三档 `ST(10,3)+MA150±5%` 与纯双均线 `100/200±5%～8%` 通过且零调参泛化至 ETH；A 股含红利低波 `H20269/510880/512890` 全线未通过趋势择时，实证应采用定投 + 国债/黄金资产分散）。
- **MTF-3 日频防抖缓冲带专题（11-23）**：[复核报告](../notes/mtf3-daily-buffer-2026-11-23-review.md)（用 ±2%～3% 空间防抖带替代死等月底，覆盖 26 年美股 SPY/QQQ、21.8 年黄金/金债盾、2011–2022 黄金熊市、10 年滚动定投、24 年换起点与国内 513500 边界验证；美股强通过，国内自身价格仍未通过）。
- **四方向联合研究与统一收口（11-22）**：[四方向总复盘](../notes/sp500-four-directions-2026-11-22-review.md)（跨资产股金双核与美股单因子、S2 趋势换黄金/金债盾、VIX 恐慌结构与信用利差、国内 513500 黄金护盾与溢价停泊 + 币圈美股摩擦压测）。
- **MTF-3 / TVT-50 与境内 513500/513100 复测（11-14 ~ 11-15）**：[新候选 MTF-3/TVT-50](../notes/sp500-new-enhance-2026-11-14-review.md)、[513500 外盘信号复测](../notes/sp500-513500-mtf-tvt-real-2026-11-14-review.md)、[513500 自身信号对照](../notes/sp500-513500-direct-signal-2026-11-15-review.md)、[统一体检](../notes/mtf-tvt-healthcheck-2026-11-15-review.md)、[与既有策略分层对比](../notes/mtf-tvt-existing-comparison-2026-11-15-review.md)、[QQQ 新规则](../notes/qqq-new-enhance-2026-11-14-review.md)、[SPY+QQQ 组合](../notes/spy-qqq-combo-2026-11-15-review.md)。
- **首轮标普择时、溢价与入场方式（11-05 ~ 11-10）**：[标普增强与定投对比](../notes/sp500-enhance-vs-dca-2026-11-10-review.md)、[参数敏感性](../notes/sp500-parameter-robustness-2026-11-10-review.md)、[持有体验](../notes/sp500-holding-experience-2026-11-10-review.md)、[境内 513500/513100 半仓趋势](../notes/domestic-us-etf-trend-2026-11-10-review.md)、[境内 ETF 溢价](../notes/qdii-premium-2026-11-10-review.md)、[入场方式](../notes/entry-methods-2026-11-10-review.md)、[同区间策略对比](../notes/strategy-comparison-2026-11-10-review.md)、[标普与红利低波增强](../notes/index-enhance-strategies-2026-11-05-review.md)、[红利低波布林带](../notes/dividend-lowvol-bollinger-2026-11-05-review.md)、[QQQ 趋势规则](../notes/qqq-trend-strategies-2026-11-05-review.md)。

## 逆波动三组合主线与主线过滤验证

- **通俗总指南**：[逆波动三组合指南（方案 A）](two-three-asset.md)、[真实持有体验（一次投入与定投）](holding-experience.md)。
- [纯三资产核心复核（2026-10-03）](../notes/three-asset-core-2026-10-03-review.md)：`510300`、`513100`、`518880` 的 20 日逆波动基线及收益来源、回撤和不利情景。
- [分红会计修正与海外 ETF 估值监测（2026-10-04）](../notes/etf-dividend-valuation-2026-10-04-review.md)：`510300` 原始份额、除息应收和现金到账的修订口径；此报告已确认交付。
- [主线里的 S2 过滤（2026-11-10）](../notes/main-line-s2-filter-2026-11-10-review.md)：验证给主线叠加 S2 周线趋势过滤未通过（无法缩短 2020 急跌回撤），主线维持简洁冻结态。

旧三资产和主题研究若使用 `510300`，必须核对各自行情来源及实现字段；分红报告不会自动改写旧 Notebook 或旧 CSV。历史决策时溢价已在 11-10 与 11-22 笔记中用东方财富净值检验，但盘中实时 IOPV 估值区间观察仍为 0/20，需实盘前瞻核验。

## BTC 趋势卫星（主线卫星部分）

- [价格口径修正重跑（2026-10-18）](../notes/btc-satellite-corrected-prices-2026-10-18-review.md)：三组合核心改用比例复权后，7.5% BTC 日线 SuperTrend(10, 3) 相对不加 BTC 仍贡献约 +2.75 个百分点/年，最大回撤略降。
- [时序修正研究说明（2026-10-03）](../notes/strategy-healthcheck-clock-correction-2026-10-03-review.md)及[独立复核](../notes/strategy-healthcheck-clock-correction-2026-10-03-independent-review.md)、[总体策略体检（2026-10-02）](../notes/strategy-healthcheck-2026-10-02-review.md)。
- [Q3、Q6–Q10 旧研究序列](../../research/README.md#btc-supertrend-研究线)。

旧 Q10 报告中的 BTC7.5 年化 19.49% 存在 next-close 时序缺陷，已废止；当前口径以 10-18 修正复核为准。

## 趋势跟踪（温斯坦）与 A 股风格

- [温斯坦测试总结（2026-10-18）](../notes/weinstein-summary-2026-10-18.md)：简化版 30 周线只在美股指数上能降低回撤；在 A 股收益和回撤都更差；在 BTC 上不如日线 SuperTrend。
- [A 股 ETF 版](../notes/weinstein-etf-stage-2026-10-18-review.md)、[美股行业 ETF 版](../notes/weinstein-us-sector-2026-10-18-review.md)、[单个指数与 BTC 快速测试](../../outputs/weinstein-quick-checks-2026-10-18/README.md)。
- [红利低波 + 中证2000（2026-10-18）](../notes/dividend-lowvol-csi2000-2026-10-18-review.md)：四种搭配规则均未在回撤上胜过单独持有红利低波。

## 归档对照与历史研究线

以下研究线经 2026-11-22 统一收口为**归档对照**，不再作为当前推荐或纸面并行方向，仅保留用于方法论复盘与历史对照：

- **聚宽四 ETF 核心资产轮动与黄金熊市测试（11-15）**：[复核报告](../notes/joinquant-core-rotation-2026-11-15-review.md)（修正未来函数后最大回撤 -42.5%、对 25 日窗口敏感；简单黄金均线过滤恶化逆波动组合）。
- **TQQQ 牛熊切换（11-10）**：[复核报告](../notes/tqqq-regime-switch-2026-11-10-review.md)（收益主要来自三倍杠杆，回撤仍在 -57%～-61%）。
- **Core90 / Bull10 与交易账本复现包**：[交易账本复现包说明](../../research/trading-ledger-2026-09-05/README.md)、[Core90 当前合同基准](../../research/trading-ledger-2026-09-05/core90_current_contract_2026_09_05/README.md)、[Q15](../../research/notebooks/q15-all-bull-flip-long-sample-practice.ipynb) / [Q16](../../research/notebooks/q16-all-bull-flip-defense-practice.ipynb)。
- **Theme Alpha 与多资产旧实验**：[主题 Alpha Q1–Q8 与 Q12](../../research/README.md#theme-alpha-研究线)、[近期 LVT 三个月复核](../notes/theme-alpha-lvt-recent-3m-2026-09-06-review.md)。

每个研究目录的 Notebook、输出和复核报告应配套阅读；早期 Notebook 中的“当前默认候选”措辞仅代表撰写当时的阶段性结论。
