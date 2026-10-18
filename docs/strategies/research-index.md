# 策略研究索引

本页汇总各研究线的入口、当前证据边界和历史归档位置。它是导航页，不构成投资建议或实盘批准。近期核心实验从[研究 Notebook 索引](../../research/README.md#当前核心实验)进入。

## 三资产核心与主题增强

- [纯三资产核心复核（2026-10-03）](../notes/three-asset-core-2026-10-03-review.md)：510300、513100、518880 的20日逆波动基线及收益来源、回撤和不利情景。
- [分红会计修正与海外ETF估值监测（2026-10-04）](../notes/etf-dividend-valuation-2026-10-04-review.md)：510300原始份额、除息应收和现金到账的修订口径；此报告已确认交付。
- [主题 Alpha Q1–Q8 与 Q12](../../research/README.md#theme-alpha-研究线)：主题筛选、核心—卫星、压力和生产现实性等历史研究；[近期 LVT 三个月复核](../notes/theme-alpha-lvt-recent-3m-2026-09-06-review.md)记录其后续边界。

旧三资产和主题研究若使用510300，必须核对各自行情来源及实现字段。分红报告不会自动改写其他 Notebook、复权价格或既有收益；未经核对不能声称旧结果已经继承新会计口径。ETF估值过滤仍未验证：真实交易日观察为0/20，不能据此估计暂停频率或断言盘中公允价值区间可靠。

## 趋势跟踪（温斯坦）与 A 股风格

- [温斯坦测试总结（2026-10-18）](../notes/weinstein-summary-2026-10-18.md)：汇总 A 股、美股和 BTC 上的趋势规则测试。简化版温斯坦在各市场都没有跑赢持有；它在美股指数上能明显降低回撤，在 A 股上收益和回撤都更差，在 BTC 上不如日线 SuperTrend。
- [A 股 ETF 版](../notes/weinstein-etf-stage-2026-10-18-review.md)、[美股行业 ETF 版](../notes/weinstein-us-sector-2026-10-18-review.md)、[单个指数与 BTC 快速测试](../../outputs/weinstein-quick-checks-2026-10-18/README.md)。
- [红利低波 + 中证2000（2026-10-18）](../notes/dividend-lowvol-csi2000-2026-10-18-review.md)：四种搭配规则都没有在回撤上胜过单独持有红利低波；中证2000 在 2023 年 8 月之前是倒推历史。

## BTC 趋势卫星

- [价格口径修正重跑（2026-10-18）](../notes/btc-satellite-corrected-prices-2026-10-18-review.md)：三组合核心 ETF 改用正确复权口径后，BTC 7.5% 相对不加 BTC 的增益仍约 2.75 个百分点每年，绝对年化小幅下调；附旧研究受加法复权影响的盘点。
- [Q3、Q6–Q10 旧研究序列](../../research/README.md#btc-supertrend-研究线)：包括 BTC 风险平价、SuperTrend 稳健性和实盘化压力测试。
- [时序修正研究说明（2026-10-03）](../notes/strategy-healthcheck-clock-correction-2026-10-03-review.md)及[独立复核](../notes/strategy-healthcheck-clock-correction-2026-10-03-independent-review.md)：修正模型通过列明的时钟反例和账本复核，但仍是异步研究模型。
- [总体策略体检（2026-10-02）](../notes/strategy-healthcheck-2026-10-02-review.md)：包含旧Q10收益与时序问题的追溯。

旧Q10报告中的 BTC7.5 年化19.49%采用有问题的 next-close 时序：新权重被用于实际成交前的收益。它不能作为当前收益，也不能因后续时钟修正而恢复为当前策略绩效。修正版仍受真实投资载体、美元与人民币兑换、异步调仓、即时结算模型和完整样本外证据缺失限制。

## 多资产跨市场研究

- [时序修正说明](../notes/strategy-healthcheck-clock-correction-2026-10-03-review.md)与[独立复核](../notes/strategy-healthcheck-clock-correction-2026-10-03-independent-review.md)是多资产结果的主要入口。
- [修正版输出说明](../../outputs/strategy-healthcheck-clock-correction-2026-10-03/README.md)和[研究 Notebook](../../research/notebooks/strategy-healthcheck-clock-correction-2026-10-03-practice.ipynb)提供产物与展示入口。

多资产交付仍未关闭两项问题：详细 `multi_asset_full.md` 留有旧执行时钟及FX措辞；重跑依赖新 source bundle 之外的旧全量 gzip 文件，README没有把它列为必需输入。FX日线可用时间、即时结算、分数份额和统一现金池均属研究假设，FX供应商的bar截止时刻未独立核实。虽然有全样本门槛与滚动分析，仍无独立样本外证明；`no_target_default` 不是实盘资格结论。

## Core90 / Bull10 与交易账本归档

- [交易账本复现包说明](../../research/trading-ledger-2026-09-05/README.md)汇总旧 xquant 研究恢复、Core90 2.1.0 合同基准和三资产变种比较。
- [Core90 当前合同基准](../../research/trading-ledger-2026-09-05/core90_current_contract_2026_09_05/README.md)及[验证账本](../../research/trading-ledger-2026-09-05/core90_current_contract_2026_09_05/validated_2_1/)。
- [Core90 恢复包](../../research/trading-ledger-2026-09-05/core90_recovery_2026_09_05/README.md)保留旧 Bull Flip 与 Def200 相关 NAV、订单和复现材料；[三资产变种比较](../../research/trading-ledger-2026-09-05/three_asset_variant_comparison_2026_09_05/)包含修复账本。
- [Q15 全牛市长样本](../../research/notebooks/q15-all-bull-flip-long-sample-practice.ipynb)和[Q16 全牛市防守](../../research/notebooks/q16-all-bull-flip-defense-practice.ipynb)是相邻的历史实验入口。

Core90/Bull10 在此处作为历史增强观察线和账本归档，不取代当前核心实验索引中的纯三资产基线；历史表现不能自动转成当前推荐或实盘资格。

## 早期 Notebook 与复现约定

早期 Q3、Q6–Q16 和 Theme Alpha Notebook 保留在[`research/notebooks/`](../../research/notebooks/)，完整分组见[研究 README](../../research/README.md)。其中“当前默认候选”“优先纸面跟踪”等措辞是各报告撰写时的阶段性结论，应结合后续复核理解，不代表此刻建议。

每个研究目录的 Notebook、输出和复核报告应配套阅读。输出可能依赖 Git 忽略的行情文件或相邻交易仓库；阅读数字时以对应报告写明的输入、执行模型与限制为准。
