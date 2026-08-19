# scan_v2_right_side_5 策略级组合回测复盘

## 决策

**将 `breakout right_side_5` 从正式信号降级为纸面实验，不删除。**

它在真实 SuperTrend 翻空退出、次日开盘执行和 20 bps 往返摩擦后仍有正收益：全期 CAGR 12.01%、Sharpe 1.32、最大回撤 -8.79%，30 笔已平仓交易胜率 60%，50 bps 成本压力下 CAGR 仍为 11.70%。这组结果足以否定“删除”。

但证据还不足以支持正式信号：36 个候选中只有 32 个在组合约束下成交、30 个完成退出；收益主要来自 2025 年和 2026 年，2023 年与 2024 年几乎没有贡献；A 股贡献了 18/30 笔已平仓交易和约 34 万的已实现净利润，而美国、黄金、加密合计样本很小，香港没有正式 breakout。更重要的是，策略是在了解完整历史后形成的，当前 walk-forward 只能算时间稳定性检查，不是未触碰的真实样本外证明。

下一步不再用这段完整样本调阈值。冻结 `0.5 ATR + MACD hist > 0` 的 right_side_5 定义，从 2026-07-11 起继续前向 paper tracking；升级条件写在文末。

> 后续 point-in-time 选池研究已完成，见 `docs/notes/scan-v2-right-side-5-pit-universe-review.md`。月度滚动 PIT 池下，`policy_eligible_bull_flip` CAGR 为 31.84%，`scan_v2_right_side_5` CAGR 为 5.89%；当前 47 回填对后者的上浮明显更大。本页的 34.08% 与 12.01% 继续只作为当前池乐观上界。

## 研究设计

- 决策源：trading 导出的 point-in-time `scan_v2_right_side_5` decision stream。
- 决策窗口：2023-03-01 至 2026-07-10，47 个当前观察标的。
- 初始资金：1,000,000 个归一化资金单位。
- 入场：完整收盘信号后的下一标的交易日开盘；正式 breakout/pullback 先用原始开盘价检查 `maxAcceptablePrice`。
- 退出：持仓后首次出现完整日线 `ST_Dir < 0`，下一标的交易日开盘退出。未用信号日固定 ST，也未用固定持有期代替退出。
- 摩擦：单边手续费 5 bps、单边不利滑点 5 bps，往返合计 20 bps。
- 组合约束：单标的目标权重 10%、最多 10 个并发、总敞口不超过 100%；同日信号按 point-in-time `readinessScore` 降序、标的代码升序处理。
- 资金竞争：已持仓、最高价、并发、总敞口和现金不足都会留下明确拒单记录。
- 基准：简单 SuperTrend 使用价格文件中的所有真实日线翻多/翻空；SPY 买入持有作为全仓机会成本基准，明确不受信号组合的单标的 10% 上限约束。
- 汇率：组合按各资产本币收益做归一化资金分配，等价于假设汇率恒定；未计入跨币种汇兑波动和融资成本。

## 全样本组合结果

| 策略 | CAGR | Sharpe | Sortino | 最大回撤 | Calmar | 年化换手 | 平均敞口 | 已平仓 | 胜率 | Profit factor |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 全部 bull flip | 34.08% | 1.74 | 2.05 | -13.04% | 2.61 | 10.03x | 76.56% | 171 | 49.7% | 2.95 |
| breakout right_side_5 | 12.01% | 1.32 | 1.06 | -8.79% | 1.37 | 1.97x | 19.09% | 30 | 60.0% | 4.28 |
| pullback | 7.17% | 0.57 | 0.48 | -13.37% | 0.54 | 6.08x | 33.25% | 99 | 35.4% | 1.54 |
| breakout + pullback | 13.82% | 0.94 | 0.84 | -14.91% | 0.93 | 6.48x | 39.88% | 104 | 38.5% | 2.08 |
| 简单 SuperTrend | 29.30% | 1.43 | 1.79 | -17.99% | 1.63 | 10.95x | 85.50% | 194 | 42.8% | 2.42 |
| SPY 买入持有 | 22.82% | 1.44 | 1.61 | -18.76% | 1.22 | 0.20x | 100.00% | — | — | — |

注意，breakout 的低绝对收益部分来自平均只有 19.09% 的资金敞口，不能只用 CAGR 与全仓 SPY 判断信号质量。它的最大回撤和交易级 profit factor 都很好；但样本量、时间分布和市场集中度使这些指标置信度有限。

## 执行漏斗与资金占用

| 策略 | 候选 | 成交入场 | 拒单 | 已平仓 | 期末持仓 |
|---|---:|---:|---:|---:|---:|
| 全部 bull flip | 368 | 180 | 188 | 171 | 9 |
| breakout right_side_5 | 36 | 32 | 4 | 30 | 2 |
| pullback | 340 | 104 | 236 | 99 | 5 |
| breakout + pullback | 376 | 110 | 266 | 104 | 6 |
| 简单 SuperTrend | 529 | 204 | 325 | 194 | 10 |

breakout 的四次拒单中，三次是下一开盘超过最高接受价，一次是并发上限。pullback 的 236 次拒单包括 156 次已持仓、55 次并发上限和 25 次超过最高接受价。组合结果因此不是把独立事件收益简单相加，而是真实反映了资金竞争。

## 分年度与 walk-forward

| 测试期 | breakout 收益 | Sharpe | 最大回撤 | 期内平仓 |
|---|---:|---:|---:|---:|
| 2023-03 至 2023-12 | -0.10% | -1.54 | -0.10% | 很少 |
| 2024 | 0.53% | 0.13 | -5.13% | 7 |
| 2025 | 29.42% | 2.09 | -8.79% | 17 |
| 2026-01 至 2026-07-10 | 12.61% | 1.93 | -5.38% | 6 |

expanding-window 检查固定使用同一组基础参数：2023 历史对应 2024 测试、截至 2024 的历史对应 2025 测试、截至 2025 的历史对应 2026 YTD 测试。没有在折内重估或选择参数。结果显示 2025 和 2026 延续为正，但 2024 基本无效，不能称为跨时间稳定。

由于 right_side_5 的定义本身是在看过这段历史后修复的，上表属于 **pseudo-OOS**。真正未触碰的样本只能从 2026-07-11 之后开始积累。

## 分市场结果

breakout 的市场独立袖套结果如下；每个袖套仍以完整 1,000,000 资金为分母并保留 10% 单标的上限，因此低样本市场的低 CAGR 同时反映低资金利用率。

| 市场 | CAGR | Sharpe | 最大回撤 | 已平仓 | 胜率 | 平均敞口 |
|---|---:|---:|---:|---:|---:|---:|
| A 股 | 11.49% | 1.37 | -8.56% | 18 | 61.1% | 15.52% |
| 美国 | 0.80% | 0.31 | -4.24% | 5 | 60.0% | 1.81% |
| 黄金 | 0.31% | 0.24 | -1.30% | 5 | 80.0% | 1.72% |
| 加密 | -0.63% | -0.63 | -2.73% | 2 | 0.0% | 0.30% |

没有香港正式 breakout。A 股产生约 34.0 万已实现净利润，明显主导组合结论。美国和黄金方向为正但各只有五笔，加密两笔均亏损。当前证据不能支持跨市场同参已经成立。

## 敏感性与增量判断

breakout 对交易摩擦不敏感：0/20/50 bps 往返成本下 CAGR 分别为 12.21%/12.01%/11.70%，Sharpe 为 1.34/1.32/1.29。仓位结构影响更大：5% × 20 并发把 CAGR 降至 6.41% 但回撤收窄到 -4.74%；20% × 5 并发把 CAGR 提高到 21.63%，同时回撤扩大到 -11.82%。这说明结果依赖资金集中方式，不能把 20% 版本选作“更优参数”。

将 breakout 加入 pullback 后，CAGR 从 7.17% 提高到 13.82%，profit factor 从 1.54 提高到 2.08；但最大回撤从 -13.37% 扩大到 -14.91%，Sharpe 仅从 0.57 提高到 0.94，仍低于 breakout 单独运行的 1.32。breakout 有正的增量价值，但没有把组合变成比简单 SuperTrend 或全部 bull flip 更稳健的正式系统。

全部 bull flip 历史表现最好，简单 SuperTrend 次之；这提示主要收益来源可能是 SuperTrend 状态转换和样本期趋势行情，而不是 right_side_5 的 MACD/周线/ADX/市场模式门槛。另一方面，全部 bull flip 年化换手约 10 倍、188 次因资金或并发拒单，实际运营强度远高于正式 breakout，不能直接替代生产规则。

## 结论模板

- Historical best：全部 bull flip，CAGR 34.08%、Sharpe 1.74。
- Risk-adjusted best：全部 bull flip，Calmar 2.61；正式 breakout 以更低敞口获得 -8.79% 的最小最大回撤。
- Most structurally balanced：当前没有达到正式部署门槛的候选；简单 SuperTrend 是最清晰的研究基准，right_side_5 作为纸面稀疏信号继续积累证据。
- Main sample-period advantage：2025–2026 的趋势行情和 A 股标的贡献。
- Main future failure mode：横盘反复翻转、A 股优势消失、跨市场同参失效，以及当前观察池的幸存者/事后选池偏差。
- What to test next：只做冻结规则的前向跟踪和预先定义的市场归因，不在旧样本继续搜索 ATR、ADX、MACD 或仓位参数。

## 纸面实验升级门槛

以下条件预先冻结，满足前不恢复为正式信号：

1. 2026-07-11 之后至少新增 20 笔可执行且完成真实翻空退出的 breakout，或积累满 12 个月，以较晚者为准。
2. 新样本在 50 bps 往返成本下累计净收益为正、profit factor 大于 1，且最大回撤不超过 -15%。
3. 新样本利润不能有超过 70% 来自单一市场；至少两个市场各有五笔以上已平仓交易且净利润非负。
4. 在相同资金约束下，breakout + pullback 相对 pullback 的新样本 Sharpe 不下降，并且最大回撤不恶化超过 2 个百分点。

若满 12 个月仍不足 20 笔，继续 paper 而不是降低门槛；若达到样本数但累计净收益为负、profit factor 小于等于 1，或组合增量条件失败，则删除正式候选资格。

## 限制

1. 当前 47 个观察标的回放历史，存在幸存者偏差和事后选池偏差。
2. 退出使用当前价格库中的历史 `ST_Dir`；它按已完成日线计算，但复权数据和公司行动可能在事后修订。
3. 固定滑点没有模拟成交量、涨跌停、市场冲击、税费差异和跨币种汇率波动。
4. SPY 是单资产全仓机会成本基准，不与受 10% 单标的上限的信号组合具有相同风险预算。
5. 期末仍有持仓按收盘市值计入 NAV，没有为了美化交易胜率而强制平仓。

## 可审计输出

- `outputs/scan-v2-right-side-5-portfolio/portfolio_metrics.csv`
- `outputs/scan-v2-right-side-5-portfolio/nav_daily.csv`
- `outputs/scan-v2-right-side-5-portfolio/drawdown_daily.csv`
- `outputs/scan-v2-right-side-5-portfolio/trades.csv`
- `outputs/scan-v2-right-side-5-portfolio/orders.csv`
- `outputs/scan-v2-right-side-5-portfolio/execution_funnel.csv`
- `outputs/scan-v2-right-side-5-portfolio/annual_metrics.csv`
- `outputs/scan-v2-right-side-5-portfolio/monthly_metrics.csv`
- `outputs/scan-v2-right-side-5-portfolio/portfolio_metrics_by_market.csv`
- `outputs/scan-v2-right-side-5-portfolio/walk_forward_metrics.csv`
- `outputs/scan-v2-right-side-5-portfolio/sensitivity_metrics.csv`
- `outputs/scan-v2-right-side-5-portfolio/nav_and_drawdown.png`
