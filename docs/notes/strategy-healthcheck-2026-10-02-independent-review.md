# strategy-healthcheck-2026-10-02 独立复核

复核日期：2026-10-03。对象为同 slug 的 review.md、保存结果、复核脚本与 trading 实现。采用 xquant-strategy-review 规范；两名 Luna 分别核对产物和 native/多资产实现，主代理复核关键代码并运行独立反例。未调参、未修改原报告/原结果、未重新下载行情、未读写生产账户。本次新增文件仅为本说明及 independent-audit 下的反例。

**总体判断：不能给整份报告“复核通过”。** 主要表格与保存 NAV 一致，旧 Q10 成交前收益错误的诊断也成立；但 BTC 与多资产存在两项可复现的跨市场执行时点缺陷，相关绩效只能视为现有模型输出，不能当作已经消除未来数据影响的执行验证。尚未重跑修正模型，不能断言修正后优势一定消失或数值一定下降。

## 1. 高优先级：BTC 用较晚的 UTC 收盘决定较早的 A 股收盘成交

位置：`scripts/review_frozen_strategies.py:50,96,125,139-156`；`../trading/backend/portfolio_strategies/market_data.py:66-80,270-278`。涉及原报告第 29、74–98、140 行。

脚本在整个快照结束时构建一次 market，再按无时区日期截断历史。BTC 的 D 日 UTC 日线在上海 D+1 日 08:00 才完整；A 股 D 日收盘在 D 日 15:00。同标签 Close 被放在同一行。执行日 E 的共同 gross NAV、调仓判断、手续费和 ETF 成交数量都使用 E 日 BTC Close，因此会用到 A 股收盘之后才出现的价格。

固定合成目标、不改策略参数的独立反例：先持有 92.5% ETF / 7.5% BTC，再按固定目标换仓。仅把执行日较晚的 BTC UTC 收盘从 100 改为 200，ETF 同日期收盘成交后数量从 **797.3072885 变成 857.1053351**。同日 A 股收盘价始终为 100。未来行情影响了较早的成交数量，资金守恒并不能排除这个错误。

还用真实本地快照检查了生产 loader：在上海 2026-09-22 16:00，只能对齐到 9/21，计算器报 `A required formal signal session is missing`；9/23 08:01 才能对齐 9/22 并得到该信号，状态为 NOT_DUE。历史批处理获得的“9/22 正式信号”不能自动等同于当天收盘已可生成。这个检查只调用纯数据/信号函数，没有运行账户服务。

需区分：原报告所述“先用旧持仓获得执行日收益，再换仓”在单一市场合成测试中正确，当前核没有旧 Q10 的那项权重提前生效错误；这里发现的是另一项时区/共同估值问题。不能将前者测试通过扩大为整体无未来数据。

**需要重跑：** 明确各资产信号可用时刻、真实执行时刻及估值时刻，禁止 E 日 UTC BTC Close 影响 E 日 A 股收盘单。在保持冻结参数的条件下，重跑 BTC 0/5/7.5/10、现金参照、成本与人民币估值诊断，输出全历史/Q3/年度/回撤。FX 诊断只修币种，没有修这个时点问题。不能只把所有 BTC 数据机械平移一行而不定义实际成交价格。

## 2. 高优先级：多资产把不同市场的同日开盘当作同时发生

位置：`../trading/scripts/research_multi_asset_balanced_portfolio.py:520-548,636-718`；原报告第 126–132 行。

`next_common_trading_date` 取日历日期交集；`rebalance_at_open` 用该日所有资产 Open 计算 initial_value 和 desired_values，并先卖出全部市场资产、再买入全部市场资产。A 股上午开盘下单时，当天美股开盘仍未知；该模型也可能让晚些时候的美股卖出款支持此前的 A 股买入。配置真实包含 SPY、QQQ、GLD、A 股 ETF 与 BTC，这并非无关分支。

独立反例：初始各持一份 A 股和 SPY，现金为零，固定目标各 50%，A 股开盘恒为 100。只把同日较晚的 SPY 开盘由 100 改成 200，函数输出的 A 股上午开盘后数量由 **1 变为 1.5**。因此“下一共同交易日开盘”不足以证明按真实时间可执行。

此外，`:110-130` 按同日 FX OHLC 分别转换资产 OHLC；尚缺汇率 bar 可用时刻和真实换汇成交规则的证据。不同市场的日内 High/Low 直接相乘也不能当作同步人民币高低价。这是附加口径限制，主要时序反例无需依赖汇率假设就成立。

**需要重跑：** 按实际市场开盘顺序和现金可用性重放，重新生成 96 个变体、85 个静态权重点及成本/汇率/稳定性门槛结果。原 `no_target_default` 可保留为“旧模型的机器输出”，不能认定修正模型已经得到相同判定。当前没有证据支持上调默认策略，也没有证据支持修正后必然仍是同一排序。

## 3. 中优先级：BTC 执行约束写错，C 与 BTC 被合并描述

位置：原报告第 29 行；`outputs/strategy-healthcheck-2026-10-02/replay/btc/config.json:56-70`；`../trading/backend/portfolio_strategies/paper_engine.py:401-452`。

报告把 C/BTC 一并写为 2% 阈值、单资产 15 个百分点交易幅度限制。实际 BTC 配置为 **1% 阈值、没有 max_asset_trade**，且 BTC on/off 切换可强制执行，其他时候按最大单项权重变化判断；C 使用含现金的半周转率阈值和 max_asset_trade。BTC 成本为每边 base 20bps + slippage 10bps，不应读成 C 的资产成本表。

这是报告文字错误；原 BTC 重放读取的是实际配置，因此不能为迎合文字把 BTC 改成 2%/15pp。应分别写清两组契约。仅修正文案不需要改参数或单独重跑，但问题 1 的重放仍必要。

## 4. 中优先级：标为 Q3 的 BTC 相关性混入 10 月 1 日

位置：原报告第 98 行；`scripts/strategy_healthcheck_diagnostics.py:130-139`。

相关性仅筛选 `index > 2026-06-30`，没有 `<= 2026-09-30`。产物的 65 条收益包含 10/1。使用同一快照、同一算法，严格截至 Q3 末应为 **64 条**：BTC 对 QQQ/SPY/GLD 的系数分别为 **0.367474 / 0.376315 / 0.520920**，原值为 0.368322 / 0.376983 / 0.521710。

需要重算该 CSV 并更正文案。三个相关系数仍是不同市场收盘时点的日标签统计，不是同步时点相关性。这一错误不影响 BTC 组合 Q3 NAV 表；后者确实截止 9/30。

## 已通过的检查与仍不足的证据

- 本地 83 个行情 parquet 全部存在，SHA256 与覆盖表逐个一致。原 validation 中五项报告/交付文件哈希也一致。原表格主要数值与产物一致；直接由 NAV 独立复算：C 全历史 CAGR 17.84753%、MDD -10.72542%，Q3 -1.48628% / -6.88986%；BTC7.5 全历史 17.51292% / -14.52140%，Q3 +0.078275% / -5.11258%。这些验证的是计算和保存结果一致，不证明生成 NAV 的执行假设有效。
- C/BTC next-close 旧持仓先估值、再换仓的顺序正确；费用按买卖绝对名义金额计提，成本加压为实际重放，没有发现费用被简单从年化收益减去的错误。native 费用还体现在成交价格/现金流水，不能只看 slippage 列是否为零判断漏费。
- C 与 BTC 各自的比较窗口、6/30 基准收盘、9/4 新快照内连续收益处理合理。不能跨 C/BTC/native 的不同历史、日程与执行口径排名；原稿已经作此限制。
- native Bull 买入逻辑会屏蔽非 CNY/没有可投资标的的资产（`next_open_strategies.py:384-386,449-459`）。观察池有海外资产和海外估值日，不等于实际买入 USD 资产。没有据此发现 native 混合币种成交问题；本轮也未发现 native 的同类成交前收益反例。原数量/现金/日期审计通过，但这不保证原始价格或券商手数可实现。
- 额外核查了 native 估值日历差异：Bull 原 4290 个收益观测的 Sharpe 为 1.269559，重采样到核心相同 2855 个收益观测后为 1.270895；RP 为 1.310837。此处频率差异没有改变两位小数的报告值或相对次序，不应夸大为重要绩效错误。
- 原文“48 测试”只有汇总计数，没有归档具体命令/用例日志。本次独立运行了 **60 个相关测试，全部通过**，见下方命令。现有测试没有覆盖上述两项跨时区反例。测试通过不能作为全部未来数据风险已排除的证据。
- 主要 NAV、fills、summary、audit 未进入原 validation 的完整产物哈希清单；源码哈希与行情哈希有保存，但多资产重放还依赖外部配置及研究脚本。建议在修正重跑时冻结全部输入/配置/依赖源码，保存命令、版本与输出哈希。
- 多资产脚本的 `inSampleEnd` / `outOfSampleStart` 仅出现在输出元数据，实际 gate/排序使用全区间汇总（`:2488-2527,2793-2794`）。目前未证明独立样本外有效。原报告没有宣称独立 OOS 通过，故这是证据范围限制，不额外计为文案造假。
- 原报告已经承认 C 重叠差异未完全归因、旧 BTC 54 项压力不能继承、未全面重做 C/BTC 参数稳定性。不能从这些结果进一步得出未来回撤上限、稳定避险或小资金可执行性结论。无需为本次复核调参；需要的是冻结规则下的时序修复与验证。

**可暂时保留的结论：** 同口径 C 在 Q3 逊于其 RP 对照、LVT100 在该窗口较弱、native ST 历史回撤较大，均有当前保存结果支撑。把核心/C 留在研究清单是研究优先级判断，不等于本轮证明其结构稳健。BTC“修正执行后仍有增益”必须加上“仍含跨时区执行缺陷，待重跑”的限制；多资产判定同理。

## 本次验证命令

从 xquant 目录运行，pytest 不写缓存，临时账本由测试使用临时目录：

```sh
../trading/backend/.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_strategy_healthcheck_review.py \
  ../trading/backend/tests/test_btc_satellite_strategy.py \
  ../trading/backend/tests/test_theme_alpha_strategy.py \
  ../trading/backend/tests/test_portfolio_paper_engine.py \
  ../trading/backend/tests/test_portfolio_strategy_market_data.py
# 36 passed

PYTHONPATH=../trading/backend ../trading/backend/.venv/bin/python -m pytest -q -p no:cacheprovider \
  ../trading/backend/tests/test_xquant_next_open_parity.py \
  ../trading/backend/tests/test_core_bull_research.py \
  ../trading/backend/tests/test_next_open_engine.py
# 24 passed

../trading/backend/.venv/bin/python \
  outputs/strategy-healthcheck-2026-10-02/independent-audit/probes.py
```

第二组测试最初因未设 PYTHONPATH 收集失败，补上后 24 项通过；不是策略测试失败。反例输出保存在 [probes.json](../../outputs/strategy-healthcheck-2026-10-02/independent-audit/probes.json)，脚本只调用纯计算函数。合成数据用于隔离时点因果关系，不是新策略或修正绩效估计。
