# 全部 bull flip：2015–2026 长样本稳健性复盘

> 当前策略的冻结定义、完整交易规则与集中式表现说明见：`docs/notes/policy-eligible-bull-flip-strategy-and-backtest.md`。本文保留研究过程、稳健性解释和长样本决策结论。

## 决策摘要

把 2023–2026 的月度滚动 PIT 回测拉长到 2015-01-01 至 2026-07-10 后，`policy_eligible_bull_flip` 仍为正且跑赢两个单一市场基准，但合理预期必须从短样本的 31.84% CAGR 下调：

| 版本 | CAGR | Sharpe | Calmar | 最大回撤 | 最长恢复 | 年化换手 | 平均资金占用 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2015 冻结 PIT | 11.57% | 0.89 | 0.40 | -29.26% | 410 日 | 9.12x | 66.04% |
| 月度滚动 PIT | **21.09%** | **1.21** | 0.57 | **-36.77%** | **1,016 日** | 9.94x | 72.49% |
| 原始 ST 翻多 + 滚动 PIT | 19.86% | 1.12 | **0.59** | -33.92% | 973 日 | 10.90x | 80.83% |
| SPY 买入持有 | 11.91% | 0.72 | 0.35 | -34.10% | 464 日 | 0.05x | 99.98% |
| 沪深 300 ETF 买入持有 | 4.82% | 0.31 | 0.09 | -52.97% | 1,747 日 | 0.07x | 99.91% |

所以“每月真实更新 31.84% 很不错”这个判断方向没错，但 31.84% 主要描述的是较短且有利的 2023–2026 阶段。拉长后仍有 21.09%，说明信号值得继续研究；同时最大回撤接近 37%、最长恢复接近 3 年，不能再把它理解成稳定的 30% 年化策略。

## 策略定义与锁定规则

本研究的“全部 bull flip”仍严格指：

- 当日 SuperTrend 从空翻多；
- production decision stream 将该事件归类为 `setup=breakout`；
- 数据不陈旧、无明显缺口；
- **不要求**正式 `right_side_5` 的周线、ADX、MACD 或 `permission=buy` 门槛。

SuperTrend 固定为生产参数 7/3。信号在收盘后确认，下一有效 Open 买入；持仓后首次完整 `ST_Dir < 0`，在该标的下一有效 Open 卖出。手续费和滑点合计往返 20 bps，单标的 10%，最多 10 个并发，总敞口 100%。完整样本上没有调整信号、退出或选池参数。

## point-in-time 选池

候选目录共 81 个本地可观察标的，使用 2013 年起数据作暖机。2014-12-31 建立冻结池；滚动池在每个自然月末只读取当时及以前的数据，结果从下一非加密交易日生效。固定规则为 252 个有效交易日、63 日流动性窗口、停牌率不高于 5%、数据完整度不低于 95%、市场内成交额门槛和分市场名额上限；合格后只按流动性排序。

有效交易日要求有限且为正的 OHLC、`Volume > 0`，若存在正式交易状态还必须显示可交易。历史台账保留未入选、退出资格和跌出排名的记录；退出选池只阻止新开仓，不会提前卖出已有持仓。

重要限制：81 个标的是本地缓存目录，不是完整历史交易所 security master。它仍漏掉从未进入当前研究视野的退市、清盘和失败产品，因此本研究降低了 point-in-time 偏差，但没有彻底消除候选目录层面的幸存者偏差。

## 34.08% 应该怎样拆解

这里不能做严格的因果加总，只能给出三个描述性对照：

1. 同一个 2023–2026 窗口内，当前 47 回填为 34.08%，月度滚动 PIT 为 31.84%。本地候选库内的当前池上浮约 **2.24 个百分点**，占 headline CAGR 的 **6.58%**。
2. 同一个长窗口与滚动池内，所有原始 ST 翻多为 19.86%，production `setup=breakout` 过滤后为 21.09%。这个生产分类带来约 **1.22 个百分点**的描述性改善，但 7/3 也是参数邻域里的历史最好点，不能视为未来确定增益。
3. 长样本滚动策略为 21.09%，SPY 为 11.91%，CAGR 差约 **9.18 个百分点**；日收益回归的年化算术 alpha 为 16.89%、beta 0.29。但这不是同资产池的纯择时实验，混合了跨市场资产机会、选池和资金占用差异。

最稳妥的结论是：34.08% 不是主要由“当前 47 回填”凭空制造，bull flip / breakout 路径确实有长期正贡献；但短样本把长期 CAGR 抬高了约 10.75 个百分点，而且本地 81 标的目录本身仍有幸存者偏差。21.09% 更适合作为研究样本结果，仍不应直接作为实盘收益预期。

## 分年度表现

月度滚动 PIT 的年度收益为：

| 年份 | 收益 | 年份 | 收益 |
|---|---:|---|---:|
| 2015 | 18.09% | 2021 | 25.06% |
| 2016 | -3.46% | 2022 | **-27.39%** |
| 2017 | 53.97% | 2023 | 0.95% |
| 2018 | **-20.01%** | 2024 | 19.97% |
| 2019 | 54.50% | 2025 | 52.44% |
| 2020 | 77.26% | 2026 至 7-10 | 40.63% |

12 个年度切片中 3 个为负，2018 和 2022 都出现约 20%–27% 的年度亏损。139 个月的月胜率为 61.87%，平均盈利月 4.95%，平均亏损月 -3.43%，月度 payoff ratio 1.44、profit factor 2.34，最好月 18.31%，最差月 -11.94%。收益依赖少数强趋势年份，不是每年平滑累积。

滚动窗口也显示相同形状：126 个一年窗口中 69.05% 为正，最差一年 CAGR -32.66%；102 个三年窗口中 84.31% 为正，最差三年 CAGR -4.99%；78 个五年窗口全部为正，最差五年 CAGR 9.27%。

## 分市场结果

各市场独立 sleeve 以完整初始资金为分母并保留 10% 单标的上限，因此同时反映信号质量和资金占用：

| 市场 | CAGR | Sharpe | 最大回撤 | 已平仓 |
|---|---:|---:|---:|---:|
| 美国 | 11.73% | 0.95 | -20.58% | 408 |
| 加密 | 9.51% | 0.99 | -12.54% | 71 |
| A 股 | 4.30% | 0.35 | -46.60% | 283 |
| 港股 | 1.26% | 0.36 | -6.11% | 38 |
| 黄金 | 1.10% | 0.60 | -3.97% | 99 |

组合的高 CAGR 主要来自跨市场机会、并发和再投资，不能把各 sleeve CAGR 简单相加。美国和加密贡献最强；A 股交易多但独立路径较弱、回撤最深。加密目录只有今天仍可观察的 BTC、ETH，尤其需要按候选目录幸存者偏差折价。

## 参数、成本与审计敏感性

原始 ST timing 层的小网格结果：7/2、7/3、7/4 CAGR 分别为 15.49%、19.86%、12.10%；10/2、10/3、10/4 为 18.58%、16.61%、16.18%；14/2、14/3、14/4 为 16.06%、13.00%、15.66%。生产 7/3 在这个邻域是历史最好点，但周围大多数仍为正，说明既存在信号形状，也存在参数选择风险。该检查不重新标注 production `setup=breakout`，仅诊断原始 ST timing 层。

滚动主策略在 0、20、50 bps 往返成本下的 CAGR 分别为 22.28%、21.09%、19.33%，高换手会持续侵蚀结果，但 50 bps 下没有失效。

两项实现审计已修正并验证：

- 熊向退出日 Open 缺失时，退出会延至下一有效 Open，不会丢失。长样本 575 笔已平仓逐笔核验，规则不匹配为 0；本批数据中旧逻辑潜在漏卖机会也为 0。
- 有效交易日现要求完整有效 OHLC 和正成交量，并优先使用正式交易状态。旧 `Close.notna()` 口径与新口径只改变 7 个“生效月×标的”选择记录；主策略 CAGR 从 21.34% 调整为 21.09%，最大回撤均为 -36.77%。
- 2023–2026 的六个原组合修正前后 CAGR 和交易数不变；滚动 PIT 仍为 31.84%。

## 结论模板

- Historical best：月度滚动 PIT + production breakout，长样本 CAGR 21.09%；参数诊断中原始 ST 7/3 也是邻域最好点。
- Risk-adjusted best：月度滚动 production breakout 的 Sharpe 1.21；原始 ST 7/3 的 Calmar 略高，为 0.59 对 0.57。
- Most structurally balanced：继续研究月度滚动 PIT + 锁定 production breakout，但按 35%–40% 回撤和多年恢复期做风险预算。
- Main sample-period advantage：2017、2019–2020、2025–2026 的强趋势，以及今天仍可观察到的美国/加密标的。
- Main future failure mode：2018/2022 式反复或跨市场同步下跌、高换手成本、A 股 sleeve 长期失效，以及候选目录漏掉退市/清盘失败者。
- What to test next：补齐历史全市场 security master、真实上市/退市/清盘记录和当时可交易状态；保持本次信号与选池参数冻结，做真正的历史目录级 PIT 重跑。

## 可审计输出

- `outputs/scan-v2-all-bull-flip-long-sample/portfolio_metrics.csv`
- `outputs/scan-v2-all-bull-flip-long-sample/nav_daily.csv`
- `outputs/scan-v2-all-bull-flip-long-sample/annual_metrics.csv`
- `outputs/scan-v2-all-bull-flip-long-sample/monthly_distribution.csv`
- `outputs/scan-v2-all-bull-flip-long-sample/rolling_window_summary.csv`
- `outputs/scan-v2-all-bull-flip-long-sample/portfolio_metrics_by_market.csv`
- `outputs/scan-v2-all-bull-flip-long-sample/drawdown_summary.csv`
- `outputs/scan-v2-all-bull-flip-long-sample/supertrend_parameter_sensitivity.csv`
- `outputs/scan-v2-all-bull-flip-long-sample/cost_sensitivity.csv`
- `outputs/scan-v2-all-bull-flip-long-sample/benchmark_comparison.csv`
- `outputs/scan-v2-all-bull-flip-long-sample/audit_fix_long_sample_metrics.csv`
- `outputs/scan-v2-all-bull-flip-long-sample/audit_fix_summary.json`
- `outputs/scan-v2-all-bull-flip-long-sample/exit_timing_audit.csv`
