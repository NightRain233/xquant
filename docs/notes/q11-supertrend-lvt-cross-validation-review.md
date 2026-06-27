# Q11 SuperTrend 与低波趋势 LVT 交叉验证 Review

Date: 2026-06-24

## 研究目的

Q11 检验一个很具体的问题：

> 在 Q8 near-live 口径下，SuperTrend 能否增强低波趋势 LVT，还是只是重复过滤？

基准不变：

- `Core80 / Expanded LVT20 / Def200 Cash`
- fixed twice-monthly calendar signals
- close-signal-next-day-trade
- 20 bps base cost + asset friction
- 2% minimum rebalance threshold
- 15% max single-ETF trade per rebalance

默认 SuperTrend 参数沿用 Q9/Q10 较均衡版本：ATR 10 / multiplier 3。参数敏感性额外测试 ATR 7/10/14 与 multiplier 2/3/4。

## 策略定义

| 策略 | 定义 |
|---|---|
| `Q8_Baseline` | Q8 默认基准：Core80 / Expanded LVT20 / Def200 Cash。 |
| `Pure_LVT_Satellite` | 与 Q8 基准相同，单独命名是为了标记“纯 LVT 卫星”。 |
| `Pure_ST_Satellite` | 用同样 20% 卫星预算，在 Expanded pool 中选择 SuperTrend 多头资产；无资产通过则卫星进现金。 |
| `LVT_ST_EntryFilter` | LVT 资产只有在 SuperTrend 多头时才允许新进入；已持有 LVT 资产可继续持有直到 LVT 本身剔除。 |
| `LVT_ST_ExitFilter` | 已持有 LVT 资产若 SuperTrend 转空则退出；新 LVT 资产不做准入过滤。 |
| `LVT_ST_Vote_HalfWeight` | LVT 选中且 ST 多头正常权重；LVT 选中但 ST 空头降为半权重，释放部分进现金。 |
| `LVT_ST_Vote_FullExit` | LVT 选中但 ST 空头完全退出到现金，不把权重再分给其他卫星资产。 |
| `LVT_ST_EntryExit` | 上限参考：必须 LVT 与 ST 同时通过，且剩余资产重新归一到完整卫星预算。 |

`Q8_Baseline` 与 `Pure_LVT_Satellite` 在本 notebook 中刻意保持完全相同：前者用于锚定 Q8，后者用于命名卫星引擎。

## 2021 至今主结果

| strategy | 累计收益 | 年化收益 | 最大回撤 | Sharpe | Calmar | Sortino | 最长水下天数 | 超过 -10% 天数 | 平均现金/Def200 | 平均卫星现金 | 年化换手 | 年化成本拖累 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Q8_Baseline | 111.46% | 15.32% | -11.29% | 1.41 | 1.36 | 1.33 | 506 | 1 | 16.21% | 0.17% | 5.94 | 1.71% |
| Pure_ST_Satellite | 90.60% | 13.06% | -10.73% | 1.22 | 1.22 | 1.15 | 525 | 1 | 16.06% | 0.12% | 6.61 | 1.91% |
| LVT_ST_EntryFilter | 111.14% | 15.29% | -10.31% | 1.42 | 1.48 | 1.34 | 506 | 1 | 16.21% | 0.17% | 5.87 | 1.69% |
| LVT_ST_ExitFilter | 107.57% | 14.91% | -10.81% | 1.37 | 1.38 | 1.31 | 525 | 1 | 16.88% | 0.77% | 6.93 | 2.01% |
| LVT_ST_Vote_HalfWeight | 111.71% | 15.35% | -10.74% | 1.44 | 1.43 | 1.37 | 505 | 1 | 18.19% | 2.21% | 5.81 | 1.67% |
| LVT_ST_Vote_FullExit | 110.85% | 15.26% | -10.19% | 1.46 | 1.50 | 1.39 | 466 | 1 | 20.23% | 4.26% | 5.91 | 1.71% |
| LVT_ST_EntryExit | 105.42% | 14.68% | -9.79% | 1.36 | 1.50 | 1.29 | 524 | 0 | 17.10% | 1.03% | 6.74 | 1.96% |

## 分窗口结论

- 2022 熊市：`LVT_ST_Vote_FullExit` 表现最好，全年 -0.54%，最大回撤 -4.54%；Q8 基准为 -1.20%，最大回撤 -5.04%。
- 2025 至今：`LVT_ST_EntryExit` 收益和 Calmar 最强，累计 45.34%，最大回撤 -9.79%，但它是更强的二次过滤，样本运气风险更高。
- 2026 YTD：`LVT_ST_EntryExit` 当前领先，累计 9.21%，但这同样可能来自 2026 上半年路径对硬过滤有利。
- 全窗口看，`Pure_ST_Satellite` 明显弱于 Q8 LVT 基准，说明 SuperTrend 不能替代 LVT 作为卫星选股引擎。

## 交叉验证诊断

LVT 选中资产里，SuperTrend 多头占比：

- asset-count weighted overlap：77.69%
- signal-date 平均 overlap：76.98%
- signal-date 中位数 overlap：100.00%

这说明 SuperTrend 与 LVT 有明显重合，不是完全独立信号。

LVT 选中资产的 forward return：

| horizon | ST 多头均值 | ST 空头均值 |
|---:|---:|---:|
| 10D | 1.25% | -0.17% |
| 20D | 1.91% | -0.30% |
| 40D | 2.02% | 1.06% |

短窗口 10/20D 中，SuperTrend 确实能过滤掉后续表现较差的 LVT 资产；40D 差距仍在，但不再是负收益过滤。这更像短中期风险控制，而不是长期 alpha 替代。

四组 forward return：

| horizon | LVT+ST 同时通过 | 仅 LVT | 仅 ST | 二者都不通过 |
|---:|---:|---:|---:|---:|
| 10D | 1.25% | -0.17% | 0.23% | 0.43% |
| 20D | 1.91% | -0.30% | 0.63% | 1.13% |
| 40D | 2.02% | 1.06% | 1.93% | 2.62% |

解读：ST 对 LVT 的短期风险过滤有帮助，但“仅 ST”不是强选股信号；40D 上甚至二者都不通过组均值最高，说明这个诊断不能被解读成稳定 alpha 排序。

## 暴露、换手与错过上涨

SuperTrend 后的改善有两类来源：

1. 一部分来自真正过滤：ST 空头 LVT 资产在 10/20D forward return 更弱。
2. 一部分来自降低暴露：`Vote_FullExit` 平均现金/Def200 达 20.23%，高于 Q8 的 16.21%；卫星现金 4.26%，明显高于 Q8 的 0.17%。

`Vote_FullExit` 改善最大回撤和最长水下，但代价是更高现金暴露。`EntryExit` 最大回撤最浅且 2021 至今没有超过 -10% 天数，但年化收益下降到 14.68%，且换手/成本更高。

错过上涨方面：

- `Pure_ST_Satellite` 在 Q8 上涨月份中 66% 跑输，说明 ST 不能单独替代 LVT。
- `Vote_HalfWeight` 与 `Vote_FullExit` 在 Q8 上涨月份中分别 56% 与 58% 跑输，但平均跑输幅度不大。
- `EntryFilter` 只在 16% 的 Q8 上涨月份跑输，是最少牺牲上涨的混合版本。

## 参数敏感性

| strategy | Calmar min | Calmar median | Calmar max | 最大回撤区间 | 平均现金中位数 |
|---|---:|---:|---:|---:|---:|
| Pure_ST_Satellite | 1.01 | 1.15 | 1.26 | -12.86% 到 -10.73% | 16.08% |
| LVT_ST_EntryExit | 1.33 | 1.44 | 1.65 | -10.84% 到 -9.79% | 17.30% |
| LVT_ST_Vote_HalfWeight | 1.33 | 1.41 | 1.43 | -11.29% 到 -10.74% | 18.24% |
| LVT_ST_Vote_FullExit | 1.29 | 1.46 | 1.50 | -11.31% 到 -10.19% | 20.31% |

默认 ATR10 / multiplier3 不是唯一有效点：

- `Vote_HalfWeight` 默认参数 Calmar 排名 2/9，Sharpe 排名 3/9。
- `Vote_FullExit` 默认参数 Calmar 排名 2/9，Sharpe 排名 3/9。
- `EntryExit` 默认参数 Calmar 排名 3/9，但 Sharpe 排名 7/9。
- `Pure_ST` 默认参数 Calmar 排名 3/9，但 Sharpe 排名 7/9。

参数敏感性总体支持“默认参数可用但不是魔法点”。不过 `EntryExit` 的表现对过滤强度和参数更敏感，不适合直接作为默认答案。

## 当前信号

最新数据日：2026-06-24。最新 fixed twice-monthly 信号日：2026-06-10。

LVT 当前选中：

- 纳指100ETF
- 芯片ETF
- 通信ETF

这三只当前均为 SuperTrend 多头，所以 Q8 基准、EntryFilter、ExitFilter、Vote/Half、Vote/FullExit、EntryExit 的最新目标权重相同：

| 资产 | 权重 |
|---|---:|
| 沪深300ETF | 35.38% |
| 纳指100ETF | 25.48% |
| 黄金ETF | 27.81% |
| 芯片ETF | 5.55% |
| 通信ETF | 5.78% |
| 现金 | 0.00% |

## 结论回答

### Historical best

默认参数下，2021 至今历史收益最好的是 `LVT_ST_Vote_HalfWeight`，累计收益 111.71%，略高于 Q8 基准 111.46%。优势很小，不能当成强历史胜利。

### Risk-adjusted best

按 Sharpe 看是 `LVT_ST_Vote_FullExit`，Sharpe 1.46。按 Calmar 看，`EntryExit` 1.50 与 `Vote_FullExit` 1.50 接近。考虑收益牺牲后，`Vote_FullExit` 比 `EntryExit` 更自然。

### Most structurally balanced

`LVT_ST_EntryFilter` 最均衡：收益几乎不输 Q8，最大回撤从 -11.29% 改到 -10.31%，Calmar 从 1.36 升到 1.48，换手和成本还略低。它没有靠大量提高现金来改善指标。

### SuperTrend 是否能增强 LVT

能增强，但幅度温和。增强主要体现在：

- 10/20D forward return 中，ST 空头的 LVT 资产后续表现明显更弱；
- 混合策略普遍改善最大回撤或 Calmar；
- `EntryFilter` 几乎不牺牲收益。

但它不是强独立 alpha，因为 LVT 与 ST overlap 高，且 Pure ST 明显弱于 Pure LVT。

### 更适合作为准入过滤、退出过滤，还是仓位降权

当前更适合作为准入过滤，其次是仓位降权。

- 准入过滤：最均衡，低成本，不明显提高现金。
- 仓位降权：`HalfWeight` 与 `FullExit` 有研究价值，尤其适合纸面并行观察。
- 退出过滤：默认定义下收益、换手、成本都不占优，不是优先方向。
- Entry+Exit：适合作为组合上限参考，但不适合直接作为默认答案。

### 互补还是高度重复

结论是“部分互补，但重合度较高”。77.69% 的 LVT 选中资产同时是 ST 多头，说明两者都在捕捉趋势/强势状态。SuperTrend 的价值更像二次风险确认，而不是独立选股来源。

### 下一阶段纸面跟踪候选

建议纸面跟踪：

1. `Q8_Baseline` 作为主基准；
2. `LVT_ST_EntryFilter` 作为第一混合候选；
3. `LVT_ST_Vote_HalfWeight` 作为仓位降权候选；
4. `LVT_ST_Vote_FullExit` 作为更防守候选；
5. `LVT_ST_EntryExit` 只作为上限参考，不作为默认候选。

### 哪些改善可能只是样本期运气

- `EntryExit` 在 2025/2026 的领先可能是当前路径正好奖励硬过滤。
- 参数网格中的局部最优可能只是样本路径；默认参数并非所有指标最佳。
- `Vote_FullExit` 的回撤改善部分来自现金提高，不应全部归因于信号更优。

### 什么环境会伤害混合策略

- 快速 V 型反弹：SuperTrend 刚退出或降权后，资产迅速反弹。
- 横盘震荡：ST 反复翻转，增加交易成本和错误过滤。
- 主题轮动很快：LVT 先识别新强势资产，但 ST 确认滞后。
- 全市场跳空下跌：fixed twice-monthly 无法及时响应。

### 是否值得进入纸面跟踪

值得进入纸面跟踪，但不值得替代 Q8 基准。Q11 的合理结论不是“SuperTrend 打败 LVT”，而是：

> SuperTrend 可作为 LVT 的二次确认层继续纸面观察；优先观察 EntryFilter 与 Vote/Half，Vote/FullExit 用来检验防守收益，Entry+Exit 只保留为上限参考。

## 文件

- Notebook: `research/notebooks/q11-supertrend-lvt-cross-validation-practice.ipynb`
- Outputs: `outputs/q11-supertrend-lvt-cross-validation/`
- Main summary: `summary_all_windows.csv`
- Parameter sensitivity: `supertrend_parameter_sensitivity.csv`
- Forward diagnostics: `forward_return_group_summary.csv`, `filtered_asset_forward_return_summary.csv`
- Latest signal: `latest_signal_summary.csv`, `latest_target_weights.csv`
