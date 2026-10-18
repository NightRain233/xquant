# 每月等额定投账户比较

完整投资报告：[review](../../docs/notes/dca-comparison-2026-10-04-review.md)。三/两组合固定20日逆波动，标普500为SPY人民币研究代理。

原仓库运行：

```sh
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 --with exchange-calendars==4.13.2 python scripts/review_dca_accounts.py --preflight-only
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 --with exchange-calendars==4.13.2 python scripts/review_dca_accounts.py --workers 2 --monthly 10000
PYTHONPATH=src uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 --with exchange-calendars==4.13.2 python -m pytest tests/test_cashflow_research.py -q
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 --with exchange-calendars==4.13.2 python scripts/render_dca_review.py
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 --with exchange-calendars==4.13.2 python scripts/verify_dca_delivery.py
```

空目录解压reproduction_bundle.zip后：

```sh
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 --with exchange-calendars==4.13.2 python scripts/review_dca_accounts.py --snapshot inputs/market_data --reference inputs/reference --workers 2
PYTHONPATH=src uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 --with exchange-calendars==4.13.2 python -m pytest tests/test_cashflow_research.py -q
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 --with exchange-calendars==4.13.2 python scripts/render_dca_review.py
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 --with exchange-calendars==4.13.2 python scripts/verify_dca_delivery.py --ledger-only
```

包内五份行情、原覆盖表、冻结三资产信号目标和估值日期完整，不依赖BTC/multi旧结果。main_summary是主账户结果；account_*是净值/本金/单位净值/费用每日账本；fills_*中valuation_index是成交首次被日估值包含的位置（SPY实际时点查contribution_clock），不是US真实成交日期标签。SPY execution_price_cny是已知FX折算报价，非真实换汇成交。terminal_liquidation和profit是末日已知收盘预扣退出费的估值代理，不是已执行的卖出。

principal_loss_events回答何时低于累计本金；unit_drawdown_events回答扣除外部资金后的回前高；profit_giveback回答累计净盈利最多回吐多少钱。cohort_accounts遍历141起点继续投及130起点投12个月后停缴；rolling_dca_accounts遍历12/36/60期定投；matched_cohort_comparisons逐起点公平比终值。cashflow_sensitivity记录入金日期、真实交易费、汇率费用/时钟与波动窗口形状，未选最优参数。

main命令会并行两进程独立账户并显示进度，所有来源/产物SHA和环境版本在manifest。verify脚本独立逐笔重建三账户并解包重算CSV；ledger-only只做哈希、时钟、逐笔账本。时间耗时和ZIP时间戳可以不同，不要求整个ZIP字节一致。当前脚本绘图缓存不属于交付。

全日历估值包括中国假期；国内ETF估值报价可能陈旧，valuation_quotes逐日保存三个国内报价日期与SPY/FX已知时钟。每日15:00:02时点只有此前美股收盘，不含当天晚些时候美股价格；FX bar截止时刻仍是研究假设。国内forward_additive与SPY auto_adjust未完成逐笔现金分红统一，税务/真实基金载体尚未验证，勿把结果当券商可得收益。
