# 三组合分红会计修正与海外估值记录

研究截止2026-09-30；前瞻采集从实际2026-10-04开始。无实际交易，无后台持续任务。原策略IV20、日历和资产池固定，溢价门槛默认不启用。

## 离线复算

将 reproduction_bundle.zip 解压到空目录，进入解包根目录。第一次安装固定Python包可能需要网络，计算不需要行情网络：

```sh
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 python scripts/review_etf_dividend_valuation.py --workers 2
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with matplotlib==3.11.0 python scripts/finalize_etf_dividend_valuation.py
PYTHONPATH=src uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pytest==9.0.2 python -m pytest tests/test_etf_dividend_accounting.py tests/test_etf_valuation_monitor.py tests/test_etf_valuation_collector.py tests/test_cashflow_research.py tests/test_three_asset_research.py tests/test_etf_execution_research.py -q
```

旧代码、原价、旧复权价格与调仓参考均随包，不需要BTC/多资产冻结数据或SPY。

## 采集真实样本

在项目或解包根目录运行；这是联网一次性研究采集，不发订单，也不安装定时器：

```sh
uv run --no-project python scripts/collect_etf_valuation.py
uv run --no-project python scripts/summarize_etf_observations.py
```

可选纸面门槛示例，1%只是此前草案，参数不设置时只观察：

```sh
uv run --no-project python scripts/collect_etf_valuation.py --premium-cap 0.01 --paper-budgets outputs/etf-dividend-valuation-2026-10-04/monitor/paper_budget_example.json --paper-plan-id illustrative-only-2026-10-04
```

示例中的五个1000元是独立假想意向，非真实入金/账户余额/交易。纸面计划年龄从首次真实记录算起，不表示一直处于暂停状态。更换预算/计划须记录，工具不会伪造历史等待。`--references`接受空模板格式的研究者参考区间，但当前没有被独立证明可靠的自动估值方法，不应随意填数字开启买入判断。

建议真实交易时段09:40/10:40/14:00采集。手动运行可以积累；长期自动运行需你另行配置cron/launchd并维护联网主机，本次没有安装。正常异常留下原始错误继续采集，硬中断残留`.collection.lock`须确认没有另一采集进程后才清理。2026日历有官方依据，2027需更新。报价≤60秒且在连续交易时段才计有效交易日，按每产品不同日期计数，不把重复采集当多天。20日还只是报价覆盖，估值可靠性单独评估。

JSONL/raw为原始追加记录，CSV与coverage_summary/status为派生视图。最新NAV日期≠披露时刻，nav_published_at未知留空，nav_first_seen_at为本工具确实首次收到时刻。最新NAV比值不等于当前真实溢价；IOPV与区间缺失明确保留。回顾快照不倒填到历史观察。门槛结果仅纸面诊断，原IV20价格基线保持无过滤。休市和估值未知不能计入“真实高溢价导致买不了”的频率。

## 会计及证据

corporate_actions/dividend_events列官方登记、除息、发放及拆分记录。原始价格与收益信号分开；应收计入权益不计可买现金，发放日收盘后转现金，下一原调仓日再投资。主比较为分数份额、每边名义成交万分之一、价差0的历史模型，非整手实盘承诺。全部新CSV与旧口径桥接、564独立滚动定投、月年/回撤/成本敏感性单独交付。独立核查见 independent_audit.json 与verify脚本；来源原件、原始失败响应、SHA及旧报告完整原文随包。

最终通俗结论见 docs/notes/etf-dividend-valuation-2026-10-04-review.md。分红修正下修三组合终值，未反转样本排序；当前估值区间未建立；20日未完成，过滤暂停频率未知。历史收益不作预测。BTC/多资产未重跑，两项旧交付问题仍未关闭。
