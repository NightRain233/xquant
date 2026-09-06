# Notebook 研究索引

所有实践 Notebook 位于 [`research/notebooks/`](notebooks/)。每个 Notebook 的第一个代码单元会把工作目录切换到仓库根目录，因此原有 `outputs/`、`docs/` 和 `scripts/` 相对路径保持不变。请从仓库根目录运行 `uv sync`，再用 `uv run jupyter lab` 打开。

## BTC SuperTrend 研究线

建议按以下顺序阅读：

1. [Q3：RiskParity 与 BTC](notebooks/q3-riskparity-btc-practice.ipynb)
2. [Q6：动量、趋势与 RiskParity](notebooks/q6-momentum-trend-riskparity-practice.ipynb)
3. [Q7：SuperTrend 稳健性](notebooks/q7-supertrend-riskparity-robustness-practice.ipynb)
4. [Q8：BTC 趋势卫星](notebooks/q8-btc-trend-satellite-practice.ipynb)
5. [Q9：BTC SuperTrend 卫星稳健性](notebooks/q9-btc-supertrend-satellite-robustness-practice.ipynb)
6. [Q10：实盘化压力测试](notebooks/q10-live-readiness-stress-practice.ipynb)

当前阶段结论见 [Q10 复盘](../docs/notes/q10-live-readiness-stress-review.md)：优先纸面跟踪 5% 和 7.5% BTC 卫星，10% 仅作进攻观察。

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

当前阶段结论见 [Theme Alpha Q12 复盘](../docs/notes/theme-alpha-q12-long-sample-proxy-validation-review.md)：Core80/LVT20/Def200 Cash 仍是默认纸面候选，LVT 只承担卫星角色。

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
