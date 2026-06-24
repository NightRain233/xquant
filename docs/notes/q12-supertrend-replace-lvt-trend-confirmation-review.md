# Q12 SuperTrend 替代 LVT 内部趋势确认 Review

Date: 2026-06-24

## 研究问题

Q12 回答这个问题：

> 如果不在 LVT 外面套 SuperTrend，而是直接把 LVT 内部的趋势确认换成 SuperTrend，会不会更好？

Q8 near-live 口径保持不变：

- Core80 / Expanded satellite20 / Def200 Cash
- fixed twice-monthly signal
- close-signal-next-day-trade
- 20 bps base cost + asset friction
- 2% minimum rebalance threshold
- 15% max single-ETF trade cap

本次只改 Expanded satellite 的 selector。低波排序、Top3、RiskParity cap50、调仓、执行和成本全部保持一致。

## 策略定义

| 策略 | 通俗定义 |
|---|---|
| `Q8_Original_LVT` | 原始 LVT：MA60 上方 + 63 日动量为正，然后选低波 Top3。 |
| `ST_Replaces_MA_Mom` | 直接替换：只看 SuperTrend 多头，然后选低波 Top3。没有 MA60，也没有动量条件。 |
| `ST_Replaces_MA_KeepMom` | 只替换 MA：SuperTrend 多头 + 63 日动量为正，然后选低波 Top3。 |
| `MA_Mom_AND_ST` | 严格双确认：原始 LVT 条件和 SuperTrend 都要通过。 |
| `MA_Mom_OR_ST` | 宽松确认：原始 LVT 条件或 SuperTrend 任一通过。 |
| `Q11_EntryFilter_Reference` | Q11 外层准入过滤参考：新进入资产需要 ST 多头，已有资产可等 LVT 自己剔除。 |

## 2021 至今主结果

| strategy | 累计收益 | 年化收益 | 最大回撤 | Sharpe | Calmar | Sortino | 最长水下天数 | 超过 -10% 天数 | 平均现金/Def200 | 平均卫星现金 | 年化换手 | 年化成本拖累 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Q8_Original_LVT | 111.46% | 15.32% | -11.29% | 1.41 | 1.36 | 1.33 | 506 | 1 | 16.21% | 0.17% | 5.94 | 1.71% |
| ST_Replaces_MA_Mom | 91.64% | 13.18% | -9.27% | 1.26 | 1.42 | 1.18 | 524 | 0 | 16.16% | 0.12% | 6.85 | 1.98% |
| ST_Replaces_MA_KeepMom | 106.56% | 14.81% | -9.79% | 1.36 | 1.51 | 1.29 | 519 | 0 | 16.85% | 0.74% | 6.83 | 1.99% |
| MA_Mom_AND_ST | 109.22% | 15.09% | -9.79% | 1.38 | 1.54 | 1.31 | 518 | 0 | 17.15% | 1.03% | 6.69 | 1.95% |
| MA_Mom_OR_ST | 95.35% | 13.59% | -11.00% | 1.29 | 1.24 | 1.21 | 506 | 1 | 16.02% | 0.00% | 6.15 | 1.76% |
| Q11_EntryFilter_Reference | 112.05% | 15.38% | -10.31% | 1.43 | 1.49 | 1.35 | 506 | 1 | 16.21% | 0.17% | 5.84 | 1.69% |

## 主要发现

### 1. 直接替代不是升级

`ST_Replaces_MA_Mom` 最大回撤最浅之一，只有 -9.27%，但收益明显下降：

- Q8 原始 LVT：累计 111.46%，年化 15.32%
- ST 直接替代：累计 91.64%，年化 13.18%

这说明 SuperTrend 不能直接替代 LVT 里的 MA60 + 动量组合。它能减少一些坏暴露，但也会把 LVT 的主题强度识别能力削弱掉。

### 2. 保留动量后，结果明显好一些

`ST_Replaces_MA_KeepMom` 比完全替代好很多：

- 累计收益从 91.64% 提到 106.56%
- 年化收益从 13.18% 提到 14.81%
- 最大回撤保持在 -9.79%
- Calmar 提到 1.51

这说明 LVT 里的“动量为正”不是多余条件。SuperTrend 如果要进入 LVT 内部，更适合替代 MA 这一层，而不是把 MA 与动量都拿掉。

### 3. AND 双确认更像防守版，不是收益版

`MA_Mom_AND_ST` 的 Calmar 最高：1.54，最大回撤也只有 -9.79%，并且 2021 至今没有超过 -10% 的水下天数。

但收益仍低于 Q8：

- AND 双确认：累计 109.22%，年化 15.09%
- Q8 原始 LVT：累计 111.46%，年化 15.32%

所以它是“更稳一点”的版本，不是“更赚钱”的版本。

### 4. OR 宽松确认不好

`MA_Mom_OR_ST` 是最不推荐的内部改法。它想扩大候选池，但结果收益低、Calmar 弱：

- 累计收益 95.35%
- 年化收益 13.59%
- Calmar 1.24

它说明 SuperTrend 多头本身不能随便加入 LVT 候选池。只靠 ST 放宽入选条件，会引入不少质量一般的资产。

### 5. Q11 外层准入过滤仍然更自然

`Q11_EntryFilter_Reference` 在这次比较中仍然最好看：

- 累计收益最高：112.05%
- 年化收益最高：15.38%
- 最大回撤改善到 -10.31%
- Sharpe 1.43
- 换手和成本还略低于 Q8

这说明 SuperTrend 更适合做 LVT 外层的“准入确认灯”，而不是替换 LVT 内部的趋势定义。

## Selector 诊断

| strategy | 平均选中数量 | 空仓信号占比 | 与原始 LVT 平均重合度 |
|---|---:|---:|---:|
| Q8_Original_LVT | 2.53 | 4.55% | 100.00% |
| ST_Replaces_MA_Mom | 2.71 | 3.90% | 65.65% |
| ST_Replaces_MA_KeepMom | 2.34 | 7.14% | 74.94% |
| MA_Mom_AND_ST | 2.25 | 9.09% | 76.98% |
| MA_Mom_OR_ST | 2.79 | 3.25% | 81.86% |

直接 ST 替代与原始 LVT 的重合度只有 65.65%，说明它确实改变了选股池。但这个改变没有带来更高收益，反而把组合带离了 LVT 原本有效的主题强度逻辑。

## Forward return 诊断

用原始 LVT 和 ST 直接替代版本比较，四组资产后续表现如下：

| horizon | 两者都选中 | 仅原始 LVT 选中 | 仅 ST 替代选中 | 二者都不选 |
|---:|---:|---:|---:|---:|
| 10D | 0.97% | 0.85% | -0.00% | 0.31% |
| 20D | 1.78% | 0.70% | 1.08% | 0.75% |
| 40D | 2.55% | 0.34% | 2.29% | 1.98% |

这张表的含义：

- 两者都选中的资产最好，说明 ST 与 LVT 共振时确实质量较高。
- 仅 ST 选中的资产短期 10D 很弱，说明 ST 直接替代会带入一些短期不够强的资产。
- 仅原始 LVT 选中的资产 10D/20D 并不差，说明 ST 会过滤掉一些仍然可用的 LVT 机会。

所以 SuperTrend 不是更好的完整替代器，它更像“共振确认器”。

## 分窗口表现

### 2022 熊市

2022 年表现最好的是 `MA_Mom_OR_ST` 与 `Q11_EntryFilter_Reference` 附近：

- Q8：-1.20%，最大回撤 -5.04%
- Q11 EntryFilter：-1.05%，最大回撤 -5.04%
- OR：-0.95%，最大回撤 -4.24%

但 OR 长窗口表现太弱，不应因为 2022 单年略好就采用。

### 2025 至今

`MA_Mom_AND_ST` 明显领先：

- AND：46.30%，最大回撤 -9.79%，Calmar 3.17
- Q8：42.79%，最大回撤 -11.29%，Calmar 2.55
- Q11 EntryFilter：43.89%，最大回撤 -10.31%，Calmar 2.86

这说明严格双确认在近期路径上很吃香，但这可能是样本期奖励“少踩错主题”的结果。

### 2026 YTD

`MA_Mom_AND_ST` 继续领先：

- AND：9.35%
- Q11 EntryFilter：8.15%
- Q8：7.39%

但这仍然是很短窗口，不足以替代长窗口判断。

## 参数敏感性

默认 ATR10 / multiplier3 的排名：

| strategy | Calmar rank | Sharpe rank |
|---|---:|---:|
| ST_Replaces_MA_Mom | 3/9 | 7/9 |
| ST_Replaces_MA_KeepMom | 3/9 | 5/9 |
| MA_Mom_AND_ST | 3/9 | 6/9 |
| MA_Mom_OR_ST | 8/9 | 7/9 |

默认参数不是魔法点，但也不是每个内部替代版本都稳定。尤其 OR 版本在参数网格中很弱，不值得继续优先研究。

## 当前信号

最新数据日：2026-06-24。最新 fixed twice-monthly 信号日：2026-06-10。

当前 selector：

| strategy | 当前选中 |
|---|---|
| Q8_Original_LVT | 纳指100ETF、通信ETF、芯片ETF |
| ST_Replaces_MA_Mom | 红利ETF、能源ETF、纳指100ETF |
| ST_Replaces_MA_KeepMom | 纳指100ETF、通信ETF、芯片ETF |
| MA_Mom_AND_ST | 纳指100ETF、通信ETF、芯片ETF |
| MA_Mom_OR_ST | 红利ETF、能源ETF、纳指100ETF |
| Q11_EntryFilter_Reference | 纳指100ETF、通信ETF、芯片ETF |

这很直观：直接 ST 替代和 OR 版本当前会把红利、能源拉进来，而原始 LVT、保留动量版、AND 版仍然选择纳指、通信、芯片。当前这组信号也解释了为什么不能把 ST 多头简单当成 LVT 趋势确认的完全替代。

## 结论回答

### Historical best

2021 至今历史收益最好的是 `Q11_EntryFilter_Reference`，累计收益 112.05%。在真正的“内部替代”版本里，最好的是 `MA_Mom_AND_ST`，累计收益 109.22%，仍低于 Q8 原始 LVT 的 111.46%。

### Risk-adjusted best

按 Calmar 看，内部替代里最好的是 `MA_Mom_AND_ST`，Calmar 1.54；按 Sharpe 看，仍然是 `Q11_EntryFilter_Reference` 最好。

### Most structurally balanced

最结构均衡的不是内部替代，而是 Q11 的外层准入过滤。若只在 Q12 内部替代版本里选，`MA_Mom_AND_ST` 是最值得保留的研究候选。

### SuperTrend 替代 LVT 趋势确认是否有帮助

不建议“完全替代”。直接把 MA60 + 动量换成 SuperTrend，收益明显下降。

有帮助的方式是：

- 保留动量，只用 ST 替代 MA；
- 或者把 ST 作为原始 LVT 的额外确认。

但这两种更像防守增强，不是收益增强。

### 与 Q11 结论是否一致

一致。Q11 说 SuperTrend 更适合做 LVT 的外层准入确认。Q12 进一步说明：如果强行把它塞进 LVT 内部、替代原始趋势定义，效果反而没那么自然。

### 是否值得进入纸面跟踪

不建议让 Q12 内部替代版直接进入主纸面候选。

建议：

1. 继续以 `Q8_Original_LVT` 为主基准；
2. 继续跟踪 `Q11_EntryFilter_Reference`；
3. 把 `MA_Mom_AND_ST` 作为研究观察项，尤其观察它是否只是 2025/2026 路径运气；
4. 放弃 `ST_Replaces_MA_Mom` 和 `MA_Mom_OR_ST` 作为优先候选。

一句话总结：

> SuperTrend 不适合直接替代 LVT 的趋势确认。它更适合作为 LVT 的确认灯，尤其是外层准入过滤；如果一定放进 LVT 内部，最合理的是 AND 双确认，但它偏防守，不是默认升级。

## 文件

- Notebook: `q12-supertrend-replace-lvt-trend-confirmation-practice.ipynb`
- Outputs: `outputs/q12-supertrend-replace-lvt-trend-confirmation/`
- Main summary: `summary_all_windows.csv`
- Parameter sensitivity: `supertrend_internal_parameter_sensitivity.csv`
- Selector diagnostics: `selector_overlap_summary.csv`
- Forward diagnostics: `forward_return_original_vs_st_summary.csv`
