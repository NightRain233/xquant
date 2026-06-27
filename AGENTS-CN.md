# 仓库协作指南

## 项目结构与模块组织

本仓库由量化策略研究和 TypeScript 仪表盘两部分组成。

- 根目录下的 `*-practice.ipynb` 是策略实验 notebook；新实验使用 `q13-<主题>-practice.ipynb` 这类命名。
- `src/xquant/` 存放经过测试、可跨实验复用的组合、指标和绩效计算；`tests/` 存放对应测试。
- `scripts/` 存放可重复运行的完整 Python 研究任务。
- `outputs/<实验名>/` 存放生成的 CSV、图表和诊断结果。
- `docs/notes/` 存放与实验对应的研究复盘。
- `dashboard/src/` 存放 React 页面、组件、数据适配、样式及相邻测试。
- `dashboard/scripts/` 将研究输出转换为 `dashboard/public/data/` 下的静态数据。

不要直接修改课程或参考 notebook。探索性工作应放入 practice notebook，并让 notebook、输出目录和复盘文档使用一致的实验名称。可复用计算应提取到 `src/xquant/`；notebook 只负责编排实验和展示结果。

## 构建、测试与本地开发

- `uv sync`：根据 `pyproject.toml` 和 `uv.lock` 创建或更新 `.venv`。
- `uv run python check_env.py`：检查 Python、研究依赖、Jupyter 和数据接口。
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
