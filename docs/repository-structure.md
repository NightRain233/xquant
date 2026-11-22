# 仓库结构说明

本仓库同时承担三件事：保存可审计的策略研究、提供可复用的计算代码、面向非技术读者呈现清晰结论。目录按这三类职责分开，避免把计算逻辑、实验过程和展示代码混在 Notebook 中。

## 当前结构

```text
.
├── README.md                 # 产品化总览：30 秒按账户选策略地图与核心结论
├── AGENTS.md / AGENTS-CN.md  # 当前研究立场（2026-11）与协作规范
├── pyproject.toml / uv.lock  # Python 3.12 依赖声明与锁定
├── src/xquant/               # 可复用、经过测试的研究计算模块
├── tests/                    # Python 单元与布局规范测试
├── research/notebooks/       # 实践 Notebook 入口
├── scripts/                  # 可重复运行的完整研究脚本与实时信号自查脚本
├── outputs/<experiment>/     # 实验结果 CSV、校验清单与缓存快照
├── docs/research-ledger.md   # 全仓研究总台账（按日期倒序索引）
├── docs/glossary.md          # 普通人术语表
├── docs/strategies/          # 面向非技术读者的常青策略指南（三组合、标普增强、持有体验、索引）
├── docs/notes/               # 带日期、不可改写的完整实验复盘笔记
├── docs/plans/               # 研究或工程实施计划
└── dashboard/                # React 报告及数据转换
```

`src/xquant/` 按用途分为：

| 用途 | 模块 |
|---|---|
| 通用计算 | `portfolio.py`（权重清洗、仓位上限、逆波动分配）、`indicators.py`（SuperTrend、低波趋势筛选）、`metrics.py`（NAV、回撤）、`project.py`（定位仓库根目录） |
| 三组合与执行时钟 | `three_asset_research.py`（next-open 研究内核）、`research_execution_clock.py`（显式 UTC 时钟与现金顺序）、`cashflow_research.py`（定投 XIRR 与外部现金流） |
| ETF 会计与执行 | `etf_dividend_accounting.py`（分红信号与原始份额现金账）、`etf_execution_research.py`（境内 ETF 执行诊断）、`etf_valuation_monitor.py`（海外 ETF 估值监测） |
| 标普增强与叠加回测 | `sp500_lab.py`（多资产日频回测引擎、摩擦拖累、统一 Q3/Q5/定投窗口评估与冻结数据加载器）、`overlay_rules.py`（单/双资产叠加规则与回测引擎）、`position_rules.py`（30 周线状态、目标波动率与趋势杠杆）、`band_timing.py`（布林带与循环位移检验）、`leveraged_switch.py`（杠杆切换）、`main_line_overlay.py`（主线过滤叠加层） |
| 择时与风格研究 | `weinstein_stage.py`（简化版温斯坦周线策略）、`style_combo.py`（两资产风格搭配）、`defensive_overlay.py`（防守门槛、核心—卫星） |
| 扫描策略事件研究（归档） | `event_study.py`、`signal_portfolio.py`、`point_in_time_universe.py`、`research_exports.py` |

另有只读工具脚本 `scripts/check_live_sp500_signals.py`，用于按仓库冻结口径即时查看标普 500、纳指 100、国内 513500/513100、黄金与 BTC 当前相对 30 周均线与近 21 日波动率状态（不修改任何研究缓存）。

## Notebook 路径约定

实践 Notebook 统一放在 `research/notebooks/`。它们使用 `outputs/<experiment>/` 等仓库根目录相对路径，因此每个 Notebook 的第一个代码单元必须保留 `repository-root-bootstrap` 标签并调用 `find_repo_root()` 切换工作目录（由 `tests/test_notebook_layout.py` 自动守卫）。

## 数据流

```text
外部行情 → scripts/fetch_*.py → outputs/<slug>/cache (冻结校验)
                                        ↓
                        scripts/research_*.py (+ src/xquant)
                                        ↓
                        outputs/<slug>/*.csv & self_checks.json
                             ├──────────┴──────────┐
                             ↓                     ↓
                       docs/notes/         dashboard/public/data
                             ↓
              docs/strategies/ & docs/research-ledger.md & README.md
```

`outputs/` 是研究证据，`dashboard/public/data/` 是可重新生成的展示数据。跨仓库的旧交易账本复现包位于 `research/trading-ledger-2026-09-05/`，其唯一执行内核在同级 `trading` 仓库中。

## 新实验约定

每个新实验使用统一 slug，对应：

- `scripts/research_<slug>.py`（含运行前写定的 `CONFIG`、反前视核验与 `self_checks.json`）
- `research/notebooks/<slug>-practice.ipynb`（登记到 `tests/test_notebook_layout.py`）
- `outputs/<slug>/`
- `docs/notes/<slug>-review.md`（同步登记到 `docs/research-ledger.md`）

研究完成后运行 `uv run pytest`（如在无 sibling `trading` 仓库的隔离环境下，可运行核心测试与 `tests/test_notebook_layout.py`）；如果影响 Dashboard，再运行 `make dashboard-check`。
