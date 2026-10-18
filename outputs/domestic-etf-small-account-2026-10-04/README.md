# 境内场内ETF小账户实施研究

完整报告在 `docs/notes/domestic-etf-small-account-2026-10-04-review.md`。这是研究与实施草案，没有实际交易；历史会计诊断、合成溢价情景和2026整手模拟不可拼成可得收益预测。旧结果不覆盖，BTC/multi未重跑且两项旧交付问题仍保留。

原仓库运行（固定uv最小环境，避免整个项目远端Git依赖）：

```sh
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 python scripts/review_domestic_etf_execution.py --preflight-only
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 python scripts/review_domestic_etf_execution.py
PYTHONPATH=src uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pytest==9.0.2 python -m pytest tests/test_etf_execution_research.py -q
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with matplotlib==3.11.0 python scripts/finalize_domestic_etf_delivery.py
```

将 reproduction_bundle.zip 解压到空目录后，可离线复算输入（第一次安装Python包仍可能需要网络）：

```sh
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 python scripts/review_domestic_etf_execution.py --evidence inputs/evidence --frozen inputs/frozen --reference inputs/reference --output outputs/domestic-etf-small-account-2026-10-04
PYTHONPATH=src uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pytest==9.0.2 python -m pytest tests/test_etf_execution_research.py -q
```

无需SPY、BTC/multi输出、券商接口、API Key或刷新行情。重算结果CSV应与包内计算结果一致；耗时、路径等清单元数据可不同。finalize展示脚本在原仓库使用evidence，在包内展示可直接读已有CSV/notebook。

`product_comparison`合并法律文件元数据、Sina收市后买卖盘口、TickFlow未复权日线、Eastmoney近期单位净值。价格最新9月30日，海外NAV最新9月29日，10月4日晚取得，NAV公布时刻UNKNOWN。price/NAV字段是最后公开净值参考比值，不能当成交时真实溢价，不能用于历史筛选。收市盘口不是未来能成交的保证。CSV含60日实际成交金额中位数/最小值，同时保留Close×份额代理作对照。原始请求、日期、失败空响应保留于evidence，官方证据部分下载失败，线上核实网址与离线文件分别列在official_source_manifest及报告。

`accounting_diagnostics`保留旧加法价格10bps基线，依次只改成本/价格/20日信号；`diagnostic_account_*`为1bps分数份额研究代理。300比例分红代理未完成全历史现金到账统一。境内513500用真实市价加精确一拆二，不再仅用SPY人民币代理；假期国内旧报价不能证明基础资产风险没变。

`pilot_execution_sensitivity`为2026年初入50k、后续8次月入金，100份整手、1bps佣金、价差0/5/20bps、10交易日/月度执行的45组会计诊断；2026 300现金分红先应收后到账。日线Open、全部成交、无溢价筛选/临停延后均为限制。月度变体权重偏差相对原10日目标，非纯舍入误差；未选择收益最高规则。

`50000_reference_lot_plan`按旧快照与最近冻结目标计算，不是新订单。gated版本只演示海外新增暂停并持现金。`premium_shock_scenarios`、`cash_wait_opportunity_scenarios`与`premium_volatility_mechanism`均为确定性合成情景。前瞻日志是空模板。执行函数只是研究用纯计算，无交易连接。

manifest记录计算SHA；delivery_manifest记录复现包成员SHA。独立账本、报价、旧基线核对见 independent_audit.json，解包重算比对见 reproduction_verification.json。核查没有验证未取得的历史发布时刻/IOPV/盘口及个人风险承受能力。
