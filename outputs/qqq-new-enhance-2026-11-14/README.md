# QQQ 新量化增强候选（2026-11-14）

本实验把旧 QQQ 半仓趋势/杠杆结果作为基线，新增多周期确认和 QQQ/SPY 相对动量轮动。数据为 QQQ、SPY 分红复权价格与 ^IRX 现金利率，信号收盘判断、下一收盘成交；主成本每边 10bp，另做 30bp 压力测试。完整结果见 `summary_q3_q5.csv`、`segments.csv`、`sensitivity.csv`、`dca_summary.csv` 和 `verdicts.csv`。

候选规则：MTF-3（周线+月线确认）、REL-12（QQQ/SPY 12个月相对动量，并要求绝对趋势为正）、REL-Q（只在 QQQ 相对强时持有 QQQ，否则现金）、TVT-50（趋势条件波动率目标）。

复现：`uv run python -I scripts/research_qqq_new_enhance_2026_11_14.py`。
