# strategy-comparison-2026-11-10

同一区间（2016-06-21 至 2026-06-23）比较 2026-11 的标普规则（S2、VT-1.0）与仓库中已有的策略净值。

- `comparison.csv`：每条净值的年化、波动、夏普（无风险利率按 0）、最大回撤、收益回撤比、最差 3 年年化、最长水下时间、期末倍数，以及来源文件和列名。
- 代码：`scripts/compare_strategies_common_window.py`。
- 币种不换算：标普规则用美元净值，境内 ETF 用人民币真实成交价，主线和冻结研究线用人民币模型净值。
- 本区间不包含 Theme Alpha（数据从 2020 或 2021 年起）和 scan-v2 右侧选股（从 2023 年起），未纳入。

解读见 `docs/notes/strategy-comparison-2026-11-10-review.md`。
