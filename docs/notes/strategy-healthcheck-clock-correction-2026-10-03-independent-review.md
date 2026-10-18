# 2026-10-03 时序修正重跑：独立复验

复验对象为本轮修正说明、输出目录及其 source bundle、manifest，并读取原始 83 份 market_data。主线重跑 BTC 全部五个策略并做了逐笔账本重建；Luna 独立核对 manifest 和数值。此前多资产分项 agent 超出使用额度，已另交给 Luna 复核，主线也检查了执行循环和保存的全量 equity curve。没有写生产账户。

## 结论

修正后的执行核在本次复验范围内解决了先前发现的两种“较晚市场价格影响较早成交”问题；BTC 冻结行情重跑与归档逐字节相同，多资产主要绩效表可由完整 equity curve 独立复算。执行结果明确标为异步研究模型，并披露即时结算、分数份额和 FX 时钟假设。因此这次重跑的研究数字有较强内部一致性证据，仍不构成券商成交或真实跨境结算证明。

交付尚有两处应修正后再称为完整可复现：生成的详细多资产 Markdown 仍保留旧执行/FX描述；multi 重跑依赖包外的旧全量结果文件，README 未把它列为必需输入。这两处不推翻已保存数值，但会误导读者或阻碍仅凭新目录复现。

## 独立复验

- manifest 核对：原始行情 83/83 哈希匹配；source bundle 34/34 成员与 manifest 源码哈希一致；声明的 48 项输出哈希全部匹配；修正报告、被归档的原报告和旧多资产结果哈希均匹配。工作区可见的 34 项源码均与清单一致。
- 将 source bundle 解到临时目录后，在解包代码上运行 7 个 `test_cross_market_execution_clock.py` 测试，全部通过。
- 从冻结 market_data 独立重放 BTC 全部五个组合，共生成 25 个文件，均与归档逐字节一致。
- 不调用新核的账本代码，仅按原始 OHLC 时间戳重建五个 BTC 组合的现金、份额、费用及每日 NAV。成交价最大误差为 0；费用与每笔成交名义金额的 30bps 相符，最大费用误差小于 3×10⁻¹⁴；最大 NAV/现金差低于 5×10⁻¹⁰。结果保存在 [BTC 账本复建](/Users/a1/Desktop/code/xquant/outputs/strategy-healthcheck-clock-correction-2026-10-03-independent-audit/independent_btc_ledger.json)，重放文件 SHA 清单在同目录。
- BTC 与多资产主要结果与 note 一致。Luna 直接从 NAV 和多资产 equityCurve 复算：BTC 五组 CAGR/MDD、以及多资产趋势候选 12.8763% / -19.7988%、静态组合 10.8868% / -13.7732% 均相符。严格 Q3 相关性样本也为 64。
- 主线重跑了 67 项相关测试，全部通过。测试通过只覆盖列明的时钟反例、行情/策略回归和账本检查，不能证明没有任何未建模风险。

## 仍需修正的交付内容

1. `outputs/strategy-healthcheck-clock-correction-2026-10-03/multi_asset_full.md` 是用户可读的详细候选报告，但第 13 行仍写“当日已知 USD/CNY 汇率”，第 19 行仍称“下一个共同可交易日开盘”。这与修正说明和执行实现冲突。脚本 `review_cross_market_clock.py:201-202` 只替换了旧报告标题，没有替换正文。应重新生成此报告，让它写明按各资产市场时间先后执行，以及 FX bar 完成时刻是未经供应商核实的研究假设；然后更新报告和对应 manifest 输出哈希。JSON 顶层 contract 已有更正字段，正文残留不表示此轮计算回退到旧执行模型。
2. 新 source bundle 不包含旧的 `outputs/strategy-healthcheck-2026-10-02/multi_asset_full.json.gz`，但 `review_cross_market_clock.py:189-192` 在 multi 重跑时会读取它来取出旧 global RS 参考行。manifest 只保存其哈希，不能代替文件。README 提到旧输出目录作参考，却没有明确把该 gzip 文件列为运行 multi family 的必需输入。应把它列为依赖并随复现包提供，或将所需未复核参考记录直接冻结到源码包；随即重建 source bundle 与 manifest。

原始行情与当前 checkout 路径均可用；34 项清单源码哈希实际全部匹配工作区。源码包本身包含固定策略/资产池代码与时钟测试。上述两项是用户文档与可复现依赖边界的问题，不是源码 hash mismatch。

## 模型解释边界

- multi 主报告说 96 个参数候选和 85 个静态权重点沿用原门槛，但 `inSampleEnd/outOfSampleStart` 仍只是元数据，排序/门槛使用全区间。修正说明已明确无独立样本外证明；因此 `no_target_default` 是此模型与全样本门槛的判定。
- FX 日线于 UTC 次日 00:00:01 完成、即时结算、单一现金池都是明示模型假设。现有数据不能证明供应商 FX bar 的实际截止时间，也不能证明真实换汇或跨账户资金在这些时点可用。
- `corrected_monthly` 的 `staleSymbols` 固定写成空列表。当前策略门槛没有消费此字段，因而这不是本轮已识别的绩效反例；但结果不应把它解读为已经完成持仓陈旧报价审计。
- Q3 correlation 仍是异步市场的日标签收益相关系数；报告已明示不能称同步相关性。

## 代表性证据位置

- 新时间/成交核：[research_execution_clock.py](/Users/a1/Desktop/code/xquant/src/xquant/research_execution_clock.py)
- BTC / 多资产调度：[review_cross_market_clock.py](/Users/a1/Desktop/code/xquant/scripts/review_cross_market_clock.py)
- 独立时钟用例：[test_cross_market_execution_clock.py](/Users/a1/Desktop/code/xquant/tests/test_cross_market_execution_clock.py)
- 原始 market_data：`outputs/strategy-healthcheck-2026-10-02/market_data/`（83 个文件，均为 ignored 文件）
