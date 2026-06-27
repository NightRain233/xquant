# Theme Alpha Q12 Long Sample and Proxy Validation Review

Date: 2026-06-25

## 研究目的

Q12 检验 Q8 当前准实盘候选在更长样本和 proxy 样本中的结构稳健性。重点不是找最高收益，而是判断 LVT、Core/Satellite、Def200 Cash 和 Q11 SuperTrend/LVT 混合候选是否跨周期站得住。

当前 Q8 实盘候选保持为：

- `Core80 / Expanded LVT20 / Def200 Cash / fixed twice-monthly / close-signal-next-day-trade / asset-friction`

本次三层严格分开：

1. 真实 ETF 样本：当前可交易 ETF，沿用 Q8 准实盘口径。
2. 长样本 proxy：使用 ASHR/QQQ/GLD/DBB/SOXX/VOX/DVY/XLE/KCE/KWEB/XLV 等代理，从 2014 下载、主要观察 2015 以来窗口。
3. 共同样本：真实 ETF 限制到所有当前资产共同可用后的时间窗口，检查资产上市时间和资产池变化影响。

重要限制：proxy 是结构验证，不是可直接实盘结果。它有币种、交易时段、成分、行业定义和 ETF 机制差异。

## 策略

| Strategy | 定义 |
|---|---|
| `Original_RiskParity_3Asset` | 原三资产 RiskParity：沪深300/纳指/黄金或对应 proxy，固定半月调仓。 |
| `Expanded_LVT_100` | 全仓 Expanded LowVolTrend：扩展资产池内 MA60+63D 动量通过后选低波 Top3，RP cap50。 |
| `Core80_LVT20_Def200_Cash` | Core80 / Expanded LVT20 / Def200 Cash，Q8 当前准实盘候选。 |
| `Core60_LVT40_Def200_Cash` | Core60 / Expanded LVT40 / Def200 Cash，更进攻卫星档位。 |
| `Core80_LVT20_STEntry_Def200_Cash` | Q11 混合候选：LVT 新进入资产必须 SuperTrend 多头，已有资产可由 LVT 自然退出。 |
| `Core80_LVT20_STHalf_Def200_Cash` | Q11 仓位降权候选：LVT 选中但 ST 空头时卫星权重减半，释放到现金。 |

## 数据可用性与 proxy 差异

真实 ETF 与 proxy 的角色对应关系见 `data_availability_all_layers.csv`。共同样本诊断见 `asset_pool_common_sample_diagnostics.csv`。

proxy 与真实 ETF 的主要差异：
- NASDAQ: QQQ，QQQ 是美元计价美国 ETF，和境内 QDII 纳指 ETF 有汇率、限购和溢价差异。
- NONFERROUS: DBB，DBB 跟踪基本金属期货，不等同有色金属股票 ETF。
- CHIP: SOXX，SOXX 是美国半导体股票 ETF，不等同中国芯片 ETF。
- COMM: VOX，VOX 是美国通信服务 ETF，不等同中国通信 ETF。
- GOLD: GLD，GLD 是美元计价黄金 ETF，和境内黄金 ETF 的货币与交易时段不同。
- DIVIDEND: DVY，DVY 是美国高股息 ETF，不等同中国红利 ETF。
- ENERGY: XLE，XLE 是美国能源股票 ETF，不等同中国能源 ETF。
- BROKER: KCE，KCE 是美国资本市场/券商 ETF，不等同中国证券 ETF。
- HK_TECH: KWEB，KWEB 是中国互联网 ETF，不等同恒生科技 ETF。
- HEALTHCARE: XLV，XLV 是美国医疗 ETF，不等同中国医疗 ETF。

## 第一层：真实 ETF 样本

真实 ETF 层主要回答“现在这套 ETF 是否可实盘”。核心看 2020 至今、2025 至今和 2026 YTD。

### 2020 至今

- `real_etf` / `2020_to_date_real_etf` / `Original_RiskParity_3Asset`: 收益 133.09%, 年化 14.58%, 最大回撤 -15.38%, Sharpe 1.15, Calmar 0.95, 水下 86.85%, >-10% 天数 164
- `real_etf` / `2020_to_date_real_etf` / `Expanded_LVT_100`: 收益 138.44%, 年化 15.00%, 最大回撤 -31.77%, Sharpe 1.07, Calmar 0.47, 水下 87.05%, >-10% 天数 470
- `real_etf` / `2020_to_date_real_etf` / `Core80_LVT20_Def200_Cash`: 收益 131.83%, 年化 14.48%, 最大回撤 -11.29%, Sharpe 1.38, Calmar 1.28, 水下 85.19%, >-10% 天数 1
- `real_etf` / `2020_to_date_real_etf` / `Core60_LVT40_Def200_Cash`: 收益 145.73%, 年化 15.56%, 最大回撤 -13.97%, Sharpe 1.40, Calmar 1.11, 水下 85.90%, >-10% 天数 94
- `real_etf` / `2020_to_date_real_etf` / `Core80_LVT20_STEntry_Def200_Cash`: 收益 130.59%, 年化 14.38%, 最大回撤 -10.31%, Sharpe 1.38, Calmar 1.40, 水下 85.45%, >-10% 天数 1

### 2025 至今与 2026 YTD

- `real_etf` / `2025_to_date` / `Core80_LVT20_Def200_Cash`: 收益 41.83%, 年化 28.16%, 最大回撤 -11.29%, Sharpe 1.80, Calmar 2.49, 水下 76.06%, >-10% 天数 1
- `real_etf` / `2025_to_date` / `Core60_LVT40_Def200_Cash`: 收益 44.55%, 年化 29.90%, 最大回撤 -10.23%, Sharpe 1.91, Calmar 2.92, 水下 78.59%, >-10% 天数 1
- `real_etf` / `2025_to_date` / `Expanded_LVT_100`: 收益 43.87%, 年化 29.46%, 最大回撤 -9.32%, Sharpe 1.73, Calmar 3.16, 水下 84.51%, >-10% 天数 0
- `real_etf` / `2026_ytd` / `Core80_LVT20_Def200_Cash`: 收益 6.67%, 年化 15.64%, 最大回撤 -11.29%, Sharpe 0.80, Calmar 1.38, 水下 86.61%, >-10% 天数 1
- `real_etf` / `2026_ytd` / `Core60_LVT40_Def200_Cash`: 收益 10.11%, 年化 24.21%, 最大回撤 -10.23%, Sharpe 1.21, Calmar 2.37, 水下 84.82%, >-10% 天数 1
- `real_etf` / `2026_ytd` / `Expanded_LVT_100`: 收益 16.04%, 年化 39.77%, 最大回撤 -9.32%, Sharpe 1.73, Calmar 4.27, 水下 84.82%, >-10% 天数 0

### ETF 层解释

真实 ETF 样本仍支持 Q8 的实盘候选。全仓 LVT 通常收益更强，但回撤、水下和策略解释难度更高；Core80/LVT20/Def200 Cash 的路径更像可以长期执行的组合，而不是单一主题轮动押注。

Core60/LVT40 是更进攻档位：如果投资者能接受更深回撤和更高主题暴露，它可作为研究候选；但默认实盘仍不应直接把卫星提高到 40%。

## 第二层：长样本 proxy 验证

proxy 层回答“LVT 和 Core/Satellite 思想是否只在 2020 后有效”。这里不能当成境内 ETF 可交易结果，只看结构方向。

### 2015-2018：A股高波动与熊市压力

- `proxy_long_sample` / `2015_2018` / `Original_RiskParity_3Asset`: 收益 24.96%, 年化 5.74%, 最大回撤 -15.30%, Sharpe 0.54, Calmar 0.38, 水下 88.67%, >-10% 天数 169
- `proxy_long_sample` / `2015_2018` / `Expanded_LVT_100`: 收益 0.95%, 年化 0.24%, 最大回撤 -18.50%, Sharpe 0.02, Calmar 0.01, 水下 95.33%, >-10% 天数 296
- `proxy_long_sample` / `2015_2018` / `Core80_LVT20_Def200_Cash`: 收益 15.77%, 年化 3.74%, 最大回撤 -14.87%, Sharpe 0.42, Calmar 0.25, 水下 93.14%, >-10% 天数 182
- `proxy_long_sample` / `2015_2018` / `Core60_LVT40_Def200_Cash`: 收益 10.97%, 年化 2.64%, 最大回撤 -15.42%, Sharpe 0.30, Calmar 0.17, 水下 92.94%, >-10% 天数 207
- `proxy_long_sample` / `2015_2018` / `Core80_LVT20_STEntry_Def200_Cash`: 收益 15.44%, 年化 3.66%, 最大回撤 -15.13%, Sharpe 0.42, Calmar 0.24, 水下 93.34%, >-10% 天数 168

### 2019-2021：成长/科技与结构行情

- `proxy_long_sample` / `2019_2021` / `Original_RiskParity_3Asset`: 收益 77.94%, 年化 21.15%, 最大回撤 -15.76%, Sharpe 1.41, Calmar 1.34, 水下 86.13%, >-10% 天数 10
- `proxy_long_sample` / `2019_2021` / `Expanded_LVT_100`: 收益 51.92%, 年化 14.94%, 最大回撤 -22.23%, Sharpe 1.07, Calmar 0.67, 水下 85.20%, >-10% 天数 22
- `proxy_long_sample` / `2019_2021` / `Core80_LVT20_Def200_Cash`: 收益 53.82%, 年化 15.41%, 最大回撤 -16.78%, Sharpe 1.12, Calmar 0.92, 水下 86.39%, >-10% 天数 11
- `proxy_long_sample` / `2019_2021` / `Core60_LVT40_Def200_Cash`: 收益 53.78%, 年化 15.40%, 最大回撤 -17.80%, Sharpe 1.14, Calmar 0.87, 水下 84.81%, >-10% 天数 15

### 2022-2026：近年完整样本

- `proxy_long_sample` / `2022_2026` / `Original_RiskParity_3Asset`: 收益 76.22%, 年化 13.57%, 最大回撤 -24.06%, Sharpe 0.95, Calmar 0.56, 水下 89.48%, >-10% 天数 229
- `proxy_long_sample` / `2022_2026` / `Expanded_LVT_100`: 收益 25.50%, 年化 5.23%, 最大回撤 -22.16%, Sharpe 0.41, Calmar 0.24, 水下 93.67%, >-10% 天数 450
- `proxy_long_sample` / `2022_2026` / `Core80_LVT20_Def200_Cash`: 收益 66.11%, 年化 12.07%, 最大回撤 -12.14%, Sharpe 1.11, Calmar 0.99, 水下 88.59%, >-10% 天数 33
- `proxy_long_sample` / `2022_2026` / `Core60_LVT40_Def200_Cash`: 收益 56.79%, 年化 10.63%, 最大回撤 -13.88%, Sharpe 0.98, Calmar 0.77, 水下 89.57%, >-10% 天数 44

### proxy 层解释

长样本 proxy 没有给 LVT 一个漂亮的跨周期胜利。2015-2018 和 2022-2026 中，全仓 Expanded LVT 的收益、回撤和水下质量都偏弱，说明不能把近五年真实 ETF 的 LVT 表现简单外推成“通用 alpha”。更准确的解释是：LVT 在当前 ETF 扩展池里有用，但 proxy 长样本降低了我们对它作为独立主引擎的信心。

Core/Satellite 在 proxy 里的结论也不是单向胜利：2015-2018 和 2019-2021 原三资产 RiskParity 更强；但 2022-2026 里 Core80/LVT20/Def200 Cash 明显降低回撤和 -10% 以下水下天数。这说明它更像压力期风险结构，而不是每个牛市都能跑赢的收益结构。

## 第三层：共同样本/共同资产池验证

共同样本层只使用当前 ETF 共同可用后的时间窗口，避免某些 ETF 后来才出现造成的错觉。

- `real_etf_common_sample` / `full_sample` / `Original_RiskParity_3Asset`: 收益 88.08%, 年化 13.73%, 最大回撤 -13.96%, Sharpe 1.16, Calmar 0.98, 水下 85.53%, >-10% 天数 81
- `real_etf_common_sample` / `full_sample` / `Expanded_LVT_100`: 收益 73.10%, 年化 11.83%, 最大回撤 -31.60%, Sharpe 0.85, Calmar 0.37, 水下 87.47%, >-10% 天数 463
- `real_etf_common_sample` / `full_sample` / `Core80_LVT20_Def200_Cash`: 收益 106.35%, 年化 15.90%, 最大回撤 -11.29%, Sharpe 1.54, Calmar 1.41, 水下 82.70%, >-10% 天数 1
- `real_etf_common_sample` / `full_sample` / `Core60_LVT40_Def200_Cash`: 收益 104.81%, 年化 15.73%, 最大回撤 -12.57%, Sharpe 1.43, Calmar 1.25, 水下 84.40%, >-10% 天数 33
- `real_etf_common_sample` / `full_sample` / `Core80_LVT20_STEntry_Def200_Cash`: 收益 106.67%, 年化 15.94%, 最大回撤 -10.31%, Sharpe 1.55, Calmar 1.55, 水下 82.94%, >-10% 天数 1

共同样本结果没有显示结论完全依赖“后来上市 ETF”。如果共同样本和真实 ETF 全样本差异较小，主要原因是当前扩展池大多在 2020 年初已有数据；真正需要警惕的是 proxy 和真实 ETF 的资产定义差异，而不是 ETF 数据缺口本身。

## 重点诊断

| layer | window | LVT MDD - Core80 MDD | LVT underwater - Core80 | Core60 return - Core80 | Core60 MDD - Core80 | ST Entry Calmar - Core80 |
|---|---:|---:|---:|---:|---:|---:|
| real_etf | full_sample | -20.47% | 1.85% | 13.90% | -2.68% | 0.11 |
| real_etf | 2022_2026 | -12.18% | 6.57% | 3.79% | 1.06% | 0.16 |
| real_etf | 2020_to_date_real_etf | -20.47% | 1.85% | 13.90% | -2.68% | 0.11 |
| real_etf | 2015_2018 | NA | NA | NA | NA | NA |
| real_etf_common_sample | full_sample | -20.31% | 4.77% | -1.54% | -1.28% | 0.14 |
| real_etf_common_sample | 2022_2026 | -12.18% | 6.94% | 2.63% | 1.06% | 0.17 |
| real_etf_common_sample | 2020_to_date_real_etf | -20.31% | 4.77% | -1.54% | -1.28% | 0.14 |
| real_etf_common_sample | 2015_2018 | NA | NA | NA | NA | NA |
| proxy_long_sample | full_sample | -8.15% | 0.99% | -27.18% | -1.02% | -0.00 |
| proxy_long_sample | 2022_2026 | -10.02% | 5.08% | -9.32% | -1.74% | -0.03 |
| proxy_long_sample | 2020_to_date_real_etf | -5.44% | 2.21% | -11.19% | -1.02% | -0.01 |
| proxy_long_sample | 2015_2018 | -3.62% | 2.19% | -4.80% | -0.55% | -0.01 |

解释：最大回撤差值为负，代表全仓 LVT 比 Core80 更深；水下差值为正，代表全仓 LVT 更长时间处于回撤。Core60 收益差值为正但回撤差值为负时，说明它确实是用更大路径风险换收益。

## 对 Q11 SuperTrend/LVT 混合的长样本判断

Q11 的 `EntryFilter` 在真实 ETF 和共同样本里仍是合理纸面候选：收益几乎不输 Q8 基准，回撤和 Calmar 略有改善。但长样本 proxy 不支持把它升级成默认主策略。它更像风险确认层：某些窗口能改善 Calmar 或回撤，但优势不稳定，且 proxy 层的资产定义差异会放大判断噪声。

`STHalf` 的逻辑更防守，适合继续观察“降低卫星暴露是否能换来更平滑路径”，但它不应替代 Q8 基准。Q11 的原结论仍成立：SuperTrend 可作为 LVT 的确认灯，而不是 LVT 的替代 alpha。

## 通俗结论

### 近五年结论是否可能过拟合？

有可能部分过拟合。近五年包含黄金、纳指和部分主题 ETF 很有利的阶段，且真实 ETF 样本不够长。长样本 proxy 没有证明 LVT 是通用赢家，反而提示近五年可能高估了 LVT 的路径舒适度。

### 拉长到十年后，LVT 因子是否仍值得相信？

仍值得继续研究和使用，但只能作为卫星因子相信。当前真实 ETF 样本支持 LVT 有用；proxy 长样本则提醒我们，它不是稳定跑赢所有周期的主引擎，不能承担整个组合的风险管理责任。

### 全仓 LVT 是否适合作为主策略？

不适合。全仓 LVT 的收益可能很诱人，但长样本下最大回撤、水下时间和未修复回撤风险更差，容易在真正压力期让执行者放弃策略。

### Core80/LVT20/Def200 Cash 是否仍是最稳妥实盘候选？

是，但理由要说准确：它不是因为所有样本都收益最好，而是因为真实 ETF 和共同样本里风险调整后最稳，proxy 压力期也显示 Def200 Cash 能明显降低深回撤。Def200 Cash 的价值在于把核心权益风险从“硬扛”改成“风险差时降暴露”。

### 是否应该提高 LVT 仓位到 30%、40% 或 60%？

不建议直接提高到 60%，也不建议把 40% 升为默认。40% 在真实 ETF 近年样本里更进攻，但共同样本和 proxy 长样本并不支持它作为更稳答案。30% 是下一阶段最值得补测的中间档：如果要提高进攻性，应该先验证 30%，而不是跳到 40% 或 60%。

### 下一阶段应该研究什么？

1. 用同一 Q8 口径补测 Core70/LVT30/Def200 Cash，作为 20% 和 40% 之间的真实中间档。
2. 做 proxy 资产替代敏感性：例如 ASHR vs 000300 指数、DBB vs XME、KWEB vs 恒生科技指数。
3. 加入组合层风控：当核心和卫星同时弱势时，是否需要 portfolio-level risk-off。
4. 做 live paper tracking，把 Q8 Baseline、Q11 EntryFilter、Core60/40 进攻档分开跟踪，而不是提前合并结论。

## 文件

- Notebook: `research/notebooks/theme-alpha-q12-long-sample-proxy-validation-practice.ipynb`
- Outputs: `outputs/theme-alpha-q12-long-sample-proxy-validation/`
- Main summary: `summary_all_layers.csv`
- Diagnostics: `long_sample_diagnostics.csv`, `asset_pool_common_sample_diagnostics.csv`
- Availability: `data_availability_all_layers.csv`
