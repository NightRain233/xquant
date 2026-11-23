# 仓库协作指南

## 当前研究立场（2026-11）

- **主线（冻结核心）**：三资产逆波动核心（`510300` / `513100` / `518880`）加 7.5% BTC 日线 SuperTrend(10, 3) 卫星，在同级 `trading` 仓库里纸面运行。将 S2 趋势过滤叠加到主线已验证未通过（见 `docs/notes/main-line-s2-filter-2026-11-10-review.md`）。
- **独立标普 500 增强方案（2026-11 验证，独立于主线）**：
  - 低换手跨资产双核（最适配高滑点币圈美股现货与国内极简 `513500+518880` 账户）：`75% 标普 + 25% 黄金` 季末再平衡（`GOLD_75_25_Q` / `CN_75_25_Q`）；注意黄金多年熊市（如 2011–2015）会阶段性拖累。
  - 低费率美元趋势换盾（≤10bp）：`S2_GOLD`、`S2_BOND_GOLD`、不怕黄金熊市的 `S2_GOLD_TREND` / `S2_CASH`，以及 2026-11-23 新验证的**美股日频防抖三档（`MTF3_BUF2`/`MTF3_BUF3`，150日上升均线+210日均线 ±2%～3% 空间缓冲带，配现金/黄金/金债双盾）**（仅限美股原盘 SPY/QQQ，循环位移 `p≤0.03`，一年 2～3 次，纯现金 5/10 年亏钱率 0%，金债双盾夏普 `0.781`；国内 `513500` 自身价格依然无效，叠加黄金 30W 过滤在黄金熊市反不如纯现金）。
  - 国内 `513500` 低回撤控波动：自身信号 `TVT-50`（换现金或换 `518880` 黄金），配合决策时 QDII 溢价纪律（定投 >3% 放现金停泊；存量 >6% 减半仓只防溢价、不防熊市）。
  - **独立 BTC 日频防抖三档与均线家族（2026-11-23 验证，独立于主线已冻结的 7.5% BTC 日线 ST 卫星）**：`HYB_ST_MA150_B5`（日线 SuperTrend(10,3) + 150日均线 ±5%，100%/50%/0%）仍为全周期综合首选（夏普 `1.397`、回撤 `-55.5%`、ETH `-45.9%`/`p=0.005`、5 年定投最惨浮亏 `-23.4%`）；低换手纯双均线三档为 `MTF3_100_200_B5/B8`。均线家族深度对比（`docs/notes/btc-ma-and-dlv-mean-reversion-2026-11-23-review.md`）表明：普通双均线与双 EMA 均未过 BTC 置换检验（`p>0.05`），裸跑 Zero-Lag（`ZLEMA/DEMA/TEMA/HMA`）陷入 19～38 次/年高频洗盘、`KAMA` 失效；但**零滞后 + ±5% 防抖（`DEMA_150_B5`）**唯一在 BTC 全期（`p=0.005`）、成熟期（37.2%/夏普 `0.994`/`p=0.050`）与 ETH（`p=0.035`）三关全过（4.8 次/年，`SMA_100_B5` 同样强势），保留为极简单线备选（代价是二元切换与 `-64%` 回撤），不替换 `HYB_ST_MA150_B5`。
  - 详见 `docs/strategies/sp500-enhance.md`、`docs/notes/sp500-four-directions-2026-11-22-review.md`、`docs/notes/mtf3-daily-buffer-2026-11-23-review.md`、`docs/notes/btc-ashare-buffered-mtf3-2026-11-23-review.md` 与 `docs/notes/btc-ma-and-dlv-mean-reversion-2026-11-23-review.md`。
- **归档对照（统一口径）**：Theme Alpha、`Core90 / Bull10`、RS 轮动、聚宽四 ETF 单标的动量轮动（参数敏感、回撤超 40%）、TQQQ 牛熊切换（仅作极小仓位参考）统一收口为归档对照，不作为当前推荐。
- **已冻结负面结论（除非用户要求，不再重复提议）**：
  - A 股择时与均值回归规则：趋势择时（简化温斯坦 30 周线、红利低波布林带，以及红利低波 `H20269/510880/512890` 与沪深 300/中证 500/创业板全谱日频缓冲带 MTF-3）均因负向趋势正反馈差（`-0.5%～-4.1%`）而失败；防抖控波动（`VOL3`）在实盘 `512890` 未通过。均值回归与反均线审计（`docs/notes/btc-ma-and-dlv-mean-reversion-2026-11-23-review.md`）全 12 年同样无一达标：`RSI(2)`、`KDJ` 全系（`p=0.64～0.96`）、裸反均线、宽基均值回归及“跌多投涨少投”同预算定投全败；慢速底仓偏离（`BIAS_MA120_6PCT_CORE` / `RSI14_CORE_70`）仅属有条件单阶段强效（2020–26 `512890` 强到 `p=0.005`，但 2014–19 跑输随机 `p=0.65～0.91` 与傻瓜股债季调）。A 股红利低波主仓仍采用无脑月定投 + 国债/黄金季调配置；
  - 标普 500 单因子替代（质量 `SPHQ` / 低波 `SPLV` / 等权 `RSP`）、VIX/VIX3M 恐慌倒挂刹车、企业债信用利差刹车（`BAA10Y` / `HYG÷IEF`）、跌深多投智能定投（`SD1`）、日历效应（`HAL`/`TOM`）、短线 RSI(2)、国内 `513500` 自身价格离散周/月趋势规则均未通过；
  - 对逆波动组合加简单黄金均线过滤会破坏分散收益（见 `test_iv20_gold_defense.py`），而 `S2_GOLD_TREND` 仅作为趋势防守仓在黄金走熊时的防接飞刀保护；
  - 面向普通投资者的规则化做空策略（美股 `SPY`/`QQQ` 跨零售融券/反向 ETF `SH`/`PSQ`/机构期货、币圈 `BTC`/`ETH` 含 `-3%/年` 有利资金费率压测、A 股 `H00300`/`510500`/`159915`、50日下跌均线+ST 快速战术做空及 `QQQ/SPY` / `BTC/ETH` 市场中性配对）全线未通过（见 `docs/notes/short-selling-challenge-2026-11-23-review.md`）：SPY 史上 95%（近 14 年 100%）前 20 大单日暴涨位于 200 日线下方，叠加做空在 SPY `0/25`、BTC `0/10` 起步年胜过纯现金（增量置换检验 `p=0.50～0.97`），全部市场最佳空头仓位均为 `0%`（用现金或黄金/金债盾替代）；
  - 币圈永续合约（资金费率磨损）与不派分红的现货美股代币对长线复利破坏极大。
- 价格使用比例复权（总回报）口径。旧的加法前复权夸大了 `510300` 的历史收益，见 `docs/notes/btc-satellite-corrected-prices-2026-10-18-review.md`。
- 结论用通俗中文写给非技术读者；带日期的历史报告保持原样，用补充笔记代替改写。

## 项目结构与模块组织

本仓库由量化策略研究和 TypeScript 仪表盘两部分组成。

- `research/notebooks/*-practice.ipynb` 是策略实验；使用与输出和复盘一致的命名（如 `<主题>-YYYY-MM-DD-practice.ipynb` 或 `q17-<主题>-practice.ipynb`）。
- `src/xquant/` 存放经过测试、可跨实验复用的组合、指标、叠加回测和绩效计算（含标普四方向共享引擎 `sp500_lab.py`）；`tests/` 存放对应测试。
- `scripts/` 存放可重复运行的完整 Python 研究任务及只读实时信号自查脚本 `scripts/check_live_sp500_signals.py`。
- `outputs/<实验名>/` 存放生成的 CSV、校验清单、图表和诊断结果。
- `docs/notes/` 存放与实验对应的带日期研究复盘；`docs/strategies/` 存放面向非技术读者的常青指南（`two-three-asset.md`、`sp500-enhance.md`、`holding-experience.md`、`research-index.md`）；`docs/research-ledger.md` 是全仓研究总台账。
- `dashboard/src/` 存放 React 页面、组件、数据适配、样式及相邻测试。
- `dashboard/scripts/` 将研究输出转换为 `dashboard/public/data/` 下的静态数据。

不要直接修改课程或参考 notebook。探索性工作应放入 practice notebook，并让 notebook、输出目录和复盘文档使用一致的实验名称。不要删除带 `bootstrap` 标签的仓库根目录启动单元。可复用计算应提取到 `src/xquant/`；notebook 只负责编排实验和展示结果。

## 构建、测试与本地开发

- `uv sync`：根据 `pyproject.toml` 和 `uv.lock` 创建或更新 `.venv`。
- `uv run python check_env.py`：检查 Python、研究依赖、Jupyter 和数据接口。
- `uv run python scripts/check_live_sp500_signals.py`：只读查看标普 500 / 纳指 100 / 黄金 / BTC 当前 30 周均线与波动状态。
- `uv run jupyter lab`：打开本地研究 notebook。
- `uv run pytest`：运行 Python 单元与脚本集成测试。
- `make dashboard-install`：安装仪表盘依赖。
- `make dashboard`：重建本地静态数据，并在 `127.0.0.1` 启动 Vite。
- `make dashboard-test`：运行一次 Vitest 测试。
- `make dashboard-build`：执行 TypeScript 类型检查并构建生产版本。
- `make dashboard-check`：依次重建数据、运行测试和构建；提交仪表盘改动前必须执行。
- `make dashboard-dev-fresh`：刷新外部基准数据后启动，需要网络连接。

## 编码风格与命名

Python 使用四空格缩进；函数和变量使用 `snake_case`，常量使用 `UPPER_SNAKE_CASE`。TypeScript 开启严格模式，使用两空格缩进和分号；变量、函数使用 `camelCase`，React 组件使用 `PascalCase`。组件文件名应明确表达用途，例如 `BenchmarkScorecardPanel.tsx`。测试文件命名为 `*.test.ts` 或 `*.test.tsx`。

不要在没有明确分层的情况下混合资产池、权重和择时假设。比较不同策略时，应保持数据区间、调仓频率和指标定义一致。

## 测试与研究验证

公共 Python 计算和脚本集成使用 pytest。仪表盘使用 Vitest、Testing Library 和 jsdom。测试应放在 `tests/`、对应 UI/数据模块附近或 `dashboard/scripts/`。当前没有覆盖率门槛，但数据契约、计算逻辑、加载与错误状态、生成文件结构必须有针对性测试。

研究改动应在 notebook 和复盘中记录基准策略、Q3/Q5 指标、年度与月度表现、回撤和参数敏感性。不要只根据单一收益指标下结论。

## 提交与拉取请求

Git 历史偏好简短、明确的提交标题，常用 `feat:`、`fix:`、`docs:`、`chore:`，也接受简洁的中文标题。每个提交只处理一个研究阶段或一项仪表盘改动。

拉取请求应说明研究假设或界面变化、列出验证命令、标明重新生成的输出。涉及可视化变化时应附截图；如有对应 issue 或研究复盘，请一并链接。
