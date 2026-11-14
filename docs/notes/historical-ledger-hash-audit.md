# 历史账本快照校验说明

`tests/test_trading_ledger_recovery.py::test_repaired_baseline_manifest_covers_both_repository_boundaries`
校验的是 2026-09-05 封存的跨仓库源码快照。当前 trading 和 xquant 继续演进后，源码自然会与该快照不同，因此普通测试不再被这项历史校验阻塞。

需要复核封存包时显式运行：

```bash
RUN_HISTORICAL_LEDGER_HASH_CHECK=1 uv run pytest tests/test_trading_ledger_recovery.py -q
```

这只改变测试门槛，不修改封存包、manifest 或历史报告。
