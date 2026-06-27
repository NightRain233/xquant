# 仓库结构说明

本仓库同时承担三件事：保存可审计的策略研究、提供可复用的计算代码、展示当前策略结论。目录按这三类职责分开，避免继续把计算逻辑、实验过程和展示代码混在 Notebook 中。

## 当前结构

```text
.
├── pyproject.toml / uv.lock  # Python 依赖声明与精确锁定
├── .python-version           # uv 默认使用 Python 3.12
├── src/xquant/               # 可复用、经过测试的研究函数
├── tests/                    # Python 单元与脚本集成测试
├── *-practice.ipynb          # 已有实验过程与可视化
├── scripts/                  # 可重复运行的完整研究任务
├── outputs/<experiment>/     # 实验结果快照
├── docs/notes/               # 研究结论与解释
├── docs/plans/               # 研究或工程实施计划
└── dashboard/                # React 报告及数据转换
```

`src/xquant/` 目前分为：

- `portfolio.py`：权重清洗、仓位上限和逆波动分配。
- `indicators.py`：SuperTrend 与低波趋势筛选。
- `metrics.py`：NAV 和回撤序列。

Notebook 应负责提出问题、组织实验和展示结果；能够跨实验复用的计算必须进入 `src/xquant/`，并先在 `tests/` 中定义行为。

## 为什么暂时不移动 Notebook

现有 18 个 Notebook 大量使用相对路径，例如 `outputs/<experiment>/`。直接移动到子目录会改变内核工作目录，可能把结果写到错误位置，也会破坏文档引用。因此本阶段先提取公共代码，不制造一次难以复核的大搬迁。

后续迁移应逐个实验进行：

1. 先把重复函数替换为 `xquant` 导入，并验证关键指标不变。
2. 统一通过项目根目录解析输入和输出路径。
3. 再用 `git mv` 移到 `research/btc/` 或 `research/theme-alpha/`。
4. 同步更新复盘链接、Dashboard 数据源和复现命令。

## 数据流

```text
外部行情 → Notebook / scripts → outputs → dashboard/scripts → dashboard/public/data
                                  └──────→ docs/notes
```

`outputs/` 是研究证据，`dashboard/public/data/` 是可重新生成的展示数据。Dashboard 不应成为指标计算的第二套实现；新增指标应优先在 Python 研究层完成并导出。

## 新实验约定

每个新实验使用同一个 slug，并至少对应：

- `<slug>-practice.ipynb`
- `outputs/<slug>/`
- `docs/notes/<slug>-review.md`

研究完成后运行 `uv run pytest`；如果影响 Dashboard，再运行 `make dashboard-check`。
