# 仓库结构说明

本仓库同时承担三件事：保存可审计的策略研究、提供可复用的计算代码、展示当前策略结论。目录按这三类职责分开，避免继续把计算逻辑、实验过程和展示代码混在 Notebook 中。

## 当前结构

```text
.
├── pyproject.toml / uv.lock  # Python 依赖声明与精确锁定
├── .python-version           # uv 默认使用 Python 3.12
├── src/xquant/               # 可复用、经过测试的研究函数
├── tests/                    # Python 单元与脚本集成测试
├── research/notebooks/       # 实验过程与可视化
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
- `project.py`：从脚本或 Notebook 位置定位仓库根目录。

Notebook 应负责提出问题、组织实验和展示结果；能够跨实验复用的计算必须进入 `src/xquant/`，并先在 `tests/` 中定义行为。

## Notebook 路径约定

18 个实践 Notebook 已统一移动到 `research/notebooks/`。它们仍使用 `outputs/<experiment>/` 等仓库根目录相对路径，因此每个 Notebook 的第一个代码单元都会调用 `find_repo_root()`，再将工作目录切换到仓库根目录。

这是一层兼容措施：它把“文件放在哪里”和“结果写到哪里”分开，确保历史 Notebook 移动后不改变输出位置。不要删除或跳过带有 `bootstrap` 标签的启动单元。

后续重构仍应逐个实验进行：先把重复函数替换为 `xquant` 导入，验证关键指标不变，再考虑是否按 BTC 和 Theme Alpha 拆分更深的子目录。

## 数据流

```text
外部行情 → Notebook / scripts → outputs → dashboard/scripts → dashboard/public/data
                                  └──────→ docs/notes
```

`outputs/` 是研究证据，`dashboard/public/data/` 是可重新生成的展示数据。Dashboard 不应成为指标计算的第二套实现；新增指标应优先在 Python 研究层完成并导出。

## 新实验约定

每个新实验使用同一个 slug，并至少对应：

- `research/notebooks/<slug>-practice.ipynb`
- `outputs/<slug>/`
- `docs/notes/<slug>-review.md`

研究完成后运行 `uv run pytest`；如果影响 Dashboard，再运行 `make dashboard-check`。
