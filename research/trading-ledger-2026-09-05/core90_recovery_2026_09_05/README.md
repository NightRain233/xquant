# Core90 原始研究恢复与执行迁移证据

截至 2026-09-05：原 xquant 研究已经恢复，并用封存的代码和行情离线重跑成功。
**这证明旧结果可重现，不证明当前 `bull_flip_ma200_v1` 合同已经通过历史验证。**

## 已恢复内容

`original_xquant.zip` 保存 301 个原始文件（约 49 MB）：

- 81 个候选标的的历史行情，原长样本决策事件、月度成员记录、订单、交易及日度 NAV；
- 原 defense 和 2026-08-20 开盘定仓修正版的输出；
- xquant 源码、研究入口、候选目录、`pyproject.toml` 和 `uv.lock`。

`source_manifest.json` 逐文件记录 SHA256、字节数、来源 Git HEAD 和旧冻结清单对照。
xquant 来源 HEAD 为 `5dbdd4d`，本轮未修改 xquant 仓库。
七项旧 fixture 哈希中六项相同；`signal_portfolio.py` 不同，来源是已存在的
`5dbdd4d fix: remove open-sizing lookahead`，因此保留差异而不修改旧 fixture。

## 离线复现

研究编排在 xquant，执行引擎依赖 trading 的后端环境。在 xquant 根目录执行：

```bash
cd /Users/zz/Desktop/Code/zsd/xquant
/Users/zz/Desktop/Code/zsd/trading/backend/.venv/bin/python \
  research/trading-ledger-2026-09-05/core90_recovery_2026_09_05/reproduce.py \
  --output /tmp/core90-recovered-new
```

输出路径必须不存在。脚本先校验整个压缩包及每个文件，再解压到临时目录，使用
封存源码、成员和决策重跑 Raw Bull、MA200 Bull 及 Core90+MA200 Bull10。
运行期间不访问行情服务、不读取本机 xquant 路径，也不修改纸面账户。
它不重新生成原扫描器决策；决策是已封存的输入，这是本次复现的明确边界。

已运行的结果在 `verified_legacy/`：

- `metrics.json`：机器生成的指标与复现状态；
- `*_daily_nav.csv`：日度净值；
- `*_orders.csv`、`*_trades.csv`：两种卫星组合的订单和交易；
- `decisions_ma200.csv`：逐信号 MA200 审计；
- `universe_manifest.csv`：81 份行情实际行数及日期范围；
- `recorded_vs_replayed_nav.csv`：与原开盘定仓修正版的逐日比较。

三条 NAV 共 12,627 行全部对齐，最大绝对差约 `1.12e-8`（初始资金 100 万）。
Core90+MA200 Bull10 旧指标重现为 CAGR 16.2767%、Sharpe 1.43438、最大回撤 -13.4906%。
这些数值来自历史本地可观察池，缺少完整退市/清盘证券主表与正式 FX 执行合同；不得
改写为“完整 PIT 市场”或修复后正式主账户的新 baseline。
组合层旧研究通过 sleeve 净值合成，不提供真实组合级逐笔成交；已导出的交易属于
卫星研究账户，不能冒充 Core90 组合完整成交账本。

## #7 执行统一：可运行迁移入口

`backend/portfolio_strategies/research_replay.py` 提供 `replay_frozen_decisions`。
研究只提供 `FrozenDecision` 和行情，直接调用 `NextOpenPaperEngine` 的下单、成交、
持仓与估值代码，使用全新 SQLite 账本，返回可导出的 decisions/orders/fills/positions/NAV。
历史逐日截断；先执行先前订单，再记录当日收盘决策，最后估值。日期集合包含币圈周末。

旧 backtest 的 next-open 查询与 paper 引擎现在共用 `execution_rules.next_valid_open`。
可选的 `OpenTradable`、`OpenSuspended`、`BuyOpenAllowed`、`SellOpenAllowed` 列描述
**开盘时已经知道**的可成交状态。存在但缺值时阻断，买卖方向分别检查。
没有这些列时仍沿用正数且有限 Open 的既有假设，不能宣称已建成完整涨跌停数据库。
不会用当日收盘、最高/最低或全天成交量反推开盘可成交性。
核心篮子为共同开盘原子再平衡，保守要求所有资产两个方向均允许。

验证：`backend/tests/test_research_replay.py` 实际走生产引擎，验证延迟买卖、手续费、
滑点和最终 NAV，并改变成交日收盘确认订单与开盘成交不变。

## 仍待完成，不能关闭 #7/#10

1. 将旧 resonance、SuperTrend、RS 轮动的所有信号与退出意图迁入该事件入口；
   原 `_pick_exit` 等仍存在独立模拟逻辑，不能宣称已有唯一完整回测内核。
2. 为真实历史数据补充开盘可成交状态、证券生命周期、FX 和企业行动的执行合同。
3. **已完成主策略范围**：用当前正式信号合同重算历史决策，生成组合级交易/NAV 和旧版差异报告，见
   [2.1.0 新基准](../core90_current_contract_2026_09_05/README.md)。其他旧策略仍按第 1 项处理。
4. 在新 baseline 上运行 walk-forward、参数稳定性、成本/延迟、集中度和多重试验验证。

当前研究包解除“原产物缺失”阻塞；#9 的生产参数优化仍不应启动。

## 导出执行 fixture 与回归验证

在 trading 根目录运行合成执行夹具：

```bash
backend/.venv/bin/python backend/tests/fixtures/research_execution/replay_execution.py --output /tmp/core90-execution-new
cd backend
PYTHONPATH=.:tests uv run --group dev pytest -q
```

`execution_golden/` 保存该合成场景的输入、完整事件链和确定性 CSV 哈希。
场景有一笔开盘买入受限后成交、一笔开盘卖出受限后成交；它验证执行链，不代表真实
投资业绩。测试要求重跑的订单、成交、持仓及每日 NAV 与版本化文件完全一致。
运行时 SQLite 只写输出目录，不放入版本化研究包。

## 本轮验收记录

2026-09-05 本地后端完整回归：`493 passed, 6 skipped`。跳过项仍为旧回测所需的
2015–2022 本地 backend 缓存条件，不影响独立压缩包中的 81 份历史数据复现。
`git diff --check` 通过；原始包逐文件 SHA256、执行样例源码和 CSV 哈希均通过校验。
本轮未提交、推送或部署代码，未修改生产账本，GitHub issue 状态未更改。

后续主策略执行修复验收更新为 trading 后端 **500 passed, 6 skipped**，xquant 研究测试
**55 passed**。2.1.0 合成样例位于 trading 的
`backend/tests/fixtures/research_execution/execution_golden_2_1/`，原 2.0.0 样例位于
同目录的 `execution_golden_2_0/`；原始 xquant 压缩包与 `verified_legacy/` 保持不变。
新基准完成了主策略研究/paper 循环统一，不代表所有旧策略已迁移。
