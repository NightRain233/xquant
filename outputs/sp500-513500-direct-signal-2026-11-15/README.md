# 513500 自身信号与 SPY 信号对照

交易价格统一为真实 513500 人民币收盘价。SELF 使用 513500 自身价格发信号，SPY 使用 SPY 仅作迁移诊断；最终可执行规则应优先看 SELF。

复现：`uv run python -I scripts/research_513500_direct_signal_2026_11_15.py`。
