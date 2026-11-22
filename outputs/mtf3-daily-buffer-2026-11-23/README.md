# 日频防抖缓冲带 MTF-3 专项研究输出（2026-11-23）

本目录保存 `scripts/research_mtf3_daily_buffer_2026_11_23.py` 的全部只读离线输出，完整通俗解读见 `docs/notes/mtf3-daily-buffer-2026-11-23-review.md`。

## 文件说明

- `config.json`：事先写定的参数、窗口、成本、敏感性网格与判定门槛。
- `self_checks.json`：208 组回测资金守恒、权重边界、防前视扰动、跨市场时差与 200 次循环位移检验结果（全部通过）。
- `summary_spy_2000.csv` / `summary_qqq_2000.csv`：2000–2026 美股 26 年全期及 2000–2012 / 2013–2026 分段表现（10bp / 30bp / 50bp）与持有 1/3/5/10 年亏钱概率。
- `summary_us_2005_shields.csv`：2005–2026 纯真实 GLD 黄金盾、黄金条件盾与金债双盾横向总表（SPY 与 QQQ，10bp / 30bp / 50bp）。
- `gold_bear_stress_2011_2022.csv`：2011-09 至 2022-12 黄金十一年大熊市压力测试。
- `rolling_dca_10y.csv`：10 年滚动每月定投（203 个 2000–2026 窗口与 143 个 2005–2026 窗口）的 XIRR、最大本金浮亏、收益率与收益回撤比胜率。
- `rolling_starts_annual.csv`：2000–2023 共 24 个年度换起点对照。
- `summary_domestic_513500.csv`：2014–2026 真实人民币 `513500` 自身信号 vs 严格 T-1 美股外盘信号对照。
- `sensitivity_grid.csv`：21 组参数敏感性网格（3 组均线 × 7 组缓冲带，SPY 与 QQQ）。
- `key_periods.csv` / `annual_returns.csv`：关键历史危机与逐年收益对照。

## 复现命令

```sh
uv run python scripts/research_mtf3_daily_buffer_2026_11_23.py
```
